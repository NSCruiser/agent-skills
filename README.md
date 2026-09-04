# Agent Skills Marketplace

A private, dual-harness marketplace that distributes one `skills` plugin with harness-specific skill visibility.

## Catalog

| Harness | Plugin | Visible skills |
| --- | --- | --- |
| Codex | [`skills`](plugins/skills) | [`ultrareview`](plugins/skills/skills/ultrareview), [`agent-team`](plugins/skills/skills/agent-team) |
| Claude Code | [`skills`](plugins/skills) | [`ultrareview`](plugins/skills/skills/ultrareview) |

The two catalogs provide different views of the same source repository:

- [`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json) points Codex at the complete plugin directory.
- [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) explicitly lists the portable skill paths exposed to Claude Code.

## Repository layout

```text
.agents/plugins/marketplace.json       Codex marketplace: complete plugin
.claude-plugin/marketplace.json        Claude marketplace: portable skill view
.claude/settings.json                  Project registration and auto-update policy
plugins/
└── skills/
    ├── .codex-plugin/plugin.json
    └── skills/
        ├── ultrareview/
        └── agent-team/
```

Each skill remains self-contained. Runtime files must not import paths outside their own skill directory.

## Codex

### GitHub workspace sync (automatic)

Workspace admins can import this private GitHub repository from **Admin → Plugins → Add → Import marketplace**:

- Source: `https://github.com/NSCruiser/agent-skills`
- Path: leave empty
- Branch: `main` (or leave empty to follow the default branch)

Authorize a GitHub account that can read the private repository. Codex enables daily marketplace sync by default; use **Sync now** to request an immediate refresh. The import reads the Codex catalog and exposes the complete `skills` plugin. Workspace policy, not the committed `policy` block, controls who receives it.

### Local checkout (manual development flow)

```bash
codex plugin marketplace add /absolute/path/to/agent-skills
codex plugin add skills@agent-skills
```

A local checkout is useful for development but does not pull GitHub automatically. After changing a plugin, bump its `.codex-plugin/plugin.json` version, reinstall it, and test in a new task. Use GitHub workspace sync when background updates are required.

## Claude Code

Add this GitHub marketplace, then install the universal plugin:

```bash
claude plugin marketplace add NSCruiser/agent-skills
claude plugin install skills@nscruiser-agent-skills
```

The Claude marketplace uses the repository root as its plugin source and explicitly lists only portable skill paths. It omits a fixed plugin version, so Claude Code uses the repository commit SHA for update detection.

Third-party marketplaces do not auto-update by default. This repository's [`.claude/settings.json`](.claude/settings.json) enables auto-update when Claude Code is running in this project. For global use, merge the same `extraKnownMarketplaces` and `enabledPlugins` entries into `~/.claude/settings.json`.

For a private repository, interactive installs and manual updates use the machine's Git credentials. GitHub shorthand clones over SSH by default, so the most reliable background update setup is a key already loaded in `ssh-agent`. If background refreshes can fail, preserve the last working cache:

```bash
export CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE=1
```

Manual refresh remains available:

```bash
claude plugin marketplace update nscruiser-agent-skills
claude plugin update skills@nscruiser-agent-skills
```

## Naming

The GitHub repository remains named `agent-skills`, and Codex uses `agent-skills` as its marketplace ID. Claude Code reserves `agent-skills` for Anthropic-owned marketplaces, so its marketplace ID is `nscruiser-agent-skills`. The Claude plugin selector is therefore `skills@nscruiser-agent-skills`.

## Classification rule

A skill is added to the Claude marketplace only when its core workflow:

- does not depend on Codex-specific tools, paths, plugins, or invocation policy;
- remains functional in another Agent Skills-compatible harness without an adapter; and
- declares any non-standard runtime dependencies.

A skill remains Codex-only when removing Codex runtime behavior would change or prevent its core outcome. Codex-only skills stay in the unified plugin but are omitted from the Claude marketplace skill list.

## Validation

```bash
python3 plugins/skills/skills/ultrareview/tests/test_pipeline.py
claude plugin validate .
```

Codex plugin manifests should also be validated with the bundled `plugin-creator` validator before release.
