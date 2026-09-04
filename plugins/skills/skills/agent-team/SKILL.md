---
name: agent-team
description: Assess and coordinate Codex subagent delegation. Read proactively when a substantial task may contain independent investigation, implementation, or review work, before choosing solo or delegated execution. This skill directs delegation for qualifying assignments where session rules permit skill-directed delegation. Handle simple questions, small edits, and quick lookups directly.
---

# Agent Team

## Applicability and authority

Read the complete active delegation rule, including its exceptions. Where session rules allow an applicable skill to request delegation, this skill explicitly instructs you to spawn subagents using collaboration tools for assignments that meet all criteria below. An additional user request for delegation is unnecessary in that case. Follow any explicit user prohibition and any higher-priority rule requiring a direct user request or forbidding subagents.

Assess candidate assignments after reading this skill. Reading or invoking it initiates that assessment; spawn only when both the active rules and the task criteria allow it. If they do not, continue the work in the main agent.

Keep the main agent's user-selected model, reasoning effort, permissions, and context. Have it own the diagnosis, design, or implementation that most depends on the full task context, alongside cross-task decisions and final integration. While children work, advance another useful part of the task and remain responsive to the user.

## When to delegate

Before spawning, identify a concrete assignment that meets all three conditions:

- Clear boundary: the child's scope, expected result, and acceptance criteria can be stated.
- Independent execution: the child can make progress without repeated decisions from the main agent or overlapping writes with another agent.
- Net benefit: parallel progress, isolation of substantial discovery, or a specific independent check is worth the briefing, waiting, verification, and integration cost.

Delegate qualifying work, such as an independent module alongside the main implementation, substantial research into separate questions, or an independent check of a complex conclusion with significant consequences if wrong. For review, identify the specific uncertainty or failure mode the reviewer should examine.

Handle simple questions, small edits, quick lookups, and tightly coupled sequential steps directly. Task complexity alone or a generic desire for another review does not justify delegation. Choose the smallest useful team; one child can be sufficient.

## Routing defaults

| Assignment | Role | Model | Effort |
|---|---|---|---|
| Narrow read-only lookup, source collection, or location work | `scout` | `gpt-5.6-sol` | `low` |
| Bounded coding with clear ownership and acceptance criteria | `coder` | `gpt-5.6-sol` | `medium` |
| Routine execution with limited investigation or integration | `worker` | `gpt-5.6-sol` | `medium` |
| Independently solvable complex logic, diagnosis, or meaningful ambiguity | `senior_worker` | `gpt-6-astra` | `high` |
| Independent correctness or completeness check | `reviewer` | `gpt-5.6-sol`; use `gpt-6-astra` for complex or consequential checks | `high` |

These are skill defaults. Choose by ambiguity, consequences of error, and difficulty of verification. Follow explicit user model choices. Role names identify assignments; registered custom roles are optional. Use a custom role's configured settings when they fit the assignment; otherwise use supported explicit fields. Never pass model or effort overrides alongside a configured role.

## Coordination

Before every spawn attempt, including retries and nested delegation, send a user-visible update identifying the child's assignment, model ID, and reasoning effort. For a batch, one update may list each child and its settings. State whether settings are explicit, supplied by a configured role, or inherited. Use runtime evidence for inherited values; if a value is unavailable, explicitly say it is inherited or runtime selected and not yet confirmed. Announce the settings that the upcoming call will actually request, and correct the update if the runtime reports different effective settings.

Give each child a concrete outcome, distinct ownership, necessary context and authorization, acceptance criteria, and a concise return contract. Provide enough information to begin; let it inspect its scope and resolve routine implementation details. Prefer fresh context for self-contained work and independent review; preserve relevant conversation turns when restating them would lose important decisions or source material.

Keep children as leaves by default and prevent overlapping writes. Respect the runtime's available capacity, counting all descendants. The main agent owns priorities, conflicts, approval decisions, and final synthesis. When the user changes requirements, update or stop affected assignments before relying on their results. Confirm a writer has stopped before reassigning its resources.

Evaluate results against the latest requirements. Check decisive evidence and integration boundaries, reuse valid completed work, and run the relevant combined checks. Expand or repeat validation only for new changes, failures, or unresolved concerns. Add unit tests only when the user or project requires them.

Do not delegate external writes, destructive actions, purchases, or material scope expansion before the exact required user approval exists. A sandbox prompt surfaced from a child does not broaden that approval.

## Conditional references

- Read [routing-and-task-packets.md](references/routing-and-task-packets.md) when context selection, task boundaries, independent review, or bounded nested delegation needs more guidance.
- Read [runtime-compatibility.md](references/runtime-compatibility.md) when the active interface cannot directly apply the chosen role, model, effort, or context. Resolve known incompatibilities before spawning; allow at most one compatibility retry per assignment.
