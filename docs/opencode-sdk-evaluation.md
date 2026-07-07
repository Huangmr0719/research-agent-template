# OpenCode SDK Evaluation

Fallback option: as of v0.6.5 this is not the primary Feishu route. The current primary route is `NeverMore93/opencode-feishu`; SDK work is only a backup if the plugin route fails and the legacy Python bridge is not sufficient.

The SDK is a backup simplification path. It is not the first priority.

## Questions

1. **Connect to existing server**: SDK documentation should be checked against the installed OpenCode version.
2. **Automatically start server**: JS/TS SDK documentation references programmatic OpenCode usage; verify whether `createOpencode` can reduce service management.
3. **Simpler mode**: if a Feishu integration is Node/Bun-based, JS/TS SDK may be simpler than Python HTTP.
4. **Reduce systemd services**: possible only if the SDK can own server lifecycle reliably; otherwise keep `opencode-serve.service`.
5. **Replace current Python `OpenCodeClient`**: useful only if a Python SDK exists or a Node bridge replaces Python.
6. **Health support**: must support `/global/health` equivalent.
7. **Session create**: must support `POST /session` equivalent.
8. **Prompt/message**: must support `POST /session/{id}/message` equivalent.
9. **Abort**: must support aborting a session task.
10. **Messages**: must support reading recent messages.
11. **Structured output**: nice to have, not required for bridge transport.
12. **Event subscribe**: useful for future, not required now.
13. **Python SDK**: not confirmed in this pass.
14. **If Python bridge remains**: prefer a Python SDK only if official, maintained, and smaller than the current HTTP client.
15. **If JS/TS bridge is adopted**: evaluate `createOpencode` and server lifecycle once, but do not rewrite prematurely.

## Recommendation

Use SDK only as a backup simplification path:

1. Evaluate existing Feishu/Lark integration first.
2. If unavailable, check official SDK coverage.
3. Replace handwritten HTTP only if it clearly reduces code and deployment risk.
4. Do not add command routing either way.

References:
- OpenCode SDK docs: https://opencode.ai/docs/sdk/
- OpenCode server docs: https://opencode.ai/docs/
