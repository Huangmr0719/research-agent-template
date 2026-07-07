# opencode-feishu Adoption

Status: v0.6.5 primary Feishu entry route.

Research-Code-Agent now recommends `NeverMore93/opencode-feishu` as the primary Feishu/Lark entry layer. The self-written Python Feishu bridge remains in this repository as a legacy fallback, but it should not keep growing into a product surface.

## Why opencode-feishu

`opencode-feishu` runs as an OpenCode plugin, not as a separate Python command router. This fits the current RCA direction:

- Feishu messages enter OpenCode directly through an existing plugin.
- OpenCode handles natural-language intent.
- RCA tools remain the experiment toolbox.
- `.opencode/commands` remain action templates for OpenCode, not user-facing commands.
- Long experiments still go through `tools/run_with_feishu_notify.sh`.

Compared with the evaluated `opencode-lark` service route, `opencode-feishu` is closer to the OpenCode-native model because it is loaded by OpenCode itself and does not require a separate `opencode serve` bridge process as the primary path.

## What It Replaces

It replaces the primary Feishu entry role of the custom Python bridge:

```text
Feishu
  -> opencode-feishu OpenCode plugin
  -> OpenCode natural-language workflow
  -> Research-Code-Agent tools
  -> Feishu CardKit reply
```

The Python bridge remains available as a fallback:

```text
Feishu
  -> tools/feishu_opencode_bridge.py
  -> opencode serve
  -> Research-Code-Agent tools
  -> Feishu card/markdown fallback
```

## What It Does Not Replace

`opencode-feishu` does not replace:

- `tools/run_with_feishu_notify.sh`;
- `tools/summarize_experiment.py`;
- `tools/compare_experiments.py`;
- `tools/project_results_adapter.py`;
- `AGENTS.md`;
- `.opencode/commands/`;
- paper context files;
- local permission boundaries and OpenCode permissions.

## Install

Install the plugin where OpenCode can load it:

```bash
npm install -g opencode-feishu
```

If package resolution is unreliable, clone the plugin and use an absolute path in OpenCode config. Do not vendor `node_modules` into this repository.

## OpenCode Plugin Config

Copy the template:

```bash
mkdir -p ~/.config/opencode
cp templates/opencode-feishu.plugin.example.json ~/.config/opencode/opencode.json
```

Example:

```json
{
  "plugin": ["opencode-feishu"]
}
```

This repository does not automatically write `~/.config/opencode/opencode.json`.

## Feishu Plugin Config

Copy the template:

```bash
mkdir -p ~/.config/opencode/plugins
cp templates/feishu.plugin.example.json ~/.config/opencode/plugins/feishu.json
chmod 600 ~/.config/opencode/plugins/feishu.json
```

Example:

```json
{
  "appId": "${FEISHU_APP_ID}",
  "appSecret": "${FEISHU_APP_SECRET}",
  "directory": "${RCA_PROJECT_DIR}",
  "maxHistoryMessages": 0,
  "maxResourceSize": 52428800,
  "dedupTtl": 600000,
  "nudge": {
    "enabled": false
  }
}
```

Keep real App ID and App Secret in local environment variables or a protected local config file. Do not commit `feishu.json`.

The template uses `maxHistoryMessages: 0` to express the safest default: do not import group history while validating the entry route. If your installed `opencode-feishu` version rejects `0` during config validation, set it to `1` and avoid enabling bot-added history ingestion until the behavior is confirmed in a throwaway chat.

## Feishu Open Platform

Create a self-built Feishu app and configure:

- bot capability enabled;
- long connection event subscription, not webhook;
- `im.message.receive_v1`;
- `im.chat.member.bot.added_v1` only if history ingestion is intentionally enabled;
- message send/receive scopes required by `opencode-feishu`;
- `cardkit:card:write`;
- `card.action.trigger` if interactive permission/question cards are enabled.

Keep the app limited to the test tenant/chat while validating.

## Throwaway Test Flow

Use a throwaway RCA-initialized project:

```bash
mkdir -p /tmp/rca-opencode-feishu-test
cd /tmp/rca-opencode-feishu-test
bash /path/to/research-agent-template/init_research_project.sh
export RCA_PROJECT_DIR="$PWD"
export FEISHU_APP_ID="..."
export FEISHU_APP_SECRET="..."
opencode
```

Then test from Feishu using natural language. Do not require `/summary`, `/compare`, or `/run`.

## Safety Checklist

Before treating `opencode-feishu` as production entry:

1. Confirm whether Langfuse tracing is enabled by environment, and keep it disabled unless explicitly needed.
2. Set `maxHistoryMessages` to `0` during initial testing.
3. Keep `maxResourceSize` conservative, such as `52428800`.
4. Confirm whether group silent listening is acceptable; group non-mention content is context, not a current instruction.
5. Confirm `card.action.trigger` validates the click operator and does not allow arbitrary command injection.
6. Review the `feishu_send_card` tool and avoid dangerous interactive cards.
7. Check whether open_id/chat allowlist is supported; if not, rely on Feishu app install scope, OpenCode permissions, and filesystem permissions.
8. Confirm local logs are sufficient for audit needs.
9. Confirm `feishu.json`, `.env`, SSH keys, tokens, and bridge env files are not readable by routine OpenCode tasks.
10. Keep App ID/App Secret in protected local config or env only.

Prompt instructions are not a security boundary. Use OpenCode permissions, Feishu app scope, and filesystem permissions.

## Fallback

If `opencode-feishu` fails a real deployment or its safety boundary is not acceptable, use the existing Python bridge as a legacy fallback:

- `tools/feishu_opencode_bridge.py`
- `templates/feishu_bridge.env.example`
- `templates/systemd/opencode-serve.service`
- `templates/systemd/rca-feishu-opencode-bridge.service`

The fallback bridge should stay thin and should not gain command router behavior.
