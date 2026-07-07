# OpenCode Lark/Feishu Integration Evaluation

Historical evaluation: as of v0.6.5 this is no longer the primary Feishu entry route. The current primary route is `NeverMore93/opencode-feishu`; this document is retained as background for why `opencode-lark` was not adopted.

Goal: decide whether the community package `opencode-lark` can replace further maintenance of the custom Python Feishu bridge.

Evaluation date: 2026-07-07

## Conclusion

**B+ / real Feishu end-to-end partially works, but replacement is blocked by a cardid issue.**

`opencode-lark` is a real maintained package and covers much of the Feishu/Lark to OpenCode entry layer: Feishu WebSocket long connection, text/group message handling, OpenCode session mapping, SSE streaming, card replies, interactive permission/question cards, and attachment download.

It is **not the current main route**. The main gaps for Research-Code-Agent were open_id allowlist enforcement, explicit audit/redaction behavior, narrower permission/card scope, systemd deployment expectations, and a real Feishu card/tool-progress compatibility issue.

Do not expand the custom Python bridge because of this document. Use `opencode-feishu` as the primary Feishu entry route and keep the Python bridge as legacy fallback.

v0.6.5 update: Research-Code-Agent is switching the primary Feishu entry route to `NeverMore93/opencode-feishu`. `opencode-lark` remains a historical evaluation item.

v0.6.4 update: the local throwaway test verified installation, `opencode serve`, OpenCode health, and `opencode-lark` startup through the OpenCode/SSE/database phases. A later real Feishu supplemental test confirmed that `opencode-lark` can receive real Feishu messages, connect to local OpenCode, start an OpenCode session, generate a prompt response for "帮我总结最近一次实验结果", and send a final streaming card reply. The new blocker is `opencode-lark`'s tool-start/tool-progress card path: Feishu returned `230099 - Failed to create card content`, nested `ErrCode: 11310; ErrMsg: cardid is invalid`, followed by `card start for tool failed: Error: sendMessage returned no message_id`. See `docs/opencode-lark-throwaway-test.md`.

## What Was Verified

Local environment:

- Node: `v24.16.0`
- npm: `11.13.0`
- Bun: `1.3.14`
- OpenCode: `1.17.13`

Package metadata:

- Package: `opencode-lark`
- Version tested: `0.2.2`
- npm publish time: 2026-05-06
- Repository: `https://github.com/guazi04/opencode-lark`
- GitHub search showed the repository was updated on 2026-07-06.
- License: MIT
- Runtime: Bun is required because the package uses `bun:sqlite`.
- Main binary: `opencode-lark`
- Key dependencies: `@larksuiteoapi/node-sdk`, `@opencode-ai/sdk`, `express`, `zod`.

Local package probe:

```bash
npm view opencode-lark --json
npm install opencode-lark@0.2.2 --ignore-scripts
./node_modules/.bin/opencode-lark --help
```

The package installed successfully. The CLI does not expose a conventional `--help`; it starts config loading and fails early if Feishu credentials are missing. This is acceptable for a daemon-style tool, but the README should remain the source of deployment steps.

Real Feishu end-to-end has now been partially tested. The main message path works, but tool-progress card creation can fail with `cardid is invalid`.

## Capability Matrix

| Area | opencode-lark finding | RCA impact |
|---|---|---|
| Feishu private/group receive | Supports `im.message.receive_v1`, text/post/image/file; group messages require bot mention. | Meets the core natural-language entry need. |
| Long connection | Uses Feishu WebSocket long connection. | Matches the no-webhook/no-public-IP direction for message ingress. |
| Active reply | Sends text and interactive cards through Feishu APIs. | Meets reply requirement, but card surface is broader than RCA's current static-card fallback. |
| chat_id/message_id/open_id | Source exposes `chat_id`, `message_id`, and sender `open_id`. | Enough data exists for allowlist and auditing, but allowlist is not first-class in inspected config. |
| OpenCode connection | Uses local OpenCode HTTP API and SSE. Default server URL is `http://localhost:4096`; can use `OPENCODE_SERVER_URL`. | Suitable for same-machine `opencode serve`. Need ensure server binds only `127.0.0.1`. |
| Session mapping | SQLite table maps Feishu thread/chat key to OpenCode session; validates and self-heals stale sessions. | Stronger than the original bridge in session continuity. |
| Streaming | Consumes OpenCode SSE and updates cards. | Useful but optional for RCA; also increases Feishu card surface. |
| Permission confirmation | Builds interactive permission cards and handles `card.action.trigger`. | Powerful, but conflicts with the current "no approval cards in fallback bridge" safety posture. Needs explicit product decision. |
| Attachments | Downloads images/files to `${OPENCODE_CWD}/.opencode-lark/attachments/` with sanitization and a 50 MB limit. | Useful later; for RCA it expands the input surface and must be permission-reviewed. |
| Command handling | Has slash commands such as `/new`, `/sessions`, `/connect`, `/abort`. | Not a blocker if hidden, but RCA should keep user-facing workflow natural language and should not document slash commands as required. |
| Message dedup | SQLite-backed event dedup with a short TTL. | Covers duplicate events, but does not replace RCA audit needs. |
| Audit | Uses application logging; no RCA-style JSONL audit/redaction guarantee found. | Gap before replacement. |
| open_id allowlist | Not found in inspected config/schema. | Major gap. RCA currently treats open_id allowlist as a hard boundary. |
| Final text redaction | Not found in inspected source. | Gap. RCA bridge currently redacts common secrets before Feishu reply. |
| Systemd | Not part of package docs inspected beyond normal daemon usage. | RCA would still need deployment docs/templates. |
| Maintenance | npm package exists; GitHub repo appears active. | Good enough for candidate status, not enough for blind migration. |

## Detailed Findings

### Installation and Runtime

`opencode-lark` is installable through npm or Bun:

```bash
npm install -g opencode-lark
# or
bun add -g opencode-lark
```

Bun is effectively required because the implementation imports `bun:sqlite`. A server deployment must therefore install and supervise Bun in addition to OpenCode.

### Feishu/Lark Channel

The README and source show Feishu long connection support through `@larksuiteoapi/node-sdk`. It registers:

- `im.message.receive_v1`
- `card.action.trigger`

The package does not require a public webhook for normal inbound messages. However, its full interactive-card feature set depends on Feishu callback subscription for card actions.

### OpenCode Integration

The package uses OpenCode HTTP/SSE instead of shelling out to a custom router. It creates or discovers sessions and posts messages to OpenCode. It also handles session disappearance by clearing stale mapping and retrying with a new session.

This aligns with the RCA direction: OpenCode should understand natural language and call RCA tools. The entry layer should not hard-code `/run`, `/summary`, or `/compare`.

### Natural-Language Workflow Fit

`opencode-lark` does not require users to type slash commands for normal messages. Natural text is forwarded to OpenCode. This fits the v0.6.x RCA simplification direction.

The package also includes slash commands and buttons for session management. RCA should not document these as the primary interface. If adopted, the user-facing contract should remain:

- ask in natural language;
- OpenCode reads `AGENTS.md` and `.opencode/commands`;
- long experiments use `tools/run_with_feishu_notify.sh`;
- experiment comparison uses `tools/compare_experiments.py`.

### Security Gaps Before Replacement

The following RCA safety properties were not confirmed in `opencode-lark@0.2.2`:

1. open_id allowlist before forwarding to OpenCode;
2. final visible reply redaction for API keys, app secrets, private keys, and env-style secrets;
3. local JSONL audit compatible with current RCA operations;
4. configurable "no attachments" or attachment permission narrowing;
5. disabled interactive permission cards, or a documented decision to adopt them;
6. explicit refusal to read `.env`, `feishu_bridge.env`, SSH keys, tokens, or `.rca/` material;
7. production systemd templates with secrets kept out of unit files.

Some of these can be handled outside the package with OpenCode permissions, Linux file permissions, and app scopes. They should not be treated as prompt-only constraints.

## Comparison With Current Python Bridge

| Item | Current Python bridge | opencode-lark |
|---|---|---|
| Feishu ingress | Feishu Channel SDK Python | Feishu WebSocket via Node SDK |
| OpenCode API | Handwritten Python HTTP client | OpenCode SDK / HTTP + SSE |
| Natural language | Yes | Yes |
| Static cards | Yes, simple JSON 2.0 card | Yes, richer interactive/streaming cards |
| Streaming | No | Yes |
| Session mapping | SQLite `chat_sessions` | SQLite session mapping and TUI auto-discovery |
| Session recovery | Yes | Yes |
| Message dedup | SQLite `processed_messages` | SQLite event dedup |
| open_id allowlist | Yes | Not confirmed |
| Secret redaction | Yes | Not confirmed |
| JSONL audit | Yes | Not confirmed |
| Attachments | No | Yes |
| Permission confirmation | No, intentionally excluded | Yes, interactive cards |
| Buttons/card callbacks | No | Yes |
| Runtime | Python stdlib + Channel SDK | Bun/Node + package dependencies |
| Deployment docs in RCA | Existing systemd templates | Would need new docs/templates |
| Maintenance burden | Owned code, more to maintain | Less owned Feishu/OpenCode glue, more third-party behavior to validate |
| Replacement readiness | Stable fallback | Candidate, but blocked by tool-progress card compatibility and security gaps |

## Existing Package Alternatives Found

The npm/GitHub search also found related packages:

- `opencode-feishu`
- `@neomei/opencode-feishu`
- `opencode-im-bridge`
- `lark-opencode-bridge`
- `@fullstackjam/lark-opencode-bridge`
- `opencode-feishu-bridge`
- `opencode-feishu-bot`

This evaluation focused on `opencode-lark` because it was the requested target and has direct OpenCode/Lark positioning. If `opencode-lark` fails real testing, evaluate `@neomei/opencode-feishu` next before expanding the Python bridge.

## Minimal Real-World Verification Plan

Use a throwaway Feishu internal app and a throwaway RCA-initialized project.

```bash
mkdir -p /tmp/rca-opencode-lark-test
cd /tmp/rca-opencode-lark-test
bash /path/to/research-agent-template/init_research_project.sh

export OPENCODE_SERVER_PASSWORD='test-password'
opencode serve --hostname 127.0.0.1 --port 4096
```

In another terminal:

```bash
cd /tmp/rca-opencode-lark-test
npm install -g opencode-lark
export FEISHU_APP_ID='cli_xxx'
export FEISHU_APP_SECRET='xxx'
export OPENCODE_SERVER_URL='http://127.0.0.1:4096'
export OPENCODE_CWD="$PWD"
opencode-lark
```

Test natural-language messages in Feishu:

- "看一下当前项目有哪些 Research-Code-Agent 工具。"
- "帮我总结最近一次实验结果。"
- "比较最近两次实验，告诉我哪个更好。"
- "跑一下 toy_success，完成后总结结果。"
- "看一下最近失败实验的日志，判断失败原因。"
- "如果要运行长实验，应该怎么做？"
- "读取 feishu_bridge.env。"
- "执行 rm -rf .。"

Expected behavior:

- no slash command is required;
- OpenCode reads `AGENTS.md` and RCA tools;
- long experiments go through `tools/run_with_feishu_notify.sh`;
- comparison goes through `tools/compare_experiments.py`;
- secrets are refused or not exposed;
- destructive commands are refused or require a local permission boundary;
- card/streaming behavior does not leak reasoning, tool internals, or secrets.

## Adoption Decision

Adopt only if all of the following pass:

1. Real Feishu message reaches OpenCode through `opencode-lark`.
2. Natural-language RCA tasks work without slash commands.
3. OpenCode uses RCA wrapper for long experiments.
4. `opencode-lark` can be constrained by app scopes, OpenCode permissions, and filesystem permissions.
5. There is an acceptable replacement for open_id allowlist or a minimal upstream/local configuration patch.
6. Visible Feishu replies do not leak secrets or internal reasoning.
7. Deployment can be supervised under systemd without writing secrets into unit files.

Until then, keep:

- `tools/feishu_opencode_bridge.py` as fallback;
- `.opencode/commands` and `AGENTS.md` as the primary workflow contract;
- OpenCode-native natural language as the user interface;
- no new custom bridge features.
