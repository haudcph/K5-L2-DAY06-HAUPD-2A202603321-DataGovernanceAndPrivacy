"""Generate internal self-check metrics (kết quả tự kiểm) for Baseline vs PoC.

Uses human review audit labels from out/poc/review_queue_reviewed.csv
and image metadata to compute Defect Recall@B, Precision@B, False Alarm rates,
and slices per light condition, saving to reports/metrics_baseline.json and
reports/metrics_poc.json.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

from src.common.report import MetricResult, write_metrics
from src.metrics import ranking as RK
from src.metrics.estimation import wilson_ci


def build_self_check_gt() -> pd.DataFrame:
    """Build internal self-check ground truth for eval split (40 images)."""
    img_df = pd.read_csv("fixtures/t02_raw_qc/images.csv")
    eval_df = img_df[img_df["split"] == "eval"].copy()
    
    reviewed = pd.read_csv("out/poc/review_queue_reviewed.csv")
    rev_map = {row["item_id"]: row for _, row in reviewed.iterrows()}
    
    labels = []
    types = []
    
    for _, row in eval_df.iterrows():
        iid = row["image_id"]
        # Rule 1: base clean images (*_0) are clean
        if iid.endswith("_0"):
            labels.append(0)
            types.append("none")
        elif iid in rev_map:
            r = rev_map[iid]
            dec = str(r["reviewer_decision"]).strip().lower()
            note = str(r.get("review_note", "")).strip().lower()
            if dec == "approve":
                labels.append(1)
                # Defect type from pipeline or note
                pred_type = str(r.get("pred_defect_type", "glare")).lower()
                types.append(pred_type if pred_type != "none" else "glare")
            elif dec == "reject":
                labels.append(0)
                types.append("none")
            elif dec == "edit":
                labels.append(1)
                types.append(note if note in ["blur", "dark", "glare", "compression"] else "glare")
            else:
                labels.append(1)
                types.append("glare")
        else:
            # Unreviewed variant in eval
            labels.append(1 if not iid.endswith("_0") else 0)
            types.append("glare" if not iid.endswith("_0") else "none")

    eval_df["is_defect"] = labels
    eval_df["defect_type"] = types
    return eval_df


def evaluate_run(run_name: str, pred_csv: str, gt: pd.DataFrame, runtime_s: float) -> list[MetricResult]:
    pred = pd.read_csv(pred_csv)
    pred_eval = pred[pred["image_id"].isin(gt["image_id"])].sort_values("score", ascending=False).reset_index(drop=True)
    B = 20
    pos = gt[gt["is_defect"] == 1]["image_id"]
    n_gt_defects = len(pos)
    
    rec_res = RK.recall_at_k(pred_eval["image_id"], pos, B)
    prec_res = RK.precision_at_k(pred_eval["image_id"], pos, B)
    top_b_ids = set(pred_eval["image_id"].head(B))
    
    metrics = [
        MetricResult(
            name="Defect Recall@B",
            value=rec_res["value"],
            direction="higher",
            unit="GT defects in top-B / GT defects",
            numerator=rec_res["numerator"],
            denominator=rec_res["denominator"],
            n=len(gt),
            primary=True,
            notes=f"B={B}, eval N={len(gt)} (Kết quả tự kiểm)"
        ),
        MetricResult(
            name="Precision@B",
            value=prec_res["value"],
            direction="higher",
            unit="GT defects in top-B / B",
            numerator=prec_res["numerator"],
            denominator=prec_res["denominator"],
            n=len(gt),
            notes=f"B={B} (Kết quả tự kiểm)"
        ),
    ]
    
    # Slices for light
    for light, sub in gt.groupby("light"):
        neg = sub[sub["is_defect"] == 0]
        posn = sub[sub["is_defect"] == 1]
        fa_num = int(neg["image_id"].isin(top_b_ids).sum())
        fa_den = len(neg)
        fa_rate = fa_num / fa_den if fa_den else 0.0
        metrics.append(MetricResult(
            name="False alarm in top-B",
            value=fa_rate,
            direction="lower",
            unit="clean in top-B / clean",
            numerator=fa_num,
            denominator=fa_den,
            n=len(sub),
            slice=f"light={light}",
            notes="Kết quả tự kiểm"
        ))
        
    return metrics


def main():
    gt = build_self_check_gt()
    Path("reports").mkdir(exist_ok=True)
    gt.to_csv("reports/internal_self_check_gt.csv", index=False)
    
    # Baseline
    b_metrics = evaluate_run("baseline", "out/baseline/ranked_review.csv", gt, runtime_s=0.0891)
    write_metrics(
        "reports/metrics_baseline.json",
        run_name="baseline",
        track="t02",
        metrics=b_metrics,
        seed=42,
        runtime_seconds=0.0891,
        n_items=96,
        extra={"evaluation_type": "internal_self_check"}
    )
    
    # PoC
    p_metrics = evaluate_run("poc", "out/poc/ranked_review.csv", gt, runtime_s=0.824)
    write_metrics(
        "reports/metrics_poc.json",
        run_name="poc",
        track="t02",
        metrics=p_metrics,
        seed=42,
        runtime_seconds=0.824,
        n_items=96,
        extra={"evaluation_type": "internal_self_check"}
    )
    print("Successfully generated reports/metrics_baseline.json and reports/metrics_poc.json")


if __name__ == "__main__":
    main()
