# Research Agent Workflow

This project uses a simple wrapper for long-running experiments. The wrapper records logs, creates a summary, and sends a Feishu notification when the command exits.

## Run Experiments

Original command:

```bash
python train.py --config configs/default.yaml
```

Run it as:

```bash
./tools/run_with_feishu_notify.sh --name baseline_default -- python train.py --config configs/default.yaml
```

Add a short experiment note when the run has a specific intent:

```bash
./tools/run_with_feishu_notify.sh \
  --name exp_042 \
  --note "去除 region mask 模块，验证该模块对 UF1/UAR 的贡献" \
  -- python train.py --config configs/exp_042.yaml
```

## Outputs

- `logs/` stores complete stdout/stderr logs.
- `experiments/summaries/` stores `.summary.json` and `.summary.md` files for each experiment name.
- Feishu receives `success`, `failed`, or `interrupted` notifications.
- `summary.json` stores the user-provided `note`, top-level `status`, factual fields, metrics, log tail, and separate `analysis`.

The first version does not require modifying `train.py`. If later experiments need more stable metric parsing, make `train.py` write `metrics.json` or `result.json`; the summary script will prefer JSON metrics over regex log extraction.

`summarize_experiment.py` only extracts facts, metrics, traceback snippets, and the last 80 log lines. `analyze_with_agent.py` calls OpenCode with the note and those limited inputs, then writes concise Chinese Agent Analysis back into `summary.json`.

## Feishu CLI

No Feishu credential is stored in this repository. Configure your existing Feishu CLI, or set:

```bash
export FEISHU_CLI_CARD_COMMAND="feishu send --card"
export FEISHU_CLI_TEXT_COMMAND="feishu send --text"
```

The command prefix should accept the message body as its final argument. For `lark-cli`, set `FEISHU_CHAT_ID` or `FEISHU_USER_ID`; `lark-cli` will be auto-detected when available.
