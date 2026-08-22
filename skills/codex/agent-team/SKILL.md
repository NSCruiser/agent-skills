---
name: agent-team
description: Coordinate job-specific Codex subagents for complex work that can be divided into clear, independent assignments. Use only when the user explicitly invokes $agent-team. Do not use for simple tasks, tightly coupled steps, or work whose delegation cost exceeds the benefit.
---

# Agent Team

Use the main agent as coordinator and keep its user-selected model, reasoning effort, permissions, and context. Keep trivial work, tightly coupled steps, cross-task decisions, and approval-bound actions in the main agent. Delegate only substantial work that divides into independent lanes.

Remain available to the user while agents work. Route narrow read-only discovery to `scout`, specified coding to `coder`, routine execution to `worker`, difficult bounded work to `senior_worker`, and independent checks to `reviewer`. Each custom agent file is the source of truth for its model and reasoning effort; do not pass duplicate overrides.

Prefer focused fresh context with `fork_turns: "none"`. Give every agent only the needed inputs, authorization, constraints, distinct ownership, validation, output contract, stop condition, and delegation boundary. Prevent overlapping writes.

Keep agents as leaves by default. Only an explicitly authorized `senior_worker` may spawn at most two independent leaf agents within remaining capacity. Choose the smallest useful team, normally two or three subagents, and count all descendants against the runtime limit. Agents may exchange dependency information, but the main agent owns priorities, conflicts, authorization decisions, and final synthesis. Reuse completed work, integrate results, and validate proportionately.

Do not delegate external writes, destructive actions, purchases, or material scope expansion before the exact required user approval exists. A sandbox prompt surfaced from a child does not broaden that approval.

## Conditional references

- Read [routing-and-task-packets.md](references/routing-and-task-packets.md) only when role selection, non-default context, nested delegation, write partitioning, or the task packet is non-obvious. Straightforward leaf assignments can use a concise packet.
- Read [runtime-compatibility.md](references/runtime-compatibility.md) only when the active client cannot apply the preferred role or fields. Use its preflight fallback and allow at most one compatibility retry per assignment.
- If useful work cannot be split safely, complete it in the main agent.
