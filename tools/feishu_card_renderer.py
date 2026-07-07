#!/usr/bin/env python3
"""Static Feishu card renderer for bridge replies."""

from __future__ import annotations

from typing import Optional


STATUS_TEMPLATES = {
    "normal": "blue",
    "success": "green",
    "warning": "orange",
    "timeout": "orange",
    "error": "red",
    "denied": "grey",
}

STATUS_TITLES = {
    "normal": "OpenCode 回复",
    "success": "任务完成",
    "warning": "任务警告",
    "timeout": "处理超时",
    "error": "任务失败",
    "denied": "权限拒绝",
}


def sanitize_card_markdown(content: str, max_chars: int = 6000) -> str:
    text = str(content or "").replace("\x00", "").strip()
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "\n\n... 内容较长，后续将以文本分片继续发送。"
    return text or "OpenCode 已完成处理，但没有返回可展示文本。"


def render_static_reply_card(
    title: Optional[str],
    content: str,
    status: str = "normal",
    subtitle: Optional[str] = "Research-Code-Agent",
    tags: Optional[list[str]] = None,
) -> dict:
    normalized_status = status if status in STATUS_TEMPLATES else "normal"
    card_title = title or STATUS_TITLES[normalized_status]
    safe_tags = [str(tag)[:32] for tag in (tags or []) if str(tag).strip()][:3]
    text_tag_list = [{"tag": "text", "text": {"content": tag}} for tag in safe_tags]
    summary = card_title
    if subtitle:
        summary = f"{card_title} - {subtitle}"

    return {
        "schema": "2.0",
        "config": {
            "update_multi": True,
            "enable_forward": False,
            "width_mode": "fill",
            "summary": {"content": summary},
        },
        "header": {
            "title": {"tag": "plain_text", "content": card_title},
            "subtitle": {"tag": "plain_text", "content": subtitle or ""},
            "text_tag_list": text_tag_list,
            "template": STATUS_TEMPLATES[normalized_status],
        },
        "body": {
            "direction": "vertical",
            "padding": "12px",
            "elements": [
                {
                    "tag": "markdown",
                    "element_id": "main_content",
                    "content": sanitize_card_markdown(content),
                    "text_size": "normal",
                }
            ],
        },
    }
