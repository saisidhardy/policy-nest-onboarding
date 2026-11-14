"""Pillar 3 Accuracy: Capability #7 (False-Decision Monitoring) and Capability #8 (Ground-Truth Evaluation).

Evaluates the decision engine against all 600 ground-truth applications in application_truth.csv
and 3,600 document extraction records in documents.csv.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from legacy.engine import PolicyNestEngine


@pytest.fixture(scope="module", autouse=True)
def migrated_db():
    """Bypass postgres requirement since ground-truth evaluation is purely file and engine based."""
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    """Bypass table cleanup."""
    yield


def find_datasets() -> tuple[Path, Path]:
    repo_root = Path(__file__).resolve().parent.parent.parent
    truth_path = repo_root / "docs" / "source_materials" / "04_DATASETS" / "application_truth.csv"
    docs_path = repo_root / "docs" / "source_materials" / "04_DATASETS" / "documents.csv"
    if not truth_path.exists() or not docs_path.exists():
        pytest.skip(f"Datasets not found at {truth_path} or {docs_path}")
    return truth_path, docs_path


def test_ground_truth_600_accuracy_and_false_decision_monitoring():
    truth_path, docs_path = find_datasets()

    df_truth = pd.read_csv(truth_path)
    df_docs = pd.read_csv(docs_path)

    assert len(df_truth) == 600, f"Expected 600 truth cases, got {len(df_truth)}"
    assert len(df_docs) == 3600, f"Expected 3600 document records, got {len(df_docs)}"

    engine = PolicyNestEngine()
    engine.df_truth = df_truth
    engine.df_docs = df_docs

    results = engine.get_benchmark_results()

    # 1. Decision Engine Overall Accuracy: Requirement >= 95.0%
    accuracy = results["accuracy"]
    assert accuracy >= 95.0, f"Benchmark accuracy {accuracy}% is below required 95.0%"

    # 2. Reject Recall: Requirement >= 98.0%
    reject_recall = results["reject_recall"]
    assert reject_recall >= 98.0, f"Reject recall {reject_recall}% is below required 98.0%"

    # 3. Straight-Through Processing (STP) Feasibility: Requirement >= 60.0%
    stp_rate = results["straight_through_rate"]
    assert stp_rate >= 60.0, f"STP rate {stp_rate}% is below required 60.0%"

    # 4. Capability #7: False-Decision Monitoring
    cm = results["confusion_matrix"]
    # Verify zero False Approvals for true rejections (Zero regulatory leakage)
    false_approvals_on_reject = cm.get("REJECT", {}).get("APPROVE", 0)
    assert false_approvals_on_reject == 0, (
        f"Critical Statutory Violation: {false_approvals_on_reject} true REJECT cases were incorrectly APPROVED!"
    )

    # Verify zero False Approvals for needs more info
    false_approvals_on_needs_info = cm.get("NEEDS_MORE_INFO", {}).get("APPROVE", 0)
    assert false_approvals_on_needs_info == 0, (
        f"Defect Leakage: {false_approvals_on_needs_info} incomplete cases were incorrectly APPROVED!"
    )

    print("\n" + "=" * 60)
    print("600-CASE GROUND-TRUTH BENCHMARK VERIFICATION RESULTS")
    print("=" * 60)
    print(f"Total Applications Evaluated: {results['total_applications']}")
    print(f"Decision Engine Accuracy:    {accuracy}% (IRDAI Requirement: >= 95.0%)")
    print(f"Statutory REJECT Recall:     {reject_recall}% (IRDAI Requirement: >= 98.0%)")
    print(f"Straight-Through Processing: {stp_rate}% ({results['straight_through_count']}/600)")
    print(f"False Approvals (FAR):       0.0% (Zero leakage)")
    print(f"Confusion Matrix:            {cm}")
    print("=" * 60)
