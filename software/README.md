# Laser-triangulation weld bead measurement

A Streamlit application for a red line laser and an Arducam UC-852 USB camera mounted side by side on a
robotic welding torch (fixture `welding_sensor_fixture_v3`). It finds the laser line on a welded
sheet, extracts the bead cross-section, and reports bead width and height.

- **Uncalibrated mode** works with no calibration: stripe detection, profile, and bead size in **pixels**.
- **Calibrated mode** reports **millimetres** using camera intrinsics plus a calibrated laser plane
  (ray-plane triangulation), and only when the calibration passes every check.

The mode is chosen **only** by `calibration.enabled` in `config/config.yaml`. The app never switches mode by itself.

Step-by-step calibration for beginners: **[Calibration.md](Calibration.md)**.
Which hardware values are known: **[HARDWARE_PARAMETERS.md](HARDWARE_PARAMETERS.md)**.

## Setup (macOS, Apple Silicon or Intel)

```bash
cd software
python3 -m venv .venv            # only the first time
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The virtual environment is created inside `software/.venv` (ignored by git).

## Run

```bash
streamlit run app.py
```

The browser opens at http://localhost:8501. The first time, macOS asks for camera permission for
Terminal or VS Code. Allow it. Use **Scan Cameras** in the sidebar: index 0 is often the built-in camera.

Try calibrated mode on synthetic data, without hardware:

```bash
python scripts/run_synthetic_demo.py
LASER_TRI_CONFIG=config/config.example.synthetic_calibrated.yaml streamlit run app.py
```

Take calibration photos into sorted folders (live preview, only good photos are saved):

```bash
python scripts/capture_photos.py --mode checkerboard   # camera calibration
python scripts/capture_photos.py --mode laser          # laser plane (laser OFF + ON pairs)
```

`LASER_TRI_CONFIG` selects another config file. Without it the app uses `config/config.yaml`.

## Test

```bash
python -m pytest
```

The suite covers configuration and mode rules, stripe detection, triangulation,
calibration, calibration-file validation, measurements, exports, and the Streamlit app in both modes.
All of them use synthetic images.

## Operating modes

| `calibration.enabled` | Calibration file | Result |
|---|---|---|
| `false` | not read | Uncalibrated mode. Pixels only. |
| `true` | valid | Calibrated mode. mm shown when measurement confidence ≥ `measurement.minimum_confidence`. |
| `true` | missing or invalid | Calibrated mode, **blocked**. With `require_valid_calibration: true` nothing is processed. With `false`, pixels are shown and mm stays blocked. |

`allow_uncalibrated_metric_estimates: true` (uncalibrated mode only) allows mm estimates that are
always labelled EXPERIMENTAL:

- a reference-scale estimate from a known width and a known step height, valid only near the reference;
- a nominal-geometry estimate, only when focal length, pixel pitch, baseline and all angles are entered.

Example configs:

- `config/config.example.uncalibrated.yaml`
- `config/config.example.calibrated.yaml`
- `config/config.example.synthetic_calibrated.yaml`

## How it works

1. **Detection** (`vision/laser_detection.py`). The red score is R − max(G, B), with saturated white
   cores restored. HSV and top-hat methods are also available. Steps:
   threshold, then remove small components, then pick a scan axis automatically (columns or rows),
   then take a peak-centred centroid with the background subtracted (sub-pixel accuracy).
   Where a scan line has several red regions, the stripe is followed by continuity, so reflections are skipped.
   Outliers are removed only when they disagree with both neighbours, so real steps are kept.
   A NaN-aware median filter smooths the result.
2. **Profile and measurement** (`vision/weld_measurement.py`). A RANSAC base line is refined on the
   local flanks of the bead. The bead can be anywhere in the profile. Edges are where the height drops
   to 5% of the peak. Width is measured along the base line and height perpendicular to it.
   Confidence combines detection, coverage, signal-to-noise and whether base material is visible on both sides.
3. **Camera calibration** (`calibration/camera_calibration.py`). OpenCV checkerboard calibration with
   view-count, image-coverage, tilt-variety and reprojection-error checks.
4. **Laser-plane calibration** (`calibration/laser_plane_calibration.py`). For each placement of the
   checkerboard, PnP measures the board plane. The laser-OFF image is subtracted and the result divided
   by the board brightness, so black and white squares do not bias the line. Laser pixels are
   triangulated onto the board plane, and the lines from all poses are fitted with a robust SVD plane.
5. **Triangulation** (`calibration/triangulation.py`). Undistort, form the camera ray, intersect it
   with the laser plane, and reject rays that are parallel, behind the camera, or out of the depth range.
6. **Validation** (`calibration/validation.py`). Checks the schema, the integrity hash (hand edits are
   detected), finite values, matrix shapes, error limits, resolution, the fixture id and camera tilt,
   and that the laser plane belongs to the current camera calibration.

## Project layout

```text
app.py                         Streamlit UI (Measure / Parameters / Calibration)
ui_labels.py                   every button label (Calibration.md is tested against it)
config/config.yaml             the active configuration (+ three example files)
calibration/                   checkerboard, camera + laser-plane calibration, triangulation,
                               calibration file, validation, nominal (approximate) model, PDF board
vision/                        camera access, laser detection, profiles, weld measurement, pipeline
utils/                         config loader, image I/O, JSON/CSV export
synthetic/                     synthetic scenes with known ground truth, demo runs
scripts/                       generate_checkerboard.py, run_synthetic_demo.py
assets/                        printable checkerboards (9 x 6 inner corners, 25 mm and 10 mm)
data/calibration/              calibration.json is written here
outputs/                       saved measurements and the synthetic demo report
tests/                         pytest suite
```

## Reused code

The existing starter kit in `AI_Welding/arducam_laser_calibration_starter` was inspected and left unchanged.

- Its checkerboard detector, `find_board`, is ported into `calibration/checkerboard.py`. The pattern size now comes from the config.
- Its camera-opening logic (AVFoundation first, then the default backend) is in `vision/camera.py`.
- Its intrinsic-calibration approach is in `calibration/camera_calibration.py`, extended with validation and JSON storage.
- Its 9 × 6 / 25 mm board is kept as the default. Photos captured with that kit can be uploaded in Calibration step 2 if they match the camera resolution.

## Limitations

- **One image is one cross-section.** Measuring along a seam needs many profiles plus robot pose data.
  That is not implemented.
- **Height definition.** Height is the perpendicular distance from the base reference line inside the
  laser plane. It equals the true reinforcement height only when the laser plane is perpendicular to the
  base metal. The v3 fixture holds the laser perpendicular to its plate, so keep the plate parallel to the work.
- **Edge resolution.** Bead edges are located to roughly half the stripe thickness. On synthetic beads
  with vertical toes and a ~4 px stripe, widths read 5–8% wide while heights are within about 1%.
  Real beads with sloped toes are affected less, but you must test this (Calibration.md, Part G).
- **Synthetic results are not hardware accuracy.** No accuracy is claimed for the real system until it
  is measured with reference parts.
- **Exposure and gain** are not controlled. OpenCV on macOS (AVFoundation) usually cannot set them.
  Adjust room light or laser power so the line is red, not white.
- **No public sample images** are bundled. Every test image is generated synthetically, so licensing
  is not an issue and the ground truth is exact.
- **Heat and safety.** The 3D-printed fixture and the camera must stay away from heat, spatter and arc
  light. See Calibration.md, Part I.
