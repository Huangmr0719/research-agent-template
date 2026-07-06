#!/usr/bin/env python3
"""Thin Feishu long-connection bridge to a local OpenCode server.

The bridge does not parse commands or decide user intent. It accepts Feishu
messages from whitelisted open_id values, deduplicates message_id values in
SQLite, forwards plain text to OpenCode, and sends OpenCode's answer back to
Feishu in text chunks.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import socket
import sqlite3
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


DEFAULT_OPENCODE_URL = "http://127.0.0.1:4096"
DEFAULT_ACK = "收到，处理中。"
DEFAULT_BUSY = "当前会话已有任务处理中，请稍后再试。"
DEFAULT_UNAVAILABLE = "OpenCode 调用失败，请查看 bridge 日志。"
DEFAULT_TIMEOUT = "处理超时，已尝试中止当前 OpenCode 会话任务，请到服务器检查日志。"
DISPLAY_TEXT_FALLBACK = "OpenCode 已完成处理，但没有返回可展示文本。"
DEFAULT_SYSTEM_PROMPT = (
    "你是 Research-Code-Agent 远程助手。你运行在用户的科研代码服务器上。"
    "你只根据当前项目文件和用户消息工作；不要编造执行结果。"
    "所有长时间实验必须通过 tools/run_with_feishu_notify.sh 执行。"
)


@dataclass(frozen=True)
class BridgeConfig:
    app_id: str
    app_secret: str
    allowed_open_ids: set[str]
    opencode_base_url: str
    opencode_username: str
    opencode_password: str
    project_dir: str
    db_path: str
    log_path: str
    timeout_seconds: int
    chunk_chars: int
    ack_text: str
    busy_text: str
    unavailable_text: str
    timeout_text: str
    system_prompt: str
    opencode_agent: str
    opencode_model_provider: str
    opencode_model_id: str


class BridgeError(RuntimeError):
    pass


class OpenCodeHttpError(BridgeError):
    def __init__(self, status_code: int, details: str):
        super().__init__(f"OpenCode HTTP {status_code}: {details}")
        self.status_code = status_code
        self.details = details


class OpenCodeTimeoutError(BridgeError):
    pass


class OpenCodeUnavailableError(BridgeError):
    pass


def load_env_file(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        raise BridgeError(f"env file not found: {path}")
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise BridgeError(f"{name} must be an integer") from exc


def load_config() -> BridgeConfig:
    allowed_env = os.environ.get("RCA_FEISHU_ALLOWED_OPEN_IDS") or os.environ.get("FEISHU_ALLOWED_OPEN_IDS", "")
    allowed = {
        item.strip()
        for item in allowed_env.split(",")
        if item.strip()
    }
    config = BridgeConfig(
        app_id=os.environ.get("LARK_APP_ID") or os.environ.get("FEISHU_APP_ID", ""),
        app_secret=os.environ.get("LARK_APP_SECRET") or os.environ.get("FEISHU_APP_SECRET", ""),
        allowed_open_ids=allowed,
        opencode_base_url=os.environ.get("OPENCODE_BASE_URL", DEFAULT_OPENCODE_URL).rstrip("/"),
        opencode_username=os.environ.get("OPENCODE_SERVER_USERNAME", "opencode"),
        opencode_password=os.environ.get("OPENCODE_SERVER_PASSWORD", ""),
        project_dir=os.environ.get("RCA_PROJECT_DIR", os.getcwd()),
        db_path=os.environ.get("BRIDGE_DB_PATH") or os.environ.get("RCA_BRIDGE_DB", "logs/feishu_opencode_bridge.sqlite3"),
        log_path=os.environ.get("BRIDGE_LOG_PATH", "logs/feishu_opencode_bridge.jsonl"),
        timeout_seconds=env_int("BRIDGE_TIMEOUT_SECONDS", env_int("RCA_BRIDGE_TIMEOUT_SECONDS", 600)),
        chunk_chars=env_int("RCA_BRIDGE_CHUNK_CHARS", 2500),
        ack_text=os.environ.get("RCA_BRIDGE_ACK_TEXT", DEFAULT_ACK),
        busy_text=os.environ.get("RCA_BRIDGE_BUSY_TEXT", DEFAULT_BUSY),
        unavailable_text=os.environ.get("RCA_BRIDGE_UNAVAILABLE_TEXT", DEFAULT_UNAVAILABLE),
        timeout_text=os.environ.get("RCA_BRIDGE_TIMEOUT_TEXT", DEFAULT_TIMEOUT),
        system_prompt=os.environ.get("RCA_BRIDGE_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
        opencode_agent=os.environ.get("OPENCODE_AGENT", ""),
        opencode_model_provider=os.environ.get("OPENCODE_MODEL_PROVIDER", ""),
        opencode_model_id=os.environ.get("OPENCODE_MODEL_ID", ""),
    )
    missing = []
    if not config.app_id:
        missing.append("LARK_APP_ID")
    if not config.app_secret:
        missing.append("LARK_APP_SECRET")
    if not config.allowed_open_ids:
        missing.append("RCA_FEISHU_ALLOWED_OPEN_IDS")
    if not config.opencode_base_url.startswith("http://127.0.0.1:"):
        missing.append("OPENCODE_BASE_URL must use http://127.0.0.1:<port>")
    if missing:
        raise BridgeError("missing or invalid config: " + ", ".join(missing))
    return config


class MessageStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_messages (
                    message_id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    open_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    status TEXT,
                    error TEXT
                )
                """
            )
            self._ensure_column(conn, "processed_messages", "status", "TEXT")
            self._ensure_column(conn, "processed_messages", "error", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    chat_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def claim_message(self, message_id: str, chat_id: str, open_id: str) -> bool:
        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO processed_messages(message_id, chat_id, open_id, created_at, status, error)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (message_id, chat_id, open_id, int(time.time()), "received", None),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def update_message_status(self, message_id: str, status: str, error: str = "") -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE processed_messages SET status = ?, error = ? WHERE message_id = ?",
                (status, error or None, message_id),
            )

    def get_chat_session(self, chat_id: str) -> Optional[str]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT session_id FROM chat_sessions WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        return row[0] if row else None

    def save_chat_session(self, chat_id: str, session_id: str) -> None:
        now = int(time.time())
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions(chat_id, session_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    updated_at = excluded.updated_at
                """,
                (chat_id, session_id, now, now),
            )


class OpenCodeClient:
    def __init__(self, config: BridgeConfig):
        self.config = config

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.opencode_password:
            token = base64.b64encode(
                f"{self.config.opencode_username}:{self.config.opencode_password}".encode("utf-8")
            )
            headers["Authorization"] = "Basic " + token.decode("ascii")
        return headers

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        url = self.config.opencode_base_url + path
        data = None
        headers = self._headers()
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.config.timeout_seconds) as resp:
                body = resp.read()
                if not body:
                    return None
                return json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", "replace")
            raise OpenCodeHttpError(exc.code, details) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise OpenCodeTimeoutError(f"OpenCode request timed out after {timeout or self.config.timeout_seconds}s") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, socket.timeout):
                raise OpenCodeTimeoutError(
                    f"OpenCode request timed out after {timeout or self.config.timeout_seconds}s"
                ) from exc
            raise OpenCodeUnavailableError(f"OpenCode request failed: {exc}") from exc

    def health(self) -> dict[str, Any]:
        data = self._request("GET", "/global/health")
        if not isinstance(data, dict) or data.get("healthy") is not True:
            raise BridgeError(f"OpenCode health check failed: {data!r}")
        return data

    def validate_doc(self) -> None:
        self.health()
        doc = self._request("GET", "/doc")
        paths = doc.get("paths", {}) if isinstance(doc, dict) else {}
        required = [
            "/session",
            "/session/{sessionID}/message",
            "/session/{sessionID}/abort",
        ]
        missing = [path for path in required if path not in paths]
        if missing:
            raise BridgeError("OpenCode /doc missing required paths: " + ", ".join(missing))

    def create_session(self, title: Optional[str] = None) -> str:
        payload: dict[str, Any] = {}
        if title:
            payload["title"] = title
        data = self._request("POST", "/session", payload)
        session = self._unwrap_data(data)
        try:
            return session["id"]
        except (TypeError, KeyError) as exc:
            raise BridgeError(f"unexpected OpenCode session response: {data!r}") from exc

    def send_message(
        self,
        session_id: str,
        user_text: str,
        feishu_context: dict[str, str],
        timeout: int,
    ) -> str:
        prompt = self._build_prompt(user_text, feishu_context)
        payload: dict[str, Any] = {"parts": [{"type": "text", "text": prompt}]}
        try:
            data = self._request("POST", f"/session/{session_id}/message", payload, timeout=timeout)
        except OpenCodeTimeoutError:
            self.abort_session(session_id)
            raise
        text = self.extract_text_from_response(data)
        if text:
            return text
        return self.extract_text_from_messages(self.list_messages(session_id, limit=5))

    def abort_session(self, session_id: str) -> bool:
        try:
            data = self._request("POST", f"/session/{session_id}/abort")
            return bool(data) if data is not None else True
        except BridgeError as exc:
            print(f"failed to abort OpenCode session {session_id}: {exc}", file=sys.stderr)
            return False

    def list_messages(self, session_id: str, limit: int = 5) -> list[dict[str, Any]]:
        data = self._request("GET", f"/session/{session_id}/message?limit={limit}")
        unwrapped = self._unwrap_data(data)
        if isinstance(unwrapped, list):
            return [item for item in unwrapped if isinstance(item, dict)]
        return []

    def _build_prompt(self, user_text: str, feishu_context: Optional[dict[str, str]] = None) -> str:
        feishu_context = feishu_context or {}
        return "\n".join(
            [
                self.config.system_prompt,
                "",
                "用户通过飞书发来请求：",
                "",
                user_text,
                "",
                "请在当前项目中处理。遵守 AGENTS.md。优先使用 Research-Code-Agent 现有 tools。长实验必须使用 tools/run_with_feishu_notify.sh。",
                "",
                "Feishu context:",
                f"- open_id: {feishu_context.get('open_id', 'unknown')}",
                f"- chat_id: {feishu_context.get('chat_id', 'unknown')}",
                f"- message_id: {feishu_context.get('message_id', 'unknown')}",
            ]
        ).strip()

    def extract_text_from_response(self, data: Any) -> str:
        item = self._unwrap_data(data)
        if isinstance(item, dict):
            if item.get("info", {}).get("error"):
                raise BridgeError("OpenCode assistant error: " + json.dumps(item["info"]["error"], ensure_ascii=False))
            return self.extract_text_from_parts(item.get("parts", []))
        return ""

    def extract_text_from_messages(self, messages: list[dict[str, Any]]) -> str:
        texts: list[str] = []
        for item in messages:
            if item.get("info", {}).get("error"):
                raise BridgeError("OpenCode assistant error: " + json.dumps(item["info"]["error"], ensure_ascii=False))
            text = self.extract_text_from_parts(item.get("parts", []))
            if text:
                texts.append(text)
        output = "\n\n".join(texts).strip()
        return output or DISPLAY_TEXT_FALLBACK

    def extract_text_from_parts(self, parts: Any) -> str:
        if not isinstance(parts, list):
            return DISPLAY_TEXT_FALLBACK
        display_types = {"text", "message", "assistant_text"}
        hidden_types = {
            "reasoning",
            "thinking",
            "thought",
            "tool",
            "tool_call",
            "tool_result",
            "step",
            "system",
            "debug",
            "internal",
        }
        texts: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type", "")).lower()
            if part_type in hidden_types:
                continue
            if part_type not in display_types:
                continue
            for key in ("text", "content"):
                value = part.get(key)
                if isinstance(value, str) and value.strip():
                    texts.append(value.strip())
                    break
        return "\n".join(texts).strip() or DISPLAY_TEXT_FALLBACK

    def _unwrap_data(self, data: Any) -> Any:
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data


class ChatLockRegistry:
    def __init__(self) -> None:
        self._global = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    def acquire(self, chat_id: str) -> Optional[threading.Lock]:
        with self._global:
            lock = self._locks.setdefault(chat_id, threading.Lock())
        if not lock.acquire(blocking=False):
            return None
        return lock


def chunk_text(text: str, chunk_chars: int) -> list[str]:
    text = text.strip() or "(empty)"
    if chunk_chars <= 0:
        chunk_chars = 2500
    chunks: list[str] = []
    current = ""
    for line in text.splitlines():
        candidate = line if not current else current + "\n" + line
        if len(candidate) <= chunk_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(line) > chunk_chars:
            chunks.append(line[:chunk_chars])
            line = line[chunk_chars:]
        current = line
    if current:
        chunks.append(current)
    return chunks or ["(empty)"]


class BridgeApp:
    def __init__(self, config: BridgeConfig, channel: Any):
        self.config = config
        self.channel = channel
        self.store = MessageStore(config.db_path)
        self.chat_locks = ChatLockRegistry()
        self.opencode = OpenCodeClient(config)

    async def handle_message(self, msg: Any) -> None:
        open_id = getattr(msg, "sender_id", "") or getattr(getattr(msg, "sender", None), "open_id", "") or ""
        chat_id = getattr(msg, "chat_id", "")
        message_id = getattr(msg, "message_id", "") or getattr(msg, "id", "")
        text = getattr(msg, "content_text", "") or ""
        if open_id not in self.config.allowed_open_ids:
            self._audit("reject_non_whitelist", message_id, chat_id, open_id)
            return
        if not self.store.claim_message(message_id, chat_id, open_id):
            self._audit("deduplicated", message_id, chat_id, open_id)
            return

        lock = self.chat_locks.acquire(chat_id)
        if lock is None:
            await self._safe_send(chat_id, message_id, self.config.busy_text)
            return

        if not await self._safe_send(chat_id, message_id, self.config.ack_text):
            lock.release()
            return

        try:
            result = await asyncio.to_thread(self._process_message, message_id, chat_id, open_id, text)
            for index, chunk in enumerate(chunk_text(result, self.config.chunk_chars), start=1):
                prefix = f"[{index}] " if index > 1 else ""
                await self._safe_send(chat_id, message_id, prefix + chunk)
            self.store.update_message_status(message_id, "success")
            self._audit("success", message_id, chat_id, open_id)
        except OpenCodeTimeoutError as exc:
            print("bridge processing timed out:", exc, file=sys.stderr)
            self.store.update_message_status(message_id, "timeout", str(exc))
            self._audit("timeout", message_id, chat_id, open_id, str(exc))
            await self._safe_send(chat_id, message_id, self.config.timeout_text)
        except OpenCodeUnavailableError as exc:
            print("OpenCode unavailable:", exc, file=sys.stderr)
            self.store.update_message_status(message_id, "opencode_unavailable", str(exc))
            self._audit("opencode_unavailable", message_id, chat_id, open_id, str(exc))
            await self._safe_send(chat_id, message_id, "OpenCode 服务不可用，请检查 opencode serve。")
        except Exception as exc:  # noqa: BLE001 - bridge must report failures to Feishu.
            print("bridge processing failed:", exc, file=sys.stderr)
            traceback.print_exc()
            self.store.update_message_status(message_id, "failed", str(exc))
            self._audit("failed", message_id, chat_id, open_id, str(exc))
            await self._safe_send(chat_id, message_id, self.config.unavailable_text)
        finally:
            lock.release()

    async def _safe_send(self, chat_id: str, message_id: str, text: str) -> bool:
        try:
            result = await self.channel.send(
                chat_id,
                {"markdown": text},
                {"reply_to": message_id},
            )
            if hasattr(result, "success") and result.success is False:
                raise BridgeError(f"Feishu send failed: {getattr(result, 'error', '')}")
            return True
        except Exception as exc:  # noqa: BLE001 - Feishu delivery failure should not crash callbacks.
            print(f"Feishu reply failed for message_id={message_id}: {exc}", file=sys.stderr)
            return False

    def _process_message(
        self,
        message_id: str,
        chat_id: str,
        open_id: str,
        text: str,
    ) -> str:
        self.store.update_message_status(message_id, "processing")
        session_id = self.store.get_chat_session(chat_id)
        if not session_id:
            session_id = self.opencode.create_session(title=f"feishu:{chat_id}")
            self.store.save_chat_session(chat_id, session_id)
        context = {"message_id": message_id, "chat_id": chat_id, "open_id": open_id}
        return self.opencode.send_message(
            session_id,
            text,
            context,
            timeout=self.config.timeout_seconds,
        )

    def _audit(self, status: str, message_id: str, chat_id: str, open_id: str, error: str = "") -> None:
        Path(self.config.log_path).parent.mkdir(parents=True, exist_ok=True)
        row = {
            "time": int(time.time()),
            "status": status,
            "message_id": message_id,
            "chat_id": chat_id,
            "open_id": open_id,
            "error": error,
        }
        with open(self.config.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def start_feishu_bridge(config: BridgeConfig) -> None:
    try:
        from lark_channel import FeishuChannel
    except ImportError as exc:
        raise BridgeError("missing dependency: install lark-channel-sdk for Feishu Channel SDK") from exc

    channel = FeishuChannel(app_id=config.app_id, app_secret=config.app_secret)
    app = BridgeApp(config, channel)
    app.opencode.validate_doc()
    channel.on("message", app.handle_message)
    asyncio.run(channel.connect())


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Feishu long-connection bridge to local OpenCode")
    parser.add_argument("--env-file", "--env", dest="env_file", help="load environment variables from a file")
    parser.add_argument("--check", action="store_true", help="validate config, sqlite, and OpenCode /doc")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        if args.env_file:
            load_env_file(args.env_file)
        config = load_config()
        if args.check:
            MessageStore(config.db_path)
            OpenCodeClient(config).validate_doc()
            print("bridge configuration check passed")
            return 0
        start_feishu_bridge(config)
        return 0
    except BridgeError as exc:
        print(f"feishu_opencode_bridge: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
