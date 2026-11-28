"""
mcp_server/llm/groq.py
----------------------

CHỨC NĂNG :
    Chuyển giao diện LLM của agent sang Groq Chat Completions.

PHỤ TRÁCH  : Vũ    |    REVIEW: Tường

LƯU Ý:
    - Key chỉ đọc từ GROQ_API_KEY; không ghi key hoặc nội dung phản hồi vào log.
    - Agent vẫn quyết định danh sách Tool 1–5 và kiểm tra mọi tool call.

THAM KHẢO  : mcp_server/llm/agent.py, docs/api-contract.md (mục 2.3)

TRẠNG THÁI : ĐANG LÀM — q07 đã thử qua Groq + MCP/MySQL; chưa đo độ ổn định.
"""

import asyncio
import json
import os
import re
from types import SimpleNamespace

from dotenv import load_dotenv
from openai import AsyncOpenAI, RateLimitError

_RETRY_AFTER_RE = re.compile(r"try again in\s+(\d+(?:\.\d+)?)s", re.IGNORECASE)


def _tpm_retry_delay(exc: RateLimitError) -> float | None:
    """Trả số giây cần chờ nếu là giới hạn theo phút (TPM/RPM); trả None nếu hết quota ngày."""
    msg = str(exc)
    lower = msg.lower()
    if "per day" in lower or "tpd" in lower or "rpd" in lower:
        return None
    match = _RETRY_AFTER_RE.search(msg)
    if match:
        return min(float(match.group(1)) + 1.5, 65.0)
    return 15.0

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _to_groq_messages(system: str, messages: list[dict]) -> list[dict]:
    """Đổi lịch sử hội thoại của agent thành role/messages mà Groq nhận."""
    converted = [{"role": "system", "content": system}]
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            converted.append({"role": message["role"], "content": content})
        elif message["role"] == "assistant":
            text = "".join(block.text for block in content if block.type == "text")
            calls = []
            for block in content:
                if block.type != "tool_use":
                    continue
                item = {
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input, ensure_ascii=False),
                    },
                }
                extra = getattr(block, "extra_content", None)
                if extra is not None:
                    item["extra_content"] = extra
                calls.append(item)
            assistant = {"role": "assistant", "content": text or None}
            if calls:
                assistant["tool_calls"] = calls
            converted.append(assistant)
        else:
            # MCP trả từng tool_result thành một message role=tool của Groq.
            converted.extend({
                "role": "tool", "tool_call_id": block["tool_use_id"],
                "content": block["content"],
            } for block in content)
    return converted


class GroqLLMClient:
    """Giữ giao diện ``messages.create`` để dùng lại agent loop hiện có."""

    def __init__(
        self,
        api_client: AsyncOpenAI,
        *,
        use_max_tokens: bool = False,
        model_override: str | None = None,
    ):
        self._api = api_client
        self._use_max_tokens = use_max_tokens
        self._model_override = model_override
        self.messages = self

    async def create(
        self, *, model: str, max_tokens: int, temperature: float,
        system: str, messages: list[dict], tools: list[dict],
    ) -> SimpleNamespace:
        """Gửi yêu cầu tới Groq/Gemini (OpenAI-compatible) và đổi câu trả lời về block mà agent hiểu."""
        groq_tools = [{
            "type": "function",
            "function": {
                "name": tool["name"], "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        } for tool in tools]
        token_arg = (
            {"max_tokens": max(max_tokens, 8192), "reasoning_effort": "low"}
            if self._use_max_tokens
            else {"max_completion_tokens": max_tokens}
        )
        response = None
        for attempt in range(5):
            try:
                response = await self._api.chat.completions.create(
                    model=self._model_override or model,
                    temperature=temperature,
                    messages=_to_groq_messages(system, messages),
                    tools=groq_tools,
                    **token_arg,
                )
                break
            except RateLimitError as exc:
                delay = _tpm_retry_delay(exc)
                if delay is None or attempt == 4:
                    raise
                await asyncio.sleep(delay)
        if response is None or not response.choices:
            raise RuntimeError("Groq không trả lựa chọn nào")
        choice = response.choices[0]
        blocks = []
        if choice.message.content:
            text = choice.message.content
            if self._use_max_tokens:
                stripped = text.strip()
                if stripped.startswith("```") and stripped.endswith("```"):
                    lines = stripped.splitlines()
                    if len(lines) >= 3:
                        text = "\n".join(lines[1:-1]).strip()
            blocks.append(SimpleNamespace(type="text", text=text))
        for call in choice.message.tool_calls or []:
            if call.type != "function":
                raise ValueError("Groq trả tool call không hỗ trợ")
            extra = getattr(call, "extra_content", None)
            if extra is None and getattr(call, "model_extra", None):
                extra = call.model_extra.get("extra_content")
            blocks.append(SimpleNamespace(
                type="tool_use", id=call.id, name=call.function.name,
                input=json.loads(call.function.arguments),
                extra_content=extra,
            ))
        stop_reason = {
            "stop": "end_turn", "tool_calls": "tool_use",
        }.get(choice.finish_reason, choice.finish_reason)
        return SimpleNamespace(stop_reason=stop_reason, content=blocks)

    async def close(self) -> None:
        """Đóng kết nối HTTP khi caller kết thúc một phiên phân tích."""
        await self._api.close()


def create_groq_client() -> GroqLLMClient:
    """Tạo client từ key cục bộ, không nhận key qua tham số hay ghi vào log."""
    load_dotenv()
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("Thiếu GROQ_API_KEY trong .env")
    return GroqLLMClient(AsyncOpenAI(api_key=key, base_url=GROQ_BASE_URL))


def create_gemini_client() -> GroqLLMClient:
    """Tạo client Gemini (OpenAI-compatible endpoint) từ GEMINI_API_KEY trong .env."""
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("Thiếu GEMINI_API_KEY trong .env")
    gemini_model = (os.getenv("GEMINI_MODEL") or "gemini-3-flash-preview").strip()
    return GroqLLMClient(
        AsyncOpenAI(api_key=key, base_url=GEMINI_BASE_URL),
        use_max_tokens=True,
        model_override=gemini_model,
    )


def create_llm_client() -> GroqLLMClient:
    """Chọn client theo LLM_PROVIDER trong .env (groq hoặc gemini; mặc định groq)."""
    load_dotenv()
    provider = (os.getenv("LLM_PROVIDER") or "groq").strip().lower()
    if provider == "gemini":
        return create_gemini_client()
    if provider == "groq":
        return create_groq_client()
    raise ValueError("LLM_PROVIDER chỉ hỗ trợ groq hoặc gemini")
