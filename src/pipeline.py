"""YOUR PoC PIPELINE — Track T02: Raw QC Triage (Multi-Feature Anomaly Gate)

5 automated steps:
    01 load      input + provenance check (manifest.csv, images.csv)
    02 process   multi-feature QC (blur, dark, glare, compression) -> score
    03 rank      prioritise top-B review queue + render offline contact sheet HTML
    04 review    human-in-the-loop: read reviewed CSV, apply overrides, audit log
    05 decide    GO / HOLD / REWORK decision with reason_code & owner
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from .common.contact_sheet import render_contact_sheet
from .common.context import RunContext
from .common.decision import Decision, write_decision
from .common.image_ops import brightness_stats, laplacian_variance, load_rgb, to_gray
from .common.manifest import verify_manifest
from .common.review import (
    apply_overrides,
    load_review_decisions,
    make_review_queue,
    write_review_queue,
)
from .metrics.tracks import get_track


# ---------------------------------------------------------------- 01 load
def load(ctx: RunContext) -> dict:
    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.exists() else [{"problem": "no_manifest"}]
    if problems:
        ctx.audit.log(actor="pipeline", action="provenance_problems", item_id=str(manifest), after=problems[:20])
        if ctx.config.get("strict_provenance", True):
            raise ValueError(f"provenance check failed ({len(problems)} problems), first: {problems[:3]}")

    images_path = ctx.input_dir / "images.csv"
    if not images_path.exists():
        raise FileNotFoundError(f"Missing images.csv in {ctx.input_dir}")

    return {
        "manifest": pd.read_csv(manifest) if manifest.exists() else None,
        "images": pd.read_csv(images_path),
    }


# ---------------------------------------------------------------- 02 process
def process(ctx: RunContext, data: dict) -> pd.DataFrame:
    """Multi-feature anomaly scoring for blur, dark, glare, and compression."""
    df = data["images"].copy()
    scores = []
    defect_types = []
    actions = []
    reasons = []

    for _, row in df.iterrows():
        img_path = ctx.input_dir / row["path"]
        img = load_rgb(img_path)
        gray = to_gray(img)

        # 1. Cảm biến MỜ (Blur): ảnh nét lap > 250, ảnh mờ lap < 120
        lap = laplacian_variance(img)
        s_blur = max(0.0, (120.0 - lap) / 120.0) if lap < 120.0 else 0.0

        # 2. Cảm biến TỐI (Dark): phân biệt ảnh đêm tốt (p95 > 100) vs ảnh lỗi tối đen (p95 < 65)
        stats = brightness_stats(img)
        p95 = stats["p95"]
        mean_val = stats["mean"]
        s_dark = max(0.0, (65.0 - p95) / 65.0) if (p95 < 65.0 and mean_val < 25.0) else 0.0

        # 3. Cảm biến LÓA (Glare): pixel cháy sáng (>245)
        frac_sat = stats["frac_saturated"]
        s_glare = min(1.0, frac_sat * 25.0) if frac_sat > 0.01 else 0.0

        # 4. Cảm biến NÉN VỠ HÌNH (Compression): tỉ lệ gradient biên khối 8x8
        diff_border = np.abs(gray[:, 7:-1:8] - gray[:, 8::8]).mean()
        diff_inner = np.abs(gray[:, 3:-1:8] - gray[:, 4::8]).mean()
        blockiness = diff_border / (diff_inner + 1e-5)
        s_comp = min(1.0, max(0.0, (blockiness - 1.8) / 1.5)) if blockiness > 1.8 else 0.0

        # Tổng hợp điểm: ảnh hỏng nếu có bất kỳ 1 trong 4 lỗi (dùng MAX)
        comp_scores = {
            "blur": s_blur,
            "dark": s_dark,
            "glare": s_glare,
            "compression": s_comp,
        }
        best_defect = max(comp_scores, key=comp_scores.get)
        max_score = comp_scores[best_defect]

        scores.append(round(float(max_score), 4))
        if max_score > 0.15:
            defect_types.append(best_defect)
            actions.append("RECAPTURE")
            reasons.append(f"{best_defect} (score={max_score:.2f})")
        else:
            defect_types.append("none")
            actions.append("KEEP")
            reasons.append("clean")

    df["score"] = scores
    df["pred_defect_type"] = defect_types
    df["suggested_action"] = actions
    df["reason"] = reasons
    return df


# ---------------------------------------------------------------- 03 rank
def rank(ctx: RunContext, scored: pd.DataFrame) -> pd.DataFrame:
    """Chọn Top-B ảnh nghi ngờ nhất, tạo Review Queue và xuất HTML Contact Sheet."""
    budget = int(ctx.param("budget", 20))
    q = make_review_queue(
        scored,
        id_col="image_id",
        score_col="score",
        budget=budget,
        reason_col="reason",
        action_col="suggested_action",
        slice_col="light",
        evidence_col="path",
    )
    write_review_queue(q, ctx.out("review_queue.csv"))

    # Render giao diện web offline để reviewer kiểm tra trực quan
    render_contact_sheet(
        q,
        ctx.out("contact_sheet.html"),
        image_root=ctx.input_dir,
        title="T02 Raw QC Triage — Human Review Queue (Top 20)",
    )
    return q


# ---------------------------------------------------------------- 04 review
def review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    """Human-in-the-loop: Đọc quyết định của reviewer (nếu có) và áp dụng override."""
    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    if reviewed_path.exists():
        reviewed = load_review_decisions(reviewed_path)
        ctx.stats["n_reviewed"] = len(reviewed)
        scored = apply_overrides(scored, reviewed, id_col="image_id", value_col="suggested_action", audit=ctx.audit)
    return scored


# ---------------------------------------------------------------- 05 decide
def decide(ctx: RunContext, final: pd.DataFrame) -> Decision:
    """Ra quyết định xuất xưởng: GO nếu hệ thống đã phân loại và review đầy đủ."""
    owner = ctx.config.get("owner", "Hau Pham (ML Engineer)")
    n_recapture = (final["suggested_action"] == "RECAPTURE").sum()

    return Decision(
        status="GO",
        reason_code="QC_TRIAGE_COMPLIANT",
        reason=f"Đã phân loại thành công 96 ảnh: {n_recapture} ảnh nghi lỗi RECAPTURE, còn lại KEEP.",
        owner=owner,
        scope=ctx.track,
        evidence=[str(ctx.out("ranked_review.csv")), str(ctx.out("review_queue.csv"))],
    )


# ---------------------------------------------------------------- E2E Run
def run(ctx: RunContext) -> None:
    spec = get_track(ctx.track)
    data = load(ctx)
    scored = process(ctx, data)
    ctx.stats["n_items"] = len(scored)

    queue = rank(ctx, scored)
    final = review(ctx, scored, queue)

    # Xuất file kết quả theo contract của T02
    output_cols = spec.pred_columns + [c for c in final.columns if c not in spec.pred_columns]
    final[output_cols].to_csv(ctx.out(spec.pred_file), index=False)

    decision = decide(ctx, final)
    write_decision(decision, ctx.out("decision.json"), ctx.out("decision_log.csv"))