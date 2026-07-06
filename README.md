# research-agent-template

A small reusable template for initializing research projects with:

- a single experiment wrapper
- Feishu notification hooks
- log capture
- simple experiment summaries
- Agent workflow constraints

This first version is intentionally plain bash plus Python standard library. It does not store Feishu credentials.

## Install Once

Keep this repository somewhere stable, for example:

```bash
~/research-agent-template
```

Make scripts executable:

```bash
chmod +x ~/research-agent-template/init_research_project.sh
chmod +x ~/research-agent-template/tools/*.sh
chmod +x ~/research-agent-template/tools/*.py
chmod +x ~/research-agent-template/examples/*.sh
```

## Initialize A Research Project

From any research project root:

```bash
~/research-agent-template/init_research_project.sh
```

The init script creates:

```text
tools/
  run_with_feishu_notify.sh
  feishu_notify.py
  summarize_experiment.py
  analyze_with_agent.py
logs/
outputs/
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

## Toy Tests

After initializing a project that has the `examples/` directory, run:

```bash
./tools/run_with_feishu_notify.sh --name toy_success --note "toy success notification check" -- bash examples/toy_success.sh
```

```bash
./tools/run_with_feishu_notify.sh --name toy_failed -- bash examples/toy_failed.sh
```

Interrupt test:

```bash
./tools/run_with_feishu_notify.sh --name toy_interrupt -- bash -c "sleep 60"
```

Then press `Ctrl+C`. You should receive an `interrupted` notification if Feishu CLI is configured.

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
