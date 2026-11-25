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

import json
import os
from types import SimpleNamespace

from dotenv import load_dotenv
from openai import AsyncOpenAI

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _to_groq_messages(system: str, messages: list[dict]) -> list[dict]:
    """Đổi lịch sử hội thoại của agent thành role/messages mà Groq nhận."""
    converted = [{"role": "system", "content": system}]
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            converted.append({"role": message["role"], "content": content})
        elif message["role"] == "assistant":
            text = "".join(block.text for block in content if block.type == "text")
            calls = [{
                "id": block.id,
                "type": "function",
                "function": {
                    "name": block.name,
                    "arguments": json.dumps(block.input, ensure_ascii=False),
                },
            } for block in content if block.type == "tool_use"]
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

    def __init__(self, api_client: AsyncOpenAI):
        self._api = api_client
        self.messages = self

    async def create(
        self, *, model: str, max_tokens: int, temperature: float,
        system: str, messages: list[dict], tools: list[dict],
    ) -> SimpleNamespace:
        """Gửi yêu cầu tới Groq và đổi câu trả lời về block mà agent hiểu."""
        groq_tools = [{
            "type": "function",
            "function": {
                "name": tool["name"], "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        } for tool in tools]
        response = await self._api.chat.completions.create(
            model=model,
            max_completion_tokens=max_tokens,
            temperature=temperature,
            messages=_to_groq_messages(system, messages),
            tools=groq_tools,
        )
        if not response.choices:
            raise RuntimeError("Groq không trả lựa chọn nào")
        choice = response.choices[0]
        blocks = []
        if choice.message.content:
            blocks.append(SimpleNamespace(type="text", text=choice.message.content))
        for call in choice.message.tool_calls or []:
            if call.type != "function":
                raise ValueError("Groq trả tool call không hỗ trợ")
            blocks.append(SimpleNamespace(
                type="tool_use", id=call.id, name=call.function.name,
                input=json.loads(call.function.arguments),
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
