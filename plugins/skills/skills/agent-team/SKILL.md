---
name: agent-team
description: Choose subagent roles by judgment demands, task clarity, and total completion cost, then coordinate useful independent assignments. Read before deciding whether to delegate; handle straightforward questions, routine edits with settled requirements, and quick factual lookups directly.
---

# Agent Team

## Delegation decision

Where active session rules permit delegation requested by an applicable skill, this skill explicitly instructs you to use collaboration tools for qualifying assignments. Follow the user's instructions over skill defaults and respect higher-priority restrictions. Reading or invoking the skill initiates an assessment; it does not require a spawn.

Delegate when all three conditions hold:

- Bounded ownership: the question, constraints, and useful deliverable can be stated. An investigation or design assignment may have an unknown solution; its deliverable can be an evidence-backed diagnosis or proposal with explicit tradeoffs.
- Independent execution: the child can progress without repeated decisions from the main agent or overlapping writes.
- Net benefit: parallel progress, substantial discovery, or a specific independent check is worth briefing, waiting, verification, and integration.

Use the smallest useful team. Keep tightly coupled steps in the main agent. For review, identify the uncertainty or failure mode to examine; complexity alone or a generic desire for another opinion is insufficient. Complete the work directly when no assignment qualifies.

## Role selection

Choose one role from the table for each assignment and apply its model, reasoning effort, and context policy. The role is the selection unit. Judge the hardest unresolved decision: how much the agent must infer, which assumptions it must question, and how difficult a wrong answer would be to detect. Task length, file count, read-only access, and passing mechanical checks do not measure these demands.

| Role | Assignment | Model | Effort | `fork_turns` default |
|---|---|---|---|---|
| `scout` | Lookup and source collection for a defined question | `gpt-5.6-sol` | `low` | `"none"` |
| `light_worker` | Low-stakes transformations with supplied rules and cheap checks | `gpt-5.6-luna` | `high` | `"none"` (required) |
| `worker` | Bounded investigation or implementation within a settled direction | `gpt-6-astra` | `low` | `"none"` |
| `senior_worker` | Ambiguous or difficult investigation, design, or implementation | `gpt-6-astra` | `high` | `"none"` |
| `reviewer` | Correctness and coverage against explicit requirements | `gpt-6-astra` | `low` | `"none"` |
| `senior_reviewer` | Judgment-led or consequential review, including unresolved difficult findings | `gpt-6-astra` | `high` | `"none"` |
| `advisor` | Exceptional difficulty or ambiguity requiring a high-level verdict | `gpt-6-astra` | `xhigh` (Extra High) | `"none"` |

These bundles are the defaults except where marked required. Honor explicit user model and budget choices. Registered custom roles are optional; apply the selected role through the active interface as described in [runtime-compatibility.md](references/runtime-compatibility.md).

Use `senior_worker` when the work depends on interpreting intent, discovering hidden constraints, inventing an approach, weighing conflicting goals, or judging quality under incomplete criteria. Aesthetic judgment is one example of this broader need for context-sensitive judgment. Use `senior_reviewer` for an independent assessment of a proposed or completed result with those demands. Both review roles are read-only leaves with the same evidence requirements; read-only investigation can still belong to `senior_worker` when framing and synthesis are the deliverable.

Use `worker` for substantial execution and routine decisions within a settled direction, and `scout` for collecting evidence to answer a defined question. Use `light_worker` only when the inputs and rules are supplied, little inference is needed, mistakes are cheap to correct, and verification costs less than doing the work.

Select the role with the lowest expected cost to an accepted result at the required quality: initial work, context, tool calls, supervision, verification, retries, and integration. A senior role can cost less overall by finding the right approach in fewer steps. Assign the appropriate role directly; trying cheaper roles first is unnecessary when the judgment demands are already clear. Apply the selected role's effort setting; extra effort is not a substitute for choosing the appropriate role.

Use `advisor` very sparingly, for a focused decision whose exceptional difficulty, vagueness, or need for a high-level verdict warrants reasoning beyond `senior_worker` or `senior_reviewer`. Its expected decision value must justify the extra usage and consultation cost. Ordinary ambiguity, routine architecture work, and standard consequential reviews belong to the senior roles. The advisor is a read-only leaf: provide the decisive question, relevant evidence, constraints, and any competing interpretations; ask for a recommendation or verdict, its rationale, material uncertainty, and what evidence would change it. The main agent owns the decision and follow-through. Consult directly when the need is evident; prior failure in another role is not required. Avoid routine second opinions, repeated consultation without new evidence, and making advisor approval a completion gate.

## Model background

These profiles explain the capability and cost assumptions behind the role bundles. They are background context, not a separate selection step or absolute limits on model capability.

- **Astra:** Broad knowledge, strong reasoning, intuition, and judgment. Better suited to vague requests, hidden constraints, connections across domains, and questioning the premise. It has the highest expected per-token cost and usage pressure of these three for comparable work, but better framing and fewer attempts can reduce total completion cost.
- **Sol:** Diligent, methodical, and careful within a sound problem frame, at lower per-token cost than Astra. Thorough local execution can still miss a flawed premise or the larger goal, which makes purpose and settled constraints valuable context.
- **Luna:** Very low per-token cost for narrow, repetitive work with explicit rules. Its limited ability to infer missing intent or rules makes supplied inputs and cheap acceptance checks central to reliable use.

Per-token pricing and plan usage limits are different measures. Use current [model guidance](https://learn.chatgpt.com/docs/models) and [usage guidance](https://learn.chatgpt.com/docs/pricing) when exact cost or availability matters, rather than assuming fixed ratios or guaranteed savings.

## Context

Default to a self-contained packet with `fork_turns: "none"`. For roles other than `light_worker`, inherit turns when doing so materially helps the task or lowers total cost, using the smallest useful positive count or `"all"` when the full history is beneficial. The `light_worker` role (Luna) requires fresh context, including retries; otherwise keep the work in the main agent or choose another suitable role. Full-history forks may require inheriting the parent's model and effort; follow [runtime-compatibility.md](references/runtime-compatibility.md).

## Handoffs and reassignment

Keep judgment with the agent that understands the problem. After a direction is settled, hand off execution only when the remaining work is substantial and the decisions, constraints, and acceptance checks can be transferred cheaply. A `worker` can own the implementation; a `light_worker` can own eligible mechanical portions. If explaining and checking the handoff would cost more than finishing, let the current agent finish. Use each role only where it adds value; there is no fixed sequence of roles.

Reassess the assignment when evidence exposes missing rules, conflicting assumptions, a broader dependency, or repeated corrections without convergence. Have the child return the decisive evidence, completed work, and unresolved question. The main agent can resolve a small gap, retain the work, or assign the remaining problem directly to a suitable role. A `light_worker` assignment may need a `worker` for bounded investigation or implementation, or a `senior_worker` when the gap requires framing or judgment. Avoid repeated prompting or increased effort as a way to compensate for a role mismatch. Stop any active writer before transferring ownership.

## Coordination and completion

Before every spawn attempt, including retries and descendants, announce the assignment, model ID, and reasoning effort to the user. Identify inherited or runtime-selected settings, state when values are unconfirmed, and correct the announcement if effective settings differ.

Give each child its outcome, ownership, necessary context and authorization, acceptance criteria, and return requirements. Include task-specific tool and safety restrictions explicitly in fresh-context packets. Let it resolve routine details within scope. Children are leaves by default; tell them: "Complete this assignment directly. Do not spawn other agents; your parent's delegation instructions apply only to your parent." Count descendants against runtime capacity.

Keep the main agent's selected model and effort. Have it do the work most dependent on full context while children progress, stay available to the user, and track assignments to avoid duplicate work. It owns shared decisions, approval handling, and integration. Let agents send relevant findings directly to teammates when supported; changes to scope or shared interfaces return to the main agent. When requirements change, update affected assignments and confirm writers have stopped before transferring ownership.

A child report is an intermediate result. Finish the user's requested outcome: for implementation, integrate the work, run relevant checks, and resolve failures caused by the changes. Preserve valid completed work and expand validation only for new changes, failures, or unresolved concerns. Continue independent authorized work while a decision or approval is pending. Delegation grants no additional permission; apply the active approval requirements to every assigned action.

## Conditional references

- Read [routing-and-task-packets.md](references/routing-and-task-packets.md) when context selection, task boundaries, independent review, or bounded nested delegation needs more guidance.
- Read [runtime-compatibility.md](references/runtime-compatibility.md) when role selection, model or effort fields, context inheritance, or recovery needs adaptation to the active interface.
