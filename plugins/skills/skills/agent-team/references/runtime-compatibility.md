# Runtime compatibility

Read this reference when the active interface cannot directly apply the chosen role, model, reasoning effort, or context. Use the exposed schema and runtime metadata to resolve known incompatibilities before the first call.

## Roles, models, and effort

The defaults live in [SKILL.md](../SKILL.md). Custom roles are optional. Select one only when the active interface exposes a role selector, the role is registered, and its configuration fits the assignment. Use its configured settings without duplicate model or effort overrides.

Otherwise omit the role selector, identify the job in `task_name` and the message, and pass the chosen model and effort through supported fields. A task name does not select a persistent custom role. Do not assume that a file on disk is registered in the current session.

When a model or effort is unavailable, choose a supported setting suitable for the assignment if the user's instructions allow it; otherwise retain the work in the main agent or report the specific blocker. Reconsider delegation cost if a routine child would inherit an expensive parent configuration. Do not silently substitute a weaker model for difficult work or claim a user's exact model choice was honored after a substitution.

When model or effort fields are absent, omit them and treat the settings as inherited or runtime selected. Confirm effective settings from the tool response or runtime metadata when available; otherwise describe only what was requested. Never invent unsupported fields.

## Context and spawn shape

Use `fork_turns: "none"` for fresh context where supported. On an interface exposing only `fork_context`, use `fork_context: false` for fresh context. If neither field is exposed, send a self-contained packet and treat inheritance as runtime selected.

When the schema requires full-history forks to inherit the parent model and effort, pass `fork_turns: "all"` and omit model, effort, and any role selector that would override those settings. Preserve the needed history. If a different model is essential, use fresh or recent-turn context only when it can retain the required information; otherwise keep the assignment in the main agent.

For an interface exposing `task_name`, `message`, `model`, `reasoning_effort`, and `fork_turns`, a fresh bounded coding assignment can use:

```json
{
  "task_name": "coder_cache",
  "fork_turns": "none",
  "model": "gpt-5.6-sol",
  "reasoning_effort": "medium",
  "message": "<task packet, including ownership, permissions, acceptance, and leaf boundary>"
}
```

Adapt this example to the active schema. With a suitable registered custom role, use the actual role selector instead of explicit model and effort fields.

## Recovery and capacity

Allow at most one compatibility retry per assignment, and only when an observed failure identifies a supported correction. Preserve required context, ownership, and permissions. If the retry fails, return the remaining work to the main agent. Do not use retries to bypass an approval denial.

If a fresh child lacks the authorizing user turn for an already authorized local write, the retry may use the smallest positive `fork_turns` count that includes that turn. This applies only to missing context, not missing approval; retain all original constraints.

Use runtime metadata or the active-agent list to respect capacity, including descendants. If capacity is unknown, begin with one useful child and expand only as capacity is established. On a capacity rejection, wait for or reuse an existing agent instead of repeatedly spawning replacements.

Before retrying or replacing an assignment that might already have started, check the existing agent's status and any partial changes. Stop its writers before transferring ownership, and preserve valid completed work.

## Permissions and missing features

Children normally inherit the parent's active permission and sandbox policy; runtime overrides may also apply. A configured read-only role can strengthen that boundary, but task text alone does not create operating-system isolation. Apply the user approval requirements in [SKILL.md](../SKILL.md) regardless of the selected role or fallback.

If subagents are unavailable, continue in the main agent. If direct agent-to-agent messaging is unavailable, relay dependencies through the main agent. If stopping an active writer is unsupported, wait for it to finish before reassigning its resources; do not integrate results that conflict with updated requirements.
