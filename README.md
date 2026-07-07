# Research-Code-Agent

面向科研代码项目的轻量级 Agent 辅助实验工具。

当前能力：

- experiment wrapper（带状态捕获）
- Feishu notification（卡片/文本）
- log capture
- summary.json / summary.md
- summary-based experiment comparison
- minimal paper context workflow
- opencode-feishu primary Feishu entry workflow
- legacy Python Feishu-OpenCode Bridge fallback
- on-demand OpenCode analysis
- project_results_adapter（项目级 metrics 适配）
- toy success / failed / interrupted tests
- Feishu smoke test

技术栈：bash + Python 标准库。核心实验工具无外部依赖；当前推荐飞书入口是 `NeverMore93/opencode-feishu` OpenCode plugin。自研 Python Feishu bridge 仅作为 legacy fallback，可能需要 Feishu Channel SDK Python（`lark-channel-sdk`）。不存储 Feishu 凭证。

当前 RCA 不做：gateway、MCP、Hermes、botmux、Vercel Chat SDK、飞书 CLI、webhook、内网穿透、多平台抽象、Python command router。

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
  opencode-feishu.plugin.example.json
  feishu.plugin.example.json
  systemd/
    opencode-serve.service
    rca-feishu-opencode-bridge.service
docs/
  opencode-feishu-adoption.md
  opencode-feishu-throwaway-test.md
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

## Primary Feishu Entry: opencode-feishu

v0.6.5 switches the primary Feishu remote entry route to `NeverMore93/opencode-feishu`:

```text
Feishu
  -> opencode-feishu OpenCode plugin
  -> OpenCode natural-language workflow
  -> Research-Code-Agent tools
  -> Feishu CardKit reply
```

This route keeps the product boundary simple:

- Feishu users speak natural language.
- Users do not need to remember `/summary`, `/compare`, `/run`, or RCA command names.
- OpenCode decides which RCA tool to use.
- `.opencode/commands/` files are action templates for OpenCode, not user-facing commands.
- Long experiments must still use `tools/run_with_feishu_notify.sh`.
- Experiment summaries, comparison, and log analysis remain provided by RCA tools.

Templates:

- `templates/opencode-feishu.plugin.example.json` for `~/.config/opencode/opencode.json`
- `templates/feishu.plugin.example.json` for `~/.config/opencode/plugins/feishu.json`

See:

- `docs/opencode-feishu-adoption.md`
- `docs/opencode-feishu-throwaway-test.md`

`opencode-lark` is now a historical evaluation item, not the current main route. OpenCode SDK evaluation is a backup option, not the current main route.

## Legacy Python Feishu-OpenCode Bridge Fallback

v0.5.0 added an optional thin bridge for remote OpenCode access from Feishu. As of v0.6.5, this is a legacy fallback route:

```text
Feishu Channel SDK Python
  -> open_id whitelist
  -> sqlite message_id dedupe
  -> per-chat lock
  -> immediate "收到，处理中。"
  -> local OpenCode server at 127.0.0.1:4096
  -> static Feishu card replies, with markdown fallback
```

v0.6.0 keeps the bridge thin and adds stable deployment support plus `opencode-pty` guidance for background session management. The intended long-task path is:

```text
Feishu
  -> bridge
  -> OpenCode
  -> opencode-pty
  -> tools/run_with_feishu_notify.sh / RCA tools
  -> OpenCode summary
  -> Feishu static card
```

The legacy bridge does not implement `/status`, `/summary`, `/run`, or any Python command router. It does not use Vercel Chat SDK, `@larksuite/vercel-chat-adapter`, Feishu CLI, DingTalk MCP, webhook, public ports, tunneling, streaming progress, approval cards, MCP, Hermes, botmux, or multi-platform routing. Feishu is the only remote entrypoint. OpenCode is responsible for understanding and executing the user request.

Long-running experiments must still be launched through:

```bash
./tools/run_with_feishu_notify.sh --name <experiment_name> -- <command>
```

### OpenCode-Native Simplification Strategy

v0.6.5 stops treating the self-written bridge, `opencode-lark`, or OpenCode SDK as the main product direction. The preferred strategy is:

1. Users keep speaking natural language in Feishu.
2. Users do not need to remember `/summary`, `/compare`, `/run`, or other command syntax.
3. OpenCode should understand the task and choose the right RCA tool.
4. RCA tools remain the stable experiment toolbox.
5. `AGENTS.md`, `.opencode/commands/`, `opencode.json`, and permissions define OpenCode behavior.
6. Use `NeverMore93/opencode-feishu` as the primary Feishu entry.
7. Keep the Python bridge as a legacy fallback transport.
8. Treat `opencode-lark` as historical evaluation and OpenCode SDK as a backup option.

The `.opencode/commands/` files are OpenCode action templates. They are not user-facing commands. A Feishu user can still say “看最近实验”, “比较最近两次”, “跑一下 toy_success”, or “分析失败原因”.

See:

- `docs/opencode-native-simplification.md`
- `docs/opencode-native-smoke-test.md`
- `docs/opencode-feishu-adoption.md`
- `docs/opencode-feishu-throwaway-test.md`
- `docs/opencode-lark-evaluation.md`
- `docs/opencode-lark-throwaway-test.md`
- `docs/opencode-sdk-evaluation.md`

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
BRIDGE_DB_PATH=/path/to/baseline-project/.rca/feishu_bridge.sqlite3
BRIDGE_LOG_PATH=/path/to/baseline-project/.rca/feishu_bridge_audit.jsonl
BRIDGE_TIMEOUT_SECONDS=600
BRIDGE_REPLY_FORMAT=card
BRIDGE_HEALTHCHECK_ENABLED=true
BRIDGE_HEALTHCHECK_INTERVAL_SECONDS=300
BRIDGE_HEALTHCHECK_FAILURE_THRESHOLD=3
BRIDGE_ADMIN_CHAT_ID=
BRIDGE_AUDIT_MAX_BYTES=10485760
BRIDGE_AUDIT_BACKUP_COUNT=5
BRIDGE_PROCESSED_MESSAGE_RETENTION_DAYS=7
```

The copied env file is private configuration and must not be committed.

Install Feishu Channel SDK Python in the runtime environment used by systemd:

```bash
python3 -m pip install --user lark-channel-sdk
```

### Foreground Deployment Check

Run the first server test in foreground before installing systemd:

```bash
git clone https://github.com/Huangmr0719/Research-Code-Agent.git
cd /path/to/baseline-project
bash /path/to/Research-Code-Agent/init_research_project.sh
cp templates/feishu_bridge.env.example feishu_bridge.env
chmod 600 feishu_bridge.env
mkdir -p .rca
chmod 700 .rca
```

Edit `feishu_bridge.env`, rotate the Feishu App Secret if it was used during local testing, then start OpenCode in terminal 1:

```bash
set -a
. ./feishu_bridge.env
set +a
opencode serve --hostname 127.0.0.1 --port 4096
```

Start the bridge in terminal 2:

```bash
python3 tools/feishu_opencode_bridge.py --env feishu_bridge.env
```

In Feishu, send a simple project question and confirm:

- the bot immediately replies `收到，处理中。`;
- the final reply is a static card by default;
- setting `BRIDGE_REPLY_FORMAT=markdown` falls back to markdown/text;
- OpenCode can see and use `opencode-pty` if installed;
- long experiments are launched through `tools/run_with_feishu_notify.sh`.

### Permission Boundary

The bridge prompt is only a behavior hint, not a security boundary. Real restrictions must come from:

- `opencode.json` permission rules;
- the Unix user running the systemd services;
- filesystem ownership and write permissions;
- keeping `opencode serve` bound to `127.0.0.1`.

Use a restricted service user if the server is shared. Do not give OpenCode write access to datasets, checkpoints, private credentials, or unrelated projects unless needed.

Recommended local file permissions:

```bash
chmod 600 feishu_bridge.env
chmod 700 .rca
chmod 600 .rca/feishu_bridge.sqlite3
chmod 600 .rca/feishu_bridge_audit.jsonl
```

If sqlite or audit files do not exist yet, run the bridge once and then apply the file `chmod` commands. `feishu_bridge.env`, `.rca/`, and audit logs are ignored by Git. Audit is local troubleshooting material only; it is not returned to Feishu.

`templates/opencode.remote.example.json` contains a lightweight permission-policy example for the remote Feishu entry. Treat it as a checklist and adapt it to your installed OpenCode version. It should express these boundaries:

- Allow reading project docs, `AGENTS.md`, `PAPER_CONTEXT.md`, logs, and `experiments/summaries/`.
- Allow Research-Code-Agent tools for summary, comparison, and notification workflows.
- Allow long experiments only through `tools/run_with_feishu_notify.sh`.
- Allow `opencode-pty` to start, read, and abort controlled background sessions inside the project.
- Deny or require confirmation for `feishu_bridge.env`, `.env`, secrets, SSH keys, token files, destructive file operations, uploads, `git push`, naked long training commands, and pty access outside the project.

`opencode-pty` is a background session manager, not a permission bypass. It must obey OpenCode permissions and Linux filesystem access.

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

### Healthcheck, Audit, and Retention

The bridge can periodically call OpenCode `GET /global/health`:

```bash
BRIDGE_HEALTHCHECK_ENABLED=true
BRIDGE_HEALTHCHECK_INTERVAL_SECONDS=300
BRIDGE_HEALTHCHECK_FAILURE_THRESHOLD=3
BRIDGE_ADMIN_CHAT_ID=oc_xxx
```

After consecutive failures reach the threshold, the bridge writes audit events and, if `BRIDGE_ADMIN_CHAT_ID` is set, sends a Feishu alert. Without an admin chat, it only writes audit. Healthcheck runs in the background and does not block normal message handling. Recovery is written to audit.

Audit rotation is built in:

```bash
BRIDGE_AUDIT_MAX_BYTES=10485760
BRIDGE_AUDIT_BACKUP_COUNT=5
```

When the audit file exceeds the size limit, it is rotated locally without external `logrotate`. Rotation failures are printed to stderr and do not stop bridge message handling.

Message dedupe rows are cleaned on bridge startup:

```bash
BRIDGE_PROCESSED_MESSAGE_RETENTION_DAYS=7
```

This only cleans old `processed_messages`; `chat_sessions` is retained so Feishu chats can continue using their OpenCode sessions.

### opencode-pty

`opencode-pty` is optional background session management for OpenCode. It does not replace `tools/run_with_feishu_notify.sh` and does not change the bridge into a router.

Use it this way:

1. Confirm `opencode-pty` is available to the OpenCode runtime.
2. Ask OpenCode from Feishu to start a controlled background session.
3. Inside the session, run a wrapped command such as:

```bash
./tools/run_with_feishu_notify.sh --name toy_success -- bash examples/toy_success.sh
```

4. Ask OpenCode to read the pty session output buffer and generated summary.
5. Ask OpenCode to abort the controlled pty session if needed.

Avoid these patterns:

- bridge parsing the Feishu message and directly calling `opencode-pty`;
- pty sessions running naked long commands instead of `tools/run_with_feishu_notify.sh`;
- pty sessions executing arbitrary user-provided shell;
- pty reading non-project directories or sensitive files.

### systemd Deployment

Copy the service templates and edit paths:

```bash
sudo cp templates/systemd/opencode-serve.service /etc/systemd/system/opencode-serve.service
sudo cp templates/systemd/rca-feishu-opencode-bridge.service /etc/systemd/system/rca-feishu-opencode-bridge.service
sudo $EDITOR /etc/systemd/system/opencode-serve.service
sudo $EDITOR /etc/systemd/system/rca-feishu-opencode-bridge.service
```

Replace `/opt/baseline-project` and `/etc/research-code-agent/feishu-bridge.env` with your actual server paths. Do not put secrets directly in service files.

Then enable both services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable opencode-serve.service
sudo systemctl enable rca-feishu-opencode-bridge.service
sudo systemctl start opencode-serve.service
sudo systemctl start rca-feishu-opencode-bridge.service
sudo systemctl status opencode-serve.service
sudo systemctl status rca-feishu-opencode-bridge.service
sudo systemctl restart rca-feishu-opencode-bridge.service
```

Check logs:

```bash
journalctl -u opencode-serve.service -f
journalctl -u rca-feishu-opencode-bridge.service -f
tail -f .rca/feishu_bridge_audit.jsonl
curl -u opencode:$OPENCODE_SERVER_PASSWORD http://127.0.0.1:4096/global/health
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

### Troubleshooting

- Feishu has no reply: check app WebSocket/event subscription, bot permissions, `RCA_FEISHU_ALLOWED_OPEN_IDS`, and `journalctl -u rca-feishu-opencode-bridge.service -f`.
- Card sending fails: set `BRIDGE_REPLY_FORMAT=markdown`, restart the bridge, and check audit for `card_send_failed`.
- OpenCode healthcheck failed: run `systemctl status opencode-serve.service` and `curl -u opencode:$OPENCODE_SERVER_PASSWORD http://127.0.0.1:4096/global/health`.
- `session_recreated` appears: OpenCode was likely restarted and the bridge created a fresh session for that chat.
- `open_id` not in whitelist: add the user's Feishu `open_id` to `RCA_FEISHU_ALLOWED_OPEN_IDS` and restart the bridge.
- Env permission errors: use `chmod 600 feishu_bridge.env`, `chmod 700 .rca`, then restart.
- systemd cannot find Python or OpenCode: edit `ExecStart` to an absolute path from `which python3` or `which opencode`.
- `lark_channel` is missing: install `lark-channel-sdk` in the same Python environment used by systemd.
- `opencode-pty` is unavailable: install or expose it to OpenCode, then ask OpenCode to confirm tool availability.
- pty session start failed: check OpenCode permission rules and service-user filesystem permissions.
- Long task lacks wrapper logs/summary: rerun it through `tools/run_with_feishu_notify.sh`.
- Markdown fallback test: set `BRIDGE_REPLY_FORMAT=markdown` and restart `rca-feishu-opencode-bridge.service`.

## Agent Rule

Long-running experiments must go through:

```bash
./tools/run_with_feishu_notify.sh --name <experiment_name> -- <command>
```

Do not directly run `python train.py` or `bash train.sh` for long tasks, and do not bypass Feishu notification.
