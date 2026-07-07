# OpenCode-Native Simplification

v0.6.5 update: the current primary Feishu entry route is `NeverMore93/opencode-feishu`. The custom Python bridge is legacy fallback, `opencode-lark` is historical evaluation, and OpenCode SDK work is a backup option.

v0.6.1 changes the strategy: stop expanding the Python bridge unless there is a clear deployment bug. Prefer OpenCode-native instructions, permissions, commands, agents, tools, and existing integrations.

## Direct Answers

1. **OpenCode native can do**: follow `AGENTS.md` instructions, use project files, run approved tools, use configured agents/subagents, use slash-command templates, enforce permission rules, connect MCP/custom tools, and expose a local server/SDK surface.
2. **Move to OpenCode native**: intent understanding, choosing between experiment run/summary/compare/log analysis, deciding when to use pty, and following project workflow rules.
3. **Keep in RCA tools**: `run_with_feishu_notify.sh`, Feishu experiment notifications, `summarize_experiment.py`, `compare_experiments.py`, `project_results_adapter.py`, paper context helpers, and bridge fallback.
4. **Do not keep adding to bridge**: command parsing, `/run`/`/summary`/`/compare` routers, pty orchestration, experiment status semantics, card callbacks, approval UI, and business workflow decisions.
5. **Natural-language usage**: users should say “看最近实验”, “比较最近两次”, “跑一下 toy_success”, or “分析失败原因”. OpenCode should map that to RCA tools.
6. **`.opencode/commands` role**: command files are OpenCode action templates. They are not commands the Feishu user must memorize.
7. **Python bridge role**: legacy fallback transport from Feishu Channel SDK to local OpenCode, with whitelist, dedupe, session mapping, card reply, redaction, audit, and healthcheck.
8. **Existing package priority**: yes, evaluate `opencode-lark` or similar Feishu/Lark integrations before adding more bridge code.
9. **If existing package works**: stop extending the Python bridge, keep it as fallback, and move new capabilities into OpenCode config/instructions/tools.
10. **If existing package does not work**: only then consider replacing the handwritten OpenCode HTTP client with an official SDK.

## Native OpenCode Areas To Use First

- `AGENTS.md`: project behavior, safety, and workflow instructions.
- Agents/subagents: specialized research, debugging, experiment, or review roles if needed.
- Commands: reusable action templates under `.opencode/commands/`.
- `opencode.json`: permissions and runtime configuration.
- Permissions: the real safety boundary, together with Linux user/file permissions.
- Tools/MCP/plugins: use existing OpenCode extension points before writing bridge code.
- SDK/server: only for transport integration if native packages are unavailable.

References:
- OpenCode docs: https://opencode.ai/docs/
- Agents: https://opencode.ai/docs/agents/
- Commands: https://opencode.ai/docs/commands/
- Permissions: https://opencode.ai/docs/permissions/
- Config: https://opencode.ai/docs/config/
- SDK: https://opencode.ai/docs/sdk/
- Tools: https://opencode.ai/docs/tools/

## Natural-Language Examples

- “看最近实验”: inspect `experiments/summaries/`, then logs only if needed.
- “比较 toy_success 和 toy_failed”: call `tools/compare_experiments.py` if summaries exist.
- “跑一个 toy_success”: use `tools/run_with_feishu_notify.sh`; if pty is available, run it in a controlled background session.
- “分析失败原因”: read the summary and tail of the relevant project log, avoiding env/secrets.

## Bridge Simplification Rule

The bridge should only transport messages and protect the transport boundary. It should not become the research workflow engine. The workflow belongs to OpenCode plus RCA tools.
