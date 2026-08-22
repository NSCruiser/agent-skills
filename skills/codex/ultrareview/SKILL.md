---
name: ultrareview
description: Run a read-only adversarial code review in four single-pass stages with independent reviewers, deduplication, refutation, and final judgment. Use only when the user explicitly requests Ultrareview for a code change or clearly bounded code topic and subagent capacity is available. Do not use for ordinary implementation, unbounded repository audits, or implicit follow-up review.
---

# Ultrareview

Run one high-confidence, read-only review while keeping detailed intermediate findings out of the main agent's context. Do not modify repository files, create commits, push branches, post remote comments, or perform another external mutation.

Never invoke or reinvoke Ultrareview implicitly. Each new semantic run requires explicit user permission naming or clearly requesting Ultrareview. Permission for one run does not authorize a later rerun; an operational retry of a failed task inside the already-authorized run is not a new semantic run.

Read the applicable repository instruction files and [references/pipeline-protocol.md](references/pipeline-protocol.md) before starting. The packaged coordinator owns the fixed mechanics; read [references/pipeline-schemas.json](references/pipeline-schemas.json) only when diagnosing or changing the contract.

## Workflow

The workflow has exactly one semantic round in each applicable stage:

1. Independent adversarial review through useful, non-overlapping lenses.
2. One fresh deduplicator that merges only true duplicates and never decides validity.
3. Fresh refuters covering every canonical candidate exactly once.
4. Fresh judges covering every disputed candidate exactly once.

Do not add another review round, extra refuters, extra judges, or a second Ultrareview run automatically. Agents within one stage may run in parallel. When capacity is limited, batch related assignments so the stage still completes in one round.

## Start a run

Create the isolated run directory with the packaged bootstrap rather than writing a coordinator:

```bash
python3 <skill-root>/scripts/bootstrap_run.py --repository <repository-path>
```

The bootstrap creates the fixed directory layout outside the repository and copies `pipeline.py`, the v3 Schema, and stage instruction templates. The main agent then writes only the run-specific `scope.json` and `lenses.json` reported by the bootstrap.

`scope.json` must precisely define the authorized change or topic, exclusions, applicable instruction files, finding standard, and baseline worktree status. `lenses.json` must split that scope into useful lanes without inventing additional scope. Use `schema_version: 3` for both.

Run `<run-root>/pipeline.py init`, schedule the emitted packets, and use the coordinator commands in the protocol between stages. Supply the current available worker count to the refutation and judgment packet creation commands; do not hardcode machine capacity into the skill or coordinator.

Every intermediate agent is a leaf and must not delegate. Prefer `fork_turns: "none"` and start it with only:

```text
Read and follow <packet-path>. Work read-only and do not delegate. Write JSON that follows the fixed schema to <output-path>. Do not include findings or evidence in your reply. Reply only with the required ARTIFACT_WRITTEN or ARTIFACT_FAILED receipt.
```

Each agent must execute the packet's complete `validation_command` argv before returning `ARTIFACT_WRITTEN`; it must not reconstruct or guess the coordinator command.

## Context boundary

Detailed findings move only through artifacts under the run directory. The main agent may read:

1. `scope.json` and `lenses.json`, which it authored.
2. Compact receipts and coordinator status output.
3. `final/final.json` after finalization.

The main agent must not open adversarial, deduplication, refutation, or judgment artifacts. It schedules agents and makes operational retry decisions without reading finding bodies. Use `pipeline.py status` to recover the current phase and packet paths after interruption or context compaction.

## Finding standard

Report only discrete, actionable problems supported by a demonstrable scenario or call path. Include correctness, security, meaningful performance or resource problems, and maintainability defects with concrete operational impact. Exclude style comments, speculative risks, intentional behavior, and suggestions whose complexity outweighs their likely value.

Every finding must include a concrete, intuitive `manifestation` that a human unfamiliar with the call path can follow. Use `verified_reproduction` only when the sequence was actually exercised and the finding includes verified `test` or `command` evidence; otherwise use `reasoned_scenario` and do not imply experimental verification. State the real setup, ordered user/system actions, and the exact visible or observable failure. Do not merely restate the trigger or impact in more words, and do not use placeholders such as “the issue occurs.”

For a change review, inspect the complete merge-relevant diff plus enough surrounding source, tests, and callers to show that each finding was introduced by the change. Cite a tight line range overlapping the diff. For a topic review, require the issue to fall inside the named scope.

Use `P0` for universal release blockers or critical failures, `P1` for urgent defects, `P2` for ordinary defects worth fixing, and `P3` for useful low-impact defects. Preserve exact evidence and distinguish verified facts from inference.

## Failure handling

There is no automatic retry. When an agent or transition fails, the main agent explicitly chooses to retry the failed task, rerun the incomplete stage, or stop and report an incomplete review. Do not advance past an incomplete stage. Use `retry-packet` so every retry receives a new task ID, attempt, packet, and output path; never reuse a stale artifact.

An operational retry repairs execution and does not solicit another semantic opinion. Do not convert an execution failure into a coverage gap.

## Final verification and response

After `finalize`, run `validate-final`, then read only `final.json`. Inspect the cited source needed to verify that each upheld, rejected, and unresolved item is in scope, cites an existing tight line range, and has a proportionate final disposition. Confirm that every manifestation is concrete and internally consistent and that each `verified_reproduction` is supported by verified test/command evidence. Do not reopen the full debate.

Present upheld findings in priority order using:

`[P1] Clear action-oriented title: path/to/file.ext:line`

1. **Context:** Where the code runs and how the issue is reached.
2. **How it manifests / how to reproduce:** Clearly label it as a verified reproduction or reasoned scenario, then give the setup, numbered steps, and exact failure a person should observe. Prefer concrete names, values, timing, and state transitions over internal shorthand.
3. **What goes wrong:** The behavior and concrete impact.
4. **Independent challenge:** Give the strongest concrete reason the finding might be wrong, overstated, unreachable, or not worth the proposed remedy, plus the refuter's verdict. Do not hide an upheld challenge merely because the finding survives.
5. **Final judgment:** State whether the binding decision came from refutation or judgment, the final verdict, the decisive basis, and the evidence used. Make clear which disputed points were resolved and which uncertainty remains.
6. **Recommendation:** The smallest proportionate change and focused verification.

Use the matching `review_records` entry as the audit source for every candidate. Its `case_for` preserves the original positive case, `challenge` preserves the independent counter-analysis and evidence, and `final_judgment` preserves the binding basis and evidence. Do not collapse these into an unsupported one-line conclusion.

Then present every entry from `rejected_findings` in a separate **Rejected/refuted candidates** section. Include its ID, original priority/title/location, the original manifestation/reproduction sequence and claimed impact, the strongest challenge, and the final rejection basis. Make clear that it is not an actionable surviving finding; do not silently omit it.

Then present every entry from `unresolved_findings` with its ID, priority/title/location, manifestation/reproduction sequence, case for, challenge, resolved points, and non-empty residual risk so a human can make the remaining judgment.

Finally report a short overall assessment, material coverage gaps, trace counts, and the `final.json` path so the structured decision history can be revisited. If no finding survives, say `No findings.` while still presenting rejected candidates, unresolved findings, coverage, and trace counts.
