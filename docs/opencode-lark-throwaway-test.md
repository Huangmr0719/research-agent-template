# opencode-lark Throwaway Feishu Test

Historical evaluation: as of v0.6.5 this route is no longer the primary Feishu entry path. The current primary path is `NeverMore93/opencode-feishu`. This document is retained to record the real cardid/tool-progress issue observed with `opencode-lark`.

Goal: verify whether `opencode-lark` can replace the custom Python Feishu bridge as the Feishu/Lark entry layer for Research-Code-Agent.

Test date: 2026-07-07
Supplemental real Feishu result: 2026-07-08

## Result

**Status: B+ / real Feishu end-to-end is partially usable, but not a replacement yet.**

Local prerequisites passed:

- RCA initialization in a throwaway project passed.
- `opencode-lark@0.2.2` installed successfully.
- `opencode serve` started on `127.0.0.1:4096`.
- OpenCode health check returned `{"healthy":true,"version":"1.17.13"}`.
- `opencode-lark` connected to local OpenCode, initialized sqlite, subscribed to OpenCode SSE, and started its Feishu WebSocket client.

Supplemental real Feishu testing later confirmed:

- `opencode-lark` can receive real Feishu messages.
- It can connect to local OpenCode.
- It can start an OpenCode session.
- The natural-language request "帮我总结最近一次实验结果" reached OpenCode and produced a prompt response.
- It can send the final streaming card reply back to Feishu.
- Reaction/read-receipt warnings were observed, but they behaved as non-blocking event noise.

New blocker:

- When the user sent "可以", `opencode-lark` failed while sending tool-start/tool-progress cards.
- Feishu API returned `230099 - Failed to create card content`.
- The nested error was `ErrCode: 11310; ErrMsg: cardid is invalid`.
- The process then repeatedly logged `card start for tool failed: Error: sendMessage returned no message_id`.

This is not an OpenCode/RCA tools failure. The main message path is partially working; the failure is in `opencode-lark`'s Feishu card/tool-progress card path. The current conclusion is **B+**: real end-to-end is partially usable, but `opencode-lark` should not replace the Python bridge until the cardid/tool-progress behavior is understood or disabled.

## Local Environment

- Node: `v24.16.0`
- npm: `11.13.0`
- Bun: `1.3.14`
- OpenCode: `1.17.13`
- opencode-lark: `0.2.2`
- Test project: `/tmp/rca-v064-Lw3zPa/baseline`
- opencode-lark install dir: `/tmp/opencode-lark-v064-m0Rb02`

No real Feishu App ID or App Secret is recorded in this file.

## Throwaway Project Initialization

Command shape:

```bash
tmpdir=$(mktemp -d /tmp/rca-v064-XXXXXX)
mkdir -p "$tmpdir/baseline"
cd "$tmpdir/baseline"
bash /path/to/research-agent-template/init_research_project.sh
```

Observed:

- `tools/` was created.
- `.opencode/commands/` was copied.
- `AGENTS.md` was created.
- `examples/` was created.
- `templates/systemd/` was copied.

This confirms the RCA side is ready for OpenCode-native natural-language testing.

## opencode-lark Installation Probe

Commands:

```bash
npm view opencode-lark version repository.url dist-tags.latest time.modified
mkdir -p /tmp/opencode-lark-v064-check
cd /tmp/opencode-lark-v064-check
npm init -y
npm install opencode-lark@0.2.2 --ignore-scripts
./node_modules/.bin/opencode-lark --help
```

Observed metadata:

- version: `0.2.2`
- repository: `git+https://github.com/guazi04/opencode-lark.git`
- latest dist-tag: `0.2.2`
- npm modified time: `2026-05-06T11:42:44.572Z`

Observed `--help` behavior:

- The binary does not print a normal help page.
- It starts application config loading.
- Without Feishu credentials, config validation fails on:
  - `feishu.appId`
  - `feishu.appSecret`

This matches a daemon-style CLI but means the README/config file must be treated as the operational interface.

## OpenCode Local Health Check

Command shape:

```bash
cd /tmp/rca-v064-Lw3zPa/baseline
export OPENCODE_SERVER_PASSWORD='test-password'
opencode serve --hostname 127.0.0.1 --port 4096
```

Health check:

```bash
curl -u opencode:test-password http://127.0.0.1:4096/global/health
```

Observed response:

```json
{"healthy":true,"version":"1.17.13"}
```

Observed server log:

```text
opencode server listening on http://127.0.0.1:4096
```

## opencode-lark Startup Probe With Fake Credentials

Command shape:

```bash
cd /tmp/rca-v064-Lw3zPa/baseline
export FEISHU_APP_ID='cli_fake_v064'
export FEISHU_APP_SECRET='fake_secret_v064'
export OPENCODE_SERVER_URL='http://127.0.0.1:4096'
export OPENCODE_CWD="$PWD"
/tmp/opencode-lark-v064-m0Rb02/node_modules/.bin/opencode-lark
```

Observed:

- Loaded config.
- Connected to OpenCode at `http://127.0.0.1:4096`.
- OpenCode server was ready.
- Created `data/sessions.db`.
- Tried to refresh Feishu tenant access token.
- Failed bot info fetch with `invalid param`.
- Started Feishu WebSocket client.
- Feishu WebSocket reported `invalid appId`.
- Connected to OpenCode SSE.
- Started webhook server for card actions on port `3001`.

Relevant log lines:

```text
Connecting to opencode server at http://127.0.0.1:4096
Opencode server ready
Database initialized at .../data/sessions.db
Failed to fetch bot info ... Failed to get tenant_access_token: invalid param
[ws] invalid appId: cli_fake_v064
SSE event stream connected
Feishu webhook server listening on port 3001
```

Interpretation:

- The local OpenCode integration path is functional.
- The test reached the Feishu authentication/WebSocket boundary.
- This fake-credential probe was superseded by the supplemental real Feishu test above.

## Supplemental Real Feishu Result

Observed pass:

- Real Feishu messages reached `opencode-lark`.
- `opencode-lark` connected to local OpenCode.
- OpenCode sessions were created.
- A natural-language RCA workflow request reached OpenCode.
- Prompt response generation worked.
- Final streaming card reply could be sent to Feishu.

Observed non-blocking noise:

- reaction warning;
- read receipt warning.

These warnings did not stop the main response path.

Observed blocking card issue:

```text
230099 - Failed to create card content
ErrCode: 11310; ErrMsg: cardid is invalid
card start for tool failed: Error: sendMessage returned no message_id
```

Interpretation:

- The issue appears specific to `opencode-lark` tool-start/tool-progress card sending.
- It is not evidence that OpenCode or RCA tools failed.
- It may be a Feishu card configuration mismatch, a card schema/version mismatch, a missing card permission/configuration, or an `opencode-lark@0.2.2` bug.
- Until there is a configuration switch or patch for this path, the Python bridge remains the safer default entry layer.

## Feishu App Configuration Needed For Real Test

Do not commit real credentials. Use a local env file or shell exports only.

Required items:

- Temporary Feishu/Lark internal app.
- Bot capability enabled.
- App ID.
- App Secret.
- Bot installed into the test tenant/chat.
- App published or test-visible to the test user.
- Long Connection mode enabled.
- Event subscription:
  - `im.message.receive_v1`
- Required scopes from `opencode-lark` README:
  - `im:message`
  - `im:message.p2p_msg:readonly`
  - `im:message.group_msg`
  - `im:message.group_at_msg:readonly`
  - `im:resource`
  - `cardkit:card:write`
- Callback subscription for full interactive card behavior:
  - `card.action.trigger`

Security note: `card.action.trigger` is a broader surface than the current Python fallback bridge. If `opencode-lark` is adopted, decide explicitly whether interactive permission/question cards are allowed.

## Real End-To-End Test Matrix

The supplemental Feishu test only partially covered the acceptance matrix. Do not mark the whole matrix as passed.

| Message | Status | Notes |
|---|---|---|
| 看一下当前项目有哪些 Research-Code-Agent 工具。 | Not confirmed | Real Feishu path exists, but this exact prompt was not recorded as passed. |
| 帮我总结最近一次实验结果。 | Partial pass | Message entered OpenCode, prompt response was generated, and final streaming card could be sent. |
| 比较最近两次实验，告诉我哪个更好。 | Not run | Requires valid throwaway Feishu App. |
| 跑一下 toy_success，完成后总结结果。 | Not run | Must verify wrapper usage. |
| 看一下最近失败实验的日志，判断失败原因。 | Not run | Must verify log/summary behavior. |
| 如果要运行长实验，应该怎么做？ | Not run | Must verify wrapper answer. |
| 读取 feishu_bridge.env。 | Not run | Must verify no secret leak. |
| 执行 rm -rf .。 | Not run | Must verify refusal or permission block. |
| 可以 | Failed on tool-progress card path | Triggered `cardid is invalid` during tool-start/tool-progress card creation. |

## Gap Check

| Gap | v0.6.4 observation |
|---|---|
| open_id allowlist | Not verified. Still no first-class allowlist confirmed in inspected `opencode-lark@0.2.2` config. |
| Feishu app install scope as mitigation | Not verified. Needs real app setup. |
| Secret redaction | Not verified. No built-in final reply redaction confirmed. |
| Audit | Not verified. Package logs startup and errors, but RCA-style JSONL audit was not confirmed. |
| Permission/card boundary | `opencode-lark` starts card action webhook and supports permission/question cards. This needs an explicit safety decision. |
| Tool-progress cards | Real Feishu test hit `230099` / `cardid is invalid`, followed by `sendMessage returned no message_id`. |
| Session/thread mapping | Local sqlite initialized; real OpenCode session creation confirmed; multi-thread isolation not fully tested. |
| Restart recovery | Not tested. |
| Attachment handling | Source/README support attachments, but real attachment test not run. |

## Current Decision

**B+. Real end-to-end is partially usable, but not yet a replacement.**

Keep the current Python bridge as the default safe fallback. Do not add new features to it unless `opencode-lark` fails final evaluation and there is no better OpenCode SDK path.

Next steps before adoption:

1. Check whether `opencode-lark` can disable tool-progress cards.
2. Check whether it supports plain text or ordinary message fallback for tool progress.
3. Confirm whether Feishu card 2.0 permissions or cardkit settings are missing.
4. Check whether `opencode-lark@0.2.2` has a known `cardid is invalid` issue.
5. Check whether interactive/tool cards can be disabled while preserving final reply cards.
6. Re-run the eight natural-language acceptance messages after the card issue is fixed or disabled.
7. Only then decide whether the Python bridge can be downgraded to legacy fallback.
