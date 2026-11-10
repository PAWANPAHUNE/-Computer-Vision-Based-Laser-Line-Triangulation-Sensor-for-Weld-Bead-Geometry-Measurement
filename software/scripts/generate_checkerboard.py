#!/usr/bin/env python3
"""Create a printable checkerboard PDF + SVG.

Default values come from config/config.yaml (calibration.checkerboard), so the printed board,
the application and Calibration.md always use the same pattern.

    python scripts/generate_checkerboard.py
    python scripts/generate_checkerboard.py --cols 9 --rows 6 --square-mm 8 --out assets/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calibration.checkerboard import CheckerboardSpec  # noqa: E402
from calibration.checkerboard_print import checkerboard_pdf, checkerboard_svg, layout  # noqa: E402
from utils.config_loader import PROJECT_ROOT, load_config  # noqa: E402


def main() -> int:
    report = load_config()
    cb = report.config["calibration"]["checkerboard"]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cols", type=int, default=cb["inner_corners_cols"], help="inner corners across")
    ap.add_argument("--rows", type=int, default=cb["inner_corners_rows"], help="inner corners down")
    ap.add_argument("--square-mm", type=float, default=cb["square_size_mm"])
    ap.add_argument("--page", choices=["A4", "A3", "Letter"], default=None)
    ap.add_argument("--out", default=str(PROJECT_ROOT / "assets"))
    a = ap.parse_args()
    spec = CheckerboardSpec(a.cols, a.rows, a.square_mm)
    lay = layout(spec, a.page)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"checkerboard_{spec.inner_corners_cols}x{spec.inner_corners_rows}_{spec.square_size_mm:g}mm"
    (out / f"{stem}.pdf").write_bytes(checkerboard_pdf(spec, a.page))
    (out / f"{stem}.svg").write_text(checkerboard_svg(spec, a.page), encoding="utf-8")
    print(f"Wrote {out / (stem + '.pdf')} and .svg on {lay['page']} landscape.")
    print(f"Squares: {spec.squares[0]} x {spec.squares[1]}, inner corners: {spec.inner_corners_cols} x "
          f"{spec.inner_corners_rows}, square size {spec.square_size_mm:g} mm. Print at 100% / Actual size.")
    if (spec.inner_corners_cols, spec.inner_corners_rows, spec.square_size_mm) != \
            (cb["inner_corners_cols"], cb["inner_corners_rows"], cb["square_size_mm"]):
        print("NOTE: this differs from calibration.checkerboard in config/config.yaml. Update the config "
              "(Parameters tab or by hand) before calibrating.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
