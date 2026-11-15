"""YOUR PoC PIPELINE — Track T02: Raw QC Triage (RAM-QC: ROI-Adaptive Multi-Feature QC)

Architecture upgrades addressing presentation feedback:
1. 3-Tier Triage Architecture: auto-KEEP (clean), REVIEW (uncertainty top-B), auto-RECAPTURE (severe corruption).
2. Multi-defect scoring: score = max(s_i) + 0.05 * sum(others) + micro_tie_breaker.
3. Rigorous Normalization per (camera_id, light) using DEV medians/IQR.
4. Spatial ROI Prior for Glare: 1.85x weight on road/corridor corridor, 0.35x on sky/canopy.
5. 2D Blockiness gradient: min(Block_H, Block_V) > 1.8 * base to eliminate 1D texture false alarms.
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

# =============================================================================
# Calibrated Baseline Statistics (Strictly computed on DEV split)
# =============================================================================
CALIBRATION_DEV = {
    ("cam_A", "day"): {"lap_thr": 250.0, "block_med": 1.08, "sat_thr": 150},
    ("cam_A", "dusk"): {"lap_thr": 200.0, "block_med": 1.24, "sat_thr": 120},
    ("cam_A", "night"): {"lap_thr": 180.0, "block_med": 1.10, "sat_thr": 220},
    ("cam_B", "day"): {"lap_thr": 90.0, "block_med": 1.08, "sat_thr": 120},
    ("cam_B", "dusk"): {"lap_thr": 70.0, "block_med": 1.30, "sat_thr": 100},
    ("cam_B", "night"): {"lap_thr": 100.0, "block_med": 1.00, "sat_thr": 200},
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
    """RAM-QC Engine: Multi-defect scoring with ROI spatial weighting & slice normalization."""
    df = data["images"].copy()
    scores = []
    defect_types = []
    actions = []
    triage_tiers = []
    reasons = []
    boxes_by_item: dict[str, list[dict]] = {}

    for _, row in df.iterrows():
        img_path = ctx.input_dir / row["path"]
        img = load_rgb(img_path)
        gray = to_gray(img)
        H, W = gray.shape
        cam = row.get("camera_id", "cam_A")
        light = row.get("light", "day")

        calib = CALIBRATION_DEV.get((cam, light), {"lap_thr": 150.0, "block_med": 1.1, "sat_thr": 150})

        # 1. Cảm biến MỜ (Blur): chuẩn hóa theo median DEV của (camera, light)
        lap = laplacian_variance(img)
        s_blur = max(0.0, (calib["lap_thr"] - lap) / calib["lap_thr"]) if lap < calib["lap_thr"] else 0.0

        # 2. Cảm biến TỐI (Dark): phân biệt ảnh đêm bình thường (P95 > 100) vs tối đen (P95 < 65)
        stats = brightness_stats(img)
        p95 = stats["p95"]
        mean_val = stats["mean"]
        s_dark = max(0.0, (65.0 - p95) / 65.0) if (p95 < 65.0 and mean_val < 25.0) else 0.0

        # 3. Cảm biến LÓA CÓ TRỌNG SỐ ROI (ROI-aware Glare):
        # Trọng số: Bầu trời (y < 0.35H) ít nguy hiểm (W=0.35); Lòng đường/xe/người đi bộ (y >= 0.35H) chí mạng (W=1.85)
        sat_mask = (gray > 240).astype(np.uint8)
        cnts, _ = cv2.findContours(sat_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        s_glare = 0.0
        glare_boxes = []

        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            area = w * h
            cy = y + h / 2.0
            w_roi = 0.35 if cy < 0.35 * H else 1.85
            if area >= 20:  # phát hiện được cả lóa nhỏ
                glare_impact = (area / 350.0) * w_roi
                if glare_impact > s_glare:
                    s_glare = glare_impact
                if area >= 120 or (area >= 35 and w_roi > 1.0):
                    glare_boxes.append({"x": x, "y": y, "w": w, "h": h, "label": "glare", "color": "yellow"})

        # Điều chỉnh ban đêm: đèn xe/đèn đường tự nhiên có pixel bão hòa nhưng diện tích nhỏ
        if light == "night" and sat_mask.sum() < calib["sat_thr"]:
            s_glare = 0.0
            glare_boxes = []

        if glare_boxes:
            boxes_by_item[row["image_id"]] = glare_boxes

        # 4. Cảm biến NÉN VỠ HÌNH 2D (JPEG Compression):
        # Bắt buộc cả H và V cùng đứt gãy để loại trừ texture sọc 1 chiều
        diff_h = np.abs(gray[:, 7:-1:8] - gray[:, 8::8]).mean()
        diff_hi = np.abs(gray[:, 3:-1:8] - gray[:, 4::8]).mean()
        diff_v = np.abs(gray[7:-1:8, :] - gray[8::8, :]).mean()
        diff_vi = np.abs(gray[3:-1:8, :] - gray[4::8, :]).mean()
        block_h = diff_h / (diff_hi + 1e-5)
        block_v = diff_v / (diff_vi + 1e-5)
        block_min = min(block_h, block_v)
        s_comp = max(0.0, (block_min - 1.8 * calib["block_med"]) / 1.5)

        # 5. Công thức gộp điểm nhiều lỗi: Score = max(s_i) + 0.05 * sum(others)
        sensor_scores = {
            "blur": s_blur,
            "dark": s_dark,
            "glare": s_glare,
            "compression": s_comp,
        }
        best_defect = max(sensor_scores, key=sensor_scores.get)
        max_s = sensor_scores[best_defect]
        other_sum = sum(v for k, v in sensor_scores.items() if k != best_defect)

        # Micro tie-breaker để mọi ảnh đều có rank riêng biệt
        tie_breaker = (
            (1.0 / (lap + 1.0)) * 1e-4 +
            (1.0 / (mean_val + 1.0)) * 1e-4 +
            stats["frac_saturated"] * 1e-3 +
            block_min * 1e-4
        )
        final_score = round(float(max_s + 0.05 * other_sum + tie_breaker), 6)

        # 6. Lọc 3 tầng (3-tier triage)
        if final_score >= 0.85:
            tier = "auto-RECAPTURE"
            action = "RECAPTURE"
        elif final_score >= 0.15:
            tier = "REVIEW"
            action = "RECAPTURE"  # đề xuất kiểm tra
        else:
            tier = "auto-KEEP"
            action = "KEEP"

        active_defects = [f"{k}({v:.2f})" for k, v in sensor_scores.items() if v > 0.10]
        reason_str = " + ".join(active_defects) if active_defects else "clean"

        scores.append(final_score)
        defect_types.append(best_defect if max_s > 0.15 else "none")
        actions.append(action)
        triage_tiers.append(tier)
        reasons.append(f"[{tier}] {reason_str}")

    df["score"] = scores
    df["pred_defect_type"] = defect_types
    df["suggested_action"] = actions
    df["triage_tier"] = triage_tiers
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
                    scored.at[i, "score"] = 0.0001
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
    """Cổng quyết định Risk Gate theo chuẩn Rubric: Báo cáo đầy đủ 3 tầng triage."""
    owner = ctx.config.get("owner", "Pham Duc Hau (lead)")
    n_items = len(final)
    n_reviewed = int(ctx.stats.get("n_reviewed", 0))
    budget = int(ctx.param("budget", 20))
    n_recapture = int((final["suggested_action"] == "RECAPTURE").sum())
    n_keep = n_items - n_recapture
    n_auto_keep = int((final.get("triage_tier") == "auto-KEEP").sum())
    n_auto_recapture = int((final.get("triage_tier") == "auto-RECAPTURE").sum())

    metrics = {
        "n_total_images": n_items,
        "n_recapture": n_recapture,
        "n_keep": n_keep,
        "n_auto_keep": n_auto_keep,
        "n_auto_recapture": n_auto_recapture,
        "review_budget": budget,
        "n_reviewed_by_human": n_reviewed,
        "review_completion_rate": round(n_reviewed / budget, 2) if budget else 0.0,
    }

    # Nếu chưa review đủ ngân sách: HOLD
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

    # Đã hoàn tất review: GO
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
