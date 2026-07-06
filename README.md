# Research-Code-Agent

面向科研代码项目的轻量级 Agent 辅助实验工具。

当前能力：

- experiment wrapper（带状态捕获）
- Feishu notification（卡片/文本）
- log capture
- summary.json / summary.md
- summary-based experiment comparison
- minimal paper context workflow
- on-demand OpenCode analysis
- project_results_adapter（项目级 metrics 适配）
- toy success / failed / interrupted tests
- Feishu smoke test

技术栈：bash + Python 标准库，无外部依赖。不存储 Feishu 凭证。

当前不做：gateway、MCP、Hermes、botmux、飞书双向控制。

## Install Once

Keep this repository somewhere stable, for example:

```bash
~/Research-Code-Agent
```

Make scripts executable:

```bash
chmod +x ~/Research-Code-Agent/init_research_project.sh
chmod +x ~/Research-Code-Agent/tools/*.sh
chmod +x ~/Research-Code-Agent/tools/*.py
chmod +x ~/Research-Code-Agent/examples/*.sh
```

## Initialize A Research Project

From any research project root:

```bash
~/Research-Code-Agent/init_research_project.sh
```

The init script creates:

```text
tools/
  run_with_feishu_notify.sh
  feishu_notify.py
  summarize_experiment.py
  analyze_with_agent.py
  compare_experiments.py
  init_paper_context.sh
  project_results_adapter.py
  test_feishu_notify.sh
templates/
  PAPER_CONTEXT_TEMPLATE.md
logs/
outputs/
papers/
experiments/
  summaries/
  runs/
examples/
  toy_success.sh
  toy_failed.sh
AGENTS.md
README_AGENT_WORKFLOW.md
```

If `tools/`, `AGENTS.md`, `README_AGENT_WORKFLOW.md`, or the toy example files already exist, existing paths are moved to `.bak.<timestamp>` before new files are copied.

## Recommended Order After Init

```bash
# 1. Initialize
bash init_research_project.sh

# 2. Verify Feishu notification
./tools/test_feishu_notify.sh

# 3. Run toy tests
./tools/run_with_feishu_notify.sh --name toy_success --note "toy success notification check" -- bash examples/toy_success.sh
./tools/run_with_feishu_notify.sh --name toy_failed -- bash examples/toy_failed.sh
```

## Minimal Paper-Aware Workflow

```bash
# 1. Initialize Research-Code-Agent
bash init_research_project.sh

# 2. Verify Feishu notification
./tools/test_feishu_notify.sh

# 3. Add local paper PDF
mkdir -p papers
cp /path/to/paper.pdf papers/

# 4. Create local paper context template
./tools/init_paper_context.sh

# 5. Ask your Agent to fill PAPER_CONTEXT.md based on:
# - papers/*.pdf
# - README.md
# - train.py / main.py
# - configs/
# - scripts/
```

Files under `papers/` and `PAPER_CONTEXT.md` are local context files and are ignored by Git. This workflow only gives the Agent paper context before code changes; it is not a knowledge base and does not parse PDFs automatically.

## Release Usage

Research-Code-Agent is the tool development repository. Do not `git clone` it into each baseline project.

Recommended baseline setup is via GitHub Release tarball:

```bash
wget https://github.com/Huangmr0719/Research-Code-Agent/releases/latest/download/research-code-agent.tar.gz
tar -xzf research-code-agent.tar.gz
bash research-code-agent/init_research_project.sh
rm -rf research-code-agent research-code-agent.tar.gz
```

The baseline project should only keep the initialized files such as `tools/`, `templates/`, `AGENTS.md`, `README_AGENT_WORKFLOW.md`, and ignore rules. Do not leave a nested `Research-Code-Agent/.git` in the baseline project.

Current development repository may still be named `research-agent-template`. The recommended future GitHub repository name is `Research-Code-Agent`; release package directory name should be `research-code-agent`.

## Run An Experiment

Original command:

```bash
python train.py --config configs/default.yaml
```

Use:

```bash
./tools/run_with_feishu_notify.sh --name baseline_default -- python train.py --config configs/default.yaml
```

You can add an experiment note:

```bash
./tools/run_with_feishu_notify.sh \
  --name exp_042 \
  --note "去除 region mask 模块，验证该模块对 UF1/UAR 的贡献" \
  -- python train.py --config configs/exp_042.yaml
```

The wrapper records the note, start time, end time, duration, host, git commit, stdout/stderr log path, exit code, signal, metrics, log tail, and Agent Analysis.

## Feishu Smoke Test

After initializing a project, verify Feishu notification:

```bash
./tools/test_feishu_notify.sh
```

If you receive the test card/message, the notification pipeline is working.

## Feishu Configuration

`tools/feishu_notify.py` defaults to Feishu card mode. It first tries to detect installed `feishu` or `lark` CLI binaries with common card/text send commands.

If you use `lark-cli`, set one target:

```bash
export FEISHU_CHAT_ID="oc_xxx"
# or
export FEISHU_USER_ID="ou_xxx"
```

`LARK_CHAT_ID` and `LARK_USER_ID` are also accepted. If needed, set `FEISHU_CLI_AS=bot` or `FEISHU_CLI_AS=user`.

If your CLI uses a different command format, set:

```bash
export FEISHU_CLI_CARD_COMMAND="feishu send --card"
export FEISHU_CLI_TEXT_COMMAND="feishu send --text"
```

The configured command should accept the notification payload as its final argument. If your CLI needs the payload in the middle of the command, use `{payload}`:

```bash
export FEISHU_CLI_CARD_COMMAND='feishu send --card-json {payload}'
```

If your CLI needs a payload file, use `{payload_file}`:

```bash
export FEISHU_CLI_CARD_COMMAND='feishu send --card-file {payload_file}'
```

For `lark-cli im +messages-send --msg-type interactive --content`, use `{card}` to pass only the card content object:

```bash
export FEISHU_CLI_CARD_COMMAND='lark-cli im +messages-send --chat-id oc_xxx --msg-type interactive --content {card}'
```

For compatibility with older setup, `FEISHU_CLI_SEND_COMMAND` is also supported. To force plain text notifications:

```bash
export FEISHU_NOTIFY_MODE=text
```

No Feishu credential should be written into this repository.

If Feishu sending fails, the script prints the notification content to stdout and exits non-zero. The experiment wrapper does not fail the experiment just because notification delivery failed.

## Summary Files

`tools/summarize_experiment.py` writes:

```text
experiments/summaries/<experiment_name>.summary.json
experiments/summaries/<experiment_name>.summary.md
```

`summarize_experiment.py` is fact-only. It extracts:

- `note`: user-provided experiment intent from `--note`
- `status`: success, failed, or interrupted
- `facts`: exit code, signal, command, host, git commit, start/end time, duration, log path
- `metrics`
- `log_tail`: last 80 log lines
- `traceback`: short traceback/error snippet if available

If `metrics.json` or `result.json` exists, JSON metrics are preferred. Otherwise the script extracts common metrics from logs:

- `accuracy`
- `acc`
- `F1`
- `UF1`
- `UAR`
- `loss`
- `val_loss`
- `best_epoch`

## Project Results Adapter

`tools/project_results_adapter.py` is a project-level metrics adapter template.

When a baseline project already produces structured metrics (e.g., `outputs/metrics.json`), the adapter extracts them before fallback to log regex.

Example `outputs/metrics.json`:

```json
{
  "metrics": {
    "UF1": 0.82,
    "UAR": 0.80,
    "loss": 0.41
  }
}
```

After running the wrapper, `summary.json` and the Feishu card will show these metrics with `metrics_source: adapter`.

If the adapter fails or finds no structured file, `summarize_experiment.py` falls back to `metrics.json` / `result.json` / log regex.  Adapter failure never blocks summary generation, OpenCode analysis, or Feishu notification.

Adapt `project_results_adapter.py` to each baseline project's output format.  Do NOT commit project-specific logic back into the mother template repository.

## Experiment Comparison

Compare experiments from generated summary files:

```bash
python tools/compare_experiments.py \
  --summaries experiments/summaries \
  --baseline baseline_default \
  --output experiments/comparisons/compare.md
```

`compare_experiments.py` only reads `*.summary.json` files under the summaries directory. It does not read full logs.

Comparison output is a local experiment artifact. `experiments/` is ignored by default and should not be committed unless you explicitly decide to preserve a cleaned result elsewhere.

## Agent Analysis

`tools/analyze_with_agent.py` reads the summary JSON and calls OpenCode:

```bash
opencode run "<prompt>"
```

Only note, facts, metrics, traceback snippets, and the last 80 log lines are sent to the agent. The analysis is written to `summary.json` under the `analysis` field and never overwrites `facts`.

The analysis schema is:

```json
{
  "concise_summary": "...",
  "evidence": [],
  "possible_causes": [],
  "next_steps": [],
  "confidence": "low|medium|high"
}
```

The prompt asks OpenCode to return concise Chinese analysis. If OpenCode is unavailable or fails, notifications still send. The analysis summary becomes:

```text
Agent 分析不可用。请查看 facts 和 log tail。
```

Feishu cards show `实验备注`, `运行概览`, `核心指标`, `Agent 分析`, `日志摘要`, and `运行命令`.

## Agent Rule

Long-running experiments must go through:

```bash
./tools/run_with_feishu_notify.sh --name <experiment_name> -- <command>
```

Do not directly run `python train.py` or `bash train.sh` for long tasks, and do not bypass Feishu notification.
