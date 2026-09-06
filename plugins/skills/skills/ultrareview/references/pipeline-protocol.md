# Pipeline protocol

Read this reference before creating an Ultrareview run. The protocol keeps detailed intermediate results out of the orchestrator's context while leaving execution decisions with the orchestrator.

## Runtime mapping

The coordinator scripts and artifacts are portable across harnesses. The active harness needs Git and Python 3, must launch isolated worker tasks and wait for their completion, and must give every worker access to the same temporary run directory and reviewed repository. Map those operations to the harness's native task primitives; no Codex tool name or parameter is part of the protocol contract.

Every adversarial, deduplication, refutation, and judgment worker, including every retry, defaults to the main agent's current model and reasoning effort. Only an explicit user request authorizes an override; another skill's role-based model defaults do not apply. Fresh context changes history exposure, not model configuration. Use the active harness's supported inheritance mechanism. If it cannot confirm or preserve either setting, disclose the actual known state and limitation; do not silently substitute settings or claim verified inheritance without runtime evidence.

When fresh worker contexts are supported, use them. If a harness has no context-control field, send only the self-contained start prompt and packet path. In every harness, workers are leaves and task replies contain only compact receipts.

Codex only: use `spawn_agent` with mandatory `fork_turns: "none"` and the collaboration wait/status primitives; omit model and reasoning overrides when the active tool contract supports inheritance. Count the orchestrator and all active workers against Codex's reported concurrency limit. These tool names and parameters do not apply to other harnesses. Fresh context alone does not prove model inheritance.

## Context boundary

Use one fresh temporary run directory outside the repository. Create it with `scripts/bootstrap_run.py`; do not author or adapt a coordinator for an individual run. Workers write detailed results to files under that directory. Their messages to the orchestrator contain status only.

The orchestrator may read:

1. `scope.json` and `lenses.json`, which it authored.
2. Compact worker receipts and coordinator status lines.
3. `final/final.json` after the coordinator finalizes the run.

The orchestrator must not open or quote files under the intermediate artifact directories.

## Run layout

```text
<run-root>/
|-- pipeline.py
|-- repository.json
|-- scope.json
|-- lenses.json
|-- pipeline-schemas.json
|-- stage-instructions.json
|-- packets/
|   |-- adversarial/
|   |-- dedup/
|   |-- refutation/
|   `-- judgment/
|-- artifacts/
|   |-- adversarial/
|   |-- dedup/
|   |-- refutation/
|   `-- judgment/
`-- final/
    `-- final.json
```

The bootstrap script binds the resolved repository path in `repository.json` and copies the packaged coordinator, fixed Schema, and stage instructions without changing them. `scope.repository_path` must be absolute and resolve to that binding. Give each task a unique packet path and output path. Resolve paths before use and reject any path outside the run directory. Reject artifact symlinks. Write coordinator-generated files atomically with a temporary sibling and `os.replace`.

At `init`, hash `repository.json`, `scope.json`, `lenses.json`, `pipeline-schemas.json`, `stage-instructions.json`, and the copied `pipeline.py`. Hash each generated current packet as well. Every later coordinator command rejects a changed contract resource or current packet; scope, output language, lenses, instructions, and assignments cannot drift inside one authorized run.

New scopes must explicitly include `effective_instructions`: an array of non-empty strings, with `[]` allowed. Capture existing authorization, effective user constraints, and applicable external or symlinked instruction-file rules after the orchestrator reads them; retain the necessary rules rather than the entire conversation. Resolve conflicts with skill or repository guidance in favor of user instructions, subject to higher-priority runtime rules, and report genuine remaining conflicts. Preserve an existing user language preference when setting `output_language`; infer language from the current request only when no explicit preference applies. Older v4 scopes may omit `effective_instructions`, which workers treat as `[]`.

`instruction_files` remains limited to readable, absolute, non-symlink files inside the reviewed repository. Applicable rules outside that boundary belong in `effective_instructions`, not in additional worker file paths. The scope hash protects this snapshot, but the original external rules are not tracked for later drift. A change to effective constraints requires a newly authorized run rather than an edit to the active scope.

Record `scope.baseline_worktree_status` as the exact output lines from `git -C <repository> status --short --untracked-files=all` immediately before `init`. When supporting evidence lives in another Git repository, add its absolute root and exact status to optional `scope.evidence_repositories`. The reviewed finding location remains in `scope.repository_path`; evidence and qualification reachability steps may use absolute, current-side paths inside a declared evidence repository. Relative paths always resolve inside the reviewed repository. Material outside these Git roots uses `location: null` plus a concrete reference.

At `init`, the coordinator fingerprints HEAD, staged and unstaged binary diffs, and non-ignored untracked contents for the reviewed repository and every declared evidence repository. It compares each status and fingerprint before validating artifacts, advancing stages, retrying, finalizing, and validating the final payload. Stop on the corresponding worktree or snapshot drift error; do not repair or restore any repository. This detects Git-visible drift but is not a substitute for a read-only filesystem sandbox.

## Fixed schemas

[pipeline-schemas.json](pipeline-schemas.json) defines the exact version 4 contracts for `scope.json`, `lenses.json`, task packets, all four stage artifacts, and `final.json`. Do not change these contracts for a particular review.

Every raw, canonical, replacement, final, rejected, or unresolved finding carries the same required `manifestation` object. It distinguishes an actually verified reproduction from a reasoned scenario and records a concrete setup, ordered steps, and exact observable failure. Generic restatements of `trigger` or `impact` do not satisfy this contract.

The coordinator must check required fields, allowed values, unknown fields, unique IDs, source mappings, and line ranges. It may use an installed JSON Schema validator. Otherwise, implement the needed checks directly with the Python standard library. Do not install a dependency for a review run.

JSON Schema cannot express every relationship between records. The coordinator must also enforce these invariants:

1. Agent IDs, task IDs, raw candidate IDs, and canonical IDs are unique in their own sets.
2. Every worker artifact's agent ID matches its packet. An adversarial artifact's lane also matches its packet and lens assignment. The coordinator's one-to-one canonical artifact uses `agent_id: coordinator` and has no worker packet.
3. Every raw candidate ID begins with its agent ID followed by `:C` and at least two digits.
4. Every canonical finding ID matches `F###`.
5. The canonical candidates' `source_candidate_ids` lists do not overlap, and their union equals the complete raw candidate ID set.
6. A replacement or final finding keeps the same ID as its `candidate_id`.
7. Each refutation and judgment assignment is covered exactly once.
8. Every worker artifact's task ID and attempt match the packet that assigned its output path.
9. Every location has `end_line` greater than or equal to `start_line` and declares side `new` or `old`; old-side locations are allowed only for change reviews and are resolved from `scope.comparison_base`.
10. Every finding has at least one non-empty manifestation step and a non-empty setup and failure result.
11. A `verified_reproduction` has at least one verified `test` or `command` evidence record; vague placeholders are rejected.
12. Every refutation and judgment result carries `qualification`. A disqualifying gate maps to refute/reject, an uncertain gate maps to unresolved, and only a fully passing gate maps to uphold or modify.
13. A qualifying refutation or judgment contains verified caller, test, command, or contract evidence and a non-empty reachability path. Every evidence item has a concrete reference; qualifying caller and contract evidence also has a repository source location.
14. Human-facing artifact prose uses `scope.output_language`; fixed JSON enums, code symbols, paths, identifiers, and commands remain unchanged.
15. For change reviews, every primary finding range identifies the changed cause and overlaps the matching new- or old-side range in `git diff --unified=0 <comparison_base> -- <path>`. Unchanged code where the failure manifests belongs in supporting evidence. Enforce this during artifact validation and again during final validation; deletion-only findings use the old side.
16. `scope.instruction_files` contains absolute, readable, non-symlink files that resolve inside the bound repository; invalid paths fail during `init` rather than in every worker.
17. All enum values are type-checked before membership checks, so malformed list or object values produce structured `VALIDATION_FAILED` output rather than a traceback.
18. Runtime contract hashes bind scope, output language, lenses, repository binding, Schema, stage instructions, and coordinator code from `init` through final validation.
19. Change-review `scope.comparison_base` is the full immutable commit OID returned by `git merge-base` or `git rev-parse`; symbolic refs and short OIDs are rejected before workers launch.
20. Every `scope.evidence_repositories` entry names a unique absolute Git repository root other than the reviewed repository and records its exact baseline worktree status. The coordinator fingerprints every declared repository at `init` and rejects later status, HEAD, diff, or untracked-content drift.
21. Primary finding and replacement-finding locations stay inside the reviewed repository. Supporting evidence and qualification reachability locations may additionally use an absolute path inside a declared evidence repository and must use side `new`; undeclared external paths and cross-repository old-side locations are rejected during artifact validation.
22. Every adversarial artifact records at least one inspected path and one completed check, including artifacts with no candidates.
23. Optional `scope.effective_instructions` is an array of non-empty strings, with an empty array allowed. Its contents are bound by the existing scope hash; absence in an older v4 scope means an empty snapshot.

The coordinator prints only status, counts, task IDs, packet paths, output paths, reason codes, and invalid field paths. It never prints findings, evidence, recommendations, raw JSON, or packet contents.

## One round per stage

Each stage has one semantic round:

1. Stage 1 assigns the selected review lenses once. Use only materially distinct lenses.
2. Stage 2 uses one fresh deduplicator only when Stage 1 used more than one reviewer and produced more than one raw candidate in total. Otherwise, the coordinator preserves every raw candidate one-to-one and assigns canonical IDs without launching a worker.
3. Stage 3 assigns each canonical candidate to one refuter. The coordinator balances IDs across the selected workers.
4. Stage 4 assigns every canonical candidate to one fresh judge using the same deterministic balancing.

Choose the smallest useful worker set rather than matching the harness's concurrency limit. A narrow review can use one reviewer, and one refuter or judge can cover multiple candidates. Because the orchestrator cannot read intermediate finding bodies, it chooses `--workers` only as a maximum from the visible record count, authorized scope breadth, expected inspection cost, and available slots; the coordinator partitions IDs deterministically. Prefer one for small or coherent work. Available slots are only a ceiling.

Do not schedule extra passes because a candidate is important, uncertain, or controversial. An orchestrator decision to rerun failed execution is an operational retry and does not add a new independent opinion.

## Task packets

Every packet follows the fixed `task_packet` Schema and contains the complete instructions the worker needs. A packet includes the worker ID, scope path, fixed Schema path, coordinator path, input artifact paths, assigned IDs, output path, complete `validation_command` argv, stage instructions, task ID, and attempt number.

Every packet must tell the worker to read `scope.json` first and apply `effective_instructions` (default `[]`), then read applicable files listed in `scope.instruction_files`. User instructions take precedence over skill or repository guidance, subject to higher-priority runtime rules; report genuine remaining conflicts. Workers may start with a fresh context and cannot rely on instructions already read by the orchestrator. The coordinator builds these instructions from the packaged `stage-instructions.json`; session-specific constraints belong in the effective-instruction snapshot, with review focus in scope or lenses and repository guidance in the applicable instruction files.

Use these stage instructions:

1. An adversarial packet names the assigned lane and requires direct inspection, at least one recorded inspected path and check, complete coverage of that lane, a concrete manifestation for every candidate, and an empty candidate list when no issue qualifies. It excludes pre-existing problems only in change reviews; existing defects inside a topic review's named scope remain eligible. It also distinguishes primary finding locations from supporting locations in declared evidence repositories.
2. When deduplication is applicable, a dedup packet requires complete raw ID coverage, merging only true duplicates, preserving the clearest accurate manifestation, and no decision on validity.
3. A refutation packet requires independent inspection of each assigned candidate and the necessary diff, source, callers, contracts, tests, and history; a complete qualification gate; and correctness, reachability, scope, impact, and proportionality analysis for every assigned canonical ID. Expand inspection only when the evidence is insufficient to decide the candidate.
4. A judgment packet independently repeats that candidate-focused inspection and qualification gate before one binding disposition for every assigned canonical ID, including candidates the refuter upheld and correction of an inaccurate finding when modifying it. Neither downstream stage repeats full-scope adversarial discovery.

## Coordinator commands

The packaged `pipeline.py` uses these commands and accepts only current-attempt paths supplied by the orchestrator:

1. `init` validates `scope.json` and `lenses.json`, then creates reviewer packets.
2. `seal-adversarial <artifact>...` validates the supplied current reviewer artifacts. It finalizes immediately when there are no raw candidates. It creates one deduplication packet only when there is more than one reviewer and more than one raw candidate; otherwise it writes a one-to-one canonical artifact and reports `STAGE_BYPASSED dedup`.
3. `start-refutation --workers N` creates at most `N` deterministically balanced refutation packets after the coordinator's one-to-one canonicalization path.
4. `accept-dedup --workers N <artifact>` validates complete source coverage and stable IDs, then creates at most `N` deterministically balanced refutation packets. Treat `N` as a useful maximum, capped by the dedup receipt's record count and available runtime slots.
5. `accept-refutation --workers N <artifact>...` validates one refutation result for every canonical candidate, then creates at most `N` deterministically balanced judgment packets covering every canonical candidate. Apply the same useful-maximum rule instead of passing total capacity by default.
6. `accept-judgment <artifact>...` validates one binding judgment for every canonical candidate.
7. `retry-packet <packet>` creates a packet with a new task ID, incremented attempt, and new output path. It never overwrites the old packet or artifact.
8. `finalize` writes `final/final.json` and prints its path plus trace counts.
9. `status` prints only the current phase and current packet/output paths so a compacted or resumed orchestrator task can recover safely.
10. `scaffold-artifact <packet>` optionally writes a top-level artifact skeleton to the packet's output path and refuses to overwrite an existing artifact.
11. `validate-artifact <packet> <artifact>` validates one worker artifact against its packet and current run state, including primary finding ranges and supporting source locations. Workers must execute the exact `validation_command` argv stored in their packet before sending a success receipt.
12. `validate-final` reconstructs and checks the final payload, then verifies that every upheld, rejected, and unresolved finding cites in-range source lines on the declared current or comparison-base side and that every supporting location belongs to the reviewed repository or a declared, unchanged evidence repository.

A transition succeeds only when all expected artifacts pass validation. The coordinator applies fixed routing rules and does not decide whether a finding is correct.

## Source mapping and routing

Raw candidate IDs include the agent ID, such as `reviewer-02:C03`. The applicable deduplicator or the coordinator's one-to-one path assigns stable IDs such as `F001`. Each canonical candidate lists its source raw IDs, and those lists form the complete non-overlapping mapping.

Use these routing rules:

1. Every refutation result goes to judgment; no Stage 3 verdict enters final assembly directly.
2. A judgment of `uphold` keeps the finding under judgment: the Stage 3 replacement when refutation returned `modify`, otherwise the canonical finding.
3. A judgment of `modify` uses the complete corrected finding.
4. A judgment of `reject` omits the finding from the upheld list and records the Stage 3 replacement finding when its verdict was `modify`, otherwise the canonical finding, plus the Stage 3 verdict and Stage 4 reason in `rejected_findings`.
5. A judgment of `unresolved` omits the finding from the upheld list and records the Stage 3 replacement finding when its verdict was `modify`, otherwise the canonical finding, plus the Stage 3 verdict, resolved points, and non-empty residual risk in `unresolved_findings`.
6. Every canonical candidate produces exactly one `review_records` entry whose final judgment source is Stage 4. The record preserves the original case, the refuter's qualification and analysis, the judge's qualification and binding basis, and the exact finding selected for presentation.

## Worker messages

After writing an artifact and successfully running `validate-artifact`, a worker replies with exactly:

```text
ARTIFACT_WRITTEN <stage> <task-id> <record-count> <output-path>
```

If it cannot complete the task, it replies with exactly:

```text
ARTIFACT_FAILED <stage> <task-id> <reason-code> <short-reason>
```

The short reason must not contain a finding, evidence, or raw artifact content. If the worker exits without a message, the harness's task failure status serves as the notification.

Use this start prompt:

```text
Read and follow <packet-path>. Work read-only and do not delegate. Write JSON that follows the fixed schema to <output-path>. Do not include findings or evidence in your reply. Reply only with the required ARTIFACT_WRITTEN or ARTIFACT_FAILED receipt.
```

## Failure decisions

There is no automatic retry and no `failure.json`. When a worker or transition fails, the orchestrator chooses one action:

1. Rerun the failed task.
2. Retry every still-current packet in the incomplete stage with `retry-packet`, accepting only the replacement attempts.
3. Stop and report that the review is incomplete.

Do not advance past an incomplete stage. Coverage gaps describe source or tool access limits reported by reviewers that completed successfully. They do not replace missing stage results.

When the orchestrator chooses a retry, run `retry-packet` for each affected current packet and use only the new packet and output path. A later transition receives the successful current artifact paths explicitly, so an older file cannot satisfy the retry. Retrying all current packets is the supported whole-stage rerun; it replaces execution attempts without adding a second accepted semantic opinion.

For a malformed artifact, the coordinator returns a compact line of this form:

```text
VALIDATION_FAILED <stage> <task-id> <reason-code> <field-path>...
```

The orchestrator may give those field paths to the responsible worker without reading or pasting the artifact.

## Final payload

The coordinator writes one `final.json` that follows the fixed Schema. It contains surviving findings, rejected findings, structured unresolved findings, Stage 1 coverage, trace counts, and one `review_records` audit entry for every canonical candidate. Each audit entry preserves both qualification decisions, the original case, the refuter's analysis and evidence, the judge's binding basis and evidence, and the exact finding selected for presentation. It must not contain raw candidates or redundant copies of complete intermediate artifacts. The coordinator records a SHA-256 digest when each stage artifact is accepted and rejects changed accepted inputs before downstream work. `validate-final` also rejects repository drift, reconstructs the expected payload from accepted artifacts, and requires exact equality before verifying primary finding locations against the reviewed diff and supporting locations against their declared repository snapshots.

Calculate trace values from unique canonical IDs:

1. `reviewers_completed` is the number of valid adversarial artifacts.
2. `raw_candidates` and `canonical_candidates` are the corresponding unique ID counts.
3. `refutation_results` and `judgment_results` both equal the canonical candidate count for a complete non-empty run.
4. `rejected_findings` counts final judge results of `reject`.
5. `unresolved` counts final judge results of `unresolved`.
6. `final_findings` is the number of findings retained after routing.

For a complete run, `canonical_candidates` equals `final_findings + rejected_findings + unresolved`.
