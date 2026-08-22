# Runtime compatibility

Read this reference only when the active client cannot apply the preferred role, model, reasoning effort, or context setting.

## Custom role selection

When the spawn interface exposes a custom agent or role selector and the required role is available, select `scout`, `coder`, `worker`, `senior_worker`, or `reviewer`. The matching custom agent file is the source of truth, so do not also pass model or reasoning overrides.

When the interface has no role selector, or a newly renamed role is not yet registered in the active session, omit the selector and use the preferred model, reasoning effort, and context fields that remain available. Put the job title in `task_name` and repeat the role instructions in the task packet. Do not claim the persistent custom agent file was selected.

Choosing this fallback before the first spawn because the active schema clearly lacks the role is preflight routing, not a retry. A newly installed or renamed role may require a new Codex task before it appears in the selector.

## Model and effort fields

Pass the routing table's model and reasoning values explicitly only when no configured custom role was selected.

If a requested Sol model is unavailable, omit the model override and use the role's requested effort when possible. Treat the model as inherited or runtime selected.

When the tool hides model or reasoning fields, omit them. Never invent an unsupported field or infer the effective setting without runtime evidence.

## Retry budget

Each assignment has one compatibility retry total after its first spawn attempt. The full-history and authorization cases below share that same budget and are mutually exclusive once a retry has been used. After the retry fails, return the assignment to the main agent without another attempt.

## Context fields

Use `fork_turns: "none"` when the interface exposes it. On interfaces that expose `fork_context`, use `fork_context: false` as the fresh-context equivalent.

If neither field exists, send the complete task packet and treat context inheritance as runtime selected. Do not copy the full parent conversation into the task message.

If the first attempt uses full history and rejects the role selector or fallback model overrides, consume the retry budget by retrying once with fresh context and the complete task packet.

If the first attempt is a fresh child that rejects an authorized local write because it cannot see direct user authorization, first confirm that the user authorized that exact class of local work. Consume the retry budget by retrying once with the smallest positive `fork_turns` value that includes the authorizing user turn, while keeping the same ownership, constraints, and leaf boundary. If no direct authorization exists, return the work to the main agent without retrying.

## Concurrency

Use runtime metadata or the active-agent list to respect available slots and the configured concurrency limit. If the limit is unavailable, keep the initial team to two or three subagents. On a capacity rejection, wait for or reuse an existing agent; do not repeatedly spawn replacements.

## Permissions and approvals

Subagents normally inherit the active parent permission and sandbox policy, and a client may reapply live runtime overrides when it spawns a child. Agent-specific read-only settings can strengthen the default, but task text alone cannot create operating-system isolation. A sandbox approval prompt may surface from the child thread; the coordinator still owns the authorization decision and must not treat the prompt as broader user consent.

Do not delegate an external write, destructive action, purchase, or material scope expansion until the user has given the exact approval required by the active policy. Keep approval decisions in the main agent.

## Missing collaboration features

If subagents are disabled or unavailable, continue in the main agent. Keep intermediate evidence compact and do not simulate or claim child work.

If direct agent-to-agent messaging is unavailable, route the dependency through the main agent. Do not spawn a replacement agent only to relay a message.

## Confirmation

Confirm the effective child role, model, effort, and context policy from the tool response, parent UI, or runtime metadata when available. If confirmation is unavailable, describe only the settings requested, not the settings guaranteed.
