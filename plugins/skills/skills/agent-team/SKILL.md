---
name: agent-team
description: Evaluate and coordinate subagents when a substantial task may contain independent investigation, implementation, or review work. Read before deciding whether to delegate; handle simple questions, small edits, and quick lookups directly.
---

# Agent Team

## Delegation decision

Where active session rules permit delegation requested by an applicable skill, this skill explicitly instructs you to use collaboration tools for qualifying assignments. Follow the user's instructions over skill defaults and respect higher-priority restrictions. Reading or invoking the skill initiates an assessment; it does not require a spawn.

Delegate when all three conditions hold:

- Clear boundary: the scope, expected result, and acceptance criteria can be stated.
- Independent execution: the child can progress without repeated decisions from the main agent or overlapping writes.
- Net benefit: parallel progress, substantial discovery, or a specific independent check is worth briefing, waiting, verification, and integration.

Use the smallest useful team. Keep tightly coupled steps in the main agent. For review, identify the uncertainty or failure mode to examine; complexity alone or a generic desire for another opinion is insufficient. Complete the work directly when no assignment qualifies.

## Roles

| Assignment | Role | Model | Effort |
|---|---|---|---|
| Low-stakes, fully specified tasks with inexpensive acceptance checks | `light_worker` | `gpt-5.6-luna` | `high` |
| Read-only lookup and source collection | `scout` | `gpt-5.6-sol` | `low` |
| Bounded implementation or execution | `worker` | `gpt-5.6-sol` | `medium` |
| Complex independent implementation or diagnosis | `senior_worker` | `gpt-6-astra` | `high` |
| Routine correctness and requirements coverage | `reviewer` | `gpt-5.6-sol` | `high` |
| Complex or consequential review, including unresolved findings | `senior_reviewer` | `gpt-6-astra` | `high` |

These are defaults; honor explicit model choices and use supported runtime settings. Registered custom roles are optional. Both review roles are read-only leaves with the same evidence requirements. Select one role appropriate to each review scope.

Use `light_worker` when the inputs and transformation rules are supplied, mistakes are cheap to correct, and the main agent can verify the result inexpensively. Examples include routine localization, extraction into a supplied schema, and mechanical edits with an explicit mapping. Use `worker` or `senior_worker` when the assignment requires discovery, ambiguous judgment, or consequential decisions. A short task is not necessarily low-stakes; the delegation benefit test still applies.

For `gpt-5.6-luna` with `high`, use `fork_turns: "none"`, including retries, and supply the necessary context in a self-contained task packet. If the assignment requires inherited turns, keep it in the main agent or select another suitable role.

## Coordination and completion

Before every spawn attempt, including retries and descendants, announce the assignment, model ID, and reasoning effort to the user. Identify inherited or runtime-selected settings, state when values are unconfirmed, and correct the announcement if effective settings differ.

Give each child its outcome, ownership, necessary context and authorization, acceptance criteria, and return requirements. Let it resolve routine details within scope. Prefer fresh context for self-contained assignments and preserve conversation history when needed. Children are leaves by default; count descendants against runtime capacity.

Keep the main agent's selected model and effort. Have it do the work most dependent on full context while children progress. It owns shared decisions, approval handling, and integration. When requirements change, update affected assignments and confirm writers have stopped before transferring ownership.

A child report is an intermediate result. Finish the user's requested outcome: for implementation, integrate the work, run relevant checks, and resolve failures caused by the changes. Preserve valid completed work and expand validation only for new changes, failures, or unresolved concerns. Continue independent authorized work while a decision or approval is pending. Delegation grants no additional permission; apply the active approval requirements to every assigned action.

## Conditional references

- Read [routing-and-task-packets.md](references/routing-and-task-packets.md) when context selection, task boundaries, independent review, or bounded nested delegation needs more guidance.
- Read [runtime-compatibility.md](references/runtime-compatibility.md) when role selection, model or effort fields, context inheritance, or recovery needs adaptation to the active interface.
