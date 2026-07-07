# Research-Code-Agent

面向科研代码项目的轻量级 Agent 辅助实验工具。

当前能力：

- experiment wrapper（带状态捕获）
- Feishu notification（卡片/文本）
- log capture
- summary.json / summary.md
- summary-based experiment comparison
- minimal paper context workflow
- Feishu-OpenCode Bridge prototype
- on-demand OpenCode analysis
- project_results_adapter（项目级 metrics 适配）
- toy success / failed / interrupted tests
- Feishu smoke test

技术栈：bash + Python 标准库。核心实验工具无外部依赖；可选 Feishu-OpenCode Bridge 需要 Feishu Channel SDK Python（`lark-channel-sdk`）。不存储 Feishu 凭证。

当前 Bridge 不做：gateway、MCP、Hermes、botmux、Vercel Chat SDK、飞书 CLI、webhook、内网穿透、飞书审批控制、多平台抽象。

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
  feishu_opencode_bridge.py
  project_results_adapter.py
  test_feishu_notify.sh
templates/
  PAPER_CONTEXT_TEMPLATE.md
  feishu_bridge.env.example
  systemd/
    opencode-serve.service
    rca-feishu-opencode-bridge.service
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

## Feishu-OpenCode Bridge Prototype

v0.5.0 adds an optional thin bridge for remote OpenCode access from Feishu:

```text
Feishu Channel SDK Python
  -> open_id whitelist
  -> sqlite message_id dedupe
  -> per-chat lock
  -> immediate "收到，处理中。"
  -> local OpenCode server at 127.0.0.1:4096
  -> static Feishu card replies, with markdown fallback
```

The bridge does not implement `/status`, `/summary`, `/run`, or any Python command router. It does not use Vercel Chat SDK, `@larksuite/vercel-chat-adapter`, Feishu CLI, DingTalk MCP, webhook, public ports, tunneling, streaming progress, approval cards, MCP, Hermes, botmux, or multi-platform routing. Feishu is the only remote entrypoint. OpenCode is responsible for understanding and executing the user request.

Long-running experiments must still be launched through:

```bash
./tools/run_with_feishu_notify.sh --name <experiment_name> -- <command>
```

### Feishu App Setup

Create a Feishu self-built app and enable WebSocket event subscription for local/server development. Subscribe to the message receive event for bot chats, grant bot message send/receive scopes, then reinstall the app into the tenant and target chat. Record:

- app id
- app secret
- allowed user `open_id` values

Only `open_id` is used for the bridge whitelist.

### OpenCode Local Server

Run OpenCode only on localhost:

```bash
export OPENCODE_SERVER_PASSWORD="<long-random-password>"
opencode serve --hostname 127.0.0.1 --port 4096
```

Before the bridge starts, it checks OpenCode health and `http://127.0.0.1:4096/doc`. The bridge uses the standard OpenCode server API:

- `GET /global/health`
- `POST /session`
- `POST /session/{sessionID}/message`
- `GET /session/{sessionID}/message`
- `POST /session/{sessionID}/abort`

When `OPENCODE_SERVER_PASSWORD` is set, OpenCode protects the HTTP API with Basic Auth. The default username is `opencode`; set `OPENCODE_SERVER_USERNAME` if your server overrides it. The bridge reads both values and sends the matching Authorization header.

The bridge stores `chat_id -> session_id` in sqlite, so a Feishu chat can continue using the same OpenCode session after the bridge restarts. If a request times out, the bridge calls `POST /session/{sessionID}/abort` and replies with a timeout notice.

If `opencode serve` restarts and the stored session no longer exists, the bridge recreates the OpenCode session for that `chat_id`, updates sqlite, and retries the current message once. It does not retry indefinitely.

### Bridge Configuration

Copy the example env file to a private location:

```bash
sudo mkdir -p /etc/research-code-agent
sudo cp templates/feishu_bridge.env.example /etc/research-code-agent/feishu-bridge.env
sudo chmod 600 /etc/research-code-agent/feishu-bridge.env
sudo $EDITOR /etc/research-code-agent/feishu-bridge.env
```

Required values:

```bash
LARK_APP_ID=cli_xxx
LARK_APP_SECRET=xxx
RCA_FEISHU_ALLOWED_OPEN_IDS=ou_xxx,ou_yyy
OPENCODE_BASE_URL=http://127.0.0.1:4096
OPENCODE_SERVER_USERNAME=opencode
OPENCODE_SERVER_PASSWORD=change-this-long-random-password
RCA_PROJECT_DIR=/path/to/baseline-project
BRIDGE_DB_PATH=/path/to/baseline-project/logs/feishu_opencode_bridge.sqlite3
BRIDGE_LOG_PATH=/path/to/baseline-project/logs/feishu_opencode_bridge.jsonl
BRIDGE_TIMEOUT_SECONDS=600
BRIDGE_REPLY_FORMAT=card
```

The copied env file is private configuration and must not be committed.

Install Feishu Channel SDK Python in the runtime environment used by systemd:

```bash
python3 -m pip install --user lark-channel-sdk
```

### Permission Boundary

The bridge prompt is only a behavior hint, not a security boundary. Real restrictions must come from:

- `opencode.json` permission rules;
- the Unix user running the systemd services;
- filesystem ownership and write permissions;
- keeping `opencode serve` bound to `127.0.0.1`.

Use a restricted service user if the server is shared. Do not give OpenCode write access to datasets, checkpoints, private credentials, or unrelated projects unless needed.

### Reply Safety and Cards

v0.5.3 defaults to static Feishu cards for final OpenCode replies:

```bash
BRIDGE_REPLY_FORMAT=card
```

Set this to markdown if card sending is incompatible with the current Feishu tenant or SDK behavior:

```bash
BRIDGE_REPLY_FORMAT=markdown
```

The card mode is static display only. It does not use buttons, card callbacks, streaming updates, approval actions, or command values. If card sending fails, the bridge automatically falls back to markdown/text replies so the user still receives the result.

The bridge applies two separate safety filters before replying to Feishu:

- OpenCode part filtering avoids structural leakage from `reasoning`, `thinking`, `tool`, `tool_result`, `system`, `debug`, and internal message parts.
- `redact_sensitive_text` reduces content leakage in the final visible reply by replacing common tokens, API keys, private key blocks, and secret-like env lines with `[REDACTED]`.

Audit logs are local troubleshooting material. They are not sent back to Feishu, are ignored by Git, and should be protected with normal file permissions.

### systemd Deployment

Copy the service templates and edit paths:

```bash
sudo cp templates/systemd/opencode-serve.service /etc/systemd/system/opencode-serve.service
sudo cp templates/systemd/rca-feishu-opencode-bridge.service /etc/systemd/system/rca-feishu-opencode-bridge.service
sudo $EDITOR /etc/systemd/system/opencode-serve.service
sudo $EDITOR /etc/systemd/system/rca-feishu-opencode-bridge.service
```

Then enable both services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now opencode-serve.service
sudo systemctl enable --now rca-feishu-opencode-bridge.service
```

Check logs:

```bash
journalctl -u opencode-serve.service -f
journalctl -u rca-feishu-opencode-bridge.service -f
```

For foreground testing on macOS, use:

```bash
python3 tools/feishu_opencode_bridge.py --env feishu_bridge.env
```

### Bridge Behavior

- Non-whitelisted `open_id` messages are ignored.
- Duplicate `message_id` values are skipped via sqlite.
- The same `chat_id` can process only one message at a time.
- If a chat is busy, the bridge replies with a short busy message.
- OpenCode output is sent as a static Feishu card by default; long output or card failures fall back to Feishu text chunks.
- If OpenCode times out or fails, the bridge replies with a short failure message and logs the exception.
- The bridge only forwards text messages in this prototype.

## Agent Rule

Long-running experiments must go through:

```bash
./tools/run_with_feishu_notify.sh --name <experiment_name> -- <command>
```

Do not directly run `python train.py` or `bash train.sh` for long tasks, and do not bypass Feishu notification.
