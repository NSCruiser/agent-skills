#!/usr/bin/env python3
"""Coordinate one harness-independent Ultrareview run using protocol v3."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unicodedata
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = 3
SCOPE_PATH = ROOT / "scope.json"
LENSES_PATH = ROOT / "lenses.json"
SCHEMA_PATH = ROOT / "pipeline-schemas.json"
STAGE_INSTRUCTIONS_PATH = ROOT / "stage-instructions.json"
REPOSITORY_BINDING_PATH = ROOT / "repository.json"
STATE_PATH = ROOT / ".pipeline-state.json"
CANONICAL_ID = re.compile(r"^F[0-9]{3,}$")
RAW_ID = re.compile(r"^[A-Za-z0-9._-]+:C[0-9]{2,}$")
AGENT_ID = re.compile(r"^[A-Za-z0-9._-]+$")
PRIORITIES = {"P0", "P1", "P2", "P3"}
CONFIDENCES = {"high", "medium", "low"}
EVIDENCE_KINDS = {"source", "test", "caller", "history", "command", "contract"}
MANIFESTATION_PLACEHOLDERS = {
    "an error occurs",
    "it fails",
    "n/a",
    "same as impact",
    "same as trigger",
    "tbd",
    "the failure occurs",
    "the issue occurs",
    "todo",
}


class ValidationError(Exception):
    def __init__(self, stage: str, task_id: str, code: str, fields: list[str]):
        super().__init__(code)
        self.stage = stage
        self.task_id = task_id
        self.code = code
        self.fields = fields


def validation_failed(error: ValidationError) -> None:
    fields = " ".join(error.fields or ["$"])
    print(f"VALIDATION_FAILED {error.stage} {error.task_id} {error.code} {fields}")
    raise SystemExit(2)


def require(condition: bool, stage: str, task_id: str, code: str, field: str) -> None:
    if not condition:
        raise ValidationError(stage, task_id, code, [field])


def exact_keys(value: object, expected: set[str], stage: str, task_id: str, field: str) -> dict:
    require(isinstance(value, dict), stage, task_id, "invalid_type", field)
    mapping = value
    missing = sorted(expected - set(mapping))
    unknown = sorted(set(mapping) - expected)
    require(not missing, stage, task_id, "missing_required", f"{field}.{','.join(missing)}")
    require(not unknown, stage, task_id, "unknown_fields", f"{field}.{','.join(unknown)}")
    return mapping


def nonempty_string(value: object, stage: str, task_id: str, field: str) -> str:
    require(isinstance(value, str) and bool(value), stage, task_id, "invalid_string", field)
    return value


def positive_integer(value: object, stage: str, task_id: str, field: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value >= 1,
            stage, task_id, "invalid_value", field)
    return value


def string_list(value: object, stage: str, task_id: str, field: str, *, unique: bool = False,
                nonempty: bool = False) -> list[str]:
    require(isinstance(value, list), stage, task_id, "invalid_type", field)
    require(all(isinstance(item, str) and (bool(item) or not nonempty) for item in value),
            stage, task_id, "invalid_string", field)
    if unique:
        require(len(value) == len(set(value)), stage, task_id, "duplicate_values", field)
    return value


def safe_path(raw: str, *, must_exist: bool = False, reject_symlink: bool = False) -> Path:
    path = Path(raw)
    candidate = path.resolve(strict=False)
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("path_outside_run") from exc
    if must_exist and not path.exists():
        raise FileNotFoundError(raw)
    if reject_symlink and path.is_symlink():
        raise ValueError("artifact_symlink")
    return candidate


def read_json(path: Path, stage: str = "coordinator", task_id: str = "coordinator") -> dict:
    try:
        safe_path(str(path), must_exist=True, reject_symlink=True)
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValidationError(stage, task_id, "invalid_json_or_path", [str(path)]) from exc
    require(isinstance(value, dict), stage, task_id, "invalid_type", "$")
    return value


def load_bound_repository(stage: str, task_id: str) -> Path:
    binding = read_json(REPOSITORY_BINDING_PATH, stage, task_id)
    mapping = exact_keys(binding, {"repository_path"}, stage, task_id, "$.repository_binding")
    raw_path = nonempty_string(
        mapping["repository_path"], stage, task_id, "$.repository_binding.repository_path"
    )
    path = Path(raw_path)
    require(path.is_absolute(), stage, task_id, "repository_not_absolute",
            "$.repository_binding.repository_path")
    repository = path.resolve(strict=False)
    require(repository.is_dir(), stage, task_id, "repository_missing",
            "$.repository_binding.repository_path")
    return repository


def git_worktree_status(repository: Path, stage: str, task_id: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), "status", "--short", "--untracked-files=all"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ValidationError(
            stage, task_id, "worktree_status_unavailable", [str(repository)]
        ) from exc
    require(result.returncode == 0, stage, task_id, "worktree_status_unavailable",
            "$.baseline_worktree_status")
    return result.stdout.splitlines()


def atomic_write(path: Path, value: dict) -> None:
    safe_path(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def validate_location(value: object, stage: str, task_id: str, field: str) -> None:
    mapping = exact_keys(value, {"path", "start_line", "end_line"}, stage, task_id, field)
    nonempty_string(mapping["path"], stage, task_id, f"{field}.path")
    start = mapping["start_line"]
    end = mapping["end_line"]
    require(isinstance(start, int) and not isinstance(start, bool) and start >= 1,
            stage, task_id, "invalid_line", f"{field}.start_line")
    require(isinstance(end, int) and not isinstance(end, bool) and end >= start,
            stage, task_id, "invalid_line_range", f"{field}.end_line")


def validate_evidence(value: object, stage: str, task_id: str, field: str) -> None:
    require(isinstance(value, dict), stage, task_id, "invalid_type", field)
    required = {"kind", "statement", "status"}
    allowed = required | {"location"}
    require(required <= set(value), stage, task_id, "missing_required", field)
    require(set(value) <= allowed, stage, task_id, "unknown_fields", field)
    require(value["kind"] in EVIDENCE_KINDS, stage, task_id, "invalid_enum", f"{field}.kind")
    nonempty_string(value["statement"], stage, task_id, f"{field}.statement")
    require(value["status"] in {"verified", "inference"}, stage, task_id,
            "invalid_enum", f"{field}.status")
    if "location" in value and value["location"] is not None:
        validate_location(value["location"], stage, task_id, f"{field}.location")


def normalized_manifestation_text(value: str) -> str:
    compatible = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\W_]+", " ", compatible, flags=re.UNICODE).strip()


def validate_manifestation(value: object, stage: str, task_id: str, field: str) -> None:
    mapping = exact_keys(value, {"kind", "setup", "steps", "failure"},
                         stage, task_id, field)
    require(mapping["kind"] in {"verified_reproduction", "reasoned_scenario"},
            stage, task_id, "invalid_enum", f"{field}.kind")
    setup = nonempty_string(mapping["setup"], stage, task_id, f"{field}.setup")
    normalized_setup = normalized_manifestation_text(setup)
    require(normalized_setup not in MANIFESTATION_PLACEHOLDERS and bool(normalized_setup),
            stage, task_id, "non_concrete_manifestation", f"{field}.setup")
    steps = string_list(mapping["steps"], stage, task_id, f"{field}.steps", nonempty=True)
    require(bool(steps), stage, task_id, "invalid_array", f"{field}.steps")
    for index, step in enumerate(steps):
        normalized_step = normalized_manifestation_text(step)
        require(normalized_step not in MANIFESTATION_PLACEHOLDERS and bool(normalized_step),
                stage, task_id, "non_concrete_manifestation", f"{field}.steps[{index}]")
    failure = nonempty_string(mapping["failure"], stage, task_id, f"{field}.failure")
    normalized_failure = normalized_manifestation_text(failure)
    require(normalized_failure not in MANIFESTATION_PLACEHOLDERS and bool(normalized_failure),
            stage, task_id, "non_concrete_manifestation", f"{field}.failure")


def validate_finding(value: object, stage: str, task_id: str, field: str, *, raw: bool) -> None:
    keys = {"id", "priority", "title", "location", "context", "trigger", "impact",
            "manifestation", "evidence", "recommendation", "confidence"}
    mapping = exact_keys(value, keys, stage, task_id, field)
    finding_id = nonempty_string(mapping["id"], stage, task_id, f"{field}.id")
    pattern = RAW_ID if raw else CANONICAL_ID
    require(bool(pattern.fullmatch(finding_id)), stage, task_id, "invalid_id", f"{field}.id")
    require(mapping["priority"] in PRIORITIES, stage, task_id, "invalid_enum", f"{field}.priority")
    for key in ("title", "context", "trigger", "impact", "recommendation"):
        nonempty_string(mapping[key], stage, task_id, f"{field}.{key}")
    validate_location(mapping["location"], stage, task_id, f"{field}.location")
    validate_manifestation(mapping["manifestation"], stage, task_id,
                           f"{field}.manifestation")
    require(isinstance(mapping["evidence"], list) and len(mapping["evidence"]) >= 1,
            stage, task_id, "invalid_array", f"{field}.evidence")
    for index, evidence in enumerate(mapping["evidence"]):
        validate_evidence(evidence, stage, task_id, f"{field}.evidence[{index}]")
    if mapping["manifestation"]["kind"] == "verified_reproduction":
        has_verified_execution = any(
            evidence["kind"] in {"test", "command"} and evidence["status"] == "verified"
            for evidence in mapping["evidence"]
        )
        require(has_verified_execution, stage, task_id,
                "verified_reproduction_requires_execution_evidence",
                f"{field}.manifestation.kind")
    require(mapping["confidence"] in CONFIDENCES, stage, task_id,
            "invalid_enum", f"{field}.confidence")


def validate_coverage(value: object, stage: str, task_id: str, field: str) -> None:
    mapping = exact_keys(value, {"inspected_paths", "checks_run", "gaps"}, stage, task_id, field)
    string_list(mapping["inspected_paths"], stage, task_id, f"{field}.inspected_paths", unique=True)
    string_list(mapping["checks_run"], stage, task_id, f"{field}.checks_run")
    string_list(mapping["gaps"], stage, task_id, f"{field}.gaps")


def validate_scope(value: object, stage: str = "init", task_id: str = "scope") -> None:
    keys = {"schema_version", "repository_path", "review_kind", "target", "comparison_base",
            "topic", "exclusions", "instruction_files", "finding_standard",
            "baseline_worktree_status"}
    mapping = exact_keys(value, keys, stage, task_id, "$")
    require(mapping["schema_version"] == SCHEMA_VERSION, stage, task_id,
            "invalid_version", "$.schema_version")
    repository_path = nonempty_string(
        mapping["repository_path"], stage, task_id, "$.repository_path"
    )
    declared_repository = Path(repository_path)
    require(declared_repository.is_absolute(), stage, task_id, "repository_not_absolute",
            "$.repository_path")
    require(declared_repository.resolve(strict=False) == load_bound_repository(stage, task_id),
            stage, task_id, "scope_repository_mismatch", "$.repository_path")
    require(mapping["review_kind"] in {"change", "topic"}, stage, task_id, "invalid_enum", "$.review_kind")
    nonempty_string(mapping["target"], stage, task_id, "$.target")
    if mapping["review_kind"] == "topic":
        require(mapping["comparison_base"] is None, stage, task_id, "invalid_value", "$.comparison_base")
        nonempty_string(mapping["topic"], stage, task_id, "$.topic")
    else:
        nonempty_string(mapping["comparison_base"], stage, task_id, "$.comparison_base")
        require(mapping["topic"] is None, stage, task_id, "invalid_value", "$.topic")
    string_list(mapping["exclusions"], stage, task_id, "$.exclusions")
    string_list(mapping["instruction_files"], stage, task_id, "$.instruction_files", unique=True)
    nonempty_string(mapping["finding_standard"], stage, task_id, "$.finding_standard")
    string_list(mapping["baseline_worktree_status"], stage, task_id, "$.baseline_worktree_status")


def require_worktree_unchanged(scope: dict, stage: str, task_id: str) -> None:
    repository = load_bound_repository(stage, task_id)
    actual = git_worktree_status(repository, stage, task_id)
    require(actual == scope["baseline_worktree_status"], stage, task_id,
            "worktree_changed", "$.baseline_worktree_status")


def validate_lenses(value: object) -> None:
    stage = "init"
    task_id = "lenses"
    mapping = exact_keys(value, {"schema_version", "reviewers"}, stage, task_id, "$")
    require(mapping["schema_version"] == SCHEMA_VERSION, stage, task_id,
            "invalid_version", "$.schema_version")
    reviewers = mapping["reviewers"]
    require(isinstance(reviewers, list) and len(reviewers) >= 1, stage, task_id,
            "invalid_array", "$.reviewers")
    ids: list[str] = []
    lanes: list[str] = []
    for index, reviewer in enumerate(reviewers):
        field = f"$.reviewers[{index}]"
        row = exact_keys(reviewer, {"agent_id", "lane", "focus"}, stage, task_id, field)
        agent_id = nonempty_string(row["agent_id"], stage, task_id, f"{field}.agent_id")
        require(bool(AGENT_ID.fullmatch(agent_id)), stage, task_id,
                "invalid_agent_id", f"{field}.agent_id")
        ids.append(agent_id)
        lanes.append(nonempty_string(row["lane"], stage, task_id, f"{field}.lane"))
        focus = string_list(row["focus"], stage, task_id, f"{field}.focus", nonempty=True)
        require(len(focus) >= 1, stage, task_id, "invalid_array", f"{field}.focus")
    require(len(ids) == len(set(ids)), stage, task_id, "duplicate_agent_id", "$.reviewers")
    require(len(lanes) == len(set(lanes)), stage, task_id, "duplicate_lane", "$.reviewers")


def validate_packet(value: object, stage: str, task_id: str) -> None:
    keys = {
        "schema_version", "stage", "task_id", "attempt", "agent_id", "scope_path",
        "schema_path", "coordinator_path", "input_paths", "assigned_ids", "lane",
        "instructions", "output_path", "validation_command", "artifact_schema_ref",
        "read_only", "no_delegate",
    }
    mapping = exact_keys(value, keys, stage, task_id, "$")
    require(mapping["schema_version"] == SCHEMA_VERSION, stage, task_id,
            "invalid_version", "$.schema_version")
    require(mapping["stage"] in {"adversarial", "dedup", "refutation", "judgment"},
            stage, task_id, "invalid_enum", "$.stage")
    nonempty_string(mapping["task_id"], stage, task_id, "$.task_id")
    positive_integer(mapping["attempt"], stage, task_id, "$.attempt")
    agent_id = nonempty_string(mapping["agent_id"], stage, task_id, "$.agent_id")
    require(bool(AGENT_ID.fullmatch(agent_id)), stage, task_id,
            "invalid_agent_id", "$.agent_id")
    nonempty_string(mapping["scope_path"], stage, task_id, "$.scope_path")
    nonempty_string(mapping["schema_path"], stage, task_id, "$.schema_path")
    coordinator_path = nonempty_string(
        mapping["coordinator_path"], stage, task_id, "$.coordinator_path"
    )
    string_list(mapping["input_paths"], stage, task_id, "$.input_paths", unique=True, nonempty=True)
    string_list(mapping["assigned_ids"], stage, task_id, "$.assigned_ids", unique=True, nonempty=True)
    instructions = string_list(mapping["instructions"], stage, task_id, "$.instructions", nonempty=True)
    require(len(instructions) >= 1, stage, task_id, "invalid_array", "$.instructions")
    nonempty_string(mapping["output_path"], stage, task_id, "$.output_path")
    validation_command = string_list(
        mapping["validation_command"], stage, task_id, "$.validation_command", nonempty=True
    )
    expected_packet_path = ROOT / "packets" / mapping["stage"] / f"{mapping['task_id']}.json"
    require(coordinator_path == str(ROOT / "pipeline.py"), stage, task_id,
            "invalid_value", "$.coordinator_path")
    require(
        len(validation_command) == 5
        and validation_command[1:] == [
            coordinator_path,
            "validate-artifact",
            str(expected_packet_path),
            mapping["output_path"],
        ],
        stage,
        task_id,
        "invalid_validation_command",
        "$.validation_command",
    )
    expected_ref = f"#/$defs/{mapping['stage']}"
    require(mapping["artifact_schema_ref"] == expected_ref, stage, task_id,
            "invalid_value", "$.artifact_schema_ref")
    require(mapping["read_only"] is True, stage, task_id, "invalid_value", "$.read_only")
    require(mapping["no_delegate"] is True, stage, task_id, "invalid_value", "$.no_delegate")
    if mapping["stage"] == "adversarial":
        nonempty_string(mapping["lane"], stage, task_id, "$.lane")
    else:
        require(mapping["lane"] is None, stage, task_id, "invalid_value", "$.lane")
        require(len(mapping["input_paths"]) >= 1, stage, task_id, "invalid_array", "$.input_paths")
        require(len(mapping["assigned_ids"]) >= 1, stage, task_id, "invalid_array", "$.assigned_ids")


def load_state() -> dict:
    return read_json(STATE_PATH)


def save_state(state: dict) -> None:
    atomic_write(STATE_PATH, state)


def load_stage_instructions() -> dict[str, list[str]]:
    value = read_json(STAGE_INSTRUCTIONS_PATH, "init", "stage-instructions")
    mapping = exact_keys(
        value,
        {"schema_version", "adversarial", "dedup", "refutation", "judgment"},
        "init",
        "stage-instructions",
        "$",
    )
    require(mapping["schema_version"] == SCHEMA_VERSION, "init", "stage-instructions",
            "invalid_version", "$.schema_version")
    for stage in ("adversarial", "dedup", "refutation", "judgment"):
        instructions = string_list(
            mapping[stage],
            "init",
            "stage-instructions",
            f"$.{stage}",
            nonempty=True,
        )
        require(bool(instructions), "init", "stage-instructions", "invalid_array", f"$.{stage}")
    return {stage: mapping[stage] for stage in ("adversarial", "dedup", "refutation", "judgment")}


def make_packet(state: dict, *, stage: str, agent_id: str, input_paths: list[str],
                assigned_ids: list[str], lane: str | None, instructions: list[str],
                attempt: int = 1) -> tuple[Path, Path, str]:
    nonce = uuid.uuid4().hex[:8]
    task_id = f"{stage}-{agent_id}-a{attempt}-{nonce}"
    packet_path = ROOT / "packets" / stage / f"{task_id}.json"
    output_path = ROOT / "artifacts" / stage / f"{task_id}.json"
    packet = {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "task_id": task_id,
        "attempt": attempt,
        "agent_id": agent_id,
        "scope_path": str(SCOPE_PATH),
        "schema_path": str(SCHEMA_PATH),
        "coordinator_path": str(ROOT / "pipeline.py"),
        "input_paths": input_paths,
        "assigned_ids": assigned_ids,
        "lane": lane,
        "instructions": instructions,
        "output_path": str(output_path),
        "validation_command": [
            sys.executable,
            str(ROOT / "pipeline.py"),
            "validate-artifact",
            str(packet_path),
            str(output_path),
        ],
        "artifact_schema_ref": f"#/$defs/{stage}",
        "read_only": True,
        "no_delegate": True,
    }
    validate_packet(packet, stage, task_id)
    atomic_write(packet_path, packet)
    state.setdefault("current_packets", {}).setdefault(stage, []).append(str(packet_path))
    return packet_path, output_path, task_id


def current_packets(state: dict, stage: str) -> list[tuple[Path, dict]]:
    rows: list[tuple[Path, dict]] = []
    for raw_path in state.get("current_packets", {}).get(stage, []):
        path = safe_path(raw_path, must_exist=True, reject_symlink=True)
        packet = read_json(path, stage, "coordinator")
        validate_packet(packet, stage, packet.get("task_id", "coordinator"))
        rows.append((path, packet))
    return rows


def match_artifact_paths(state: dict, stage: str, raw_paths: list[str]) -> list[tuple[dict, dict, str]]:
    packets = current_packets(state, stage)
    require(len(raw_paths) == len(packets), stage, "coordinator", "artifact_count",
            "$.artifacts")
    normalized: dict[str, dict] = {}
    for _, packet in packets:
        output = str(safe_path(packet["output_path"]))
        normalized[output] = packet
    require(len(normalized) == len(packets), stage, "coordinator", "duplicate_output_path",
            "$.packets")
    results: list[tuple[dict, dict, str]] = []
    seen: set[str] = set()
    for raw_path in raw_paths:
        try:
            path = safe_path(raw_path, must_exist=True, reject_symlink=True)
        except (ValueError, FileNotFoundError) as exc:
            raise ValidationError(stage, "coordinator", "invalid_artifact_path", [raw_path]) from exc
        key = str(path)
        require(key in normalized, stage, "coordinator", "unexpected_artifact", raw_path)
        require(key not in seen, stage, "coordinator", "duplicate_artifact", raw_path)
        seen.add(key)
        packet = normalized[key]
        artifact = read_json(path, stage, packet["task_id"])
        results.append((packet, artifact, key))
    require(seen == set(normalized), stage, "coordinator", "missing_artifact", "$.artifacts")
    return results


def validate_adversarial(packet: dict, value: object) -> None:
    stage = "adversarial"
    task_id = packet["task_id"]
    keys = {"schema_version", "stage", "task_id", "attempt", "agent_id", "lane",
            "coverage", "candidates"}
    mapping = exact_keys(value, keys, stage, task_id, "$")
    require(mapping["schema_version"] == SCHEMA_VERSION, stage, task_id,
            "invalid_version", "$.schema_version")
    require(mapping["stage"] == stage, stage, task_id, "stage_mismatch", "$.stage")
    positive_integer(mapping["attempt"], stage, task_id, "$.attempt")
    for key in ("task_id", "attempt", "agent_id", "lane"):
        require(mapping[key] == packet[key], stage, task_id, "packet_mismatch", f"$.{key}")
    validate_coverage(mapping["coverage"], stage, task_id, "$.coverage")
    require(isinstance(mapping["candidates"], list), stage, task_id, "invalid_type", "$.candidates")
    ids: list[str] = []
    for index, candidate in enumerate(mapping["candidates"]):
        validate_finding(candidate, stage, task_id, f"$.candidates[{index}]", raw=True)
        candidate_id = candidate["id"]
        require(candidate_id.startswith(f"{packet['agent_id']}:C"), stage, task_id,
                "candidate_prefix", f"$.candidates[{index}].id")
        ids.append(candidate_id)
    require(len(ids) == len(set(ids)), stage, task_id, "duplicate_candidate_id", "$.candidates")


def validate_dedup(packet: dict, value: object, raw_ids: set[str]) -> None:
    stage = "dedup"
    task_id = packet["task_id"]
    keys = {"schema_version", "stage", "task_id", "attempt", "agent_id",
            "canonical_candidates"}
    mapping = exact_keys(value, keys, stage, task_id, "$")
    require(mapping["schema_version"] == SCHEMA_VERSION, stage, task_id,
            "invalid_version", "$.schema_version")
    require(mapping["stage"] == stage, stage, task_id, "stage_mismatch", "$.stage")
    positive_integer(mapping["attempt"], stage, task_id, "$.attempt")
    for key in ("task_id", "attempt", "agent_id"):
        require(mapping[key] == packet[key], stage, task_id, "packet_mismatch", f"$.{key}")
    candidates = mapping["canonical_candidates"]
    require(isinstance(candidates, list) and len(candidates) >= 1, stage, task_id,
            "invalid_array", "$.canonical_candidates")
    canonical_ids: list[str] = []
    source_ids: list[str] = []
    for index, candidate in enumerate(candidates):
        field = f"$.canonical_candidates[{index}]"
        row = exact_keys(candidate, {"finding", "source_candidate_ids", "merge_basis"},
                         stage, task_id, field)
        validate_finding(row["finding"], stage, task_id, f"{field}.finding", raw=False)
        canonical_ids.append(row["finding"]["id"])
        sources = string_list(row["source_candidate_ids"], stage, task_id,
                              f"{field}.source_candidate_ids", unique=True, nonempty=True)
        require(len(sources) >= 1, stage, task_id, "invalid_array", f"{field}.source_candidate_ids")
        source_ids.extend(sources)
        nonempty_string(row["merge_basis"], stage, task_id, f"{field}.merge_basis")
    require(len(canonical_ids) == len(set(canonical_ids)), stage, task_id,
            "duplicate_canonical_id", "$.canonical_candidates")
    require(len(source_ids) == len(set(source_ids)), stage, task_id,
            "overlapping_source_ids", "$.canonical_candidates")
    require(set(source_ids) == raw_ids, stage, task_id, "incomplete_source_coverage",
            "$.canonical_candidates[*].source_candidate_ids")


def validate_refutation(packet: dict, value: object) -> None:
    stage = "refutation"
    task_id = packet["task_id"]
    keys = {"schema_version", "stage", "task_id", "attempt", "agent_id", "results"}
    mapping = exact_keys(value, keys, stage, task_id, "$")
    require(mapping["schema_version"] == SCHEMA_VERSION, stage, task_id,
            "invalid_version", "$.schema_version")
    require(mapping["stage"] == stage, stage, task_id, "stage_mismatch", "$.stage")
    positive_integer(mapping["attempt"], stage, task_id, "$.attempt")
    for key in ("task_id", "attempt", "agent_id"):
        require(mapping[key] == packet[key], stage, task_id, "packet_mismatch", f"$.{key}")
    results = mapping["results"]
    require(isinstance(results, list) and len(results) >= 1, stage, task_id,
            "invalid_array", "$.results")
    ids: list[str] = []
    for index, result in enumerate(results):
        field = f"$.results[{index}]"
        row = exact_keys(result, {"candidate_id", "verdict", "correctness_analysis",
                         "proportionality_analysis", "evidence", "replacement_finding",
                         "residual_uncertainty"}, stage, task_id, field)
        candidate_id = nonempty_string(row["candidate_id"], stage, task_id, f"{field}.candidate_id")
        require(bool(CANONICAL_ID.fullmatch(candidate_id)), stage, task_id,
                "invalid_id", f"{field}.candidate_id")
        ids.append(candidate_id)
        require(row["verdict"] in {"uphold", "modify", "refute", "unresolved"},
                stage, task_id, "invalid_enum", f"{field}.verdict")
        nonempty_string(row["correctness_analysis"], stage, task_id, f"{field}.correctness_analysis")
        nonempty_string(row["proportionality_analysis"], stage, task_id,
                        f"{field}.proportionality_analysis")
        require(isinstance(row["evidence"], list), stage, task_id, "invalid_type", f"{field}.evidence")
        for evidence_index, evidence in enumerate(row["evidence"]):
            validate_evidence(evidence, stage, task_id, f"{field}.evidence[{evidence_index}]")
        require(isinstance(row["residual_uncertainty"], str), stage, task_id,
                "invalid_string", f"{field}.residual_uncertainty")
        if row["verdict"] == "modify":
            validate_finding(row["replacement_finding"], stage, task_id,
                             f"{field}.replacement_finding", raw=False)
            require(row["replacement_finding"]["id"] == candidate_id, stage, task_id,
                    "replacement_id_mismatch", f"{field}.replacement_finding.id")
        else:
            require(row["replacement_finding"] is None, stage, task_id,
                    "unexpected_replacement", f"{field}.replacement_finding")
    require(len(ids) == len(set(ids)), stage, task_id, "duplicate_candidate_id", "$.results")
    require(set(ids) == set(packet["assigned_ids"]), stage, task_id,
            "assignment_coverage", "$.results[*].candidate_id")


def validate_judgment(packet: dict, value: object) -> None:
    stage = "judgment"
    task_id = packet["task_id"]
    keys = {"schema_version", "stage", "task_id", "attempt", "agent_id", "results"}
    mapping = exact_keys(value, keys, stage, task_id, "$")
    require(mapping["schema_version"] == SCHEMA_VERSION, stage, task_id,
            "invalid_version", "$.schema_version")
    require(mapping["stage"] == stage, stage, task_id, "stage_mismatch", "$.stage")
    positive_integer(mapping["attempt"], stage, task_id, "$.attempt")
    for key in ("task_id", "attempt", "agent_id"):
        require(mapping[key] == packet[key], stage, task_id, "packet_mismatch", f"$.{key}")
    results = mapping["results"]
    require(isinstance(results, list) and len(results) >= 1, stage, task_id,
            "invalid_array", "$.results")
    ids: list[str] = []
    for index, result in enumerate(results):
        field = f"$.results[{index}]"
        row = exact_keys(result, {"candidate_id", "verdict", "resolved_points", "evidence",
                         "final_finding", "residual_risk"}, stage, task_id, field)
        candidate_id = nonempty_string(row["candidate_id"], stage, task_id, f"{field}.candidate_id")
        require(bool(CANONICAL_ID.fullmatch(candidate_id)), stage, task_id,
                "invalid_id", f"{field}.candidate_id")
        ids.append(candidate_id)
        require(row["verdict"] in {"uphold", "modify", "reject", "unresolved"},
                stage, task_id, "invalid_enum", f"{field}.verdict")
        resolved_points = string_list(
            row["resolved_points"], stage, task_id, f"{field}.resolved_points", nonempty=True
        )
        require(bool(resolved_points), stage, task_id,
                "invalid_array", f"{field}.resolved_points")
        require(isinstance(row["evidence"], list), stage, task_id, "invalid_type", f"{field}.evidence")
        for evidence_index, evidence in enumerate(row["evidence"]):
            validate_evidence(evidence, stage, task_id, f"{field}.evidence[{evidence_index}]")
        require(isinstance(row["residual_risk"], str), stage, task_id,
                "invalid_string", f"{field}.residual_risk")
        if row["verdict"] == "unresolved":
            nonempty_string(row["residual_risk"], stage, task_id, f"{field}.residual_risk")
        if row["verdict"] == "modify":
            validate_finding(row["final_finding"], stage, task_id,
                             f"{field}.final_finding", raw=False)
            require(row["final_finding"]["id"] == candidate_id, stage, task_id,
                    "replacement_id_mismatch", f"{field}.final_finding.id")
        else:
            require(row["final_finding"] is None, stage, task_id,
                    "unexpected_replacement", f"{field}.final_finding")
    require(len(ids) == len(set(ids)), stage, task_id, "duplicate_candidate_id", "$.results")
    require(set(ids) == set(packet["assigned_ids"]), stage, task_id,
            "assignment_coverage", "$.results[*].candidate_id")


def validate_challenge_record(value: object, candidate_id: str,
                              stage: str, task_id: str, field: str) -> dict:
    row = exact_keys(
        value,
        {
            "verdict", "correctness_analysis", "proportionality_analysis",
            "evidence", "proposed_finding", "residual_uncertainty",
        },
        stage,
        task_id,
        field,
    )
    require(row["verdict"] in {"uphold", "modify", "refute", "unresolved"},
            stage, task_id, "invalid_enum", f"{field}.verdict")
    nonempty_string(row["correctness_analysis"], stage, task_id,
                    f"{field}.correctness_analysis")
    nonempty_string(row["proportionality_analysis"], stage, task_id,
                    f"{field}.proportionality_analysis")
    require(isinstance(row["evidence"], list), stage, task_id,
            "invalid_type", f"{field}.evidence")
    for index, evidence in enumerate(row["evidence"]):
        validate_evidence(evidence, stage, task_id, f"{field}.evidence[{index}]")
    require(isinstance(row["residual_uncertainty"], str), stage, task_id,
            "invalid_string", f"{field}.residual_uncertainty")
    if row["verdict"] == "modify":
        validate_finding(row["proposed_finding"], stage, task_id,
                         f"{field}.proposed_finding", raw=False)
        require(row["proposed_finding"]["id"] == candidate_id, stage, task_id,
                "replacement_id_mismatch", f"{field}.proposed_finding.id")
    else:
        require(row["proposed_finding"] is None, stage, task_id,
                "unexpected_replacement", f"{field}.proposed_finding")
    return row


def validate_final_judgment_record(value: object, challenge: dict,
                                   stage: str, task_id: str, field: str) -> dict:
    row = exact_keys(value, {"source", "verdict", "basis", "evidence", "residual_risk"},
                     stage, task_id, field)
    require(row["source"] in {"refutation", "judgment"}, stage, task_id,
            "invalid_enum", f"{field}.source")
    require(row["verdict"] in {"uphold", "modify", "reject", "unresolved"},
            stage, task_id, "invalid_enum", f"{field}.verdict")
    basis = string_list(row["basis"], stage, task_id, f"{field}.basis", nonempty=True)
    require(bool(basis), stage, task_id, "invalid_array", f"{field}.basis")
    require(isinstance(row["evidence"], list), stage, task_id,
            "invalid_type", f"{field}.evidence")
    for index, evidence in enumerate(row["evidence"]):
        validate_evidence(evidence, stage, task_id, f"{field}.evidence[{index}]")
    require(isinstance(row["residual_risk"], str), stage, task_id,
            "invalid_string", f"{field}.residual_risk")
    if row["verdict"] == "unresolved":
        nonempty_string(row["residual_risk"], stage, task_id, f"{field}.residual_risk")
    if row["source"] == "refutation":
        require(challenge["verdict"] == "uphold" and row["verdict"] == "uphold",
                stage, task_id, "invalid_judgment_source", field)
        require(
            row["basis"] == [
                challenge["correctness_analysis"],
                challenge["proportionality_analysis"],
            ]
            and row["evidence"] == challenge["evidence"]
            and row["residual_risk"] == challenge["residual_uncertainty"],
            stage,
            task_id,
            "refutation_judgment_mismatch",
            field,
        )
    else:
        require(challenge["verdict"] != "uphold", stage, task_id,
                "invalid_judgment_source", field)
    return row


def validate_final_payload(value: object, expected_scope: dict,
                           expected_trace: dict[str, int]) -> None:
    stage = "finalize"
    task_id = "final"
    mapping = exact_keys(
        value,
        {
            "schema_version", "scope", "findings", "rejected_findings",
            "unresolved_findings", "review_records", "coverage", "trace",
        },
        stage,
        task_id,
        "$",
    )
    require(mapping["schema_version"] == SCHEMA_VERSION, stage, task_id,
            "invalid_version", "$.schema_version")
    validate_scope(mapping["scope"], stage, task_id)
    require(mapping["scope"] == expected_scope, stage, task_id,
            "scope_mismatch", "$.scope")

    findings = mapping["findings"]
    require(isinstance(findings, list), stage, task_id, "invalid_type", "$.findings")
    finding_ids: list[str] = []
    for index, finding in enumerate(findings):
        validate_finding(finding, stage, task_id, f"$.findings[{index}]", raw=False)
        finding_ids.append(finding["id"])
    require(len(finding_ids) == len(set(finding_ids)), stage, task_id,
            "duplicate_canonical_id", "$.findings")
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    expected_order = sorted(
        findings,
        key=lambda item: (priority_order[item["priority"]], item["id"]),
    )
    require(findings == expected_order, stage, task_id,
            "findings_not_sorted", "$.findings")

    rejected_findings = mapping["rejected_findings"]
    require(isinstance(rejected_findings, list), stage, task_id,
            "invalid_type", "$.rejected_findings")
    rejected_ids: list[str] = []
    for index, rejected in enumerate(rejected_findings):
        field = f"$.rejected_findings[{index}]"
        row = exact_keys(
            rejected,
            {"finding", "refutation_verdict", "judgment_verdict", "reason"},
            stage,
            task_id,
            field,
        )
        validate_finding(row["finding"], stage, task_id, f"{field}.finding", raw=False)
        rejected_ids.append(row["finding"]["id"])
        require(row["refutation_verdict"] in {"modify", "refute", "unresolved"},
                stage, task_id, "invalid_enum", f"{field}.refutation_verdict")
        require(row["judgment_verdict"] == "reject", stage, task_id,
                "invalid_enum", f"{field}.judgment_verdict")
        nonempty_string(row["reason"], stage, task_id, f"{field}.reason")
    require(len(rejected_ids) == len(set(rejected_ids)), stage, task_id,
            "duplicate_canonical_id", "$.rejected_findings")
    require(not set(finding_ids).intersection(rejected_ids), stage, task_id,
            "overlapping_final_disposition", "$.rejected_findings")
    expected_rejected_order = sorted(
        rejected_findings,
        key=lambda item: (
            priority_order[item["finding"]["priority"]],
            item["finding"]["id"],
        ),
    )
    require(rejected_findings == expected_rejected_order, stage, task_id,
            "findings_not_sorted", "$.rejected_findings")

    unresolved_findings = mapping["unresolved_findings"]
    require(isinstance(unresolved_findings, list), stage, task_id,
            "invalid_type", "$.unresolved_findings")
    unresolved_ids: list[str] = []
    for index, unresolved_finding in enumerate(unresolved_findings):
        field = f"$.unresolved_findings[{index}]"
        row = exact_keys(
            unresolved_finding,
            {
                "finding", "refutation_verdict", "judgment_verdict",
                "resolved_points", "residual_risk",
            },
            stage,
            task_id,
            field,
        )
        validate_finding(row["finding"], stage, task_id, f"{field}.finding", raw=False)
        unresolved_ids.append(row["finding"]["id"])
        require(row["refutation_verdict"] in {"modify", "refute", "unresolved"},
                stage, task_id, "invalid_enum", f"{field}.refutation_verdict")
        require(row["judgment_verdict"] == "unresolved", stage, task_id,
                "invalid_enum", f"{field}.judgment_verdict")
        resolved_points = string_list(
            row["resolved_points"], stage, task_id,
            f"{field}.resolved_points", nonempty=True,
        )
        require(bool(resolved_points), stage, task_id,
                "invalid_array", f"{field}.resolved_points")
        nonempty_string(row["residual_risk"], stage, task_id, f"{field}.residual_risk")
    require(len(unresolved_ids) == len(set(unresolved_ids)), stage, task_id,
            "duplicate_canonical_id", "$.unresolved_findings")
    require(not set(finding_ids).intersection(unresolved_ids), stage, task_id,
            "overlapping_final_disposition", "$.unresolved_findings")
    require(not set(rejected_ids).intersection(unresolved_ids), stage, task_id,
            "overlapping_final_disposition", "$.unresolved_findings")
    expected_unresolved_order = sorted(
        unresolved_findings,
        key=lambda item: (
            priority_order[item["finding"]["priority"]],
            item["finding"]["id"],
        ),
    )
    require(unresolved_findings == expected_unresolved_order, stage, task_id,
            "findings_not_sorted", "$.unresolved_findings")

    presented_by_id = {finding["id"]: finding for finding in findings}
    presented_by_id.update({row["finding"]["id"]: row["finding"] for row in rejected_findings})
    presented_by_id.update({row["finding"]["id"]: row["finding"] for row in unresolved_findings})
    review_records = mapping["review_records"]
    require(isinstance(review_records, list), stage, task_id,
            "invalid_type", "$.review_records")
    review_ids: list[str] = []
    for index, record in enumerate(review_records):
        field = f"$.review_records[{index}]"
        row = exact_keys(
            record,
            {"candidate_id", "case_for", "challenge", "final_judgment", "presented_finding"},
            stage,
            task_id,
            field,
        )
        candidate_id = nonempty_string(row["candidate_id"], stage, task_id,
                                       f"{field}.candidate_id")
        require(bool(CANONICAL_ID.fullmatch(candidate_id)), stage, task_id,
                "invalid_id", f"{field}.candidate_id")
        review_ids.append(candidate_id)
        validate_finding(row["case_for"], stage, task_id, f"{field}.case_for", raw=False)
        require(row["case_for"]["id"] == candidate_id, stage, task_id,
                "review_record_id_mismatch", f"{field}.case_for.id")
        challenge = validate_challenge_record(
            row["challenge"], candidate_id, stage, task_id, f"{field}.challenge"
        )
        final_judgment = validate_final_judgment_record(
            row["final_judgment"], challenge,
            stage, task_id, f"{field}.final_judgment",
        )
        validate_finding(row["presented_finding"], stage, task_id,
                         f"{field}.presented_finding", raw=False)
        require(row["presented_finding"]["id"] == candidate_id, stage, task_id,
                "review_record_id_mismatch", f"{field}.presented_finding.id")
        require(candidate_id in presented_by_id, stage, task_id,
                "missing_final_disposition", f"{field}.candidate_id")
        require(row["presented_finding"] == presented_by_id[candidate_id], stage, task_id,
                "presented_finding_mismatch", f"{field}.presented_finding")
        if final_judgment["verdict"] != "modify":
            disputed_finding = (
                challenge["proposed_finding"]
                if challenge["verdict"] == "modify"
                else row["case_for"]
            )
            require(row["presented_finding"] == disputed_finding, stage, task_id,
                    "judgment_selection_mismatch", f"{field}.presented_finding")
        expected_verdicts = (
            {"uphold", "modify"} if candidate_id in finding_ids
            else {"reject"} if candidate_id in rejected_ids
            else {"unresolved"}
        )
        require(final_judgment["verdict"] in expected_verdicts, stage, task_id,
                "final_disposition_mismatch", f"{field}.final_judgment.verdict")
    require(len(review_ids) == len(set(review_ids)), stage, task_id,
            "duplicate_canonical_id", "$.review_records")
    require(set(review_ids) == set(presented_by_id), stage, task_id,
            "incomplete_review_record_coverage", "$.review_records")
    require(review_records == sorted(review_records, key=lambda item: item["candidate_id"]),
            stage, task_id, "review_records_not_sorted", "$.review_records")

    coverage = exact_keys(mapping["coverage"], {"review_lanes", "checks_run", "gaps"},
                          stage, task_id, "$.coverage")
    for key in ("review_lanes", "checks_run", "gaps"):
        string_list(coverage[key], stage, task_id, f"$.coverage.{key}")

    trace_keys = {
        "reviewers_completed", "raw_candidates", "canonical_candidates",
        "refutation_results", "judgment_results", "rejected_findings",
        "unresolved", "final_findings",
    }
    trace = exact_keys(mapping["trace"], trace_keys, stage, task_id, "$.trace")
    for key in trace_keys:
        require(isinstance(trace[key], int) and not isinstance(trace[key], bool) and trace[key] >= 0,
                stage, task_id, "invalid_count", f"$.trace.{key}")
    require(trace["final_findings"] == len(findings), stage, task_id,
            "trace_invariant", "$.trace.final_findings")
    require(trace["rejected_findings"] == len(rejected_findings), stage, task_id,
            "trace_invariant", "$.trace.rejected_findings")
    require(trace["unresolved"] == len(unresolved_findings), stage, task_id,
            "trace_invariant", "$.trace.unresolved")
    require(trace["canonical_candidates"] == len(review_records), stage, task_id,
            "trace_invariant", "$.trace.canonical_candidates")
    require(
        trace["canonical_candidates"]
        == trace["final_findings"] + trace["rejected_findings"] + trace["unresolved"],
        stage,
        task_id,
        "trace_invariant",
        "$.trace.canonical_candidates",
    )
    require(trace["refutation_results"] == trace["canonical_candidates"], stage, task_id,
            "trace_invariant", "$.trace.refutation_results")
    for key, expected in expected_trace.items():
        require(trace[key] == expected, stage, task_id,
                "trace_invariant", f"$.trace.{key}")


def artifact_record_count(stage: str, artifact: dict) -> int:
    if stage == "adversarial":
        return len(artifact["candidates"])
    if stage == "dedup":
        return len(artifact["canonical_candidates"])
    return len(artifact["results"])


def validate_packet_artifact(packet: dict, artifact: dict, state: dict) -> None:
    stage = packet["stage"]
    if stage == "adversarial":
        validate_adversarial(packet, artifact)
    elif stage == "dedup":
        validate_dedup(packet, artifact, set(state.get("raw_ids", [])))
    elif stage == "refutation":
        validate_refutation(packet, artifact)
    else:
        validate_judgment(packet, artifact)


def require_current_packet(state: dict, packet_path: Path, packet: dict) -> None:
    require(state.get("phase") == packet["stage"], packet["stage"], packet["task_id"],
            "invalid_phase", "$.phase")
    active_paths = {
        str(safe_path(raw_path))
        for raw_path in state.get("current_packets", {}).get(packet["stage"], [])
    }
    require(str(packet_path) in active_paths, packet["stage"], packet["task_id"],
            "packet_not_current", str(packet_path))


def command_scaffold_artifact(raw_packet_path: str) -> None:
    state = load_state()
    try:
        packet_path = safe_path(raw_packet_path, must_exist=True, reject_symlink=True)
    except (ValueError, FileNotFoundError) as exc:
        raise ValidationError("scaffold", "coordinator", "invalid_packet_path",
                              [raw_packet_path]) from exc
    packet = read_json(packet_path, "scaffold", "coordinator")
    stage = packet.get("stage", "scaffold")
    task_id = packet.get("task_id", "coordinator")
    validate_packet(packet, stage, task_id)
    require_current_packet(state, packet_path, packet)
    scope = read_json(SCOPE_PATH, stage, task_id)
    validate_scope(scope, stage, task_id)
    require_worktree_unchanged(scope, stage, task_id)
    output_path = safe_path(packet["output_path"])
    require(not output_path.exists(), stage, task_id, "artifact_exists", str(output_path))
    artifact: dict = {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "task_id": task_id,
        "attempt": packet["attempt"],
        "agent_id": packet["agent_id"],
    }
    if stage == "adversarial":
        artifact.update({
            "lane": packet["lane"],
            "coverage": {"inspected_paths": [], "checks_run": [], "gaps": []},
            "candidates": [],
        })
    elif stage == "dedup":
        artifact["canonical_candidates"] = []
    else:
        artifact["results"] = []
    atomic_write(output_path, artifact)
    print(f"ARTIFACT_SCAFFOLDED {stage} {task_id} {output_path}")


def command_validate_artifact(raw_packet_path: str, raw_artifact_path: str) -> None:
    state = load_state()
    try:
        packet_path = safe_path(raw_packet_path, must_exist=True, reject_symlink=True)
        artifact_path = safe_path(raw_artifact_path, must_exist=True, reject_symlink=True)
    except (ValueError, FileNotFoundError) as exc:
        raise ValidationError("validate", "coordinator", "invalid_artifact_path",
                              [raw_packet_path, raw_artifact_path]) from exc
    packet = read_json(packet_path, "validate", "coordinator")
    stage = packet.get("stage", "validate")
    task_id = packet.get("task_id", "coordinator")
    validate_packet(packet, stage, task_id)
    require_current_packet(state, packet_path, packet)
    scope = read_json(SCOPE_PATH, stage, task_id)
    validate_scope(scope, stage, task_id)
    require_worktree_unchanged(scope, stage, task_id)
    require(str(artifact_path) == str(safe_path(packet["output_path"])), stage, task_id,
            "unexpected_artifact", str(artifact_path))
    artifact = read_json(artifact_path, stage, task_id)
    validate_packet_artifact(packet, artifact, state)
    print(
        f"ARTIFACT_VALID {stage} {task_id} "
        f"{artifact_record_count(stage, artifact)} {artifact_path}"
    )


def partition(ids: list[str], count: int) -> list[list[str]]:
    buckets = [[] for _ in range(count)]
    for index, item in enumerate(ids):
        buckets[index % count].append(item)
    return [bucket for bucket in buckets if bucket]


def command_init() -> None:
    if STATE_PATH.exists():
        raise ValidationError("init", "coordinator", "already_initialized", [str(STATE_PATH)])
    scope = read_json(SCOPE_PATH, "init", "scope")
    lenses = read_json(LENSES_PATH, "init", "lenses")
    read_json(SCHEMA_PATH, "init", "schema")
    stage_instructions = load_stage_instructions()
    validate_scope(scope)
    validate_lenses(lenses)
    require_worktree_unchanged(scope, "init", "scope")
    state = {"phase": "adversarial", "current_packets": {}, "accepted": {}}
    for reviewer in lenses["reviewers"]:
        instructions = [
            item.format(lane=reviewer["lane"])
            for item in stage_instructions["adversarial"]
        ] + [f"Lane focus: {item}" for item in reviewer["focus"]]
        packet_path, output_path, task_id = make_packet(
            state,
            stage="adversarial",
            agent_id=reviewer["agent_id"],
            input_paths=[],
            assigned_ids=[],
            lane=reviewer["lane"],
            instructions=instructions,
        )
        print(f"PACKET_CREATED adversarial {task_id} {packet_path} {output_path}")
    save_state(state)
    print(f"STAGE_READY adversarial {len(lenses['reviewers'])}")


def command_seal_adversarial(raw_paths: list[str]) -> None:
    state = load_state()
    require(state.get("phase") == "adversarial", "adversarial", "coordinator",
            "invalid_phase", "$.phase")
    scope = read_json(SCOPE_PATH, "adversarial", "coordinator")
    validate_scope(scope, "adversarial", "coordinator")
    require_worktree_unchanged(scope, "adversarial", "coordinator")
    rows = match_artifact_paths(state, "adversarial", raw_paths)
    all_ids: list[str] = []
    for packet, artifact, _ in rows:
        validate_adversarial(packet, artifact)
        all_ids.extend(candidate["id"] for candidate in artifact["candidates"])
    require(len(all_ids) == len(set(all_ids)), "adversarial", "coordinator",
            "duplicate_candidate_id", "$.candidates")
    state["accepted"]["adversarial"] = [path for _, _, path in rows]
    state["current_packets"]["adversarial"] = []
    state["raw_ids"] = all_ids
    if not all_ids:
        state["phase"] = "ready_finalize_empty"
        save_state(state)
        print(f"STAGE_SEALED adversarial {len(rows)} 0")
        command_finalize()
        return
    instructions = load_stage_instructions()["dedup"]
    packet_path, output_path, task_id = make_packet(
        state,
        stage="dedup",
        agent_id="deduplicator-01",
        input_paths=state["accepted"]["adversarial"],
        assigned_ids=all_ids,
        lane=None,
        instructions=instructions,
    )
    state["phase"] = "dedup"
    save_state(state)
    print(f"STAGE_SEALED adversarial {len(rows)} {len(all_ids)}")
    print(f"PACKET_CREATED dedup {task_id} {packet_path} {output_path}")


def command_accept_dedup(raw_path: str, worker_count: int) -> None:
    state = load_state()
    require(state.get("phase") == "dedup", "dedup", "coordinator", "invalid_phase", "$.phase")
    scope = read_json(SCOPE_PATH, "dedup", "coordinator")
    validate_scope(scope, "dedup", "coordinator")
    require_worktree_unchanged(scope, "dedup", "coordinator")
    rows = match_artifact_paths(state, "dedup", [raw_path])
    packet, artifact, path = rows[0]
    validate_dedup(packet, artifact, set(state["raw_ids"]))
    canonical_ids = [row["finding"]["id"] for row in artifact["canonical_candidates"]]
    state["accepted"]["dedup"] = path
    state["current_packets"]["dedup"] = []
    state["canonical_ids"] = canonical_ids
    groups = partition(canonical_ids, min(worker_count, len(canonical_ids)))
    stage_instructions = load_stage_instructions()
    for index, assigned in enumerate(groups, start=1):
        instructions = stage_instructions["refutation"]
        packet_path, output_path, task_id = make_packet(
            state,
            stage="refutation",
            agent_id=f"refuter-{index:02d}",
            input_paths=[path],
            assigned_ids=assigned,
            lane=None,
            instructions=instructions,
        )
        print(f"PACKET_CREATED refutation {task_id} {packet_path} {output_path}")
    state["phase"] = "refutation"
    save_state(state)
    print(f"STAGE_ACCEPTED dedup {len(canonical_ids)} {len(groups)}")


def command_accept_refutation(raw_paths: list[str], worker_count: int) -> None:
    state = load_state()
    require(state.get("phase") == "refutation", "refutation", "coordinator",
            "invalid_phase", "$.phase")
    scope = read_json(SCOPE_PATH, "refutation", "coordinator")
    validate_scope(scope, "refutation", "coordinator")
    require_worktree_unchanged(scope, "refutation", "coordinator")
    rows = match_artifact_paths(state, "refutation", raw_paths)
    covered: list[str] = []
    disputed: list[str] = []
    for packet, artifact, _ in rows:
        validate_refutation(packet, artifact)
        for result in artifact["results"]:
            covered.append(result["candidate_id"])
            if result["verdict"] != "uphold":
                disputed.append(result["candidate_id"])
    require(len(covered) == len(set(covered)), "refutation", "coordinator",
            "duplicate_candidate_id", "$.results")
    require(set(covered) == set(state["canonical_ids"]), "refutation", "coordinator",
            "assignment_coverage", "$.results[*].candidate_id")
    state["accepted"]["refutation"] = [path for _, _, path in rows]
    state["current_packets"]["refutation"] = []
    state["disputed_ids"] = disputed
    if not disputed:
        state["phase"] = "ready_finalize"
        save_state(state)
        print(f"STAGE_ACCEPTED refutation {len(covered)} 0")
        return
    groups = partition(disputed, min(worker_count, len(disputed)))
    judgment_inputs = [state["accepted"]["dedup"]] + state["accepted"]["refutation"]
    stage_instructions = load_stage_instructions()
    for index, assigned in enumerate(groups, start=1):
        instructions = stage_instructions["judgment"]
        packet_path, output_path, task_id = make_packet(
            state,
            stage="judgment",
            agent_id=f"judge-{index:02d}",
            input_paths=judgment_inputs,
            assigned_ids=assigned,
            lane=None,
            instructions=instructions,
        )
        print(f"PACKET_CREATED judgment {task_id} {packet_path} {output_path}")
    state["phase"] = "judgment"
    save_state(state)
    print(f"STAGE_ACCEPTED refutation {len(covered)} {len(disputed)}")


def command_accept_judgment(raw_paths: list[str]) -> None:
    state = load_state()
    require(state.get("phase") == "judgment", "judgment", "coordinator",
            "invalid_phase", "$.phase")
    scope = read_json(SCOPE_PATH, "judgment", "coordinator")
    validate_scope(scope, "judgment", "coordinator")
    require_worktree_unchanged(scope, "judgment", "coordinator")
    rows = match_artifact_paths(state, "judgment", raw_paths)
    covered: list[str] = []
    for packet, artifact, _ in rows:
        validate_judgment(packet, artifact)
        covered.extend(result["candidate_id"] for result in artifact["results"])
    require(len(covered) == len(set(covered)), "judgment", "coordinator",
            "duplicate_candidate_id", "$.results")
    require(set(covered) == set(state["disputed_ids"]), "judgment", "coordinator",
            "assignment_coverage", "$.results[*].candidate_id")
    state["accepted"]["judgment"] = [path for _, _, path in rows]
    state["current_packets"]["judgment"] = []
    state["phase"] = "ready_finalize"
    save_state(state)
    print(f"STAGE_ACCEPTED judgment {len(covered)}")


def aggregate_coverage(state: dict) -> dict:
    lanes: list[str] = []
    checks: list[str] = []
    gaps: list[str] = []
    for raw_path in state["accepted"].get("adversarial", []):
        artifact = read_json(Path(raw_path), "finalize", "coverage")
        lanes.append(artifact["lane"])
        checks.extend(artifact["coverage"]["checks_run"])
        gaps.extend(artifact["coverage"]["gaps"])
    return {
        "review_lanes": lanes,
        "checks_run": list(dict.fromkeys(checks)),
        "gaps": list(dict.fromkeys(gaps)),
    }


def expected_trace_from_state(state: dict) -> dict[str, int]:
    return {
        "reviewers_completed": len(state.get("accepted", {}).get("adversarial", [])),
        "raw_candidates": len(state.get("raw_ids", [])),
        "canonical_candidates": len(state.get("canonical_ids", [])),
        "refutation_results": len(state.get("canonical_ids", [])),
        "judgment_results": len(state.get("disputed_ids", [])),
    }


def command_finalize() -> None:
    state = load_state()
    require(state.get("phase") in {"ready_finalize", "ready_finalize_empty", "finalized"},
            "finalize", "coordinator", "invalid_phase", "$.phase")
    scope = read_json(SCOPE_PATH, "finalize", "coordinator")
    validate_scope(scope, "finalize", "coordinator")
    require_worktree_unchanged(scope, "finalize", "coordinator")
    final_path = ROOT / "final" / "final.json"
    if state.get("phase") == "finalized":
        final = read_json(final_path, "finalize", "final")
        trace = final["trace"]
        print("FINALIZED", final_path, *(f"{key}={value}" for key, value in trace.items()))
        return
    findings: list[dict] = []
    rejected_findings: list[dict] = []
    unresolved_findings: list[dict] = []
    review_records: list[dict] = []
    rejected = 0
    unresolved = 0
    canonical_count = len(state.get("canonical_ids", []))
    refutation_count = 0
    judgment_count = 0
    if state["phase"] != "ready_finalize_empty":
        dedup = read_json(Path(state["accepted"]["dedup"]), "finalize", "dedup")
        canonical = {row["finding"]["id"]: row["finding"] for row in dedup["canonical_candidates"]}
        refutations: dict[str, dict] = {}
        for raw_path in state["accepted"]["refutation"]:
            artifact = read_json(Path(raw_path), "finalize", "refutation")
            for result in artifact["results"]:
                refutations[result["candidate_id"]] = result
        judgments: dict[str, dict] = {}
        for raw_path in state["accepted"].get("judgment", []):
            artifact = read_json(Path(raw_path), "finalize", "judgment")
            for result in artifact["results"]:
                judgments[result["candidate_id"]] = result
        refutation_count = len(refutations)
        judgment_count = len(judgments)
        for candidate_id in state["canonical_ids"]:
            case_for = canonical[candidate_id]
            refutation = refutations[candidate_id]
            challenge = {
                "verdict": refutation["verdict"],
                "correctness_analysis": refutation["correctness_analysis"],
                "proportionality_analysis": refutation["proportionality_analysis"],
                "evidence": refutation["evidence"],
                "proposed_finding": refutation["replacement_finding"],
                "residual_uncertainty": refutation["residual_uncertainty"],
            }
            if refutation["verdict"] == "uphold":
                presented_finding = case_for
                findings.append(presented_finding)
                final_judgment = {
                    "source": "refutation",
                    "verdict": "uphold",
                    "basis": [
                        refutation["correctness_analysis"],
                        refutation["proportionality_analysis"],
                    ],
                    "evidence": refutation["evidence"],
                    "residual_risk": refutation["residual_uncertainty"],
                }
            else:
                disputed_finding = (
                    refutation["replacement_finding"]
                    if refutation["verdict"] == "modify"
                    else case_for
                )
                judgment = judgments[candidate_id]
                if judgment["verdict"] == "uphold":
                    presented_finding = disputed_finding
                    findings.append(presented_finding)
                elif judgment["verdict"] == "modify":
                    presented_finding = judgment["final_finding"]
                    findings.append(presented_finding)
                elif judgment["verdict"] == "reject":
                    presented_finding = disputed_finding
                    rejected += 1
                    rejected_findings.append({
                        "finding": presented_finding,
                        "refutation_verdict": refutation["verdict"],
                        "judgment_verdict": "reject",
                        "reason": " ".join(judgment["resolved_points"]),
                    })
                else:
                    presented_finding = disputed_finding
                    unresolved += 1
                    unresolved_findings.append({
                        "finding": presented_finding,
                        "refutation_verdict": refutation["verdict"],
                        "judgment_verdict": "unresolved",
                        "resolved_points": judgment["resolved_points"],
                        "residual_risk": judgment["residual_risk"],
                    })
                final_judgment = {
                    "source": "judgment",
                    "verdict": judgment["verdict"],
                    "basis": judgment["resolved_points"],
                    "evidence": judgment["evidence"],
                    "residual_risk": judgment["residual_risk"],
                }
            review_records.append({
                "candidate_id": candidate_id,
                "case_for": case_for,
                "challenge": challenge,
                "final_judgment": final_judgment,
                "presented_finding": presented_finding,
            })
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    findings.sort(key=lambda item: (priority_order[item["priority"]], item["id"]))
    rejected_findings.sort(
        key=lambda item: (
            priority_order[item["finding"]["priority"]],
            item["finding"]["id"],
        )
    )
    unresolved_findings.sort(
        key=lambda item: (
            priority_order[item["finding"]["priority"]],
            item["finding"]["id"],
        )
    )
    review_records.sort(key=lambda item: item["candidate_id"])
    trace = {
        "reviewers_completed": len(state["accepted"].get("adversarial", [])),
        "raw_candidates": len(state.get("raw_ids", [])),
        "canonical_candidates": canonical_count,
        "refutation_results": refutation_count,
        "judgment_results": judgment_count,
        "rejected_findings": rejected,
        "unresolved": unresolved,
        "final_findings": len(findings),
    }
    require(canonical_count == len(findings) + rejected + unresolved,
            "finalize", "coordinator", "trace_invariant", "$.trace")
    final = {
        "schema_version": SCHEMA_VERSION,
        "scope": scope,
        "findings": findings,
        "rejected_findings": rejected_findings,
        "unresolved_findings": unresolved_findings,
        "review_records": review_records,
        "coverage": aggregate_coverage(state),
        "trace": trace,
    }
    validate_final_payload(final, scope, expected_trace_from_state(state))
    atomic_write(final_path, final)
    state["phase"] = "finalized"
    save_state(state)
    print("FINALIZED", final_path, *(f"{key}={value}" for key, value in trace.items()))


def command_retry_packet(raw_packet_path: str) -> None:
    state = load_state()
    try:
        old_path = safe_path(raw_packet_path, must_exist=True, reject_symlink=True)
    except (ValueError, FileNotFoundError) as exc:
        raise ValidationError("retry", "coordinator", "invalid_packet_path", [raw_packet_path]) from exc
    packet = read_json(old_path, "retry", "coordinator")
    stage = packet.get("stage", "retry")
    validate_packet(packet, stage, packet.get("task_id", "coordinator"))
    require_current_packet(state, old_path, packet)
    scope = read_json(SCOPE_PATH, stage, packet["task_id"])
    validate_scope(scope, stage, packet["task_id"])
    require_worktree_unchanged(scope, stage, packet["task_id"])
    active = state.get("current_packets", {}).get(stage, [])
    require(str(old_path) in [str(safe_path(item)) for item in active], stage,
            packet["task_id"], "packet_not_current", str(old_path))
    new_packet_path, output_path, task_id = make_packet(
        state,
        stage=stage,
        agent_id=packet["agent_id"],
        input_paths=packet["input_paths"],
        assigned_ids=packet["assigned_ids"],
        lane=packet["lane"],
        instructions=packet["instructions"],
        attempt=packet["attempt"] + 1,
    )
    paths = state["current_packets"][stage]
    paths.remove(str(old_path))
    save_state(state)
    print(f"PACKET_RETRIED {stage} {task_id} {new_packet_path} {output_path}")


def command_status() -> None:
    state = load_state()
    phase = nonempty_string(state.get("phase"), "status", "coordinator", "$.phase")
    print(f"STATUS {phase}")
    stage = phase if phase in {"adversarial", "dedup", "refutation", "judgment"} else None
    if stage is not None:
        for packet_path, packet in current_packets(state, stage):
            print(
                f"TASK {stage} {packet['task_id']} attempt={packet['attempt']} "
                f"packet={packet_path} output={packet['output_path']}"
            )
    if phase == "finalized":
        print(f"FINAL {ROOT / 'final' / 'final.json'}")


def source_path(scope: dict, location: dict, field: str) -> Path:
    stage = "validate-final"
    task_id = "final"
    repository = load_bound_repository(stage, task_id)
    raw_path = Path(location["path"])
    candidate = raw_path.resolve(strict=False) if raw_path.is_absolute() else (
        repository / raw_path
    ).resolve(strict=False)
    try:
        candidate.relative_to(repository)
    except ValueError as exc:
        raise ValidationError(stage, task_id, "source_path_outside_repository", [field]) from exc
    require(candidate.is_file(), stage, task_id, "source_path_missing", field)
    return candidate


def command_validate_final() -> None:
    expected_scope = read_json(SCOPE_PATH, "validate-final", "scope")
    validate_scope(expected_scope, "validate-final", "scope")
    require_worktree_unchanged(expected_scope, "validate-final", "scope")
    final_path = ROOT / "final" / "final.json"
    final = read_json(final_path, "validate-final", "final")
    state = load_state()
    require(state.get("phase") == "finalized", "validate-final", "final",
            "invalid_phase", "$.phase")
    validate_final_payload(final, expected_scope, expected_trace_from_state(state))
    located_findings = [
        (f"$.findings[{index}].location", finding)
        for index, finding in enumerate(final["findings"])
    ] + [
        (f"$.rejected_findings[{index}].finding.location", rejected["finding"])
        for index, rejected in enumerate(final["rejected_findings"])
    ] + [
        (f"$.unresolved_findings[{index}].finding.location", unresolved_finding["finding"])
        for index, unresolved_finding in enumerate(final["unresolved_findings"])
    ] + [
        (f"$.review_records[{index}].case_for.location", record["case_for"])
        for index, record in enumerate(final["review_records"])
    ] + [
        (f"$.review_records[{index}].challenge.proposed_finding.location",
         record["challenge"]["proposed_finding"])
        for index, record in enumerate(final["review_records"])
        if record["challenge"]["proposed_finding"] is not None
    ]
    for field, finding in located_findings:
        path = source_path(final["scope"], finding["location"], field)
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            line_count = sum(1 for _ in handle)
        require(finding["location"]["end_line"] <= line_count,
                "validate-final", "final", "source_line_out_of_range", field)
    print(
        f"FINAL_VALID {final_path} findings={len(final['findings'])} "
        f"rejected={len(final['rejected_findings'])} "
        f"unresolved={len(final['unresolved_findings'])} "
        f"review_records={len(final['review_records'])}"
    )


def parse_worker_count(raw: str, stage: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationError(stage, "coordinator", "invalid_worker_count", [raw]) from exc
    require(value >= 1, stage, "coordinator", "invalid_worker_count", raw)
    return value


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print("USAGE pipeline.py <command>")
        raise SystemExit(2)
    command = argv[1]
    try:
        if command == "init" and len(argv) == 2:
            command_init()
        elif command == "seal-adversarial" and len(argv) >= 3:
            command_seal_adversarial(argv[2:])
        elif command == "accept-dedup" and len(argv) == 5 and argv[2] == "--workers":
            command_accept_dedup(argv[4], parse_worker_count(argv[3], "dedup"))
        elif command == "accept-refutation" and len(argv) >= 5 and argv[2] == "--workers":
            command_accept_refutation(argv[4:], parse_worker_count(argv[3], "refutation"))
        elif command == "accept-judgment" and len(argv) >= 3:
            command_accept_judgment(argv[2:])
        elif command == "retry-packet" and len(argv) == 3:
            command_retry_packet(argv[2])
        elif command == "scaffold-artifact" and len(argv) == 3:
            command_scaffold_artifact(argv[2])
        elif command == "validate-artifact" and len(argv) == 4:
            command_validate_artifact(argv[2], argv[3])
        elif command == "status" and len(argv) == 2:
            command_status()
        elif command == "finalize" and len(argv) == 2:
            command_finalize()
        elif command == "validate-final" and len(argv) == 2:
            command_validate_final()
        else:
            print(f"INVALID_COMMAND {command}")
            raise SystemExit(2)
    except ValidationError as error:
        validation_failed(error)


if __name__ == "__main__":
    main(sys.argv)
