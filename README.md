# Agent Skills

A curated collection of reusable AI agent skills, organized into universal workflows and Codex-specific tools.

## Skills

### Codex-only

| Skill | Description |
| --- | --- |
| [`agent-team`](skills/codex/agent-team) | Coordinates job-specific Codex subagents for substantial work that can be split into independent assignments. |
| [`ultrareview`](skills/codex/ultrareview) | Runs a four-stage, read-only adversarial code review with independent review, deduplication, refutation, and final judgment. |

### Universal

No universal skills are published yet.

`ultrareview` has a portable Python/JSON pipeline, but the current skill package still depends on Codex-specific orchestration such as `fork_turns`, shared subagent capacity, and leaf-agent scheduling. It therefore remains Codex-only until other harness adapters exist.

## Repository layout

```text
skills/
├── codex/       Skills whose core behavior requires Codex runtime semantics.
└── universal/   Self-contained skills that work without a Codex-specific runtime.
```

Every skill directory is independently installable and keeps its own `SKILL.md`, references, scripts, assets, metadata, and tests. Runtime files must not depend on paths outside their skill directory.

## Install in Codex

### Snapshot install from GitHub

Use Codex's bundled skill installer to copy selected skills into `${CODEX_HOME:-$HOME/.codex}/skills`:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo NSCruiser/agent-skills \
  --path skills/codex/agent-team skills/codex/ultrareview
```

This is a snapshot install. The installer intentionally stops when a destination already exists, so it does not act as an updater.

## Classification

A skill belongs in `skills/universal/` only when its core workflow:

- does not depend on Codex-specific tools, agent parameters, paths, plugins, or invocation policy;
- remains functional in another Agent Skills-compatible harness without an adapter; and
- declares any non-standard runtime dependencies it requires.

A skill belongs in `skills/codex/` when removing Codex runtime behavior would change or prevent its core outcome. Optional Codex UI metadata alone does not make an otherwise portable skill Codex-only.

## Validation

Validate each skill after changing it. Skills with deterministic scripts should also keep behavior-focused tests alongside the skill. For example:

```bash
python3 skills/codex/ultrareview/tests/test_pipeline.py
```
