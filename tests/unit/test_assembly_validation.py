"""Unit tests for output validation and health checks."""

from __future__ import annotations

from pathlib import Path

from blazzid_assembly.config import AssemblyConfig
from blazzid_assembly.models import EditPlan
from blazzid_assembly.validation import validate_rendered_montage


def test_validation_non_existent_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "non_existent.mp4"
    plan = EditPlan(
        clips=[],
        total_duration_seconds=10.0,
        target_budget_seconds=10.0,
        budget_shortfall_seconds=0.0,
        selected_count=0,
    )
    cfg = AssemblyConfig()

    report = validate_rendered_montage(missing_file, plan, cfg)

    assert report.is_valid is False
    assert any("does not exist" in err for err in report.errors)


def test_validation_zero_byte_file(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.mp4"
    empty_file.write_bytes(b"")

    plan = EditPlan(
        clips=[],
        total_duration_seconds=10.0,
        target_budget_seconds=10.0,
        budget_shortfall_seconds=0.0,
        selected_count=0,
    )
    cfg = AssemblyConfig()

    report = validate_rendered_montage(empty_file, plan, cfg)

    assert report.is_valid is False
    assert any("0 bytes" in err or "failed" in err for err in report.errors)
