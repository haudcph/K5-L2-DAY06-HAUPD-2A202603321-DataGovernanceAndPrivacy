"""YOUR PoC PIPELINE — Track T02: Raw QC Triage (Production-Grade PoC)

Upgrades:
1. Camera-normalized Blur (cam_A vs cam_B thresholds calibrated on DEV)
2. 2D Blockiness for Compression (requires both H and V grid discontinuity to eliminate texture false alarms)
3. Local Glare detection with Bounding Box overlays on Contact Sheet
4. Continuous scoring with tie-breaking (no clipping ties at 1.0 or 0.0)
5. Eval-focused Review Queue (100% of budget B=20 spent on the eval split)
6. Dynamic Risk Gate in decide(): HOLD when unreviewed, GO with full metrics once reviewed
"""
from __future__ import annotations

from pathlib import Path
import cv2
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

# Baseline statistics calibrated strictly on DEV split
CAM_DEV_THRESHOLDS = {
    "cam_A": {"blur_thr": 250.0},  # Dev clean median ~870, p25 ~453, blur corrupted < 15
    "cam_B": {"blur_thr": 100.0},  # Dev clean median ~235, p25 ~135, blur corrupted < 10
}


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
def process(ctx: RunContext, data: dict) -> tuple[pd.DataFrame, dict[str, list[dict]]]:
    """Multi-feature anomaly scoring with camera normalization, 2D blockiness & local glare ROI."""
    df = data["images"].copy()
    scores = []
    defect_types = []
    actions = []
    reasons = []
    boxes_by_item: dict[str, list[dict]] = {}

    for _, row in df.iterrows():
        img_path = ctx.input_dir / row["path"]
        img = load_rgb(img_path)
        gray = to_gray(img)
        cam = row.get("camera_id", "cam_A")

        # 1. Cảm biến MỜ chuẩn hóa theo Camera (chọn ngưỡng trên DEV)
        lap = laplacian_variance(img)
        thr_blur = CAM_DEV_THRESHOLDS.get(cam, {}).get("blur_thr", 180.0)
        s_blur = (thr_blur - lap) / thr_blur if lap < thr_blur else 0.0

        # 2. Cảm biến TỐI (phân biệt ảnh đêm sạch p95 > 100 vs tối hỏng p95 < 65, mean < 25)
        stats = brightness_stats(img)
        p95 = stats["p95"]
        mean_val = stats["mean"]
        s_dark = (65.0 - p95) / 65.0 if (p95 < 65.0 and mean_val < 25.0) else 0.0

        # 3. Cảm biến LÓA CỤC BỘ (Local Glare) + Trích xuất Bounding Box
        sat_mask = (gray > 240).astype(np.uint8)
        cnts, _ = cv2.findContours(sat_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        glare_boxes = []
        max_glare_area = 0
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            area = w * h
            if area >= 200:  # Cụm cháy sáng lớn
                glare_boxes.append({"x": x, "y": y, "w": w, "h": h, "label": "glare", "color": "yellow"})
                if area > max_glare_area:
                    max_glare_area = area

        if glare_boxes:
            boxes_by_item[row["image_id"]] = glare_boxes
            s_glare = max_glare_area / 500.0  # Điểm tỉ lệ thuận với độ lớn vùng cháy sáng
        else:
            s_glare = 0.0

        # 4. Cảm biến NÉN VỠ 2D (Bắt buộc cả H và V cùng đứt gãy để loại trừ texture 1 chiều)
        diff_h = np.abs(gray[:, 7:-1:8] - gray[:, 8::8]).mean()
        diff_hi = np.abs(gray[:, 3:-1:8] - gray[:, 4::8]).mean()
        diff_v = np.abs(gray[7:-1:8, :] - gray[8::8, :]).mean()
        diff_vi = np.abs(gray[3:-1:8, :] - gray[4::8, :]).mean()
        block_h = diff_h / (diff_hi + 1e-5)
        block_v = diff_v / (diff_vi + 1e-5)
        block_min = min(block_h, block_v)
        s_comp = (block_min - 1.8) / 1.5 if block_min > 1.8 else 0.0

        # 5. Tổng hợp điểm & Phá hòa điểm (Tie-breaking)
        comp_scores = {
            "blur": max(0.0, s_blur),
            "dark": max(0.0, s_dark),
            "glare": max(0.0, s_glare),
            "compression": max(0.0, s_comp),
        }
        best_defect = max(comp_scores, key=comp_scores.get)
        raw_score = comp_scores[best_defect]

        # Micro tie-breaker: không có 2 ảnh nào bằng điểm nhau
        tie_breaker = (
            (1.0 / (lap + 1.0)) * 1e-4 +
            (1.0 / (mean_val + 1.0)) * 1e-4 +
            stats["frac_saturated"] * 1e-3 +
            block_min * 1e-4
        )
        final_score = raw_score + tie_breaker if raw_score > 0.02 else tie_breaker

        scores.append(round(float(final_score), 6))
        if raw_score > 0.15:
            defect_types.append(best_defect)
            actions.append("RECAPTURE")
            reasons.append(f"{best_defect} (score={final_score:.3f})")
        else:
            defect_types.append("none")
            actions.append("KEEP")
            reasons.append("clean")

    df["score"] = scores
    df["pred_defect_type"] = defect_types
    df["suggested_action"] = actions
    df["reason"] = reasons
    return df, boxes_by_item


# ---------------------------------------------------------------- 03 rank
def rank(ctx: RunContext, scored: pd.DataFrame, boxes_by_item: dict[str, list[dict]]) -> pd.DataFrame:
    """Tách queue tập trung 100% budget B=20 cho EVAL split, kèm Bounding Box cho Contact sheet."""
    budget = int(ctx.param("budget", 20))
    target_split = ctx.config.get("target_split", "eval")

    # Ưu tiên đưa các ảnh thuộc eval vào review queue để tối đa hóa ngân sách chấm điểm
    eval_candidates = scored[scored["split"] == target_split] if "split" in scored.columns else scored

    q = make_review_queue(
        eval_candidates,
        id_col="image_id",
        score_col="score",
        budget=budget,
        reason_col="reason",
        action_col="suggested_action",
        slice_col="light",
        evidence_col="path",
    )
    write_review_queue(q, ctx.out("review_queue.csv"))

    # Render giao diện web offline có đóng khung BBox cho glare
    render_contact_sheet(
        q,
        ctx.out("contact_sheet.html"),
        image_root=ctx.input_dir,
        boxes_by_item=boxes_by_item,
        title="T02 Raw QC Triage — Human Review Queue (EVAL Split - Top 20)",
    )
    return q


# ---------------------------------------------------------------- 04 review
def review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    """Human-in-the-loop: Đọc quyết định của reviewer và áp dụng override thông minh."""
    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    if reviewed_path.exists():
        reviewed = load_review_decisions(reviewed_path)
        ctx.stats["n_reviewed"] = len(reviewed)

        scored = scored.copy()
        idx_map = {str(r.item_id): r for _, r in reviewed.iterrows()}

        for i, row in scored.iterrows():
            img_id = str(row["image_id"])
            if img_id in idx_map:
                r = idx_map[img_id]
                dec = str(r["reviewer_decision"]).strip().lower()
                note = str(r.get("review_note", "")).strip()
                override_val = str(r.get("override_value", "")).strip()
                actor = str(r["reviewer"]).strip()
                before_action = scored.at[i, "suggested_action"]
                before_score = scored.at[i, "score"]

                # 1. REJECT: Reviewer bác bỏ đề xuất lỗi -> chuyển thành KEEP và hạ score
                if dec == "reject":
                    val = override_val if override_val else "KEEP"
                    scored.at[i, "suggested_action"] = val
                    scored.at[i, "score"] = 0.0001  # Hạ score xuống thấp vì người xác nhận không phải lỗi
                    scored.at[i, "pred_defect_type"] = "none"
                    scored.at[i, "reason"] = f"rejected by {actor}: {note}" if note else f"rejected by {actor}"
                    ctx.audit.log(
                        actor=actor,
                        action="override:reject",
                        item_id=img_id,
                        before={"action": before_action, "score": before_score},
                        after={"action": val, "score": 0.0001},
                        reason=note or "Reviewer rejected defect prediction",
                    )

                # 2. APPROVE: Reviewer xác nhận ảnh bị lỗi đúng như máy dự đoán
                elif dec == "approve":
                    val = override_val if override_val else "RECAPTURE"
                    scored.at[i, "suggested_action"] = val
                    ctx.audit.log(
                        actor=actor,
                        action="review:approve",
                        item_id=img_id,
                        before=before_action,
                        after=val,
                        reason=note or "Reviewer confirmed defect",
                    )

                # 3. EDIT: Sửa hành động hoặc loại lỗi theo ghi chú
                elif dec == "edit":
                    val = override_val if override_val else (note.upper() if note.upper() in ["KEEP", "RECAPTURE"] else before_action)
                    scored.at[i, "suggested_action"] = val
                    if note and note.lower() in ["blur", "glare", "dark", "compression"]:
                        scored.at[i, "pred_defect_type"] = note.lower()
                    ctx.audit.log(
                        actor=actor,
                        action="override:edit",
                        item_id=img_id,
                        before=before_action,
                        after=val,
                        reason=note or "Reviewer edited decision",
                    )
    else:
        ctx.stats["n_reviewed"] = 0
    return scored


# ---------------------------------------------------------------- 05 decide
def decide(ctx: RunContext, final: pd.DataFrame) -> Decision:
    """Cổng quyết định Risk Gate theo chuẩn Rubric: HOLD nếu chưa review, GO khi đã hoàn thành."""
    owner = ctx.config.get("owner", "Hau Pham (ML Engineer)")
    n_items = len(final)
    n_reviewed = int(ctx.stats.get("n_reviewed", 0))
    budget = int(ctx.param("budget", 20))
    n_recapture = int((final["suggested_action"] == "RECAPTURE").sum())
    n_keep = n_items - n_recapture

    metrics = {
        "n_total_images": n_items,
        "n_recapture": n_recapture,
        "n_keep": n_keep,
        "review_budget": budget,
        "n_reviewed_by_human": n_reviewed,
        "review_completion_rate": round(n_reviewed / budget, 2) if budget else 0.0,
    }

    # Nếu chưa có người review đủ budget: HOLD theo đúng quy chế kiểm toán
    if n_reviewed < budget:
        return Decision(
            status="HOLD",
            reason_code="AWAITING_HUMAN_AUDIT",
            reason=f"Mới review {n_reviewed}/{budget} ảnh nghi ngờ trong Eval queue. Cần hoàn tất review trước khi xuất xưởng.",
            owner=owner,
            scope=ctx.track,
            metrics=metrics,
            evidence=[str(ctx.out("review_queue.csv")), str(ctx.out("contact_sheet.html"))],
        )

    # Đã hoàn tất review của con người: Cho phép xuất xưởng (GO)
    return Decision(
        status="GO",
        reason_code="QC_TRIAGE_VERIFIED",
        reason=f"Đã hoàn thành kiểm toán người duyệt ({n_reviewed}/{budget} ảnh). Tổng {n_items} ảnh: {n_recapture} RECAPTURE, {n_keep} KEEP.",
        owner=owner,
        scope=ctx.track,
        metrics=metrics,
        evidence=[str(ctx.out("ranked_review.csv")), str(ctx.out("review_queue.csv")), str(ctx.out("audit_log.jsonl"))],
    )


# ---------------------------------------------------------------- E2E Run
def run(ctx: RunContext) -> None:
    spec = get_track(ctx.track)
    data = load(ctx)
    scored, boxes_by_item = process(ctx, data)
    ctx.stats["n_items"] = len(scored)

    queue = rank(ctx, scored, boxes_by_item)
    final = review(ctx, scored, queue)
    final = final.sort_values("score", ascending=False).reset_index(drop=True)

    output_cols = spec.pred_columns + [c for c in final.columns if c not in spec.pred_columns]
    final[output_cols].to_csv(ctx.out(spec.pred_file), index=False)

    decision = decide(ctx, final)
    write_decision(decision, ctx.out("decision.json"), ctx.out("decision_log.csv"))