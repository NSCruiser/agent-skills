# Pipeline protocol

Read this reference before creating an Ultrareview run. The protocol keeps detailed intermediate results out of the main agent's context while leaving execution decisions with the main agent.

## Context boundary

Use one fresh temporary run directory outside the repository. Create it with `scripts/bootstrap_run.py`; do not author or adapt a coordinator for an individual run. Agents write detailed results to files under that directory. Their messages to the main agent contain status only.

The main agent may read:

1. `scope.json` and `lenses.json`, which it authored.
2. Compact agent receipts and coordinator status lines.
3. `final/final.json` after the coordinator finalizes the run.

The main agent must not open or quote files under the intermediate artifact directories.

## Run layout

```text
<run-root>/
|-- pipeline.py
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

The bootstrap script copies the packaged coordinator, fixed Schema, and stage instructions without changing them. Give each task a unique packet path and output path. Resolve paths before use and reject any path outside the run directory. Reject artifact symlinks. Write coordinator-generated files atomically with a temporary sibling and `os.replace`.

## Fixed schemas

[pipeline-schemas.json](pipeline-schemas.json) defines the exact version 3 contracts for `scope.json`, `lenses.json`, task packets, all four stage artifacts, and `final.json`. Do not change these contracts for a particular review.

Every raw, canonical, replacement, final, rejected, or unresolved finding carries the same required `manifestation` object. It distinguishes an actually verified reproduction from a reasoned scenario and records a concrete setup, ordered steps, and exact observable failure. Generic restatements of `trigger` or `impact` do not satisfy this contract.

The coordinator must check required fields, allowed values, unknown fields, unique IDs, source mappings, and line ranges. It may use an installed JSON Schema validator. Otherwise, implement the needed checks directly with the Python standard library. Do not install a dependency for a review run.

JSON Schema cannot express every relationship between records. The coordinator must also enforce these invariants:

1. Agent IDs, task IDs, raw candidate IDs, and canonical IDs are unique in their own sets.
2. Every artifact's agent ID matches its packet. An adversarial artifact's lane also matches its packet and lens assignment.
3. Every raw candidate ID begins with its agent ID followed by `:C` and at least two digits.
4. Every canonical finding ID matches `F###`.
5. The canonical candidates' `source_candidate_ids` lists do not overlap, and their union equals the complete raw candidate ID set.
6. A replacement or final finding keeps the same ID as its `candidate_id`.
7. Each refutation and judgment assignment is covered exactly once.
8. Every artifact's task ID and attempt match the packet that assigned its output path.
9. Every location has `end_line` greater than or equal to `start_line`.
10. Every finding has at least one non-empty manifestation step and a non-empty setup and failure result.
11. A `verified_reproduction` has at least one verified `test` or `command` evidence record; vague placeholders are rejected.

The coordinator prints only status, counts, task IDs, packet paths, output paths, reason codes, and invalid field paths. It never prints findings, evidence, recommendations, raw JSON, or packet contents.

## One round per stage

Each stage has one semantic round:

1. Stage 1 assigns the selected review lenses once. Combine related lenses when capacity is limited.
2. Stage 2 uses one fresh deduplicator.
3. Stage 3 assigns each canonical candidate to one refuter. Batch related candidates when needed.
4. Stage 4 assigns each disputed candidate to one fresh judge. Batch candidates when needed.

Do not schedule extra passes because a candidate is important, uncertain, or controversial. A main-agent decision to rerun failed execution is an operational retry and does not add a new independent opinion.

## Task packets

Every packet follows the fixed `task_packet` Schema and contains the complete instructions the subagent needs. A packet includes the agent ID, scope path, fixed Schema path, coordinator path, input artifact paths, assigned IDs, output path, complete `validation_command` argv, stage instructions, task ID, and attempt number.

Every packet must tell the agent to read `scope.json` first, then read and follow every file listed in `scope.instruction_files`. This is required because agents normally start with `fork_turns: "none"` and cannot rely on instructions already read by the main agent. The coordinator builds these instructions from the packaged `stage-instructions.json`; session-specific domain guidance belongs in scope, lenses, or repository instruction files rather than the fixed templates.

Use these stage instructions:

1. An adversarial packet names the assigned lane and requires direct inspection, complete coverage of that lane, a concrete manifestation for every candidate, and an empty candidate list when no issue qualifies.
2. A dedup packet requires complete raw ID coverage, merging only true duplicates, preserving the clearest accurate manifestation, and no decision on validity.
3. A refutation packet requires direct inspection plus correctness, manifestation reachability, and proportionality analysis for every assigned canonical ID.
4. A judgment packet requires direct inspection and one binding disposition for every assigned disputed ID, including correction of an inaccurate manifestation when modifying a finding.

## Coordinator commands

The packaged `pipeline.py` uses these commands and accepts only current-attempt paths supplied by the main agent:

1. `init` validates `scope.json` and `lenses.json`, then creates reviewer packets.
2. `seal-adversarial <artifact>...` validates the supplied current reviewer artifacts, then creates one deduplication packet. It finalizes immediately when there are no raw candidates.
3. `accept-dedup --workers N <artifact>` validates complete source coverage and stable IDs, then creates at most `N` refutation packets.
4. `accept-refutation --workers N <artifact>...` validates one refutation result for every canonical candidate, then creates at most `N` judgment packets only for disputed candidates.
5. `accept-judgment <artifact>...` validates one binding judgment for every disputed candidate.
6. `retry-packet <packet>` creates a packet with a new task ID, incremented attempt, and new output path. It never overwrites the old packet or artifact.
7. `finalize` writes `final/final.json` and prints its path plus trace counts.
8. `status` prints only the current phase and current packet/output paths so a compacted or resumed main-agent turn can recover safely.
9. `scaffold-artifact <packet>` optionally writes a top-level artifact skeleton to the packet's output path and refuses to overwrite an existing artifact.
10. `validate-artifact <packet> <artifact>` validates one agent artifact against its packet and current run state. Agents must execute the exact `validation_command` argv stored in their packet before sending a success receipt.
11. `validate-final` checks the final payload invariants and verifies that every upheld, rejected, and unresolved finding cites an existing repository file and in-range source lines.

A transition succeeds only when all expected artifacts pass validation. The coordinator applies fixed routing rules and does not decide whether a finding is correct.

## Source mapping and routing

Raw candidate IDs include the agent ID, such as `reviewer-02:C03`. The deduplicator assigns stable IDs such as `F001`. Each canonical candidate lists its source raw IDs, and those lists form the complete non-overlapping mapping.

Use these routing rules:

1. A refutation result of `uphold` goes directly to final assembly.
2. A result of `modify`, `refute`, or `unresolved` goes to judgment.
3. A judgment of `uphold` keeps the canonical finding.
4. A judgment of `modify` uses the complete corrected finding.
5. A judgment of `reject` omits the finding from the upheld list and records the Stage 3 replacement finding when its verdict was `modify`, otherwise the canonical finding, plus the Stage 3 verdict and Stage 4 reason in `rejected_findings`.
6. A judgment of `unresolved` omits the finding from the upheld list and records the Stage 3 replacement finding when its verdict was `modify`, otherwise the canonical finding, plus the Stage 3 verdict, resolved points, and non-empty residual risk in `unresolved_findings`.
7. Every canonical candidate produces exactly one `review_records` entry. A Stage 3 `uphold` uses refutation as the final judgment source; every disputed candidate uses Stage 4 judgment. The record preserves both sides even when the final disposition rejects the finding.

## Agent messages

After writing an artifact and successfully running `validate-artifact`, an agent replies with exactly:

```text
ARTIFACT_WRITTEN <stage> <task-id> <record-count> <output-path>
```

If it cannot complete the task, it replies with exactly:

```text
ARTIFACT_FAILED <stage> <task-id> <reason-code> <short-reason>
```

The short reason must not contain a finding, evidence, or raw artifact content. If the subagent exits without a message, the subagent tool's failure status serves as the notification.

Use this start prompt:

```text
Read and follow <packet-path>. Work read-only and do not delegate. Write JSON that follows the fixed schema to <output-path>. Do not include findings or evidence in your reply. Reply only with the required ARTIFACT_WRITTEN or ARTIFACT_FAILED receipt.
```

## Failure decisions

There is no automatic retry and no `failure.json`. When an agent or transition fails, the main agent chooses one action:

1. Rerun the failed task.
2. Rerun the whole stage.
3. Stop and report that the review is incomplete.

Do not advance past an incomplete stage. Coverage gaps describe source or tool access limits reported by reviewers that completed successfully. They do not replace missing stage results.

When the main agent chooses a retry, run `retry-packet` and use only the new packet and output path. A later transition receives the successful current artifact paths explicitly, so an older file cannot satisfy the retry.

For a malformed artifact, the coordinator returns a compact line of this form:

```text
VALIDATION_FAILED <stage> <task-id> <reason-code> <field-path>...
```

The main agent may give those field paths to the responsible agent without reading or pasting the artifact.

## Final payload

The coordinator writes one `final.json` that follows the fixed Schema. It contains surviving findings, rejected findings, structured unresolved findings, Stage 1 coverage, trace counts, and one `review_records` audit entry for every canonical candidate. Each audit entry preserves the original case for the finding, the independent challenge and its evidence, the final judgment source/basis/evidence, and the exact finding selected for presentation. It must not contain raw candidates or redundant copies of complete intermediate artifacts.

Calculate trace values from unique canonical IDs:

1. `reviewers_completed` is the number of valid adversarial artifacts.
2. `raw_candidates` and `canonical_candidates` are the corresponding unique ID counts.
3. `refutation_results` and `judgment_results` are the unique candidate ID counts in those stages.
4. `rejected_findings` counts final judge results of `reject`.
5. `unresolved` counts final judge results of `unresolved`.
6. `final_findings` is the number of findings retained after routing.

For a complete run, `canonical_candidates` equals `final_findings + rejected_findings + unresolved`.
