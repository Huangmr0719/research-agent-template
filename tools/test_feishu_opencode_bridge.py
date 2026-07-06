#!/usr/bin/env python3
"""Small self-test for the Feishu Channel SDK bridge core."""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

import feishu_opencode_bridge as bridge


class MockMessage:
    def __init__(self, message_id: str, chat_id: str = "chat1", sender_id: str = "ou_allowed", text: str = "hello"):
        self.message_id = message_id
        self.id = message_id
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.content_text = text


class MockChannel:
    def __init__(self):
        self.sent = []

    async def send(self, chat_id, message, opts=None):
        self.sent.append((chat_id, message, opts or {}))
        return True


class MockOpenCode(bridge.OpenCodeClient):
    def __init__(self, config):
        super().__init__(config)
        self.created = 0
        self.abort_called = False
        self.mode = "ok"

    def create_session(self, title=None):
        self.created += 1
        return "ses_test"

    def send_message(self, session_id, user_text, feishu_context, timeout):
        if self.mode == "timeout":
            self.abort_session(session_id)
            raise bridge.OpenCodeTimeoutError("timeout")
        if self.mode == "empty":
            return bridge.DISPLAY_TEXT_FALLBACK
        if self.mode == "long":
            return "abcdefghi"
        return "ok"

    def abort_session(self, session_id):
        self.abort_called = True
        return True


def make_config(tmpdir: str, chunk_chars: int = 80) -> bridge.BridgeConfig:
    return bridge.BridgeConfig(
        app_id="cli_test",
        app_secret="secret",
        allowed_open_ids={"ou_allowed"},
        opencode_base_url="http://127.0.0.1:4096",
        opencode_username="opencode",
        opencode_password="pw",
        project_dir=tmpdir,
        db_path=str(Path(tmpdir) / "bridge.sqlite3"),
        log_path=str(Path(tmpdir) / "bridge.jsonl"),
        timeout_seconds=1,
        chunk_chars=chunk_chars,
        ack_text="收到，处理中。",
        busy_text="busy",
        unavailable_text="unavailable",
        timeout_text="timeout",
        system_prompt="system",
        opencode_agent="",
        opencode_model_provider="",
        opencode_model_id="",
    )


async def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        channel = MockChannel()
        config = make_config(tmpdir, chunk_chars=200)
        app = bridge.BridgeApp(config, channel)
        mock = MockOpenCode(config)
        app.opencode = mock

        await app.handle_message(MockMessage("m1"))
        assert ("chat1", {"markdown": "收到，处理中。"}, {"reply_to": "m1"}) in channel.sent
        assert any(item[1]["markdown"] == "ok" for item in channel.sent)
        assert app.store.get_chat_session("chat1") == "ses_test"

        before = len(channel.sent)
        await app.handle_message(MockMessage("m1"))
        assert len(channel.sent) == before

        await app.handle_message(MockMessage("m2", sender_id="ou_blocked"))
        assert len(channel.sent) == before

        mock.mode = "long"
        await app.handle_message(MockMessage("m3", chat_id="chat2"))
        assert bridge.chunk_text("abcdefghi", 4) == ["abcd", "efgh", "i"]

        mock.mode = "empty"
        await app.handle_message(MockMessage("m4", chat_id="chat3"))
        m4_text = "".join(
            item[1]["markdown"].replace("[2] ", "").replace("[3] ", "").replace("[4] ", "")
            for item in channel.sent
            if item[2].get("reply_to") == "m4" and item[1]["markdown"] != "收到，处理中。"
        )
        assert bridge.DISPLAY_TEXT_FALLBACK in m4_text

        mock.mode = "timeout"
        await app.handle_message(MockMessage("m5", chat_id="chat4"))
        assert mock.abort_called
        assert any(item[1]["markdown"] == "timeout" for item in channel.sent)

        lock = app.chat_locks.acquire("busy")
        try:
            await app.handle_message(MockMessage("m6", chat_id="busy"))
            assert any(item[1]["markdown"] == "busy" for item in channel.sent)
        finally:
            lock.release()

        extractor = bridge.OpenCodeClient(config)
        assert extractor.extract_text_from_parts(
            [
                {"type": "reasoning", "text": "hidden chain of thought"},
                {"type": "text", "text": "visible answer"},
            ]
        ) == "visible answer"
        assert extractor.extract_text_from_parts(
            [{"type": "reasoning", "text": "hidden chain of thought"}]
        ) == bridge.DISPLAY_TEXT_FALLBACK
        assert extractor.extract_text_from_parts(
            [{"type": "tool_result", "content": "secret tool output"}]
        ) == bridge.DISPLAY_TEXT_FALLBACK
        assert extractor.extract_text_from_parts(
            [{"unexpected": {"nested": "do not dump me"}}]
        ) == bridge.DISPLAY_TEXT_FALLBACK

    print("feishu opencode bridge tests passed")


if __name__ == "__main__":
    asyncio.run(main())
