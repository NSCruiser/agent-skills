---
name: ultrareview
description: Run a read-only adversarial code review through independent review, deduplication, Ponytail-guided refutation, and selective final judgment. Use only when the user explicitly requests Ultrareview for a bounded code change or topic and the runtime can launch isolated workers. Do not use for ordinary implementation, unbounded repository audits, or implicit follow-up review.
---

# Ultrareview

Run one high-confidence, read-only review while keeping detailed intermediate findings out of the orchestrator's context. Do not modify repository files, create commits, push branches, post remote comments, or perform another external mutation.

Never invoke or reinvoke Ultrareview implicitly. Each new semantic run requires explicit user permission naming or clearly requesting Ultrareview. Permission for one run does not authorize a later rerun; an operational retry of a failed task inside the already-authorized run is not a new semantic run.

Read the applicable repository instruction files and [references/pipeline-protocol.md](references/pipeline-protocol.md) before starting. The packaged coordinator owns the fixed mechanics; read [references/pipeline-schemas.json](references/pipeline-schemas.json) only when diagnosing or changing the contract.

## Workflow

The workflow has exactly one semantic round in each applicable stage:

1. Independent adversarial review through useful, non-overlapping lenses.
2. One fresh deduplicator that merges only true duplicates and never decides validity.
3. Fresh refuters covering every canonical candidate exactly once.
4. Fresh judges independently deciding only candidates whose refuter returned `modify`, `refute`, or `unresolved`. A refuter `uphold` is binding and bypasses judgment.

Do not add another review round, extra refuters, extra judges, or a second Ultrareview run automatically. Workers within one stage may run in parallel. The coordinator balances candidate IDs across the selected worker count so the stage still completes in one round.

Choose the smallest useful worker set at every stage. A narrow change may need one review lens; broader changes may justify several genuinely distinct lenses. One refuter or judge may handle several candidates. Runtime capacity is a ceiling, not a target: do not invent lenses or spawn one worker per candidate merely to occupy available slots.

## Runtime portability

The pipeline, packets, and artifact contracts are runtime-independent and require Python 3, Git, JSON, a shared filesystem, and a harness that can launch and wait for isolated worker tasks. Map the terms *orchestrator*, *worker*, *launch*, and *wait* to the active harness's equivalents. Give each worker only its packet prompt and keep detailed results in artifacts, not task replies. Use a fresh context when the harness supports one; otherwise rely on the self-contained packet rather than copying the parent conversation.

In Codex, launch packet workers with `spawn_agent`, prefer `fork_turns: "none"`, and use the collaboration wait/status primitives. Count the orchestrator and all active workers against the reported concurrency limit. These are Codex-specific optimizations, not requirements for other harnesses. Every intermediate worker is a leaf and must not delegate in any runtime.

## Start a run

Create the isolated run directory with the packaged bootstrap rather than writing a coordinator:

```bash
python3 <skill-root>/scripts/bootstrap_run.py \
  --repository <repository-path> \
  --ponytail-review-skill <current-ponytail-review-SKILL.md>
```

Resolve the currently active `ponytail-review` skill from the harness's available skill catalog. Stop before bootstrap and report the missing dependency when it is unavailable; do not substitute copied Ponytail prose or a versioned cache path. The bootstrap snapshots that `SKILL.md` under the run directory so future runs pick up plugin updates while an active run stays reproducible.

The bootstrap creates the fixed directory layout outside the repository, records the resolved `--repository` in `repository.json`, and copies `pipeline.py`, the frozen Ponytail policy, the v5 Schema, and stage instruction templates. The orchestrator then writes only the run-specific `scope.json` and `lenses.json` reported by the bootstrap.

`scope.json` must precisely define the authorized change or topic, output language, exclusions, applicable instruction files, finding standard, and baseline worktree status. Set `output_language` to the language explicitly requested by the user, or otherwise the language of the user's request. Write human-readable scope, lane, and focus text in that language. Its absolute `repository_path` must match `repository.json`. Record `baseline_worktree_status` immediately before `init` as the exact output lines from `git -C <repository-path> status --short --untracked-files=all`.

When callers, contracts, or implementation details needed as supporting evidence live in another Git repository, add that repository root to optional `evidence_repositories` as `{ "repository_path": <absolute-root>, "baseline_worktree_status": [...] }`. Record each status with the same command immediately before `init`. Finding locations remain in the reviewed repository; cross-repository evidence and reachability locations must be absolute, current-side paths inside a declared evidence repository. Cite other external material with `location: null` and a concrete reference. The coordinator freezes every declared evidence repository's HEAD, staged and unstaged diff, and untracked contents just like the reviewed repository.

`lenses.json` must split the scope into useful lanes without inventing additional scope. Use `schema_version: 5` for both.

At `init`, the coordinator fixes hashes for `scope.json`, `lenses.json`, `repository.json`, the frozen Ponytail policy, the Schema, stage instructions, and the copied pipeline, and fingerprints the reviewed repository plus every declared evidence repository. Any later change to scope, output language, lenses, Ponytail policy, repository snapshots, or another runtime contract resource invalidates the run; start a newly authorized semantic run instead of editing an active one.

The coordinator rejects Git-visible worktree drift before artifact validation, stage transitions, retries, finalization, and final validation. Treat a mismatch as an incomplete review; report it and do not restore or alter the repository. Use a genuinely read-only filesystem sandbox when the harness offers one because Git status detection does not prevent writes or cover ignored files.

Run `<run-root>/pipeline.py init`, schedule the emitted packets with the active harness, and use the coordinator commands in the protocol between stages. For the refutation and judgment packet creation commands, `--workers` is a maximum: choose it from the visible candidate count, scope breadth, expected inspection cost, and available slots. Prefer one for a small or coherent scope and increase it only when parallel inspection is worth the coordination overhead. Do not pass full capacity by default or hardcode machine capacity into the skill or coordinator.

Start every intermediate worker with only:

```text
Read and follow <packet-path>. Work read-only and do not delegate. Write JSON that follows the fixed schema to <output-path>. Do not include findings or evidence in your reply. Reply only with the required ARTIFACT_WRITTEN or ARTIFACT_FAILED receipt.
```

Each worker must execute the packet's complete `validation_command` argv before returning `ARTIFACT_WRITTEN`; it must not reconstruct or guess the coordinator command.

## Context boundary

Detailed findings move only through artifacts under the run directory. The orchestrator may read:

1. `scope.json` and `lenses.json`, which it authored.
2. Compact receipts and coordinator status output.
3. `final/final.json` after finalization.

The orchestrator must not open adversarial, deduplication, refutation, or judgment artifacts. It schedules workers and makes operational retry decisions without reading finding bodies. Use `pipeline.py status` to recover the current phase and packet paths after interruption or context compaction.

## Finding standard

Report a candidate only when all of these are true:

- It has a meaningful correctness, security, performance, resource, or maintainability impact.
- It is discrete and actionable.
- For a change review, it was introduced by the reviewed change; for a topic review, it falls inside the named scope.
- The affected scenario or call path can be demonstrated from source, callers, contracts, tests, or verified execution.
- The author would probably fix it if they knew about it.

Exclude speculative concerns, pre-existing problems, intentional behavior changes, style nits that do not obscure behavior, dead or unreachable paths, test-only paths outside scope, unsupported configurations, states blocked by existing guards, completed migrations, and remedies whose complexity or maintenance cost outweighs their likely value. Continue through the complete assigned scope after finding an issue; do not stop at the first candidate.

Refuters and judges must record the v5 `qualification` gate and `ponytail_assessment`. Refuters actively use the frozen Ponytail policy to decide whether a finding is over-defensive or its proposed remedy is over-engineered. Judges independently repeat that assessment only for challenged candidates. A result is actionable only when reachability, authorized scope, material impact, fix value, and likely author action all pass, and change reviews also prove introduction by the reviewed diff. A disqualifying value binds to refute/reject; uncertainty binds to unresolved. Uphold and modify require verified reachability evidence from a caller, test, command, or contract. The coordinator rejects artifacts whose verdict contradicts these gates.

Every finding must include a concrete, intuitive `manifestation` that a human unfamiliar with the call path can follow. Use `verified_reproduction` only when the sequence was actually exercised and the finding includes verified `test` or `command` evidence; otherwise use `reasoned_scenario` and do not imply experimental verification. State the real setup, ordered user/system actions, and the exact visible or observable failure. Do not merely restate the trigger or impact in more words, and do not use placeholders such as “the issue occurs.” Use `location.side: new` for added or current lines and `location.side: old` for deletion-only lines from the comparison base.

For a change review, inspect the complete merge-relevant diff plus enough surrounding source, tests, callers, and declared cross-repository evidence to show that each finding was introduced by the change. For a base-branch target, resolve its configured upstream when that upstream exists and is ahead of the local branch; otherwise use the local branch, compute `git merge-base HEAD <comparison-ref>`, and store the resulting full immutable commit OID in `scope.comparison_base`. Symbolic refs and short OIDs are rejected. If the local branch cannot be resolved, try its configured upstream explicitly before declaring the target unavailable. Cite a tight finding range inside the reviewed repository that overlaps the diff; cross-repository paths may support the finding but may not become its primary location. For a topic review, require the issue to fall inside the named scope.

Use `P0` for universal release blockers or critical failures, `P1` for urgent defects, and `P2` for ordinary defects the author is likely to fix now. Do not emit low-impact advisory findings. Preserve exact evidence and distinguish verified facts from inference.

## Failure handling

There is no automatic retry. When a worker or transition fails, the orchestrator explicitly chooses to retry the failed task, rerun the incomplete stage, or stop and report an incomplete review. Do not advance past an incomplete stage. Use `retry-packet` so every retry receives a new task ID, attempt, packet, and output path; never reuse a stale artifact.

An operational retry repairs execution and does not solicit another semantic opinion. Do not convert an execution failure into a coverage gap.
Only a valid semantic `uphold` bypasses judgment. A failed or missing refutation artifact leaves the review incomplete and never counts as an uphold.

## Final verification and response

After `finalize`, run `validate-final`, then read only `final.json`. Inspect the cited source needed to verify that each upheld, rejected, and unresolved item is in scope, cites a tight valid range on the declared current or comparison-base side, and has a proportionate final disposition. Confirm that cross-repository supporting locations belong to declared, unchanged evidence repositories, every manifestation is concrete and internally consistent, and each `verified_reproduction` is supported by verified test/command evidence. Do not reopen the full debate.

Write every part of the response, including headings and stock phrases, in `scope.output_language`. Do not leak fixed English labels into another-language response. Keep only code symbols, paths, commands, identifiers, and priority codes in their original form.

Present upheld findings in priority order using:

`[P1] <clear action-oriented title>: path/to/file.ext:line`

For `location.side: old`, append a short natural-language label in `scope.output_language` saying that the location is from `scope.comparison_base` before deletion. Do not render an old-side path as though it were a current clickable file location. New-side findings need no side label.

Explain each finding at an ELI5 level: use short sentences, everyday cause-and-effect, and enough concrete setup that a person unfamiliar with the code can understand it without tracing the call graph. Avoid unexplained internal shorthand. Choose natural section labels in `scope.output_language` rather than translating or copying a fixed template. Cover these ideas:

1. Where the code runs and how a real user or system reaches it.
2. A verified reproduction or reasoned scenario with setup, ordered steps, and the exact observable failure.
3. What the user or system experiences and why it matters.
4. The binding refuter or judge basis, the smallest proportionate fix, and a focused verification.

When the refuter verdict is `uphold`, omit the independent-challenge section by default because the independent check agreed with the finding. When the refuter returned `modify`, `refute`, or `unresolved` but the judge retained a finding, include the strongest challenge and explain in plain language how the judge resolved it.

Use the matching `review_records` entry as the audit source for every candidate. Its `case_for` preserves the original positive case, `challenge` preserves the independent counter-analysis, Ponytail assessment, and evidence, and `final_judgment` records whether the binding source was refutation or judgment. Do not collapse these into an unsupported one-line conclusion.

Do not expand rejected candidates in the normal response. Report only their count and concise rejection-reason categories in `scope.output_language`; keep their complete audit trail in `final.json`. Expand them only when the user asks.

Present unresolved candidates separately from findings, in `scope.output_language`, only when their residual risk is material enough to require a human decision. Explain the known facts, the missing fact, and the decision the human needs to make at the same ELI5 level.

Finally report a short overall assessment, material coverage gaps, trace counts, and the `final.json` path so the structured decision history can be revisited. If no finding survives, use the natural equivalent of “no actionable findings” in `scope.output_language`; do not emit the English phrase `No findings.` unless English is the requested language.
