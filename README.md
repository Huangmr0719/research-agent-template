# Research-Code-Agent

Research-Code-Agent is an OpenCode Skill for research experiment workflows.

Research-Code-Agent 是面向 OpenCode 的科研实验工作流 Skill。它让 OpenCode 在科研代码项目中安全地计划、运行、记录、总结和诊断实验。

RCA 第一版默认服务于“飞书自然语言入口 + OpenCode 执行科研项目”的场景，但 RCA 本身不做飞书接入。Feishu、opencode-feishu、botmux、systemd、tmux 都是外部入口或运行设施；RCA 从 OpenCode 已经进入项目目录之后开始工作。

## What RCA Is

RCA is:

- OpenCode global Skill: `skills/rca/SKILL.md`
- RCA CLI: `bin/rca`
- project-local context: `RCA.md`
- project-local workspace: `.rca/`
- structured profile: `.rca/profile.json`
- experiment ledger: `.rca/experiments.json`
- standard run wrapper: `.rca/scripts/run_experiment.sh`
- consistency check: `rca check`

RCA is not:

- Feishu bridge
- MCP Server
- OpenCode Plugin
- botmux integration
- multi-CLI platform
- dashboard
- complex MLOps system
- Python command router
- agent runtime

Legacy optional tools remain under `tools/` for compatibility, but the current core workflow is Skill + `.rca/`.

## Install Once

Keep this repository somewhere stable:

```bash
~/Research-Code-Agent
```

Make scripts executable:

```bash
chmod +x ~/Research-Code-Agent/bin/rca
chmod +x ~/Research-Code-Agent/templates/rca/run_experiment.sh
chmod +x ~/Research-Code-Agent/init_research_project.sh
chmod +x ~/Research-Code-Agent/tools/*.sh
chmod +x ~/Research-Code-Agent/tools/*.py
```

Add `bin/` to `PATH`:

```bash
export PATH="$HOME/Research-Code-Agent/bin:$PATH"
```

Install the OpenCode Skill by copying or symlinking `skills/rca/SKILL.md` into your OpenCode global skills directory according to your local OpenCode setup.

This repository does not modify your home directory automatically.

## Recommended Workflow

```text
existing research code project
  -> OpenCode init / OpenCode reads the project
  -> rca init
  -> OpenCode uses the RCA Skill
  -> OpenCode reads README, train/eval scripts, configs, data flow, outputs, paper materials
  -> OpenCode fills RCA.md and .rca/profile.json
  -> user asks for an experiment in natural language
  -> RCA proposes an experiment plan
  -> user explicitly confirms
  -> RCA runs .rca/scripts/run_experiment.sh --confirm
  -> RCA updates .rca/experiments.json
  -> OpenCode summarizes results in the conversation
```

Rules:

- Run OpenCode/project initialization first, then `rca init`.
- `rca init` is mechanical scaffolding, not deep project analysis.
- OpenCode should fill `RCA.md` and `.rca/profile.json` after reading the actual project.
- RCA must propose an experiment plan before launching long experiments.
- The user must explicitly confirm the plan.
- Long experiments must go through `.rca/scripts/run_experiment.sh --confirm`.
- `.rca/scripts/run_experiment.sh` uses `.rca/experiments.lock` or `.rca/experiments.lockdir` and atomic replacement for `summary.json` and `.rca/experiments.json`.
- `.rca/experiments.json` is the first source for experiment history, comparison, and result lookup.

## Initialize A Project

From a research project root:

```bash
rca init
```

If `rca` is not on `PATH`:

```bash
~/Research-Code-Agent/bin/rca init
```

`rca init` creates:

```text
RCA.md
.rca/
  README.md
  profile.json
  experiments.json
  scripts/
    run_experiment.sh
  runs/
  plans/
```

It does not modify source code, does not write secrets, and does not overwrite `RCA.md`, `.rca/profile.json`, or `.rca/experiments.json` unless `--force` is passed.

After init, ask OpenCode:

```text
帮这个项目做 RCA 深度初始化
```

OpenCode should then read project docs/code/configs/paper materials, fill `RCA.md` and `.rca/profile.json`, summarize its project understanding, and wait for your confirmation before any experiment.

## Check A Workspace

```bash
rca check
```

`rca check` validates:

- required RCA files and directories;
- JSON validity;
- `.rca/experiments.json` top-level array shape;
- run directories missing from the ledger;
- ledger records with missing run directories;
- duplicate `run_id`;
- failed runs and `failure.json` compatibility.

It prints `PASS`, `WARN`, or `FAIL`.

## Run An Experiment

Original command:

```bash
python train.py --config configs/default.yaml
```

RCA command after the user has explicitly confirmed the plan:

```bash
./.rca/scripts/run_experiment.sh \
  --name baseline_default \
  --note "跑一次默认 baseline，作为后续实验对照" \
  --confirm \
  --task-type baseline \
  --config configs/default.yaml \
  -- python train.py --config configs/default.yaml
```

The wrapper saves:

- `.rca/runs/<run_id>/command.sh`
- `.rca/runs/<run_id>/stdout.log`
- `.rca/runs/<run_id>/stderr.log`
- `.rca/runs/<run_id>/summary.json`
- `.rca/runs/<run_id>/failure.json` on failure
- `.rca/runs/<run_id>/error_tail.txt` on failure
- `.rca/experiments.json`

The wrapper refuses to run without `--confirm`.

In `opencode.json`, configure `.rca/scripts/run_experiment.sh` as `ask`, not unconditional `allow`. RCA confirmation is the first boundary; OpenCode tool approval is the second boundary.

## Confirmation Rules

Only unconditional confirmation counts:

- `确认执行`
- `开始运行`
- `跑吧`
- `执行这个计划`
- `按这个计划运行`

These do not count:

- `基本可以，不过……`
- `是不是先……`
- `要不要……`
- `可以吗？`
- `先看看……`
- `确认执行，不过 output 目录改一下`
- `跑吧，但 batch size 改成 16`

If confirmation words appear together with any requested change, condition, question, or reservation, OpenCode must update the plan and wait for a new unconditional confirmation.

See `docs/rca-validation-checklist.md`.

## Quick Smoke Test

```bash
tmpdir=$(mktemp -d)
cd "$tmpdir"
rca init
mkdir -p examples
printf 'echo "UF1: 82.4"\n' > examples/toy_success.sh
chmod +x examples/toy_success.sh
./.rca/scripts/run_experiment.sh \
  --name toy_success \
  --note "跑一次 toy success，验证 RCA 记录流程" \
  --confirm \
  -- bash examples/toy_success.sh
rca check
```

## Repository Layout

```text
skills/
  rca/
    SKILL.md
bin/
  rca
templates/
  RCA.md
  rca/
    README.md
    profile.template.json
    experiments.template.json
    RCA_INIT_PROMPT.md
    run_experiment.sh
docs/
  requirements.md
  implementation-plan.md
  rca-validation-checklist.md
tools/
  legacy optional helpers
```

## Legacy And Optional Integrations

Feishu is an optional remote entry layer, not the RCA product core.

If Feishu access is needed, the currently recommended external route is `NeverMore93/opencode-feishu` or botmux. The legacy Python Feishu-OpenCode bridge remains in this repository as a legacy fallback, not the main RCA path.

Historical/optional docs:

- `docs/opencode-feishu-adoption.md`
- `docs/opencode-feishu-throwaway-test.md`
- `docs/opencode-lark-evaluation.md`
- `docs/opencode-lark-throwaway-test.md`
- `docs/opencode-sdk-evaluation.md`
- `docs/opencode-native-simplification.md` for the historical OpenCode-Native Simplification Strategy
- `docs/opencode-native-smoke-test.md`

Legacy bridge references retained for existing users:

- `templates/feishu_bridge.env.example`
- `templates/systemd/opencode-serve.service`
- `templates/systemd/rca-feishu-opencode-bridge.service`
- `tools/feishu_opencode_bridge.py`
- `tools/test_feishu_opencode_bridge.py`

Legacy bridge env variables include `BRIDGE_HEALTHCHECK_ENABLED` and `BRIDGE_AUDIT_MAX_BYTES`. Legacy audit troubleshooting may use:

```bash
tail -f .rca/feishu_bridge_audit.jsonl
```

`opencode-pty` is also optional background-session infrastructure, not RCA core.

## Old Release Users

`init_research_project.sh` remains for old release users. It copies optional `tools/`, Feishu templates, examples, and legacy docs.

New v0.7+ workflows should prefer:

```bash
rca init
rca check
```

## More Docs

- `docs/requirements.md`
- `docs/implementation-plan.md`
- `docs/rca-validation-checklist.md`
- `docs/rca-final-convergence.md`

## Security

Do not commit:

- `.env`
- `feishu.json`
- Feishu App ID / App Secret
- SSH keys
- tokens
- datasets
- checkpoints
- model weights
- `.rca/` run artifacts unless explicitly cleaned and intentionally shared

RCA check does not read secrets. It only inspects RCA workspace structure, JSON validity, ledger records, and run artifact existence.
