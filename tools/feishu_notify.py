#!/usr/bin/env python3
"""Send a research experiment notification through a local Feishu CLI."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


STATUS_META = {
    "success": {
        "title": "✅ 实验完成",
        "color": "green",
        "summary": "实验已成功完成。",
    },
    "failed": {
        "title": "❌ 实验失败",
        "color": "red",
        "summary": "实验以非零状态退出，请优先查看折叠日志摘要。",
    },
    "interrupted": {
        "title": "⚠️ 实验中断",
        "color": "orange",
        "summary": "实验在完成前中断，请查看中断前日志是否有异常。",
    },
}

STATUS_LABELS = {
    "success": "成功",
    "failed": "失败",
    "interrupted": "中断",
}

METRIC_ORDER = [
    ("UF1", ("UF1", "uf1")),
    ("UAR", ("UAR", "uar")),
    ("F1", ("F1", "f1")),
    ("Accuracy", ("accuracy", "Accuracy")),
    ("Acc", ("acc", "ACC", "Acc")),
    ("Loss", ("loss", "Loss")),
    ("Val Loss", ("val_loss", "val loss", "Val Loss")),
    ("Best Epoch", ("best_epoch", "best epoch", "Best Epoch")),
]

MAX_TAIL_LINES = 80
MAX_TAIL_LINE_CHARS = 300
MAX_TAIL_CHARS = 5000
MAX_COMMAND_CHARS = 1000
MAX_PATH_CHARS = 240
MAX_NOTE_CHARS = 600


def load_json(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        print(f"Warning: failed to parse JSON {path}: {exc}", file=sys.stderr)
        return {}


def read_text(path: Optional[str]) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def fallback(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 18)].rstrip() + " ... [truncated]"


def code_block(text: str, language: str = "text") -> str:
    safe_text = text.replace("```", "'''")
    return f"```{language}\n{safe_text}\n```"


def format_duration(seconds: Any) -> str:
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return "unknown"
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def flatten_metrics(metrics: Any) -> Dict[str, Any]:
    if not isinstance(metrics, dict):
        return {}
    if isinstance(metrics.get("metrics"), dict):
        return metrics["metrics"]
    return metrics


def metric_lookup(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {str(key).lower(): value for key, value in metrics.items()}


def ordered_metrics(metrics: Dict[str, Any]) -> List[Tuple[str, Any]]:
    if not metrics:
        return []

    lookup = metric_lookup(metrics)
    result = []
    seen = set()
    for label, aliases in METRIC_ORDER:
        for alias in aliases:
            key = alias.lower()
            if key in lookup:
                result.append((label, lookup[key]))
                seen.add(key)
                break

    for key in sorted(metrics):
        lower = str(key).lower()
        if lower not in seen and len(result) < 10:
            result.append((str(key), metrics[key]))
    return result[:10]


def lark_md(text: str) -> Dict[str, str]:
    return {"tag": "lark_md", "content": text}


def plain_text(text: str) -> Dict[str, str]:
    return {"tag": "plain_text", "content": text}


def fields(items: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    return [
        {
            "is_short": True,
            "text": lark_md(f"**{label}**\n{value}"),
        }
        for label, value in items
    ]


def section_title(title: str) -> Dict[str, Any]:
    return {
        "tag": "div",
        "text": lark_md(f"**{title}**"),
    }


def subdued(text: str) -> str:
    return f"<font color='grey'>{text}</font>"


def sanitize_tail(tail_log: str) -> str:
    if not tail_log.strip():
        return "未捕获到日志摘要。"

    raw_lines = tail_log.splitlines()[-MAX_TAIL_LINES:]
    lines = [truncate(line, MAX_TAIL_LINE_CHARS) for line in raw_lines]
    content = "\n".join(lines).strip()
    if len(content) > MAX_TAIL_CHARS:
        content = truncate(content, MAX_TAIL_CHARS)
        content += "\n\n[卡片日志摘要已截断，请查看完整 log path。]"
    return content or "未捕获到日志摘要。"


def join_tail(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(line) for line in value)
    return str(value or "")


def normalize_analysis(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "concise_summary": "Agent 分析不可用。请查看 facts 和 log tail。",
            "evidence": [],
            "possible_causes": [],
            "next_steps": [],
            "confidence": "low",
        }
    return {
        "concise_summary": fallback(value.get("concise_summary"), "Agent 分析不可用。请查看 facts 和 log tail。"),
        "evidence": value.get("evidence") if isinstance(value.get("evidence"), list) else [],
        "possible_causes": value.get("possible_causes") if isinstance(value.get("possible_causes"), list) else [],
        "next_steps": value.get("next_steps") if isinstance(value.get("next_steps"), list) else [],
        "confidence": fallback(value.get("confidence"), "low"),
    }


def bullet_list(items: List[Any], empty: str = "None") -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return subdued(empty)
    return "\n".join(f"- {truncate(value, 220)}" for value in values[:6])


def load_payload_data(args: argparse.Namespace) -> Dict[str, Any]:
    metadata = load_json(args.metadata)
    summary = load_json(args.summary)
    facts = summary.get("facts") if isinstance(summary.get("facts"), dict) else {}
    metrics = flatten_metrics(summary.get("metrics") or metadata.get("metrics"))
    status = fallback(summary.get("status") or facts.get("status") or args.status)
    if status not in STATUS_META:
        status = args.status
    analysis = normalize_analysis(summary.get("analysis"))
    log_tail = join_tail(summary.get("log_tail")) or read_text(args.tail_log)
    note = fallback(summary.get("note") or metadata.get("note"), "未填写")
    summary_path = fallback(args.summary, "unknown")
    return {
        "name": args.name,
        "note": note,
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "title": f"{STATUS_META[status]['title']} | {args.name}",
        "color": STATUS_META[status]["color"],
        "host": fallback(facts.get("host") or metadata.get("host")),
        "git_commit": fallback(facts.get("git_commit") or metadata.get("git_commit")),
        "command": fallback(facts.get("command") or metadata.get("command")),
        "start_time": fallback(facts.get("start_time") or metadata.get("start_time")),
        "end_time": fallback(facts.get("end_time") or metadata.get("end_time")),
        "duration": fallback(facts.get("duration") or format_duration(metadata.get("duration_seconds"))),
        "exit_code": fallback(facts.get("exit_code") or metadata.get("exit_code")),
        "signal": fallback(facts.get("signal") or metadata.get("signal")),
        "log_path": fallback(facts.get("log_path") or metadata.get("log_path")),
        "summary_path": summary_path,
        "metrics": ordered_metrics(metrics),
        "analysis": analysis,
        "tail_log": sanitize_tail(log_tail),
    }


def build_text_message(data: Dict[str, Any], include_tail: bool) -> str:
    lines = [
        data["title"],
        "",
        "实验备注:",
        truncate(data["note"], MAX_NOTE_CHARS),
        "",
        "运行概览:",
        f"- 状态: {data['status_label']}",
        f"- 耗时: {data['duration']}",
        f"- 主机: {data['host']}",
        f"- git commit: {data['git_commit']}",
        f"- exit code: {data['exit_code']}",
        f"- signal: {data['signal']}",
        f"- 开始时间: {data['start_time']}",
        f"- 结束时间: {data['end_time']}",
        "",
        "核心指标:",
    ]

    if data["metrics"]:
        for label, value in data["metrics"]:
            lines.append(f"- {label}: {value}")
    else:
        lines.append("- 未提取到核心指标")

    analysis = data["analysis"]
    lines.extend(
        [
            "",
            "Agent 分析:",
            f"- 结论: {analysis['concise_summary']}",
            f"- 置信度: {analysis['confidence']}",
        ]
    )
    if analysis["evidence"]:
        lines.append("- 依据:")
        lines.extend(f"  - {item}" for item in analysis["evidence"])
    if analysis["possible_causes"]:
        lines.append("- 可能原因:")
        lines.extend(f"  - {item}" for item in analysis["possible_causes"])
    if analysis["next_steps"]:
        lines.append("- 下一步建议:")
        lines.extend(f"  - {item}" for item in analysis["next_steps"])

    if include_tail:
        lines.extend(["", "日志摘要（最后 80 行）:", data["tail_log"]])

    lines.extend(
        [
            "",
            "运行命令:",
            f"- Command: {data['command']}",
            f"- Log Path: {data['log_path']}",
            f"- Summary Path: {data['summary_path']}",
        ]
    )
    return "\n".join(lines)


def build_card(data: Dict[str, Any], include_tail: bool) -> Dict[str, Any]:
    metric_fields = fields([(label, f"**{value}**") for label, value in data["metrics"]])
    if not metric_fields:
        metric_block = {
            "tag": "div",
            "text": lark_md(subdued("未提取到核心指标")),
        }
    else:
        metric_block = {"tag": "div", "fields": metric_fields}

    command = truncate(data["command"], MAX_COMMAND_CHARS)
    log_path = truncate(data["log_path"], MAX_PATH_CHARS)
    summary_path = truncate(data["summary_path"], MAX_PATH_CHARS)
    note = truncate(data["note"], MAX_NOTE_CHARS)
    analysis = data["analysis"]
    elements: List[Dict[str, Any]] = [
        section_title("实验备注"),
        {
            "tag": "div",
            "text": lark_md(note),
        },
        {"tag": "hr"},
        section_title("运行概览"),
        {
            "tag": "div",
            "fields": fields(
                [
                    ("状态", data["status_label"]),
                    ("耗时", data["duration"]),
                    ("主机", data["host"]),
                    ("git commit", data["git_commit"]),
                    ("exit code", data["exit_code"]),
                    ("signal", data["signal"]),
                    ("开始时间", data["start_time"]),
                    ("结束时间", data["end_time"]),
                ]
            ),
        },
        {"tag": "hr"},
        section_title("核心指标"),
        metric_block,
        {"tag": "hr"},
        section_title("Agent 分析"),
        {
            "tag": "div",
            "text": lark_md(
                f"**结论**\n{analysis['concise_summary']}\n\n"
                f"**依据**\n{bullet_list(analysis['evidence'], '现有信息不足以判断')}\n\n"
                f"**可能原因**\n{bullet_list(analysis['possible_causes'], '现有信息不足以判断或不适用')}\n\n"
                f"**下一步建议**\n{bullet_list(analysis['next_steps'], '现有信息不足以给出具体建议')}\n\n"
                f"{subdued('置信度: ' + analysis['confidence'])}"
            ),
        },
    ]

    if include_tail:
        elements.extend(
            [
                {"tag": "hr"},
                {
                    "tag": "collapsible_panel",
                    "expanded": False,
                    "header": {
                        "title": plain_text("日志摘要（最后 80 行）"),
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": lark_md(
                                subdued("默认折叠。完整 log 路径见底部。")
                                + "\n"
                                + code_block(data["tail_log"])
                            ),
                        }
                    ],
                },
            ]
        )

    elements.extend(
        [
            {"tag": "hr"},
            section_title("运行命令"),
            {
                "tag": "div",
                "text": lark_md(
                    subdued("Command")
                    + "\n"
                    + code_block(command, "bash")
                    + "\n"
                    + subdued("Log Path")
                    + f"\n`{log_path}`\n"
                    + subdued("Summary Path")
                    + f"\n`{summary_path}`"
                ),
            },
        ]
    )

    return {
        "config": {
            "wide_screen_mode": True,
            "enable_forward": True,
        },
        "header": {
            "title": plain_text(data["title"]),
            "template": data["color"],
        },
        "elements": elements,
    }


def build_card_payload(data: Dict[str, Any], include_tail: bool) -> Tuple[str, str]:
    card = build_card(data, include_tail)
    payload = {
        "msg_type": "interactive",
        "card": card,
    }
    full_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    card_content = json.dumps(card, ensure_ascii=False, separators=(",", ":"))
    return full_payload, card_content


def split_env_command(value: str) -> List[str]:
    return shlex.split(value.strip())


def explicit_command(var_name: str) -> Optional[List[str]]:
    value = os.environ.get(var_name, "").strip()
    return split_env_command(value) if value else None


def find_lark_cli() -> Optional[str]:
    direct = shutil.which("lark-cli")
    if direct:
        return direct

    patterns = [
        str(Path.home() / ".nvm/versions/node/*/bin/lark-cli"),
        str(Path.home() / ".nvm/versions/node/*/lib/node_modules/@larksuite/cli/bin/lark-cli"),
        "/opt/homebrew/bin/lark-cli",
        "/usr/local/bin/lark-cli",
    ]
    for pattern in patterns:
        for match in sorted(glob(pattern), reverse=True):
            if os.path.isfile(match) and os.access(match, os.X_OK):
                return match
    return None


def lark_cli_target_args() -> List[str]:
    chat_id = os.environ.get("FEISHU_CHAT_ID") or os.environ.get("LARK_CHAT_ID")
    user_id = os.environ.get("FEISHU_USER_ID") or os.environ.get("LARK_USER_ID")
    if chat_id:
        return ["--chat-id", chat_id]
    if user_id:
        return ["--user-id", user_id]
    return []


def lark_cli_identity_args() -> List[str]:
    identity = os.environ.get("FEISHU_CLI_AS") or os.environ.get("LARK_CLI_AS")
    return ["--as", identity] if identity else []


def lark_cli_commands(kind: str) -> List[List[str]]:
    lark_cli = find_lark_cli()
    target_args = lark_cli_target_args()
    if not lark_cli or not target_args:
        return []

    base = [lark_cli, "im", "+messages-send"] + lark_cli_identity_args() + target_args
    if kind == "card":
        return [base + ["--msg-type", "interactive", "--content", "{card}"]]
    return [base + ["--text", "{payload}"]]


def auto_commands(kind: str) -> List[List[str]]:
    commands = []  # type: List[List[str]]
    if kind == "card":
        variants = [
            ["send", "--card"],
            ["message", "send", "--card"],
            ["notify", "--card"],
            ["send", "--type", "card"],
            ["send", "--msg-type", "interactive"],
        ]
    else:
        variants = [
            ["send", "--text"],
            ["message", "send", "--text"],
            ["notify", "--text"],
        ]

    for binary in ("feishu", "lark"):
        if shutil.which(binary):
            commands.extend([[binary] + variant for variant in variants])
    commands.extend(lark_cli_commands(kind))
    return commands


def candidate_commands(kind: str) -> List[List[str]]:
    if kind == "card":
        command = explicit_command("FEISHU_CLI_CARD_COMMAND")
        if command:
            return [command]
    else:
        command = explicit_command("FEISHU_CLI_TEXT_COMMAND")
        if command:
            return [command]

    shared = explicit_command("FEISHU_CLI_SEND_COMMAND")
    if shared:
        return [shared]

    return auto_commands(kind)


def render_command(command_prefix: List[str], payload: str, card_content: Optional[str]) -> Tuple[List[str], Optional[str]]:
    payload_file = None
    if any("{payload_file}" in arg for arg in command_prefix):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            f.write(payload)
            payload_file = f.name
        rendered = [arg.replace("{payload_file}", payload_file) for arg in command_prefix]
        return rendered, payload_file

    if any("{card}" in arg for arg in command_prefix):
        rendered_card = card_content if card_content is not None else payload
        return [arg.replace("{card}", rendered_card) for arg in command_prefix], None

    if any("{payload}" in arg for arg in command_prefix):
        return [arg.replace("{payload}", payload) for arg in command_prefix], None

    return command_prefix + [payload], None


def run_command(command_prefix: List[str], payload: str, card_content: Optional[str]) -> int:
    command, payload_file = render_command(command_prefix, payload, card_content)
    try:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return 127
    except OSError as exc:
        print(f"Failed to run Feishu CLI: {exc}", file=sys.stderr)
        return 1
    finally:
        if payload_file:
            try:
                os.unlink(payload_file)
            except OSError:
                pass

    if completed.returncode != 0:
        if completed.stderr:
            print(completed.stderr.strip(), file=sys.stderr)
        if completed.stdout:
            print(completed.stdout.strip(), file=sys.stderr)
    return completed.returncode


def send_payload(kind: str, payload: str, card_content: Optional[str] = None) -> int:
    commands = candidate_commands(kind)
    if not commands:
        return 127

    last_code = 1
    for command in commands:
        last_code = run_command(command, payload, card_content)
        if last_code == 0:
            return 0
    return last_code or 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", required=True, choices=("success", "failed", "interrupted"))
    parser.add_argument("--name", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--summary")
    parser.add_argument("--tail-log")
    args = parser.parse_args()

    data = load_payload_data(args)
    include_tail = data["status"] in {"failed", "interrupted"}
    text_message = build_text_message(data, include_tail=include_tail)

    mode = os.environ.get("FEISHU_NOTIFY_MODE", "card").strip().lower() or "card"
    if mode not in {"card", "text"}:
        print(f"Unknown FEISHU_NOTIFY_MODE={mode!r}; falling back to card.", file=sys.stderr)
        mode = "card"

    if mode == "text":
        code = send_payload("text", text_message)
        if code == 0:
            return 0
        print("\nFeishu text send failed. Notification content:\n")
        print(text_message)
        return code

    card_payload, card_content = build_card_payload(data, include_tail=include_tail)
    card_code = send_payload("card", card_payload, card_content)
    if card_code == 0:
        return 0

    print("Feishu card send failed; falling back to text.", file=sys.stderr)
    text_code = send_payload("text", text_message)
    if text_code == 0:
        return 0

    if card_code == 127 and text_code == 127:
        print("No Feishu CLI command detected.", file=sys.stderr)
        print("Set FEISHU_CLI_CARD_COMMAND or FEISHU_CLI_TEXT_COMMAND, for example:", file=sys.stderr)
        print('  export FEISHU_CLI_CARD_COMMAND="feishu send --card"', file=sys.stderr)
        print('  export FEISHU_CLI_TEXT_COMMAND="feishu send --text"', file=sys.stderr)

    print("\nFeishu notification failed. Text fallback content:\n")
    print(text_message)
    return text_code or card_code or 1


if __name__ == "__main__":
    raise SystemExit(main())
