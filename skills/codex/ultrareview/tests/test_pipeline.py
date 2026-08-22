#!/usr/bin/env python3
"""Behavioral tests for the packaged Ultrareview coordinator."""

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
        self.scope_source = self.root / "prepared-scope.json"
        self.lenses_source = self.root / "prepared-lenses.json"
        write_json(self.scope_source, {
            "schema_version": 2,
            "repository_path": str(self.repository),
            "review_kind": "topic",
            "target": "Synthetic persistence topic",
            "comparison_base": None,
            "topic": "Synthetic persistence behavior",
            "exclusions": ["UI-only behavior"],
            "instruction_files": [str(instructions)],
            "finding_standard": "Only discrete actionable defects with a reachable impact.",
            "baseline_worktree_status": [],
        })
        write_json(self.lenses_source, {
            "schema_version": 2,
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
            "location": {"path": "sample.py", "start_line": 2, "end_line": 4},
            "context": "The synthetic path runs during a persistent mutation.",
            "trigger": "A deterministic test trigger reaches the path.",
            "impact": "A stored value can become unavailable after the operation.",
            "evidence": [{
                "kind": "source",
                "location": {"path": "sample.py", "start_line": 2, "end_line": 4},
                "statement": "The fixture represents the inspected source path.",
                "status": "verified",
            }],
            "recommendation": "Preserve the value and add a focused regression test.",
            "confidence": "high",
        }

    def write_adversarial(self, candidates: list[dict]) -> tuple[Path, Path]:
        packet_path, packet = self.one_packet("adversarial")
        artifact_path = Path(packet["output_path"])
        write_json(artifact_path, {
            "schema_version": 2,
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
        self.assertEqual(final["schema_version"], 2)
        self.assertEqual(final["findings"], [])
        self.assertEqual(final["rejected_findings"], [])
        self.assertEqual(final["unresolved_findings"], [])
        self.assertEqual(final["trace"]["canonical_candidates"], 0)

    def test_rejected_candidate_is_preserved_with_reason(self) -> None:
        self.command("init")
        raw = self.finding("reviewer-01:C01")
        _, adversarial_path = self.write_adversarial([raw])
        self.command("seal-adversarial", str(adversarial_path))

        dedup_packet_path, dedup_packet = self.one_packet("dedup")
        dedup_path = Path(dedup_packet["output_path"])
        canonical = self.finding("F001")
        write_json(dedup_path, {
            "schema_version": 2,
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
            "schema_version": 2,
            "stage": "refutation",
            "task_id": refutation_packet["task_id"],
            "attempt": refutation_packet["attempt"],
            "agent_id": refutation_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "refute",
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
            "schema_version": 2,
            "stage": "judgment",
            "task_id": judgment_packet["task_id"],
            "attempt": judgment_packet["attempt"],
            "agent_id": judgment_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "reject",
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
        self.assertEqual(rejected["refutation_verdict"], "refute")
        self.assertEqual(rejected["reason"], reason)
        self.assertEqual(final["trace"]["rejected_findings"], 1)
        self.assertEqual(final["unresolved_findings"], [])

    def test_unresolved_candidate_is_structured_and_requires_nonempty_risk(self) -> None:
        self.command("init")
        raw = self.finding("reviewer-01:C01")
        _, adversarial_path = self.write_adversarial([raw])
        self.command("seal-adversarial", str(adversarial_path))

        dedup_packet_path, dedup_packet = self.one_packet("dedup")
        dedup_path = Path(dedup_packet["output_path"])
        write_json(dedup_path, {
            "schema_version": 2,
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
        write_json(refutation_path, {
            "schema_version": 2,
            "stage": "refutation",
            "task_id": refutation_packet["task_id"],
            "attempt": refutation_packet["attempt"],
            "agent_id": refutation_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "unresolved",
                "correctness_analysis": "The fixture cannot establish production reachability.",
                "proportionality_analysis": "A human decision is needed before remediation.",
                "evidence": [],
                "replacement_finding": None,
                "residual_uncertainty": "Production configuration is unavailable.",
            }],
        })
        self.run_argv(refutation_packet["validation_command"])
        self.command("accept-refutation", "--workers", "1", str(refutation_path))

        judgment_packet_path, judgment_packet = self.one_packet("judgment")
        judgment_path = Path(judgment_packet["output_path"])
        judgment = {
            "schema_version": 2,
            "stage": "judgment",
            "task_id": judgment_packet["task_id"],
            "attempt": judgment_packet["attempt"],
            "agent_id": judgment_packet["agent_id"],
            "results": [{
                "candidate_id": "F001",
                "verdict": "unresolved",
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
        self.assertEqual(unresolved["refutation_verdict"], "unresolved")
        self.assertEqual(unresolved["residual_risk"], residual_risk)
        self.assertEqual(final["trace"]["unresolved"], 1)

    def test_invalid_agent_id_is_rejected_during_init(self) -> None:
        lenses = json.loads((self.run_root / "lenses.json").read_text(encoding="utf-8"))
        lenses["reviewers"][0]["agent_id"] = "reviewer 01/unsafe"
        write_json(self.run_root / "lenses.json", lenses)
        failure = self.command("init", expected_code=2)
        self.assertIn("invalid_agent_id", failure.stdout)

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

    def test_validate_final_rejects_out_of_range_source_line(self) -> None:
        self.command("init")
        _, artifact_path = self.write_adversarial([])
        self.command("seal-adversarial", str(artifact_path))
        final_path = self.run_root / "final" / "final.json"
        final = json.loads(final_path.read_text(encoding="utf-8"))
        final["findings"] = [self.finding("F999")]
        final["findings"][0]["location"] = {
            "path": "sample.py", "start_line": 200, "end_line": 201,
        }
        final["trace"]["canonical_candidates"] = 1
        final["trace"]["raw_candidates"] = 1
        final["trace"]["refutation_results"] = 1
        final["trace"]["final_findings"] = 1
        write_json(final_path, final)
        failure = self.command("validate-final", expected_code=2)
        self.assertIn("source_line_out_of_range", failure.stdout)


class PureCoordinatorCase(unittest.TestCase):
    def test_partition_respects_requested_worker_count(self) -> None:
        specification = importlib.util.spec_from_file_location(
            "ultrareview_pipeline", SKILL_ROOT / "scripts" / "pipeline.py"
        )
        self.assertIsNotNone(specification)
        self.assertIsNotNone(specification.loader)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        self.assertEqual(module.partition(["F001", "F002", "F003"], 2), [
            ["F001", "F003"], ["F002"],
        ])


if __name__ == "__main__":
    unittest.main()
