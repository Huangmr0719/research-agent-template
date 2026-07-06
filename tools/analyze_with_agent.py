#!/usr/bin/env python3
"""Append CLI-agent analysis to an experiment summary JSON file."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict


UNAVAILABLE = "Agent 分析不可用。请查看 facts 和 log tail。"


def unavailable_analysis() -> Dict[str, Any]:
    return {
        "concise_summary": UNAVAILABLE,
        "evidence": [],
        "possible_causes": [],
        "next_steps": [],
        "confidence": "low",
    }


def load_summary(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError("summary JSON must contain an object")
    return value


def extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        value = json.loads(fenced.group(1))
        if isinstance(value, dict):
            return value

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        value = json.loads(text[start : end + 1])
        if isinstance(value, dict):
            return value

    raise ValueError("agent output did not contain a JSON object")


def normalize_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalize_analysis(value: Dict[str, Any]) -> Dict[str, Any]:
    confidence = str(value.get("confidence", "low")).strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "low"
    concise_summary = str(value.get("concise_summary", "")).strip() or UNAVAILABLE
    return {
        "concise_summary": concise_summary,
        "evidence": normalize_list(value.get("evidence")),
        "possible_causes": normalize_list(value.get("possible_causes")),
        "next_steps": normalize_list(value.get("next_steps")),
        "confidence": confidence,
    }


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def build_prompt(summary: Dict[str, Any]) -> str:
    note = str(summary.get("note") or "未填写")
    facts = summary.get("facts") if isinstance(summary.get("facts"), dict) else {}
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    log_tail = summary.get("log_tail") if isinstance(summary.get("log_tail"), list) else []
    traceback = summary.get("traceback") if isinstance(summary.get("traceback"), list) else []
    status = str(summary.get("status") or facts.get("status") or "unknown")

    status_instruction = {
        "success": (
            "success 状态下，重点分析结果是否值得保留，指标是否值得记录，是否需要补 seed、ablation 或稳定性检查。"
        ),
        "failed": (
            "failed 状态下，重点分析错误类型、可能原因和具体排查步骤。"
        ),
        "interrupted": (
            "interrupted 状态下，只分析中断前日志是否有异常，不要把未经验证的中断原因写成事实。"
        ),
    }.get(status, "请只根据提供的信息保守分析。")

    return f"""你是一个机器学习实验结果分析助手。请用中文分析本次实验。

你会收到：
1. 用户填写的实验备注 note；
2. wrapper 收集到的客观 facts；
3. 提取到的 metrics；
4. 最后 80 行 log tail；
5. 必要时的错误或 traceback 片段。

要求：
- 只根据提供的信息分析，不要编造事实；
- facts 是事实，不允许修改；
- note 是用户的实验意图，不是实验结果；
- 分析必须使用中文；
- 如果证据不足，请明确写“现有信息不足以判断”；
- 输出必须简洁，适合手机飞书阅读，不要写长篇报告；
- 返回严格 JSON，不要输出 Markdown 或额外说明。

返回 JSON 格式：
{{
  "concise_summary": "一句话中文总结",
  "evidence": ["依据1", "依据2"],
  "possible_causes": ["可能原因1", "可能原因2"],
  "next_steps": ["建议1", "建议2"],
  "confidence": "low|medium|high"
}}

状态专项要求：
{status_instruction}

实验备注 note：
{note}

Status:
{status}

Facts:
{compact_json(facts)}

Metrics:
{compact_json(metrics)}

错误或 traceback 片段（如有）:
{compact_json(traceback)}

Log tail, last 80 lines:
{compact_json(log_tail)}
"""


def run_opencode(prompt: str, timeout: int) -> str:
    if shutil.which("opencode") is None:
        raise FileNotFoundError("opencode CLI not found")
    completed = subprocess.run(
        ["opencode", "run", prompt],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "opencode failed")
    return completed.stdout


def write_summary(path: Path, summary: Dict[str, Any]) -> None:
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    path = Path(args.summary)
    summary = load_summary(path)
    prompt = build_prompt(summary)

    try:
        output = run_opencode(prompt, args.timeout)
        analysis = normalize_analysis(extract_json_object(output))
    except Exception as exc:
        analysis = unavailable_analysis()
        summary["analysis_error"] = str(exc)

    summary["analysis"] = analysis
    write_summary(path, summary)
    print(f"Updated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
