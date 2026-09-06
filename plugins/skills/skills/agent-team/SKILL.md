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

| Assignment | Role | Model | Effort | `fork_turns` |
|---|---|---|---|---|
| Read-only lookup and source collection | `scout` | `gpt-5.6-sol` | `low` | `"none"` |
| Low-stakes, fully specified tasks with inexpensive acceptance checks | `light_worker` | `gpt-5.6-luna` | `high` | `"none"` (required) |
| Bounded implementation or execution | `worker` | `gpt-5.6-sol` | `medium` | `"none"` |
| Complex independent implementation, diagnosis, or judgment-led design | `senior_worker` | `gpt-6-astra` | `high` | `"none"` |
| Routine correctness and requirements coverage | `reviewer` | `gpt-5.6-sol` | `high` | `"none"` |
| Complex, consequential, or judgment-led review, including unresolved findings | `senior_reviewer` | `gpt-6-astra` | `high` | `"none"` |

These are defaults except where marked required; honor explicit model choices and use supported runtime settings. Registered custom roles are optional. Both review roles are read-only leaves with the same evidence requirements. Select one role appropriate to each review scope.

When delegating work whose primary difficulty is aesthetic quality, design taste, product or interaction judgment, or high-level intuition under ambiguous criteria, use `senior_worker` with `gpt-6-astra` and `high` effort. For a read-only assessment of that work, use `senior_reviewer` at the same model and effort. This includes UI/UX critique, visual hierarchy, typography, and deciding whether an experience feels polished. Do not route these judgments to Sol or Luna merely because the code change is small, reversible, or easy to compile; mechanical checks do not establish design quality. Implementation of an already settled design and routine evidence collection can still use the lighter roles. The delegation benefit test still applies.

Context defaults favor self-contained assignments. Except for Luna High's required fresh context, use the smallest positive `fork_turns` count that preserves needed decisions, or `"all"` when the full history is necessary. Full-history forks may require inheriting the parent's model and effort; follow [runtime-compatibility.md](references/runtime-compatibility.md). Required fresh context also applies to retries; if inherited turns are essential, keep the work in the main agent or choose another suitable role.

Use `light_worker` when the inputs and transformation rules are supplied, mistakes are cheap to correct, and the main agent can verify the result inexpensively. Examples include routine localization, extraction into a supplied schema, and mechanical edits with an explicit mapping. Use `worker` or `senior_worker` when the assignment requires discovery, ambiguous judgment, or consequential decisions. A short task is not necessarily low-stakes; the delegation benefit test still applies.

## Coordination and completion

Before every spawn attempt, including retries and descendants, announce the assignment, model ID, and reasoning effort to the user. Identify inherited or runtime-selected settings, state when values are unconfirmed, and correct the announcement if effective settings differ.

Give each child its outcome, ownership, necessary context and authorization, acceptance criteria, and return requirements. Include task-specific tool and safety restrictions explicitly in fresh-context packets. Let it resolve routine details within scope. Children are leaves by default; tell them: "Complete this assignment directly. Do not spawn other agents; your parent's delegation instructions apply only to your parent." Count descendants against runtime capacity.

Keep the main agent's selected model and effort. Have it do the work most dependent on full context while children progress, stay available to the user, and track assignments to avoid duplicate work. It owns shared decisions, approval handling, and integration. Let agents send relevant findings directly to teammates when supported; changes to scope or shared interfaces return to the main agent. When requirements change, update affected assignments and confirm writers have stopped before transferring ownership.

A child report is an intermediate result. Finish the user's requested outcome: for implementation, integrate the work, run relevant checks, and resolve failures caused by the changes. Preserve valid completed work and expand validation only for new changes, failures, or unresolved concerns. Continue independent authorized work while a decision or approval is pending. Delegation grants no additional permission; apply the active approval requirements to every assigned action.

## Conditional references

- Read [routing-and-task-packets.md](references/routing-and-task-packets.md) when context selection, task boundaries, independent review, or bounded nested delegation needs more guidance.
- Read [runtime-compatibility.md](references/runtime-compatibility.md) when role selection, model or effort fields, context inheritance, or recovery needs adaptation to the active interface.
