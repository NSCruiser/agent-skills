# Runtime compatibility

Read this reference when applying the selected role's model, reasoning effort, and context policy to the active interface. Use the exposed schema and runtime metadata to resolve known incompatibilities before the first call.

## Roles, models, and effort

Choose the assignment's role in [SKILL.md](../SKILL.md). A registered custom role is an optional way to apply that choice when the active interface exposes a role selector and the registered configuration matches the selected role's settings. Use that selector without duplicate model or effort overrides.

Otherwise omit the role selector, identify the selected role and job in `task_name` and the message, and pass the role's bundled model and effort through supported fields. These fields implement the role choice; they are not a separate model selection step. A task name does not select a persistent custom role. Do not assume that a file on disk is registered in the current session.

When the selected role's model or effort is unavailable, choose another listed role only if it fits the assignment and the user's instructions allow it; otherwise retain the work in the main agent or report the specific blocker. Honor explicit user overrides. Reconsider delegation cost if a suitable alternative role is more expensive. Do not silently substitute settings within a role or claim a user's exact model choice was honored after a substitution.

When model or effort fields are absent, omit them and use runtime metadata to check whether inherited or runtime-selected settings match the role. Apply the same fallback rule to a known mismatch. If effective settings cannot be confirmed, describe the intended role and the unconfirmed settings accurately. Never invent unsupported fields.

## Context and spawn shape

Apply the context defaults and required settings from [SKILL.md](../SKILL.md). Use `fork_turns: "none"` for fresh context where supported. On an interface exposing only `fork_context`, use `fork_context: false` for fresh context. If neither field is exposed, send a self-contained packet and treat inheritance as runtime selected. If the selected configuration requires fresh context and the runtime cannot guarantee it, keep the work in the main agent or select another suitable role.

When the schema requires full-history forks to inherit the parent model and effort, use that form only when the inherited settings match the selected role or an explicit user override. Pass `fork_turns: "all"` and omit model, effort, and any role selector that would override those settings. Otherwise use fresh or recent-turn context if it preserves the needed information, select another suitable listed role, or keep the assignment in the main agent.

For an interface exposing `task_name`, `message`, `model`, `reasoning_effort`, and `fork_turns`, applying the `worker` role to a fresh bounded coding assignment can use:

```json
{
  "task_name": "worker_cache",
  "fork_turns": "none",
  "model": "gpt-6-astra",
  "reasoning_effort": "low",
  "message": "<task packet, including ownership, permissions, acceptance, and leaf boundary>"
}
```

Adapt this example to the active schema. With a suitable registered custom role, use the actual role selector instead of explicit model and effort fields.

## Recovery and capacity

Allow at most one compatibility retry per assignment, and only when an observed failure identifies a supported correction. Preserve required context, ownership, and permissions. If the retry fails, return the remaining work to the main agent. Do not use retries to bypass an approval denial.

If a fresh child lacks the authorizing user turn for an already authorized local write, the retry may use the smallest positive `fork_turns` count that includes that turn, unless the selected model and effort require fresh context under [SKILL.md](../SKILL.md). This applies only to missing context, not missing approval; retain all original constraints.

Use runtime metadata or the active-agent list to respect capacity, including descendants. If capacity is unknown, begin with one useful child and expand only as capacity is established. On a capacity rejection, wait for or reuse an existing agent instead of repeatedly spawning replacements.

Before retrying or replacing an assignment that might already have started, check the existing agent's status and any partial changes. Stop its writers before transferring ownership, and preserve valid completed work.

## Permissions and missing features

Children normally inherit the parent's active permission and sandbox policy; runtime overrides may also apply. A configured read-only role can strengthen that boundary, but task text alone does not create operating-system isolation. Apply the user approval requirements in [SKILL.md](../SKILL.md) regardless of the selected role or fallback.

If subagents are unavailable, continue in the main agent. If direct agent-to-agent messaging is unavailable, relay dependencies through the main agent. If stopping an active writer is unsupported, wait for it to finish before reassigning its resources; do not integrate results that conflict with updated requirements.
