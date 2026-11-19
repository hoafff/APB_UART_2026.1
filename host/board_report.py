"""Load manual board-test plans and export the operator's acceptance sheet."""

import csv
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


_CASE_FIELDS = ("id", "title", "steps", "expected", "evidence")
_METADATA_FIELDS = ("operator", "board_id", "cp2102_id", "sof_sha256")
_COLUMNS = (
    "test_id", "procedure", "expected", "status", "datetime_local",
    *_METADATA_FIELDS, "observed", "evidence_path", "profile", "title", "evidence_hint",
)
_EMPTY_RESULT = {"status": "NOT_RUN", "observed": "", "evidence_path": "", "datetime_local": ""}


def load_plans():
    """Read board_plans.json beside this module. Invalid plans raise ValueError."""
    path = Path(__file__).resolve().with_name("board_plans.json")
    with path.open(encoding="utf-8-sig") as stream:
        plans = json.load(stream)

    if not isinstance(plans, dict) or set(plans) != {"target", "pulp"}:
        raise ValueError("board_plans.json must contain the target and pulp profiles")
    for profile, cases in plans.items():
        if not isinstance(cases, list):
            raise ValueError(f"{profile} must be a list of board tests")
        seen = set()
        for number, case in enumerate(cases, 1):
            if not isinstance(case, dict):
                raise ValueError(f"{profile} case {number} must be an object")
            for field in _CASE_FIELDS:
                if not isinstance(case.get(field), str):
                    raise ValueError(f"{profile} case {number} needs a string field {field!r}")
            test_id = case["id"]
            if not test_id.strip() or test_id in seen:
                raise ValueError(f"{profile} case {number} has an empty or duplicate id {test_id!r}")
            seen.add(test_id)
    return plans


def new_results(plans):
    """Create an independent, unrun result for every case in each profile."""
    return {
        profile: {case["id"]: _EMPTY_RESULT.copy() for case in cases}
        for profile, cases in plans.items()
    }


def save_sheet(path, profile, cases, results, metadata):
    """Atomically export one profile in plan order. File errors propagate to the caller."""
    destination = Path(path)
    session = {key: metadata.get(key, "") for key in _METADATA_FIELDS}
    temp = NamedTemporaryFile(
        mode="w", encoding="utf-8-sig", newline="", dir=destination.parent, delete=False,
    )
    try:
        with temp as stream:
            writer = csv.DictWriter(stream, fieldnames=_COLUMNS)
            writer.writeheader()
            for case in cases:
                result = results.get(case["id"], {})
                row = {
                    **session,
                    "test_id": case["id"],
                    "procedure": case["steps"],
                    "expected": case["expected"],
                    "profile": profile,
                    "title": case["title"],
                    "evidence_hint": case["evidence"],
                }
                for key, default in _EMPTY_RESULT.items():
                    row[key] = result.get(key, default)
                writer.writerow(row)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp.name, destination)
    except BaseException:
        Path(temp.name).unlink(missing_ok=True)
        raise
