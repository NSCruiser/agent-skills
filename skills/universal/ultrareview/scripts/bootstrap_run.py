#!/usr/bin/env python3
"""Create a harness-independent Ultrareview run from packaged resources."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
PACKAGED_FILES = {
    SKILL_ROOT / "scripts" / "pipeline.py": "pipeline.py",
    SKILL_ROOT / "references" / "pipeline-schemas.json": "pipeline-schemas.json",
    SKILL_ROOT / "references" / "stage-instructions.json": "stage-instructions.json",
}
STAGE_NAMES = ("adversarial", "dedup", "refutation", "judgment")


def fail(message: str) -> None:
    raise SystemExit(f"BOOTSTRAP_FAILED {message}")


def resolved_directory(raw: str, label: str) -> Path:
    path = Path(raw).resolve(strict=False)
    if not path.is_dir():
        fail(f"{label}_not_directory {path}")
    return path


def resolved_skill(raw: str, label: str, expected_name: str) -> Path:
    path = Path(raw).resolve(strict=False)
    if not path.is_file():
        fail(f"{label}_not_file {path}")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        frontmatter_end = lines.index("---", 1)
    except (OSError, UnicodeError, ValueError):
        fail(f"{label}_invalid_frontmatter {path}")
    if not lines or lines[0] != "---":
        fail(f"{label}_invalid_frontmatter {path}")
    names = []
    for line in lines[1:frontmatter_end]:
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            names.append(value.strip().strip("'\""))
    if names != [expected_name]:
        fail(f"{label}_wrong_name {path}")
    return path


def ensure_disjoint(run_root: Path, repository: Path) -> None:
    try:
        run_root.relative_to(repository)
    except ValueError:
        pass
    else:
        fail(f"run_root_inside_repository {run_root}")
    try:
        repository.relative_to(run_root)
    except ValueError:
        pass
    else:
        fail(f"run_root_contains_repository {run_root}")


def atomic_copy(source: Path, target: Path) -> None:
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    shutil.copyfile(source, temporary)
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def atomic_write_json(target: Path, value: dict) -> None:
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def verify_scope_repository(scope_path: Path, repository: Path) -> None:
    try:
        with scope_path.open("r", encoding="utf-8") as handle:
            scope = json.load(handle)
        declared = Path(scope["repository_path"]).resolve(strict=False)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        fail(f"invalid_scope {scope_path} {type(exc).__name__}")
    if declared != repository:
        fail(f"scope_repository_mismatch {declared}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="Repository being reviewed.")
    parser.add_argument(
        "--ponytail-review-skill",
        required=True,
        help="Current ponytail-review SKILL.md to freeze for this run.",
    )
    parser.add_argument(
        "--run-root",
        help="New run directory. Defaults to a fresh directory under the system temp root.",
    )
    parser.add_argument("--scope", help="Optional prepared scope.json to copy into the run.")
    parser.add_argument("--lenses", help="Optional prepared lenses.json to copy into the run.")
    args = parser.parse_args()
    if bool(args.scope) != bool(args.lenses):
        parser.error("--scope and --lenses must be supplied together")
    return args


def main() -> None:
    args = parse_args()
    repository = resolved_directory(args.repository, "repository")
    ponytail_review_skill = resolved_skill(
        args.ponytail_review_skill, "ponytail_review_skill", "ponytail-review"
    )
    if args.run_root:
        run_root = Path(args.run_root).resolve(strict=False)
        ensure_disjoint(run_root, repository)
        try:
            run_root.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            fail(f"cannot_create_run_root {run_root} {type(exc).__name__}")
    else:
        run_root = Path(tempfile.mkdtemp(prefix="ultrareview-")).resolve()
        ensure_disjoint(run_root, repository)

    for stage in STAGE_NAMES:
        (run_root / "packets" / stage).mkdir(parents=True)
        (run_root / "artifacts" / stage).mkdir(parents=True)
    (run_root / "final").mkdir()
    ponytail_policy_path = run_root / "policies" / "ponytail-review" / "SKILL.md"
    ponytail_policy_path.parent.mkdir(parents=True)

    for source, relative_target in PACKAGED_FILES.items():
        if not source.is_file():
            fail(f"packaged_file_missing {source}")
        atomic_copy(source, run_root / relative_target)
    atomic_copy(ponytail_review_skill, ponytail_policy_path)

    repository_binding_path = run_root / "repository.json"
    atomic_write_json(repository_binding_path, {"repository_path": str(repository)})

    if args.scope and args.lenses:
        scope_path = Path(args.scope).resolve(strict=True)
        lenses_path = Path(args.lenses).resolve(strict=True)
        verify_scope_repository(scope_path, repository)
        atomic_copy(scope_path, run_root / "scope.json")
        atomic_copy(lenses_path, run_root / "lenses.json")

    print(f"RUN_CREATED {run_root}")
    print(f"REPOSITORY_BINDING_PATH {repository_binding_path}")
    print(f"SCOPE_PATH {run_root / 'scope.json'}")
    print(f"LENSES_PATH {run_root / 'lenses.json'}")
    print(f"PONYTAIL_POLICY_PATH {ponytail_policy_path}")
    print(f"COORDINATOR_PATH {run_root / 'pipeline.py'}")


if __name__ == "__main__":
    main()
