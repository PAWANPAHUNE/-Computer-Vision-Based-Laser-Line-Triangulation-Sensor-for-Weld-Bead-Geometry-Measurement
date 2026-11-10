#!/usr/bin/env python3
"""Run the synthetic demonstration (no hardware needed).

1. Detection/measurement on synthetic weld images (clean, noisy, weak, saturated, gaps, reflection,
   off-centre bead, tilted plate) compared with known ground truth.
2. Full camera + laser-plane calibration on rendered checkerboard images, then calibrated
   measurement of synthetic beads.

Writes:
  outputs/synthetic_demo/report.json and report.md
  outputs/synthetic_demo/images/...      sample images you can upload in the app
  data/calibration/synthetic_demo_calibration.json   (NEVER your real calibration file)

    python scripts/run_synthetic_demo.py

These results only show that the software is self-consistent. They are NOT the accuracy of
your real camera, laser and fixture.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402

from calibration.calibration_file import save_calibration  # noqa: E402
from synthetic.demo import (DEMO_SPEC, INTRINSIC_POSES, LASER_POSES, demo_rig, run_calibrated_demo,  # noqa: E402
                            run_detection_demo)
from synthetic.scene import BeadSpec, SyntheticRig, look_at_pose, render_board_image, render_weld_image  # noqa: E402
from utils.config_loader import PROJECT_ROOT  # noqa: E402
from utils.export import _clean  # noqa: E402

OUT = PROJECT_ROOT / "outputs" / "synthetic_demo"
CAL_PATH = PROJECT_ROOT / "data" / "calibration" / "synthetic_demo_calibration.json"


def pct(a, b):
    return "-" if a is None else f"{100 * (a - b) / b:+.1f}%"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    img_dir = OUT / "images"
    lines = ["# Synthetic demo report", "",
             "SYNTHETIC DATA ONLY. These numbers check the software against known ground truth. They say nothing "
             "about the accuracy of the real hardware.", ""]

    print("1) Detection and pixel measurement on synthetic weld images (uncalibrated mode)")
    rows = run_detection_demo()
    lines += ["## 1. Uncalibrated mode (pixel) + nominal-geometry estimate", "",
              "| scenario | status | det. conf | width px (true) | height px (true) | nominal width mm (true 8) | nominal height mm (true 2) |",
              "|---|---|---|---|---|---|---|"]
    for r in rows:
        line = (f"| {r['scenario']} | {r['status']} | {r['detection_conf']:.2f} | {r['width_px']:.1f} ({r['width_px_true']:.1f}) | "
                f"{r['height_px']:.2f} ({r['height_px_true']:.2f}) | {r['nominal_width_mm']:.2f} | {r['nominal_height_mm']:.2f} |")
        lines.append(line)
        print("  " + line)

    print("2) Synthetic camera + laser-plane calibration and calibrated measurement")
    demo = run_calibrated_demo()
    cal = demo["calibration"]
    intr = cal["intrinsics"]
    lines += ["", "## 2. Calibration on rendered checkerboard images", "",
              f"- Camera: {intr.num_views} views, reprojection error {intr.rms_px:.3f} px, fx error "
              f"{cal.get('fx_error_pct', float('nan')):.3f}%"]
    if demo["ok"]:
        lp = cal["laser"]
        lines += [f"- Laser plane: {lp.num_poses} poses, RMS {lp.rms_mm:.4f} mm, normal error "
                  f"{cal['plane_angle_error_deg']:.3f} deg, distance error {cal['plane_distance_error_mm']:.3f} mm", "",
                  "## 3. Calibrated mode measurement", "",
                  "| true width mm | measured | error | true height mm | measured | error | validated |", "|---|---|---|---|---|---|---|"]
        for m in demo["measurements"]:
            lines.append(f"| {m['true_width_mm']} | {m['width_mm']:.3f} | {pct(m['width_mm'], m['true_width_mm'])} | "
                         f"{m['true_height_mm']} | {m['height_mm']:.3f} | {pct(m['height_mm'], m['true_height_mm'])} | "
                         f"{m['validated']} |")
        save_calibration(cal["calibration_data"], CAL_PATH)
        print(f"  synthetic calibration written to {CAL_PATH}")
    else:
        lines.append("- Calibration FAILED: " + "; ".join(intr.errors + (cal["laser"].errors if "laser" in cal else [])))
    lines += ["", "Known effect: widths read about 0.3-0.5 mm wide here because the rendered bead has vertical toes and "
              "the stripe is about 4 px thick; the bead edge is only located to within about half the stripe width."]
    for l_ in lines[-8:]:
        print("  " + l_)

    # Sample images for practising in the app (uncalibrated + synthetic calibrated config).
    rig = demo_rig()
    (img_dir / "camera_views").mkdir(parents=True, exist_ok=True)
    (img_dir / "laser_poses").mkdir(parents=True, exist_ok=True)
    for k, (d, tx, ty, sx, sy) in enumerate(INTRINSIC_POSES):
        rv, tv = look_at_pose(d, tx, ty, DEMO_SPEC, (sx, sy))
        cv2.imwrite(str(img_dir / "camera_views" / f"view_{k:02d}.png"), render_board_image(rig, DEMO_SPEC, rv, tv, seed=k))
    for k, (d, tx, ty) in enumerate(LASER_POSES):
        rv, tv = look_at_pose(d, tx, ty, DEMO_SPEC)
        cv2.imwrite(str(img_dir / "laser_poses" / f"pose_{k + 1}_laser_off.png"),
                    render_board_image(rig, DEMO_SPEC, rv, tv, False, seed=100 + k))
        cv2.imwrite(str(img_dir / "laser_poses" / f"pose_{k + 1}_laser_on.png"),
                    render_board_image(rig, DEMO_SPEC, rv, tv, True, seed=200 + k))
    img, _ = render_weld_image(rig, BeadSpec(8.0, 2.0, 5.0, 160.0), seed=3)
    cv2.imwrite(str(img_dir / "weld_for_synthetic_calibration_8x2mm.png"), img)
    img, _ = render_weld_image(SyntheticRig(), BeadSpec(8.0, 2.0, 5.0, 150.0), seed=3, reflection=True)
    cv2.imwrite(str(img_dir / "weld_uncalibrated_with_reflection.png"), img)
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "report.json").write_text(json.dumps(_clean({"detection": rows, "calibrated": demo.get("measurements"),
                                                        "plane_angle_error_deg": cal.get("plane_angle_error_deg"),
                                                        "fx_error_pct": cal.get("fx_error_pct")}), indent=2))
    print(f"Report: {OUT / 'report.md'}\nImages: {img_dir}")
    return 0 if demo["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
