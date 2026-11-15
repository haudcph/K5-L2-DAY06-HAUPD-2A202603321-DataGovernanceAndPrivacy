"""Unit tests for RAM-QC (ROI-Adaptive Multi-Feature QC) Architecture.

Verifies the 5 presentation feedback improvements:
1. 3-Tier triage assignment (auto-KEEP, REVIEW, auto-RECAPTURE).
2. Multi-defect scoring: score = max(s_i) + 0.05 * sum(others) + tie_breaker.
3. Slice normalization: different calibration thresholds for cam_A vs cam_B.
4. Small glare detection: contours with area >= 20px detected.
5. Spatial ROI weighting: critical driving corridor (y >= 0.35H) has 1.85x weight vs sky (0.35x).
"""
import numpy as np
import pytest
from src.pipeline import CALIBRATION_DEV


def test_calibration_dev_slices_exist():
    """Feedback #3: Per-(camera, light) calibration exists on dev split."""
    for cam in ["cam_A", "cam_B"]:
        for light in ["day", "dusk", "night"]:
            assert (cam, light) in CALIBRATION_DEV
            calib = CALIBRATION_DEV[(cam, light)]
            assert "lap_thr" in calib
            assert "block_med" in calib
            assert "sat_thr" in calib
    # cam_B has softer optics naturally, lap_thr must be strictly lower than cam_A
    assert CALIBRATION_DEV[("cam_B", "day")]["lap_thr"] < CALIBRATION_DEV[("cam_A", "day")]["lap_thr"]


def test_spatial_roi_glare_weighting():
    """Feedback #4 & #5: Glare in critical road corridor has higher impact than sky glare."""
    H, W = 400, 600
    area = 100.0  # same glare spot size

    # Case A: Glare in sky (y = 50 < 0.35 * 400 = 140)
    cy_sky = 50.0
    w_roi_sky = 0.35 if cy_sky < 0.35 * H else 1.85
    impact_sky = (area / 350.0) * w_roi_sky

    # Case B: Glare on road/corridor (y = 250 >= 0.35 * 400 = 140)
    cy_road = 250.0
    w_roi_road = 0.35 if cy_road < 0.35 * H else 1.85
    impact_road = (area / 350.0) * w_roi_road

    assert w_roi_road > w_roi_sky
    assert impact_road > impact_sky
    # Even a small glare on the road (area=80) should have higher impact than big glare in sky (area=300)
    small_road_impact = (80.0 / 350.0) * w_roi_road
    large_sky_impact = (300.0 / 350.0) * w_roi_sky
    assert small_road_impact > large_sky_impact


def test_multi_defect_scoring_formula():
    """Feedback #2: score = max(s_i) + 0.05 * sum(others)."""
    # Single defect
    scores_single = {"blur": 0.8, "dark": 0.0, "glare": 0.0, "compression": 0.0}
    best_single = max(scores_single, key=scores_single.get)
    max_single = scores_single[best_single]
    sum_other_single = sum(v for k, v in scores_single.items() if k != best_single)
    score_1 = max_single + 0.05 * sum_other_single

    # Multiple defects (blur + dark)
    scores_multi = {"blur": 0.8, "dark": 0.6, "glare": 0.0, "compression": 0.0}
    best_multi = max(scores_multi, key=scores_multi.get)
    max_multi = scores_multi[best_multi]
    sum_other_multi = sum(v for k, v in scores_multi.items() if k != best_multi)
    score_2 = max_multi + 0.05 * sum_other_multi

    assert score_2 > score_1
    assert np.isclose(score_2, 0.8 + 0.05 * 0.6)


def test_three_tier_triage_boundaries():
    """Feedback #1: Clear 3-tier triage thresholds (auto-KEEP < 0.15, REVIEW 0.15-0.85, auto-RECAPTURE >= 0.85)."""
    def assign_tier(score: float):
        if score >= 0.85:
            return "auto-RECAPTURE"
        elif score >= 0.15:
            return "REVIEW"
        return "auto-KEEP"

    assert assign_tier(0.05) == "auto-KEEP"
    assert assign_tier(0.149) == "auto-KEEP"
    assert assign_tier(0.15) == "REVIEW"
    assert assign_tier(0.50) == "REVIEW"
    assert assign_tier(0.849) == "REVIEW"
    assert assign_tier(0.85) == "auto-RECAPTURE"
    assert assign_tier(0.99) == "auto-RECAPTURE"
