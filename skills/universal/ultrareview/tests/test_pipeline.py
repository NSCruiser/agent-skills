#!/usr/bin/env python3
"""Behavioral tests for the portable Ultrareview coordinator."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = SKILL_ROOT / "scripts" / "bootstrap_run.py"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class PipelineCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="ultrareview-test-")
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()
        (self.repository / "sample.py").write_text(
            "\n".join(f"line {index}" for index in range(1, 21)) + "\n",
            encoding="utf-8",
        )
        instructions = self.repository / "AGENTS.md"
        instructions.write_text("Review read-only.\n", encoding="utf-8")
        subprocess.run(
            ["git", "init", "-q", str(self.repository)],
            text=True,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repository), "add", "--all"],
            text=True,
            capture_output=True,
            check=True,
        )
        baseline = subprocess.run(
            [
                "git", "-C", str(self.repository), "status", "--short",
                "--untracked-files=all",
            ],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        self.scope_source = self.root / "prepared-scope.json"
        self.lenses_source = self.root / "prepared-lenses.json"
        write_json(self.scope_source, {
            "schema_version": 4,
            "repository_path": str(self.repository),
            "review_kind": "topic",
            "target": "Synthetic persistence topic",
            "comparison_base": None,
            "topic": "Synthetic persistence behavior",
            "output_language": "English",
            "exclusions": ["UI-only behavior"],
            "instruction_files": [str(instructions)],
            "finding_standard": "Only discrete actionable defects with a reachable impact.",
            "baseline_worktree_status": baseline,
        })
        write_json(self.lenses_source, {
            "schema_version": 4,
            "reviewers": [{
                "agent_id": "reviewer-01",
                "lane": "state transitions",
                "focus": ["Persistence and recovery invariants"],
            }],
        })
        self.run_root = self.root / "run"
        result = self.run_process(
            BOOTSTRAP,
            "--repository", str(self.repository),
            "--run-root", str(self.run_root),
            "--scope", str(self.scope_source),
            "--lenses", str(self.lenses_source),
        )
        self.assertIn("RUN_CREATED", result.stdout)
        self.pipeline = self.run_root / "pipeline.py"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_process(
        self,
        script: Path,
        *arguments: str,
        expected_code: int = 0,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(script), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != expected_code:
            self.fail(
                f"Unexpected exit {result.returncode}; stdout={result.stdout!r}; "
                f"stderr={result.stderr!r}"
            )
        return result

    def command(self, *arguments: str, expected_code: int = 0) -> subprocess.CompletedProcess[str]:
        return self.run_process(self.pipeline, *arguments, expected_code=expected_code)

    def run_argv(
        self,
        arguments: list[str],
        expected_code: int = 0,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(arguments, text=True, capture_output=True, check=False)
        if result.returncode != expected_code:
            self.fail(
                f"Unexpected exit {result.returncode}; stdout={result.stdout!r}; "
                f"stderr={result.stderr!r}"
            )
        return result

    def one_packet(self, stage: str) -> tuple[Path, dict]:
        paths = sorted((self.run_root / "packets" / stage).glob("*.json"))
        self.assertEqual(len(paths), 1)
        return paths[0], json.loads(paths[0].read_text(encoding="utf-8"))

    def finding(self, finding_id: str) -> dict:
        return {
            "id": finding_id,
            "priority": "P1",
            "title": "Synthetic persistent state can be lost",
            "location": {
                "path": "sample.py", "start_line": 2, "end_line": 4, "side": "new",
            },
            "context": "The synthetic path runs during a persistent mutation.",
            "trigger": "A deterministic test trigger reaches the path.",
            "impact": "A stored value can become unavailable after the operation.",
            "manifestation": {
                "kind": "reasoned_scenario",
                "setup": "A stored record exists with value 100 and the affected mutation path is enabled.",
                "steps": [
                    "Run the mutation that enters sample.py lines 2 through 4.",
                    "Reload the same record from persistent storage.",
                ],
                "failure": "The reloaded record no longer contains the previously stored value 100.",
            },
            "evidence": [{
                "kind": "source",
                "location": {
                    "path": "sample.py", "start_line": 2, "end_line": 4, "side": "new",
                },
                "reference": "sample.py synthetic mutation",
                "statement": "The fixture represents the inspected source path.",
                "status": "verified",
            }],
            "recommendation": "Preserve the value and add a focused regression test.",
            "confidence": "high",
        }

    def qualification(self, disposition: str = "qualify") -> dict:
        value = {
            "production_reachable": "yes",
            "reachability_path": [{
                "location": {
                    "path": "sample.py", "start_line": 2, "end_line": 4, "side": "new",
                },
                "reference": "mutation entry to persistent reload",
            }],
            "inside_authorized_scope": "yes",
            "introduced_by_change": "not_applicable",
            "material_impact": "yes",
            "fix_value": "positive",
            "likely_author_would_fix_now": "yes",
        }
        if disposition == "reject":
            value["production_reachable"] = "no"
            value["reachability_path"] = []
        elif disposition == "unresolved":
            value["production_reachable"] = "unknown"
            value["reachability_path"] = []
        return value

    def reachability_evidence(self) -> dict:
        return {
            "kind": "caller",
            "location": {
                "path": "sample.py", "start_line": 2, "end_line": 4, "side": "new",
            },
            "reference": "synthetic production caller",
            "statement": "A production caller reaches the synthetic mutation path.",
            "status": "verified",
        }

    def write_adversarial(self, candidates: list[dict]) -> tuple[Path, Path]:
        packet_path, packet = self.one_packet("adversarial")
        artifact_path = Path(packet["output_path"])
        write_json(artifact_path, {
            "schema_version": 4,
            "stage": "adversarial",
            "task_id": packet["task_id"],
            "attempt": packet["attempt"],
            "agent_id": packet["agent_id"],
            "lane": packet["lane"],
            "coverage": {
                "inspected_paths": ["sample.py"],
                "checks_run": ["synthetic source inspection"],
                "gaps": [],
            },
            "candidates": candidates,
        })
        validation = self.run_argv(packet["validation_command"])
        self.assertIn("ARTIFACT_VALID", validation.stdout)
        return packet_path, artifact_path

    def test_empty_review_finalizes_and_validates(self) -> None:
        self.command("init")
        _, artifact_path = self.write_adversarial([])
        result = self.command("seal-adversarial", str(artifact_path))
        self.assertIn("FINALIZED", result.stdout)
        self.command("validate-final")
        final = json.loads((self.run_root / "final" / "final.json").read_text(encoding="utf-8"))
        self.assertEqual(final["schema_version"], 4)
        self.assertEqual(final["findings"], [])
        self.assertEqual(final["rejected_findings"], [])
        self.assertEqual(final["unresolved_findings"], [])
        self.assertEqual(final["review_records"], [])
        self.assertEqual(final["trace"]["canonical_candidates"], 0)

    def test_validate_final_rejects_trace_counts_that_disagree_with_state(self) -> None:
        self.command("init")
        _, artifact_path = self.write_adversarial([])
        self.command("seal-adversarial", str(artifact_path))
        final_path = self.run_root / "final" / "final.json"
        original = json.loads(final_path.read_text(encoding="utf-8"))

        for key in ("reviewers_completed", "raw_candidates", "judgment_results"):
            tampered = json.loads(json.dumps(original))
            tampered["trace"][key] += 1
            write_json(final_path, tampered)
            failure = self.command("validate-final", expected_code=2)
            self.assertIn(f"$.trace.{key}", failure.stdout)

        write_json(final_path, original)
        self.command("validate-final")

    def test_bootstrap_binding_supports_scope_written_after_creation(self) -> None:
        run_root = self.root / "postwritten-run"
        result = self.run_process(
            BOOTSTRAP,
            "--repository", str(self.repository),
            "--run-root", str(run_root),
        )
        self.assertIn("REPOSITORY_BINDING_PATH", result.stdout)
        write_json(
            run_root / "scope.json",
            json.loads(self.scope_source.read_text(encoding="utf-8")),
        )
        write_json(
            run_root / "lenses.json",
            json.loads(self.lenses_source.read_text(encoding="utf-8")),
        )
        initialized = self.run_process(run_root / "pipeline.py", "init")
        self.assertIn("STAGE_READY adversarial 1", initialized.stdout)

    def test_bootstrap_binding_rejects_mismatched_scope_repository(self) -> None:
        run_root = self.root / "mismatched-run"
        self.run_process(
            BOOTSTRAP,
            "--repository", str(self.repository),
            "--run-root", str(run_root),
        )
        other_repository = self.root / "other-repository"
        other_repository.mkdir()
        scope = json.loads(self.scope_source.read_text(encoding="utf-8"))
        scope["repository_path"] = "relative-repository"
        write_json(run_root / "scope.json", scope)
        write_json(
            run_root / "lenses.json",
            json.loads(self.lenses_source.read_text(encoding="utf-8")),
        )
        relative_failure = self.run_process(
            run_root / "pipeline.py", "init", expected_code=2,
        )
        self.assertIn("repository_not_absolute", relative_failure.stdout)

        scope["repository_path"] = str(other_repository)
        write_json(run_root / "scope.json", scope)
        failure = self.run_process(
            run_root / "pipeline.py", "init", expected_code=2,
        )
        self.assertIn("scope_repository_mismatch", failure.stdout)

    def test_worktree_drift_blocks_artifact_validation(self) -> None:
        self.command("init")
        packet_path, _ = self.one_packet("adversarial")
        (self.repository / "sample.py").write_text("mutated\n", encoding="utf-8")
        failure = self.command(
            "scaffold-artifact", str(packet_path), expected_code=2,
        )
        self.assertIn("worktree_changed", failure.stdout)

    def test_same_status_content_drift_is_blocked_by_repository_fingerprint(self) -> None:
        volatile = self.repository / "volatile.txt"
        volatile.write_text("before\n", encoding="utf-8")
        baseline = subprocess.run(
            [
                "git", "-C", str(self.repository), "status", "--short",
                "--untracked-files=all",
            ],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        scope_path = self.run_root / "scope.json"
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
        scope["baseline_worktree_status"] = baseline
        write_json(scope_path, scope)

        self.command("init")
        packet_path, _ = self.one_packet("adversarial")
        volatile.write_text("after\n", encoding="utf-8")
        failure = self.command(
            "scaffold-artifact", str(packet_path), expected_code=2,
        )
        self.assertIn("repository_snapshot_changed", failure.stdout)

    def test_clean_branch_switch_is_blocked_by_repository_fingerprint(self) -> None:
        for arguments in (
            ["config", "user.name", "Ultrareview Test"],
            ["config", "user.email", "ultrareview@example.invalid"],
            ["commit", "-q", "-m", "baseline"],
            ["switch", "-q", "-c", "alternate"],
        ):
            subprocess.run(
                ["git", "-C", str(self.repository), *arguments],
                text=True,
                capture_output=True,
                check=True,
            )
        (self.repository / "sample.py").write_text("alternate\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.repository), "add", "sample.py"],
            text=True,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repository), "commit", "-q", "-m", "alternate"],
            text=True,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repository), "switch", "-q", "-"],
            text=True,
            capture_output=True,
            check=True,
        )
        scope_path = self.run_root / "scope.json"
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
        scope["baseline_worktree_status"] = []
        write_json(scope_path, scope)

        self.command("init")
        packet_path, _ = self.one_packet("adversarial")
        subprocess.run(
            ["git", "-C", str(self.repository), "switch", "-q", "alternate"],
            text=True,
            capture_output=True,
            check=True,
        )
        failure = self.command(
            "scaffold-artifact", str(packet_path), expected_code=2,
        )
        self.assertIn("repository_snapshot_changed", failure.stdout)

    def test_manifestation_requires_at_least_one_concrete_step(self) -> None:
        self.command("init")
        packet_path, packet = self.one_packet("adversarial")
        self.command("scaffold-artifact", str(packet_path))
        artifact_path = Path(packet["output_path"])
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        candidate = self.finding("reviewer-01:C01")
        candidate["manifestation"]["steps"] = []
        artifact["coverage"] = {
            "inspected_paths": ["sample.py"],
            "checks_run": ["synthetic source inspection"],
            "gaps": [],
        }
        artifact["candidates"] = [candidate]
        write_json(artifact_path, artifact)

        failure = self.run_argv(packet["validation_command"], expected_code=2)
        self.assertIn("$.candidates[0].manifestation.steps", failure.stdout)

    def test_low_impact_p3_candidate_is_rejected(self) -> None:
        self.command("init")
        packet_path, packet = self.one_packet("adversarial")
        self.command("scaffold-artifact", str(packet_path))
        artifact_path = Path(packet["output_path"])
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        candidate = self.finding("reviewer-01:C01")
        candidate["priority"] = "P3"
        artifact["coverage"] = {
            "inspected_paths": ["sample.py"],
            "checks_run": ["synthetic source inspection"],
            "gaps": [],
        }
        artifact["candidates"] = [candidate]
        write_json(artifact_path, artifact)
        failure = self.run_argv(packet["validation_command"], expected_code=2)
        self.assertIn("$.candidates[0].priority", failure.stdout)

    def test_verified_reproduction_requires_execution_evidence_and_rejects_placeholders(self) -> None:
        self.command("init")
        packet_path, packet = self.one_packet("adversarial")
        self.command("scaffold-artifact", str(packet_path))
        artifact_path = Path(packet["output_path"])
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["coverage"] = {
            "inspected_paths": ["sample.py"],
            "checks_run": ["synthetic source inspection"],
            "gaps": [],
        }
        candidate = self.finding("reviewer-01:C01")
        candidate["manifestation"]["kind"] = "verified_reproduction"
        artifact["candidates"] = [candidate]
        write_json(artifact_path, artifact)

        missing_evidence = self.run_argv(packet["validation_command"], expected_code=2)
        self.assertIn("verified_reproduction_requires_execution_evidence",
                      missing_evidence.stdout)

        candidate["evidence"].append({
            "kind": "command",
            "location": None,
            "reference": "synthetic-reproduction --record 100",
            "statement": "The reproduction command produced the described failure.",
            "status": "verified",
        })
        write_json(artifact_path, artifact)
        self.run_argv(packet["validation_command"])

        candidate["manifestation"]["kind"] = "reasoned_scenario"
        candidate["manifestation"]["setup"] = "The issue occurs."
        write_json(artifact_path, artifact)
        placeholder = self.run_argv(packet["validation_command"], expected_code=2)
        self.assertIn("non_concrete_manifestation", placeholder.stdout)

        candidate["manifestation"]["setup"] = "Ｔｈｅ ｉｓｓｕｅ ｏｃｃｕｒｓ。"
        write_json(artifact_path, artifact)
        fullwidth_placeholder = self.run_argv(packet["validation_command"], expected_code=2)
        self.assertIn("non_concrete_manifestation", fullwidth_placeholder.stdout)

    def test_rejected_candidate_is_preserved_with_reason(self) -> None:
        self.command("init")
        raw = self.finding("reviewer-01:C01")
        _, adversarial_path = self.write_adversarial([raw])
        self.command("seal-adversarial", str(adversarial_path))

        dedup_packet_path, dedup_packet = self.one_packet("dedup")
        dedup_path = Path(dedup_packet["output_path"])
        canonical = self.finding("F001")
        write_json(dedup_path, {
            "schema_version": 4,
            "stage": "dedup",
            "task_id": dedup_packet["task_id"],
            "attempt": dedup_packet["attempt"],
            "agent_id": dedup_packet["agent_id"],
            "canonical_candidates": [{
                "finding": canonical,
                "source_candidate_ids": ["reviewer-01:C01"],
                "merge_basis": "The only raw candidate maps directly to this finding.",
            }],
        })
        self.command("validate-artifact", str(dedup_packet_path), str(dedup_path))
        self.command("accept-dedup", "--workers", "3", str(dedup_path))

        refutation_packet_path, refutation_packet = self.one_packet("refutation")
        refutation_path = Path(refutation_packet["output_path"])
        write_json(refutation_path, {
            "schema_version": 4,
            "stage": "refutation",
            "task_id": refutation_packet["task_id"],
            "attempt": refutation_packet["attempt"],
            "agent_id": refutation_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "refute",
                "qualification": self.qualification("reject"),
                "correctness_analysis": "The synthetic call path is not reachable as claimed.",
                "proportionality_analysis": "No remediation is justified for unreachable behavior.",
                "evidence": [],
                "replacement_finding": None,
                "residual_uncertainty": "",
            }],
        })
        self.command("validate-artifact", str(refutation_packet_path), str(refutation_path))
        self.command("accept-refutation", "--workers", "2", str(refutation_path))

        judgment_packet_path, judgment_packet = self.one_packet("judgment")
        judgment_path = Path(judgment_packet["output_path"])
        reason = "Direct inspection confirms that the claimed call path is unreachable."
        write_json(judgment_path, {
            "schema_version": 4,
            "stage": "judgment",
            "task_id": judgment_packet["task_id"],
            "attempt": judgment_packet["attempt"],
            "agent_id": judgment_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "reject",
                "qualification": self.qualification("reject"),
                "resolved_points": [reason],
                "evidence": [],
                "final_finding": None,
                "residual_risk": "",
            }],
        })
        self.command("validate-artifact", str(judgment_packet_path), str(judgment_path))
        self.command("accept-judgment", str(judgment_path))
        self.command("finalize")
        self.command("validate-final")

        final = json.loads((self.run_root / "final" / "final.json").read_text(encoding="utf-8"))
        self.assertEqual(final["findings"], [])
        self.assertEqual(len(final["rejected_findings"]), 1)
        rejected = final["rejected_findings"][0]
        self.assertEqual(rejected["finding"]["id"], "F001")
        self.assertEqual(rejected["finding"]["manifestation"]["kind"], "reasoned_scenario")
        self.assertEqual(len(rejected["finding"]["manifestation"]["steps"]), 2)
        self.assertEqual(rejected["refutation_verdict"], "refute")
        self.assertEqual(rejected["reason"], reason)
        self.assertEqual(final["trace"]["rejected_findings"], 1)
        self.assertEqual(final["unresolved_findings"], [])
        review_record = final["review_records"][0]
        self.assertEqual(review_record["case_for"]["id"], "F001")
        self.assertEqual(review_record["challenge"]["verdict"], "refute")
        self.assertEqual(review_record["final_judgment"]["source"], "judgment")
        self.assertEqual(review_record["final_judgment"]["basis"], [reason])
        self.assertEqual(review_record["presented_finding"], rejected["finding"])

        judgment_artifact = json.loads(judgment_path.read_text(encoding="utf-8"))
        judgment_artifact["results"][0]["resolved_points"] = ["Changed after acceptance."]
        write_json(judgment_path, judgment_artifact)
        changed = self.command("validate-final", expected_code=2)
        self.assertIn("accepted_artifact_changed", changed.stdout)

    def test_upheld_candidate_is_confirmed_by_fresh_judgment(self) -> None:
        self.command("init")
        raw = self.finding("reviewer-01:C01")
        _, adversarial_path = self.write_adversarial([raw])
        self.command("seal-adversarial", str(adversarial_path))

        dedup_packet_path, dedup_packet = self.one_packet("dedup")
        dedup_path = Path(dedup_packet["output_path"])
        canonical = self.finding("F001")
        write_json(dedup_path, {
            "schema_version": 4,
            "stage": "dedup",
            "task_id": dedup_packet["task_id"],
            "attempt": dedup_packet["attempt"],
            "agent_id": dedup_packet["agent_id"],
            "canonical_candidates": [{
                "finding": canonical,
                "source_candidate_ids": ["reviewer-01:C01"],
                "merge_basis": "The only raw candidate maps directly to this finding.",
            }],
        })
        self.command("validate-artifact", str(dedup_packet_path), str(dedup_path))
        self.command("accept-dedup", "--workers", "1", str(dedup_path))

        refutation_packet_path, refutation_packet = self.one_packet("refutation")
        refutation_path = Path(refutation_packet["output_path"])
        correctness = "The source path and state transition make the failure reachable."
        proportionality = "The persistent loss justifies the focused remediation."
        write_json(refutation_path, {
            "schema_version": 4,
            "stage": "refutation",
            "task_id": refutation_packet["task_id"],
            "attempt": refutation_packet["attempt"],
            "agent_id": refutation_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "uphold",
                "qualification": self.qualification(),
                "correctness_analysis": correctness,
                "proportionality_analysis": proportionality,
                "evidence": [self.reachability_evidence()],
                "replacement_finding": None,
                "residual_uncertainty": "",
            }],
        })
        self.command("validate-artifact", str(refutation_packet_path), str(refutation_path))
        self.command("accept-refutation", "--workers", "1", str(refutation_path))

        judgment_packet_path, judgment_packet = self.one_packet("judgment")
        judgment_path = Path(judgment_packet["output_path"])
        judgment_basis = "Fresh caller inspection confirms the actionable failure."
        write_json(judgment_path, {
            "schema_version": 4,
            "stage": "judgment",
            "task_id": judgment_packet["task_id"],
            "attempt": judgment_packet["attempt"],
            "agent_id": judgment_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "uphold",
                "qualification": self.qualification(),
                "resolved_points": [judgment_basis],
                "evidence": [self.reachability_evidence()],
                "final_finding": None,
                "residual_risk": "",
            }],
        })
        self.command("validate-artifact", str(judgment_packet_path), str(judgment_path))
        self.command("accept-judgment", str(judgment_path))
        self.command("finalize")
        self.command("validate-final")

        final = json.loads((self.run_root / "final" / "final.json").read_text(encoding="utf-8"))
        self.assertEqual(len(final["findings"]), 1)
        record = final["review_records"][0]
        self.assertEqual(record["case_for"], canonical)
        self.assertEqual(record["challenge"]["verdict"], "uphold")
        self.assertEqual(record["final_judgment"]["source"], "judgment")
        self.assertEqual(record["final_judgment"]["basis"], [judgment_basis])
        self.assertEqual(record["presented_finding"], canonical)

        final["review_records"][0]["final_judgment"]["source"] = "refutation"
        final_path = self.run_root / "final" / "final.json"
        write_json(final_path, final)
        mismatch = self.command("validate-final", expected_code=2)
        self.assertIn("invalid_judgment_source", mismatch.stdout)

    def test_judgment_uphold_and_modify_preserve_final_basis_and_selected_finding(self) -> None:
        self.command("init")
        raw_one = self.finding("reviewer-01:C01")
        raw_two = self.finding("reviewer-01:C02")
        _, adversarial_path = self.write_adversarial([raw_one, raw_two])
        self.command("seal-adversarial", str(adversarial_path))

        dedup_packet_path, dedup_packet = self.one_packet("dedup")
        dedup_path = Path(dedup_packet["output_path"])
        canonical_one = self.finding("F001")
        canonical_two = self.finding("F002")
        write_json(dedup_path, {
            "schema_version": 4,
            "stage": "dedup",
            "task_id": dedup_packet["task_id"],
            "attempt": dedup_packet["attempt"],
            "agent_id": dedup_packet["agent_id"],
            "canonical_candidates": [
                {
                    "finding": canonical_one,
                    "source_candidate_ids": ["reviewer-01:C01"],
                    "merge_basis": "The first raw candidate remains independent.",
                },
                {
                    "finding": canonical_two,
                    "source_candidate_ids": ["reviewer-01:C02"],
                    "merge_basis": "The second raw candidate remains independent.",
                },
            ],
        })
        self.command("validate-artifact", str(dedup_packet_path), str(dedup_path))
        self.command("accept-dedup", "--workers", "1", str(dedup_path))

        refutation_packet_path, refutation_packet = self.one_packet("refutation")
        refutation_path = Path(refutation_packet["output_path"])
        write_json(refutation_path, {
            "schema_version": 4,
            "stage": "refutation",
            "task_id": refutation_packet["task_id"],
            "attempt": refutation_packet["attempt"],
            "agent_id": refutation_packet["agent_id"],
            "results": [
                {
                    "candidate_id": "F001",
                    "verdict": "refute",
                    "qualification": self.qualification("reject"),
                    "correctness_analysis": "The first call path initially appears unreachable.",
                    "proportionality_analysis": "No change would be justified if it were unreachable.",
                    "evidence": [],
                    "replacement_finding": None,
                    "residual_uncertainty": "",
                },
                {
                    "candidate_id": "F002",
                    "verdict": "refute",
                    "qualification": self.qualification("reject"),
                    "correctness_analysis": "The second manifestation overstates the observed failure.",
                    "proportionality_analysis": "The remedy should match the corrected impact.",
                    "evidence": [],
                    "replacement_finding": None,
                    "residual_uncertainty": "",
                },
            ],
        })
        self.command("validate-artifact", str(refutation_packet_path), str(refutation_path))
        self.command("accept-refutation", "--workers", "1", str(refutation_path))

        judgment_packet_path, judgment_packet = self.one_packet("judgment")
        judgment_path = Path(judgment_packet["output_path"])
        modified = self.finding("F002")
        modified["title"] = "Synthetic persistent state can become stale"
        modified["manifestation"]["failure"] = (
            "The reloaded record still shows value 100 after the source has changed to 125."
        )
        uphold_basis = "Caller inspection confirms that the first call path is reachable."
        modify_basis = "The second issue survives with a corrected stale-value manifestation."
        write_json(judgment_path, {
            "schema_version": 4,
            "stage": "judgment",
            "task_id": judgment_packet["task_id"],
            "attempt": judgment_packet["attempt"],
            "agent_id": judgment_packet["agent_id"],
            "results": [
                {
                    "candidate_id": "F001",
                    "verdict": "uphold",
                    "qualification": self.qualification(),
                    "resolved_points": [uphold_basis],
                    "evidence": [self.reachability_evidence()],
                    "final_finding": None,
                    "residual_risk": "",
                },
                {
                    "candidate_id": "F002",
                    "verdict": "modify",
                    "qualification": self.qualification(),
                    "resolved_points": [modify_basis],
                    "evidence": [self.reachability_evidence()],
                    "final_finding": modified,
                    "residual_risk": "",
                },
            ],
        })
        self.command("validate-artifact", str(judgment_packet_path), str(judgment_path))
        self.command("accept-judgment", str(judgment_path))
        self.command("finalize")
        self.command("validate-final")

        final = json.loads((self.run_root / "final" / "final.json").read_text(encoding="utf-8"))
        records = {record["candidate_id"]: record for record in final["review_records"]}
        self.assertEqual(records["F001"]["final_judgment"]["verdict"], "uphold")
        self.assertEqual(records["F001"]["final_judgment"]["basis"], [uphold_basis])
        self.assertEqual(records["F001"]["presented_finding"], canonical_one)
        self.assertEqual(records["F002"]["final_judgment"]["verdict"], "modify")
        self.assertEqual(records["F002"]["final_judgment"]["basis"], [modify_basis])
        self.assertEqual(records["F002"]["presented_finding"], modified)

        final_path = self.run_root / "final" / "final.json"
        final = json.loads(final_path.read_text(encoding="utf-8"))
        final["findings"] = [canonical_one, canonical_two]
        final["review_records"][1]["presented_finding"] = canonical_two
        write_json(final_path, final)
        tampered = self.command("validate-final", expected_code=2)
        self.assertIn("final_payload_mismatch", tampered.stdout)

    def test_judgment_uphold_keeps_refutation_replacement(self) -> None:
        self.command("init")
        raw = self.finding("reviewer-01:C01")
        _, adversarial_path = self.write_adversarial([raw])
        self.command("seal-adversarial", str(adversarial_path))

        dedup_packet_path, dedup_packet = self.one_packet("dedup")
        dedup_path = Path(dedup_packet["output_path"])
        canonical = self.finding("F001")
        write_json(dedup_path, {
            "schema_version": 4,
            "stage": "dedup",
            "task_id": dedup_packet["task_id"],
            "attempt": dedup_packet["attempt"],
            "agent_id": dedup_packet["agent_id"],
            "canonical_candidates": [{
                "finding": canonical,
                "source_candidate_ids": ["reviewer-01:C01"],
                "merge_basis": "The raw candidate maps directly to this finding.",
            }],
        })
        self.command("validate-artifact", str(dedup_packet_path), str(dedup_path))
        self.command("accept-dedup", "--workers", "1", str(dedup_path))

        refutation_packet_path, refutation_packet = self.one_packet("refutation")
        refutation_path = Path(refutation_packet["output_path"])
        replacement = self.finding("F001")
        replacement["title"] = "Synthetic persistent state can become stale"
        replacement["impact"] = "A stored value can remain stale after the operation."
        replacement["manifestation"]["failure"] = (
            "The reloaded record still contains value 100 instead of the new value 125."
        )
        write_json(refutation_path, {
            "schema_version": 4,
            "stage": "refutation",
            "task_id": refutation_packet["task_id"],
            "attempt": refutation_packet["attempt"],
            "agent_id": refutation_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "modify",
                "qualification": self.qualification(),
                "correctness_analysis": "The defect is stale state rather than lost state.",
                "proportionality_analysis": "A focused refresh fix remains proportionate.",
                "evidence": [self.reachability_evidence()],
                "replacement_finding": replacement,
                "residual_uncertainty": "",
            }],
        })
        self.command(
            "validate-artifact", str(refutation_packet_path), str(refutation_path),
        )
        self.command("accept-refutation", "--workers", "1", str(refutation_path))

        judgment_packet_path, judgment_packet = self.one_packet("judgment")
        judgment_path = Path(judgment_packet["output_path"])
        write_json(judgment_path, {
            "schema_version": 4,
            "stage": "judgment",
            "task_id": judgment_packet["task_id"],
            "attempt": judgment_packet["attempt"],
            "agent_id": judgment_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "uphold",
                "qualification": self.qualification(),
                "resolved_points": ["The corrected stale-state finding is actionable."],
                "evidence": [self.reachability_evidence()],
                "final_finding": None,
                "residual_risk": "",
            }],
        })
        self.command("validate-artifact", str(judgment_packet_path), str(judgment_path))
        self.command("accept-judgment", str(judgment_path))
        self.command("finalize")
        self.command("validate-final")

        final_path = self.run_root / "final" / "final.json"
        final = json.loads(final_path.read_text(encoding="utf-8"))
        self.assertEqual(final["findings"], [replacement])
        self.assertEqual(final["review_records"][0]["presented_finding"], replacement)

        final["findings"] = [canonical]
        final["review_records"][0]["presented_finding"] = canonical
        write_json(final_path, final)
        mismatch = self.command("validate-final", expected_code=2)
        self.assertIn("judgment_selection_mismatch", mismatch.stdout)

    def test_unresolved_candidate_is_structured_and_requires_nonempty_risk(self) -> None:
        self.command("init")
        raw = self.finding("reviewer-01:C01")
        _, adversarial_path = self.write_adversarial([raw])
        self.command("seal-adversarial", str(adversarial_path))

        dedup_packet_path, dedup_packet = self.one_packet("dedup")
        dedup_path = Path(dedup_packet["output_path"])
        write_json(dedup_path, {
            "schema_version": 4,
            "stage": "dedup",
            "task_id": dedup_packet["task_id"],
            "attempt": dedup_packet["attempt"],
            "agent_id": dedup_packet["agent_id"],
            "canonical_candidates": [{
                "finding": self.finding("F001"),
                "source_candidate_ids": ["reviewer-01:C01"],
                "merge_basis": "The only raw candidate maps directly to this finding.",
            }],
        })
        self.run_argv(dedup_packet["validation_command"])
        self.command("accept-dedup", "--workers", "1", str(dedup_path))

        refutation_packet_path, refutation_packet = self.one_packet("refutation")
        refutation_path = Path(refutation_packet["output_path"])
        replacement = self.finding("F001")
        replacement["manifestation"]["setup"] = (
            "The reviewed configuration fixture enables the persistent mutation path."
        )
        replacement["manifestation"]["failure"] = (
            "If the path executes, reloading the record may omit the stored value 100."
        )
        write_json(refutation_path, {
            "schema_version": 4,
            "stage": "refutation",
            "task_id": refutation_packet["task_id"],
            "attempt": refutation_packet["attempt"],
            "agent_id": refutation_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "modify",
                "qualification": self.qualification(),
                "correctness_analysis": "The reviewed fixture and caller establish reachability.",
                "proportionality_analysis": "The narrowed persistent-state fix is proportionate.",
                "evidence": [self.reachability_evidence()],
                "replacement_finding": replacement,
                "residual_uncertainty": "",
            }],
        })
        self.run_argv(refutation_packet["validation_command"])
        self.command("accept-refutation", "--workers", "1", str(refutation_path))

        judgment_packet_path, judgment_packet = self.one_packet("judgment")
        judgment_path = Path(judgment_packet["output_path"])
        judgment = {
            "schema_version": 4,
            "stage": "judgment",
            "task_id": judgment_packet["task_id"],
            "attempt": judgment_packet["attempt"],
            "agent_id": judgment_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "unresolved",
                "qualification": self.qualification("unresolved"),
                "resolved_points": ["Available source does not reveal production configuration."],
                "evidence": [],
                "final_finding": None,
                "residual_risk": "",
            }],
        }
        write_json(judgment_path, judgment)
        invalid = self.run_argv(judgment_packet["validation_command"], expected_code=2)
        self.assertIn("residual_risk", invalid.stdout)

        residual_risk = "If production enables this path, the persistent value may be lost."
        judgment["results"][0]["residual_risk"] = residual_risk
        write_json(judgment_path, judgment)
        self.run_argv(judgment_packet["validation_command"])
        self.command("accept-judgment", str(judgment_path))
        self.command("finalize")
        self.command("validate-final")

        final = json.loads((self.run_root / "final" / "final.json").read_text(encoding="utf-8"))
        self.assertEqual(final["findings"], [])
        self.assertEqual(final["rejected_findings"], [])
        self.assertEqual(len(final["unresolved_findings"]), 1)
        unresolved = final["unresolved_findings"][0]
        self.assertEqual(unresolved["finding"]["id"], "F001")
        self.assertEqual(unresolved["finding"]["manifestation"]["failure"],
                         "If the path executes, reloading the record may omit the stored value 100.")
        self.assertEqual(unresolved["refutation_verdict"], "modify")
        self.assertEqual(unresolved["residual_risk"], residual_risk)
        self.assertEqual(final["trace"]["unresolved"], 1)
        review_record = final["review_records"][0]
        self.assertEqual(review_record["challenge"]["verdict"], "modify")
        self.assertEqual(
            review_record["challenge"]["proposed_finding"]["manifestation"]["failure"],
            "If the path executes, reloading the record may omit the stored value 100.",
        )
        self.assertEqual(review_record["final_judgment"]["verdict"], "unresolved")
        self.assertEqual(review_record["presented_finding"], unresolved["finding"])

    def test_invalid_agent_id_is_rejected_during_init(self) -> None:
        lenses = json.loads((self.run_root / "lenses.json").read_text(encoding="utf-8"))
        lenses["reviewers"][0]["agent_id"] = "reviewer 01/unsafe"
        write_json(self.run_root / "lenses.json", lenses)
        failure = self.command("init", expected_code=2)
        self.assertIn("invalid_agent_id", failure.stdout)

    def test_invalid_enum_type_returns_structured_validation_failure(self) -> None:
        scope = json.loads((self.run_root / "scope.json").read_text(encoding="utf-8"))
        scope["review_kind"] = []
        write_json(self.run_root / "scope.json", scope)
        failure = self.command("init", expected_code=2)
        self.assertIn("invalid_type $.review_kind", failure.stdout)
        self.assertEqual(failure.stderr, "")

    def test_instruction_files_are_absolute_readable_repository_files(self) -> None:
        scope_path = self.run_root / "scope.json"
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
        scope["instruction_files"] = ["AGENTS.md"]
        write_json(scope_path, scope)
        relative = self.command("init", expected_code=2)
        self.assertIn("instruction_path_not_absolute", relative.stdout)

        scope["instruction_files"] = [str(self.repository / "missing.md")]
        write_json(scope_path, scope)
        missing = self.command("init", expected_code=2)
        self.assertIn("instruction_file_unreadable", missing.stdout)

    def test_runtime_scope_is_immutable_after_init(self) -> None:
        self.command("init")
        scope_path = self.run_root / "scope.json"
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
        scope["output_language"] = "French"
        scope["topic"] = "A different topic"
        write_json(scope_path, scope)
        failure = self.command("status", expected_code=2)
        self.assertIn("runtime_contract_changed", failure.stdout)

    def test_change_scope_requires_immutable_comparison_oid(self) -> None:
        for arguments in (
            ["config", "user.name", "Ultrareview Test"],
            ["config", "user.email", "ultrareview@example.invalid"],
            ["commit", "-q", "-m", "baseline"],
        ):
            subprocess.run(
                ["git", "-C", str(self.repository), *arguments],
                text=True,
                capture_output=True,
                check=True,
            )
        scope_path = self.run_root / "scope.json"
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
        scope.update({
            "review_kind": "change",
            "comparison_base": "HEAD",
            "topic": None,
            "baseline_worktree_status": [],
        })
        write_json(scope_path, scope)
        failure = self.command("init", expected_code=2)
        self.assertIn("comparison_base_not_immutable_oid", failure.stdout)

    def test_boolean_attempt_is_rejected_for_packet_and_artifact(self) -> None:
        self.command("init")
        packet_path, packet = self.one_packet("adversarial")
        self.command("scaffold-artifact", str(packet_path))
        artifact_path = Path(packet["output_path"])

        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["attempt"] = True
        write_json(artifact_path, artifact)
        artifact_failure = self.run_argv(packet["validation_command"], expected_code=2)
        self.assertIn("$.attempt", artifact_failure.stdout)

        artifact["attempt"] = 1
        write_json(artifact_path, artifact)
        packet["attempt"] = True
        write_json(packet_path, packet)
        packet_failure = self.run_argv(packet["validation_command"], expected_code=2)
        self.assertIn("$.attempt", packet_failure.stdout)

    def test_retry_replaces_current_packet_and_stale_artifact_is_rejected(self) -> None:
        self.command("init")
        old_packet_path, old_packet = self.one_packet("adversarial")
        self.command("scaffold-artifact", str(old_packet_path))
        old_artifact_path = Path(old_packet["output_path"])
        self.command("validate-artifact", str(old_packet_path), str(old_artifact_path))
        retry = self.command("retry-packet", str(old_packet_path))
        self.assertIn("PACKET_RETRIED", retry.stdout)
        status = self.command("status")
        self.assertIn("attempt=2", status.stdout)
        failure = self.command("seal-adversarial", str(old_artifact_path), expected_code=2)
        self.assertIn("VALIDATION_FAILED", failure.stdout)

    def test_retry_rejects_packet_from_completed_stage(self) -> None:
        self.command("init")
        old_packet_path, _ = self.one_packet("adversarial")
        _, artifact_path = self.write_adversarial([])
        self.command("seal-adversarial", str(artifact_path))
        failure = self.command("retry-packet", str(old_packet_path), expected_code=2)
        self.assertIn("invalid_phase", failure.stdout)

    def test_deletion_only_change_accepts_old_side_finding(self) -> None:
        for arguments in (
            ["config", "user.name", "Ultrareview Test"],
            ["config", "user.email", "ultrareview@example.invalid"],
            ["commit", "-q", "-m", "baseline"],
        ):
            subprocess.run(
                ["git", "-C", str(self.repository), *arguments],
                text=True,
                capture_output=True,
                check=True,
            )
        comparison_base = subprocess.run(
            ["git", "-C", str(self.repository), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        lines = (self.repository / "sample.py").read_text(encoding="utf-8").splitlines()
        (self.repository / "sample.py").write_text(
            "\n".join(lines[:1] + lines[2:]) + "\n", encoding="utf-8",
        )
        baseline = subprocess.run(
            [
                "git", "-C", str(self.repository), "status", "--short",
                "--untracked-files=all",
            ],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        scope_path = self.run_root / "scope.json"
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
        scope.update({
            "review_kind": "change",
            "comparison_base": comparison_base,
            "topic": None,
            "target": "Deletion-only synthetic change",
            "baseline_worktree_status": baseline,
        })
        write_json(scope_path, scope)
        change_qualification = self.qualification()
        change_qualification["introduced_by_change"] = "yes"

        self.command("init")
        raw = self.finding("reviewer-01:C01")
        raw["location"] = {
            "path": "sample.py", "start_line": 2, "end_line": 2, "side": "old",
        }
        _, adversarial_path = self.write_adversarial([raw])
        self.command("seal-adversarial", str(adversarial_path))

        dedup_packet_path, dedup_packet = self.one_packet("dedup")
        dedup_path = Path(dedup_packet["output_path"])
        canonical = self.finding("F001")
        canonical["location"] = raw["location"]
        write_json(dedup_path, {
            "schema_version": 4,
            "stage": "dedup",
            "task_id": dedup_packet["task_id"],
            "attempt": dedup_packet["attempt"],
            "agent_id": dedup_packet["agent_id"],
            "canonical_candidates": [{
                "finding": canonical,
                "source_candidate_ids": ["reviewer-01:C01"],
                "merge_basis": "The deleted line is the only raw candidate.",
            }],
        })
        self.command("validate-artifact", str(dedup_packet_path), str(dedup_path))
        self.command("accept-dedup", "--workers", "1", str(dedup_path))

        refutation_packet_path, refutation_packet = self.one_packet("refutation")
        refutation_path = Path(refutation_packet["output_path"])
        write_json(refutation_path, {
            "schema_version": 4,
            "stage": "refutation",
            "task_id": refutation_packet["task_id"],
            "attempt": refutation_packet["attempt"],
            "agent_id": refutation_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "uphold",
                "qualification": change_qualification,
                "correctness_analysis": "The deleted line was required by the reachable path.",
                "proportionality_analysis": "Restoring the line is a focused fix.",
                "evidence": [self.reachability_evidence()],
                "replacement_finding": None,
                "residual_uncertainty": "",
            }],
        })
        self.command("validate-artifact", str(refutation_packet_path), str(refutation_path))
        self.command("accept-refutation", "--workers", "1", str(refutation_path))

        judgment_packet_path, judgment_packet = self.one_packet("judgment")
        judgment_path = Path(judgment_packet["output_path"])
        write_json(judgment_path, {
            "schema_version": 4,
            "stage": "judgment",
            "task_id": judgment_packet["task_id"],
            "attempt": judgment_packet["attempt"],
            "agent_id": judgment_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "uphold",
                "qualification": change_qualification,
                "resolved_points": ["The deletion causes the reachable failure."],
                "evidence": [self.reachability_evidence()],
                "final_finding": None,
                "residual_risk": "",
            }],
        })
        self.command("validate-artifact", str(judgment_packet_path), str(judgment_path))
        self.command("accept-judgment", str(judgment_path))
        self.command("finalize")
        self.command("validate-final")

    def test_validate_final_rejects_out_of_range_source_line(self) -> None:
        self.command("init")
        raw = self.finding("reviewer-01:C01")
        raw["location"] = {
            "path": "sample.py", "start_line": 200, "end_line": 201, "side": "new",
        }
        _, adversarial_path = self.write_adversarial([raw])
        self.command("seal-adversarial", str(adversarial_path))

        dedup_packet_path, dedup_packet = self.one_packet("dedup")
        dedup_path = Path(dedup_packet["output_path"])
        canonical = self.finding("F001")
        canonical["location"] = raw["location"]
        write_json(dedup_path, {
            "schema_version": 4,
            "stage": "dedup",
            "task_id": dedup_packet["task_id"],
            "attempt": dedup_packet["attempt"],
            "agent_id": dedup_packet["agent_id"],
            "canonical_candidates": [{
                "finding": canonical,
                "source_candidate_ids": ["reviewer-01:C01"],
                "merge_basis": "The raw candidate maps directly to this finding.",
            }],
        })
        self.command("validate-artifact", str(dedup_packet_path), str(dedup_path))
        self.command("accept-dedup", "--workers", "1", str(dedup_path))

        refutation_packet_path, refutation_packet = self.one_packet("refutation")
        refutation_path = Path(refutation_packet["output_path"])
        write_json(refutation_path, {
            "schema_version": 4,
            "stage": "refutation",
            "task_id": refutation_packet["task_id"],
            "attempt": refutation_packet["attempt"],
            "agent_id": refutation_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "uphold",
                "qualification": self.qualification(),
                "correctness_analysis": "The synthetic path remains reachable.",
                "proportionality_analysis": "The persistent impact merits remediation.",
                "evidence": [self.reachability_evidence()],
                "replacement_finding": None,
                "residual_uncertainty": "",
            }],
        })
        self.command("validate-artifact", str(refutation_packet_path), str(refutation_path))
        self.command("accept-refutation", "--workers", "1", str(refutation_path))

        judgment_packet_path, judgment_packet = self.one_packet("judgment")
        judgment_path = Path(judgment_packet["output_path"])
        write_json(judgment_path, {
            "schema_version": 4,
            "stage": "judgment",
            "task_id": judgment_packet["task_id"],
            "attempt": judgment_packet["attempt"],
            "agent_id": judgment_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "uphold",
                "qualification": self.qualification(),
                "resolved_points": ["The candidate remains actionable."],
                "evidence": [self.reachability_evidence()],
                "final_finding": None,
                "residual_risk": "",
            }],
        })
        self.command("validate-artifact", str(judgment_packet_path), str(judgment_path))
        self.command("accept-judgment", str(judgment_path))
        self.command("finalize")
        failure = self.command("validate-final", expected_code=2)
        self.assertIn("source_line_out_of_range", failure.stdout)


class PureCoordinatorCase(unittest.TestCase):
    def setUp(self) -> None:
        specification = importlib.util.spec_from_file_location(
            "ultrareview_pipeline", SKILL_ROOT / "scripts" / "pipeline.py"
        )
        self.assertIsNotNone(specification)
        self.assertIsNotNone(specification.loader)
        self.module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(self.module)

    def qualification(self, disposition: str) -> dict:
        value = {
            "production_reachable": "yes",
            "reachability_path": [{
                "location": {
                    "path": "sample.py", "start_line": 2, "end_line": 4, "side": "new",
                },
                "reference": "entry to mutation",
            }],
            "inside_authorized_scope": "yes",
            "introduced_by_change": "not_applicable",
            "material_impact": "yes",
            "fix_value": "positive",
            "likely_author_would_fix_now": "yes",
        }
        if disposition == "reject":
            value["production_reachable"] = "no"
            value["reachability_path"] = []
        elif disposition == "unresolved":
            value["fix_value"] = "unclear"
        return value

    def test_partition_respects_requested_worker_count(self) -> None:
        self.assertEqual(self.module.partition(["F001", "F002", "F003"], 2), [
            ["F001", "F003"], ["F002"],
        ])

    def test_qualification_gate_maps_to_binding_disposition(self) -> None:
        for expected in ("qualify", "reject", "unresolved"):
            actual = self.module.validate_qualification(
                self.qualification(expected), "topic", "test", "qualification", "$",
            )
            self.assertEqual(actual, expected)

        with self.assertRaises(self.module.ValidationError):
            self.module.validate_qualification_verdict(
                "reject", "uphold", judgment=False,
                stage="test", task_id="qualification", field="$.verdict",
            )

    def test_qualifying_result_requires_verified_reachability_evidence(self) -> None:
        with self.assertRaises(self.module.ValidationError):
            self.module.validate_qualifying_evidence(
                [], "qualify", "test", "qualification", "$.evidence",
            )
        unsupported_caller = {
            "kind": "caller",
            "location": None,
            "reference": "unlocated caller claim",
            "statement": "Trust me: a caller exists.",
            "status": "verified",
        }
        with self.assertRaises(self.module.ValidationError):
            self.module.validate_qualifying_evidence(
                [unsupported_caller], "qualify", "test", "qualification", "$.evidence",
            )

    def test_changed_line_parser_supports_both_diff_sides(self) -> None:
        diff_text = "\n".join([
            "@@ -2,1 +2,3 @@",
            "@@ -10,2 +12,0 @@",
            "@@ -20 +18 @@",
        ])
        self.assertEqual(
            self.module.parse_changed_line_ranges(diff_text, "new"),
            [(2, 4), (18, 18)],
        )
        self.assertEqual(
            self.module.parse_changed_line_ranges(diff_text, "old"),
            [(2, 2), (10, 11), (20, 20)],
        )


if __name__ == "__main__":
    unittest.main()
