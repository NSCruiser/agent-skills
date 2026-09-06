# Routing and task packets

Choose roles using [SKILL.md](../SKILL.md) and apply their bundled settings. Read this reference when context selection, task boundaries, independent review, or bounded nested delegation needs more guidance.

## Assignment boundaries

Split by an independently answerable question, resource, or subsystem. Keep tightly coupled work with the agent that has the relevant context. Bound ownership and the useful outcome without pretending an exploratory solution is already known. A design packet can ask for a recommendation grounded in user goals, constraints, and alternatives; numerical acceptance criteria are not required for judgment-led work.

If the difficulty comes from dependencies on the main agent's ongoing decisions, keep that work in the main agent. An independent problem can still belong to `senior_worker` even when its framing or solution requires discovery. When uncertainty changes scope, permissions, or a shared interface, return the evidence and the specific decision needed to the main agent. Follow the handoff and reassignment guidance in [SKILL.md](../SKILL.md), preserving useful findings and completed checks.

Name assignments `<role>_<scope>`, such as `scout_auth`, `worker_cache`, or `senior_reviewer_migration`. Names identify work and ownership; apply the selected role's settings through the active interface.

## Routing examples

These examples assume the assignment passes the delegation benefit test. Apply the same reasoning when keeping work in the main agent.

| Assignment | Selection and reason |
|---|---|
| Assess whether a proposed design has the right aesthetic quality for its purpose. | `senior_reviewer`: assess quality using context and judgment beyond mechanical checks. |
| Implement an agreed workflow across several components, with behavior and interfaces specified. | `worker`: substantial, careful implementation within a settled direction. |
| Apply supplied terminology replacements across a batch of resource files with explicit exclusions and a cheap diff check. | `light_worker`: low-stakes repetition with supplied rules. |
| “Translate this campaign so it feels native and persuasive.” | `senior_worker`: creative intent and audience judgment are unresolved; the label “translation” does not make it mechanical. |
| Collect references and call sites for a named API to answer a defined compatibility question. | `scout`: bounded evidence collection. If the deliverable includes implementation analysis, use `worker`. |
| “Latency became erratic after the migration; determine which subsystem or assumption is responsible.” | `senior_worker`: uncertain cause and interacting evidence need hypothesis selection and synthesis. |
| Review a one-line authorization change that may affect tenant isolation. | `senior_reviewer`: consequential reasoning across a security boundary outweighs the small diff. |
| Review an implementation against a settled contract and existing checks. | `reviewer`: systematic correctness and requirements coverage. |
| Conflicting evidence supports incompatible system strategies; a consequential choice hinges on exceptionally unclear assumptions that normal analysis has not resolved. | `advisor`: a focused, read-only verdict on the decisive tradeoff, only when its expected value warrants the extra cost. |

## Context selection

Use the context policy in [SKILL.md](../SKILL.md). Include the relevant user decisions, authorization boundaries, task-specific tool and safety restrictions, paths, and inputs in a fresh-context packet. For roles that permit inheritance, useful prior decisions, evidence, or exploration can justify inherited turns when they improve the result or reduce total cost; see [runtime-compatibility.md](runtime-compatibility.md) for supported fields and inheritance constraints.

For independent review, provide the requirements, artifacts, relevant constraints, and validation evidence. Let the reviewer form its own conclusion without supplying the author's preferred verdict. Preserve necessary user context even when fresh context is impractical.

## Task packet

Use a concise packet with these contents; the headings are optional:

```text
Outcome: <one concrete result and the role doing it>
Ownership: <files, resources, or questions; leaf unless bounded delegation is assigned>
Context and permissions: <user purpose, needed inputs, settled decisions, open questions, exact authorization basis, and constraints>
Acceptance: <observable criteria and relevant checks, or evidence and tradeoffs needed to assess an exploratory result>
Return: <result, decisive evidence or changed paths, validation outcome, and unresolved decisions>
```

For leaves, explicitly say to complete the assignment directly without spawning agents. State which resources and actions are authorized, including local edits and checks when relevant. Give a `worker` the purpose and settled constraints so it can check implementation against the larger goal. A `light_worker` needs supplied rules and an instruction to return unmatched cases instead of inventing missing rules. Give a `senior_worker` the desired outcome, evidence, and constraints with room to choose the approach.

For implementation, acceptance includes running the relevant checks and fixing failures caused by the assigned changes. For review, acceptance is an evidence-backed assessment of the assigned scope. A child may resolve routine details and report assumptions; return the specific decision needed when missing information prevents correct or authorized progress, while completing independent work that remains possible.

## Independent review, advice, and integration

Use `reviewer` for directly verifiable correctness and coverage within a settled frame. Use `senior_reviewer` when assessing the frame itself, design quality, complex concurrency, security boundaries, data integrity, cross-component reasoning, or consequential uncertainty. Select the appropriate role directly. When a completed review leaves a difficult question unresolved, give a senior reviewer that question and its evidence, preserving the valid completed checks. Both return findings as read-only leaves; assign implementation fixes to the main agent or a suitable worker within the user's scope.

Use `advisor` only when the focused question meets the exceptional difficulty and value threshold in [SKILL.md](../SKILL.md). Give it the actual decision and competing evidence rather than commissioning another full review. An advisory verdict may identify insufficient evidence or a user preference that must be resolved; it does not grant authority to change the user's requirements or permissions.

Ask for actionable findings with evidence, a trigger or counterexample, and an explanation of the consequence. Distinguish observed failures from unverified concerns. The main agent resolves disagreements using the artifacts and evidence, then validates the integrated result against current requirements.

Keep returned evidence compact enough to act on. Raw transcripts are useful only when a specific diagnostic requires them. Report checks that could not run and uncertainties that remain.

## Bounded nested delegation

The main agent may explicitly authorize a `senior_worker` to coordinate at most two independent leaf children when that local coordination has a clear benefit. Specify the allowed child scopes and remaining concurrency budget in its packet. This is delegation authority within the already authorized task; it does not grant additional permission to change resources.

Include the pre-spawn announcement rule from [SKILL.md](../SKILL.md) in that packet. If the child's updates are not user-visible, have the main agent relay the model and effort announcement before the descendant is spawned.

Keep descendant writes disjoint from each other and from work elsewhere in the team. Agents may exchange specific dependency evidence directly; decisions that change scope or shared interfaces return to the main agent. Propagate requirement changes and cancellations to affected descendants, and confirm their writers have stopped before transferring ownership.
