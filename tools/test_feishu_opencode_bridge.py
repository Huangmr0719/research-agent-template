#!/usr/bin/env python3
"""Small self-test for the Feishu Channel SDK bridge core."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import feishu_card_renderer
import feishu_opencode_bridge as bridge


class MockMessage:
    def __init__(self, message_id: str, chat_id: str = "chat1", sender_id: str = "ou_allowed", text: str = "hello"):
        self.message_id = message_id
        self.id = message_id
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.content_text = text


class MockChannel:
    def __init__(self, fail_card: bool = False):
        self.sent = []
        self.fail_card = fail_card

    async def send(self, chat_id, message, opts=None):
        if self.fail_card and "card" in message:
            raise RuntimeError("card rejected")
        self.sent.append((chat_id, message, opts or {}))
        return True

    def markdown_texts(self):
        return [item[1]["markdown"] for item in self.sent if "markdown" in item[1]]

    def cards(self):
        return [item[1]["card"] for item in self.sent if "card" in item[1]]


class MockOpenCode(bridge.OpenCodeClient):
    def __init__(self, config):
        super().__init__(config)
        self.created = 0
        self.abort_called = False
        self.mode = "ok"
        self.send_calls = []
        self.health_calls = 0

    def create_session(self, title=None):
        self.created += 1
        return f"ses_{self.created}"

    def send_message(self, session_id, user_text, feishu_context, timeout):
        self.send_calls.append(session_id)
        if self.mode == "timeout":
            self.abort_session(session_id)
            raise bridge.OpenCodeTimeoutError("timeout")
        if self.mode == "exception":
            raise bridge.BridgeError("boom")
        if self.mode == "session_missing_once" and len(self.send_calls) == 1:
            raise bridge.OpenCodeSessionNotFound("session not found")
        if self.mode == "empty":
            return bridge.DISPLAY_TEXT_FALLBACK
        if self.mode == "long":
            return "abcdefghi"
        if self.mode == "secret":
            return "ok sk-abcdefghijklmnopqrstuvwxyz SECRET=hidden"
        return "ok"

    def abort_session(self, session_id):
        self.abort_called = True
        return True

    def health(self):
        self.health_calls += 1
        if self.mode == "health_fail":
            raise bridge.OpenCodeUnavailableError("down")
        return {"healthy": True, "version": "test"}


class MockHttp404OpenCode(bridge.OpenCodeClient):
    def _request(self, method, path, payload=None, timeout=None):
        if path.endswith("/message"):
            raise bridge.OpenCodeHttpError(404, "session not found")
        return {}


def make_config(tmpdir: str, chunk_chars: int = 80, reply_format: str = "card") -> bridge.BridgeConfig:
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
        reply_format=reply_format,
        healthcheck_enabled=True,
        healthcheck_interval_seconds=1,
        healthcheck_failure_threshold=3,
        admin_chat_id="",
        audit_max_bytes=10 * 1024 * 1024,
        audit_backup_count=5,
        processed_message_retention_days=7,
    )


def card_body(card: dict) -> str:
    return card["body"]["elements"][0]["content"]


def test_redaction() -> None:
    private_key = "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
    text = "\n".join(
        [
            "Bearer abcdefghijklmnop",
            "sk-abcdefghijklmnopqrstuvwxyz",
            "AKIA1234567890ABCDEF",
            "ASIA1234567890ABCDEF",
            "ghp_abcdefghijklmnopqrstuvwxyz123456",
            "github_pat_abcdefghijklmnopqrstuvwxyz123456",
            private_key,
            "SECRET=abc",
            "PASSWORD=abc",
            "APP_SECRET=abc",
        ]
    )
    redacted = bridge.redact_sensitive_text(text)
    assert "Bearer abc" not in redacted
    assert "sk-abc" not in redacted
    assert "AKIA" not in redacted
    assert "ASIA" not in redacted
    assert "ghp_" not in redacted
    assert "github_pat_" not in redacted
    assert "BEGIN PRIVATE KEY" not in redacted
    assert "SECRET=abc" not in redacted
    assert "PASSWORD=abc" not in redacted
    assert "APP_SECRET=abc" not in redacted
    assert "[REDACTED]" in redacted


def test_card_renderer() -> None:
    success = feishu_card_renderer.render_static_reply_card("done", "visible", "success", tags=["a", "b", "c", "d"])
    error = feishu_card_renderer.render_static_reply_card(None, "visible", "error")
    timeout = feishu_card_renderer.render_static_reply_card(None, "visible", "timeout")
    assert success["schema"] == "2.0"
    assert success["header"]["template"] == "green"
    assert error["header"]["template"] == "red"
    assert timeout["header"]["template"] == "orange"
    assert len(success["header"]["text_tag_list"]) == 3
    assert "reasoning" not in card_body(success)
    assert "thinking" not in card_body(success)
    assert "tool_result" not in card_body(success)


def test_part_filtering(config: bridge.BridgeConfig) -> None:
    extractor = bridge.OpenCodeClient(config)
    visible = extractor.extract_text_from_parts(
        [
            {"type": "reasoning", "text": "hidden chain of thought"},
            {"type": "text", "text": "visible answer"},
        ]
    )
    assert visible == "visible answer"
    assert extractor.extract_text_from_parts(
        [{"type": "reasoning", "text": "hidden chain of thought"}]
    ) == bridge.DISPLAY_TEXT_FALLBACK
    assert extractor.extract_text_from_parts(
        [{"type": "tool_result", "content": "secret tool output"}]
    ) == bridge.DISPLAY_TEXT_FALLBACK
    assert extractor.extract_text_from_parts(
        [{"unexpected": {"nested": "do not dump me"}}]
    ) == bridge.DISPLAY_TEXT_FALLBACK


def test_session_404_mapping(config: bridge.BridgeConfig) -> None:
    client = MockHttp404OpenCode(config)
    try:
        client.send_message("old_session", "hello", {}, timeout=1)
    except bridge.OpenCodeSessionNotFound:
        pass
    else:
        raise AssertionError("404 session not found should map to OpenCodeSessionNotFound")


def test_audit_rotation(tmpdir: str) -> None:
    path = str(Path(tmpdir) / "audit.jsonl")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("x" * 50, encoding="utf-8")
    bridge.append_audit_event(path, {"status": "new"}, max_bytes=10, backup_count=2)
    assert Path(path).exists()
    assert Path(path + ".1").exists()
    assert "new" in Path(path).read_text(encoding="utf-8")

    original_replace = bridge.os.replace
    try:
        bridge.os.replace = lambda src, dst: (_ for _ in ()).throw(OSError("no rotate"))
        bridge.append_audit_event(path, {"status": "after_failure"}, max_bytes=1, backup_count=2)
    finally:
        bridge.os.replace = original_replace
    assert "after_failure" in Path(path).read_text(encoding="utf-8")


def test_processed_message_cleanup(tmpdir: str) -> None:
    store = bridge.MessageStore(str(Path(tmpdir) / "cleanup.sqlite3"))
    old_time = int(__import__("time").time()) - 9 * 86400
    new_time = int(__import__("time").time())
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO processed_messages(message_id, chat_id, open_id, created_at, status, error) VALUES (?, ?, ?, ?, ?, ?)",
            ("old", "chat", "ou", old_time, "received", None),
        )
        conn.execute(
            "INSERT INTO processed_messages(message_id, chat_id, open_id, created_at, status, error) VALUES (?, ?, ?, ?, ?, ?)",
            ("new", "chat", "ou", new_time, "received", None),
        )
    removed = store.cleanup_processed_messages(7)
    assert removed == 1
    with store._connect() as conn:
        remaining = {row[0] for row in conn.execute("SELECT message_id FROM processed_messages")}
    assert remaining == {"new"}


async def test_bridge_flow(tmpdir: str) -> None:
    channel = MockChannel()
    config = make_config(tmpdir, chunk_chars=200)
    app = bridge.BridgeApp(config, channel)
    mock = MockOpenCode(config)
    app.opencode = mock

    await app.handle_message(MockMessage("m1"))
    assert ("chat1", {"markdown": "收到，处理中。"}, {"reply_to": "m1"}) in channel.sent
    assert channel.cards()
    assert "ok" in card_body(channel.cards()[-1])
    assert app.store.get_chat_session("chat1") == "ses_1"

    before = len(channel.sent)
    await app.handle_message(MockMessage("m1"))
    assert len(channel.sent) == before

    await app.handle_message(MockMessage("m2", sender_id="ou_blocked"))
    assert len(channel.sent) == before

    mock.mode = "secret"
    await app.handle_message(MockMessage("m3", chat_id="secret-chat"))
    body = card_body(channel.cards()[-1])
    assert "[REDACTED]" in body
    assert "sk-abc" not in body
    assert "SECRET=hidden" not in body

    mock.mode = "empty"
    await app.handle_message(MockMessage("m4", chat_id="chat3"))
    assert bridge.DISPLAY_TEXT_FALLBACK in card_body(channel.cards()[-1])

    mock.mode = "timeout"
    await app.handle_message(MockMessage("m5", chat_id="chat4"))
    assert mock.abort_called
    assert channel.cards()[-1]["header"]["template"] == "orange"

    mock.mode = "ok"
    await app.handle_message(MockMessage("m6", chat_id="chat4"))
    assert channel.cards()[-1]["header"]["template"] == "blue"

    mock.mode = "exception"
    await app.handle_message(MockMessage("m7", chat_id="chat5"))
    assert channel.cards()[-1]["header"]["template"] == "red"

    mock.mode = "ok"
    await app.handle_message(MockMessage("m8", chat_id="chat5"))
    assert channel.cards()[-1]["header"]["template"] == "blue"

    lock = app.chat_locks.acquire("busy")
    try:
        await app.handle_message(MockMessage("m9", chat_id="busy"))
        assert "busy" in channel.markdown_texts()
    finally:
        lock.release()


async def test_session_recovery(tmpdir: str) -> None:
    channel = MockChannel()
    config = make_config(tmpdir)
    app = bridge.BridgeApp(config, channel)
    mock = MockOpenCode(config)
    mock.mode = "session_missing_once"
    app.opencode = mock
    app.store.save_chat_session("chat-session", "old_session")

    await app.handle_message(MockMessage("m10", chat_id="chat-session"))

    assert mock.send_calls == ["old_session", "ses_1"]
    assert app.store.get_chat_session("chat-session") == "ses_1"
    assert channel.cards()
    assert "ok" in card_body(channel.cards()[-1])
    audit = Path(config.log_path).read_text(encoding="utf-8")
    assert "session_recreated" in audit


async def test_reply_format_and_fallback(tmpdir: str) -> None:
    markdown_channel = MockChannel()
    markdown_config = make_config(str(Path(tmpdir) / "markdown"), reply_format="markdown")
    markdown_app = bridge.BridgeApp(markdown_config, markdown_channel)
    markdown_app.opencode = MockOpenCode(markdown_config)
    await markdown_app.handle_message(MockMessage("m11", chat_id="markdown-chat"))
    assert not markdown_channel.cards()
    assert "ok" in markdown_channel.markdown_texts()

    fallback_channel = MockChannel(fail_card=True)
    fallback_config = make_config(str(Path(tmpdir) / "fallback"), reply_format="card")
    fallback_app = bridge.BridgeApp(fallback_config, fallback_channel)
    fallback_app.opencode = MockOpenCode(fallback_config)
    await fallback_app.handle_message(MockMessage("m12", chat_id="fallback-chat"))
    assert not fallback_channel.cards()
    assert "ok" in fallback_channel.markdown_texts()
    assert "card_send_failed" in Path(fallback_config.log_path).read_text(encoding="utf-8")


def test_load_config_reply_format(tmpdir: str) -> None:
    old_env = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(
            {
                "LARK_APP_ID": "cli_test",
                "LARK_APP_SECRET": "secret",
                "RCA_FEISHU_ALLOWED_OPEN_IDS": "ou_allowed",
                "OPENCODE_BASE_URL": "http://127.0.0.1:4096",
                "BRIDGE_DB_PATH": str(Path(tmpdir) / "env.sqlite3"),
            }
        )
        assert bridge.load_config().reply_format == "card"
        os.environ["BRIDGE_REPLY_FORMAT"] = "markdown"
        assert bridge.load_config().reply_format == "markdown"
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def test_docs_and_templates() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    agents = (root / "templates" / "AGENTS.md").read_text(encoding="utf-8")
    env_example = (root / "templates" / "feishu_bridge.env.example").read_text(encoding="utf-8")
    opencode_example = (root / "templates" / "opencode.remote.example.json").read_text(encoding="utf-8")
    service_text = "\n".join(
        [
            (root / "templates" / "systemd" / "opencode-serve.service").read_text(encoding="utf-8"),
            (root / "templates" / "systemd" / "rca-feishu-opencode-bridge.service").read_text(encoding="utf-8"),
        ]
    )
    assert "opencode-pty" in readme
    assert "BRIDGE_HEALTHCHECK_ENABLED" in readme
    assert "BRIDGE_AUDIT_MAX_BYTES" in readme
    assert "OpenCode-Native Simplification Strategy" in readme
    assert "natural language" in readme
    assert "tail -f .rca/feishu_bridge_audit.jsonl" in readme
    assert "opencode-pty" in agents
    assert "Feishu Remote Natural-Language Workflow" in agents
    assert "Do not inspect `.rca/`" in agents
    assert "/summary" in agents
    assert "tools/run_with_feishu_notify.sh" in agents
    assert "BRIDGE_REPLY_FORMAT=card" in env_example
    assert "BRIDGE_PROCESSED_MESSAGE_RETENTION_DAYS=7" in env_example
    assert "feishu_bridge.env" in opencode_example
    assert "network-online.target" in service_text
    assert "Restart=always" in service_text
    assert "127.0.0.1" in service_text
    assert "cli_" not in service_text
    assert "LARK_APP_SECRET" not in service_text
    for doc_name in [
        "opencode-native-simplification.md",
        "opencode-native-smoke-test.md",
        "opencode-lark-evaluation.md",
        "opencode-sdk-evaluation.md",
    ]:
        assert (root / "docs" / doc_name).read_text(encoding="utf-8")
    lark_eval = (root / "docs" / "opencode-lark-evaluation.md").read_text(encoding="utf-8")
    assert "opencode-lark`" in lark_eval
    assert "Partially usable" in lark_eval
    assert "open_id allowlist" in lark_eval
    for command_name in [
        "experiment-run.md",
        "experiment-summary.md",
        "experiment-compare.md",
        "log-tail.md",
    ]:
        command_text = (root / ".opencode" / "commands" / command_name).read_text(encoding="utf-8")
        assert "Do not ask the user to type this command name." in command_text


async def test_healthcheck(tmpdir: str) -> None:
    channel = MockChannel()
    config = make_config(tmpdir)
    config = bridge.BridgeConfig(**{**config.__dict__, "healthcheck_interval_seconds": 1, "healthcheck_failure_threshold": 2})
    app = bridge.BridgeApp(config, channel)
    mock = MockOpenCode(config)
    mock.mode = "health_fail"
    app.opencode = mock

    task = asyncio.create_task(app.healthcheck_loop())
    await app.handle_message(MockMessage("m_health", chat_id="health-chat"))
    assert channel.cards()
    sent_after_message = len(channel.sent)
    await asyncio.sleep(2.4)
    task.cancel()
    audit = Path(config.log_path).read_text(encoding="utf-8")
    assert "healthcheck_failed_threshold" in audit
    assert len(channel.sent) == sent_after_message

    admin_channel = MockChannel()
    admin_config = make_config(str(Path(tmpdir) / "admin"))
    admin_config = bridge.BridgeConfig(
        **{
            **admin_config.__dict__,
            "admin_chat_id": "oc_admin",
            "healthcheck_interval_seconds": 1,
            "healthcheck_failure_threshold": 1,
        }
    )
    admin_app = bridge.BridgeApp(admin_config, admin_channel)
    admin_mock = MockOpenCode(admin_config)
    admin_mock.mode = "health_fail"
    admin_app.opencode = admin_mock
    task = asyncio.create_task(admin_app.healthcheck_loop())
    await asyncio.sleep(1.3)
    task.cancel()
    assert admin_channel.sent

    recovery_config = make_config(str(Path(tmpdir) / "recovery"))
    recovery_config = bridge.BridgeConfig(**{**recovery_config.__dict__, "healthcheck_interval_seconds": 1})
    recovery_app = bridge.BridgeApp(recovery_config, MockChannel())
    recovery_mock = MockOpenCode(recovery_config)
    recovery_mock.mode = "health_fail"
    recovery_app.opencode = recovery_mock
    task = asyncio.create_task(recovery_app.healthcheck_loop())
    await asyncio.sleep(1.2)
    recovery_mock.mode = "ok"
    await asyncio.sleep(1.2)
    task.cancel()
    assert "healthcheck_recovered" in Path(recovery_config.log_path).read_text(encoding="utf-8")


async def main():
    test_redaction()
    test_card_renderer()
    with tempfile.TemporaryDirectory() as tmpdir:
        config = make_config(tmpdir)
        test_part_filtering(config)
        test_session_404_mapping(config)
        test_audit_rotation(str(Path(tmpdir) / "audit"))
        test_processed_message_cleanup(str(Path(tmpdir) / "cleanup"))
        await test_bridge_flow(str(Path(tmpdir) / "flow"))
        await test_session_recovery(str(Path(tmpdir) / "session"))
        await test_reply_format_and_fallback(str(Path(tmpdir) / "format"))
        test_load_config_reply_format(str(Path(tmpdir) / "env"))
        await test_healthcheck(str(Path(tmpdir) / "health"))
        test_docs_and_templates()
    assert bridge.chunk_text("abcdefghi", 4) == ["abcd", "efgh", "i"]
    print("feishu opencode bridge tests passed")


if __name__ == "__main__":
    asyncio.run(main())
