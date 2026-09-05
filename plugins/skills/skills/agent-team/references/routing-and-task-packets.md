# Routing and task packets

Use the model defaults in [SKILL.md](../SKILL.md). Read this reference when context selection, task boundaries, independent review, or bounded nested delegation needs more guidance.

## Assignment boundaries

Split by an independently answerable question, resource, or subsystem. Keep tightly coupled work with the agent that has the relevant context. A `worker` can implement code, investigate, or perform routine execution within its assigned scope.

Use `senior_worker` for a difficult independent problem. If the difficulty comes from dependencies on the main agent's ongoing decisions, keep that work in the main agent. When a child encounters uncertainty that changes scope, permissions, or a shared interface, have it return the evidence and the specific decision needed. The main agent can resolve that decision, take over, or reassign the remaining bounded work at an appropriate capability level. Preserve useful findings when doing so.

Name assignments `<job>_<scope>`, such as `scout_auth`, `worker_cache`, or `senior_reviewer_migration`. Names identify work and ownership; select models through the active interface.

## Context selection

Use `fork_turns: "none"` for a self-contained assignment. Include the relevant user decisions, authorization boundaries, constraints, paths, and inputs in its task packet.

Use a positive `fork_turns` count when recent turns contain decisions or source material that would be risky to restate. Use `fork_turns: "all"` when the full history is necessary. Check whether the runtime requires full-history children to inherit model and effort before constructing the call; see [runtime-compatibility.md](runtime-compatibility.md).

For independent review, provide the requirements, artifacts, relevant constraints, and validation evidence. Let the reviewer form its own conclusion without supplying the author's preferred verdict. Preserve necessary user context even when fresh context is impractical.

## Task packet

Use a concise packet with these contents; the headings are optional:

```text
Outcome: <one concrete result and the role doing it>
Ownership: <files, resources, or questions; leaf unless bounded delegation is assigned>
Context and permissions: <needed inputs, user decisions, exact authorization basis, and constraints>
Acceptance: <observable criteria and relevant checks; finish when these are met>
Return: <result, decisive evidence or changed paths, validation outcome, and unresolved decisions>
```

For leaves, explicitly say to complete the assignment directly without spawning agents. State which resources and actions are authorized, including local edits and checks when relevant. For implementation, acceptance includes running the relevant checks and fixing failures caused by the assigned changes. For review, acceptance is an evidence-backed assessment of the assigned scope. A child may resolve routine details and report assumptions; return the specific decision needed when missing information prevents correct or authorized progress, while completing independent work that remains possible.

## Independent review and integration

Use `reviewer` for routine, directly verifiable changes and `senior_reviewer` for complex concurrency, security boundaries, data integrity, cross-component reasoning, or consequential uncertainty. Select the appropriate role directly. When a completed review leaves a difficult question unresolved, give a senior reviewer that question and its evidence, preserving the valid completed checks. Both return findings as read-only leaves; assign implementation fixes to the main agent or a worker within the user's scope.

Ask for actionable findings with evidence, a trigger or counterexample, and an explanation of the consequence. Distinguish observed failures from unverified concerns. The main agent resolves disagreements using the artifacts and evidence, then validates the integrated result against current requirements.

Keep returned evidence compact enough to act on. Raw transcripts are useful only when a specific diagnostic requires them. Report checks that could not run and uncertainties that remain.

## Bounded nested delegation

The main agent may explicitly authorize a `senior_worker` to coordinate at most two independent leaf children when that local coordination has a clear benefit. Specify the allowed child scopes and remaining concurrency budget in its packet. This is delegation authority within the already authorized task; it does not grant additional permission to change resources.

Include the pre-spawn announcement rule from [SKILL.md](../SKILL.md) in that packet. If the child's updates are not user-visible, have the main agent relay the model and effort announcement before the descendant is spawned.

Keep descendant writes disjoint from each other and from work elsewhere in the team. Agents may exchange specific dependency evidence directly; decisions that change scope or shared interfaces return to the main agent. Propagate requirement changes and cancellations to affected descendants, and confirm their writers have stopped before transferring ownership.
