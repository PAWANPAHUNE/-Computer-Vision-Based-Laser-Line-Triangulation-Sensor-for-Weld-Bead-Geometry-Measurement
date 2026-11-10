<div align="center">

# Computer Vision Based Laser-Line Triangulation Sensor for Weld Bead Geometry Measurement

**A low-cost 3D-printed camera + line-laser sensor for a robotic MIG torch, with checkerboard camera calibration, laser-plane calibration and an image-processing pipeline. It measures the width, height and cross-section area of a surface feature from a single photo.**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-computer%20vision-5C3EE8?logo=opencv&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-app-FF4B4B?logo=streamlit&logoColor=white)
![OpenSCAD](https://img.shields.io/badge/OpenSCAD-parametric%20CAD-F9D72C)
![Tests](https://img.shields.io/badge/tests-139%20passing-2ea44f)

<img src="docs/images/cad_v3_front.jpg" width="48%" alt="CAD model of the sensor fixture on the torch"/>
<img src="docs/images/box_overlay.jpg" width="40%" alt="Detected laser stripe crossing a 50 mm reference box"/>

*Left: the parametric fixture holding the camera and laser on the torch neck (CAD). Right: the detected laser stripe (green) stepping up over a 50 mm reference box.*

</div>

---

## Highlights

| What | Result |
|---|---|
| Camera calibration (Zhang, 57 checkerboard views) | **0.467 px** RMS reprojection error (held-out half: 0.44 px) |
| Laser-plane calibration (6 poses, 487 points) | **0.36 mm** RMS plane residual, leave-one-out 0.31–0.58 mm |
| Height of a 50.0 mm reference box (direct triangulation) | **50.38 mm** (+0.38 mm, +0.8 %) |
| Height of the same box (fully automatic app pipeline) | 52.04 mm (+4.1 %) |
| Synthetic beads (known geometry) | height within **0.5 %** |
| Predicted height resolution at the design stand-off (100–200 mm) | **0.06–0.23 mm** |
| Fixture | 3D-printable, all fasteners printed, camera tilt lockable 0–45° in 5° steps, all fits verified in CAD |

---

## Contents

1. [How it works](#how-it-works)
2. [Hardware](#hardware)
3. [CAD fixture design](#cad-fixture-design)
4. [Camera calibration (checkerboard)](#camera-calibration-checkerboard)
5. [Laser-plane calibration](#laser-plane-calibration)
6. [Measurement pipeline and key formulas](#measurement-pipeline-and-key-formulas)
7. [Results and validation](#results-and-validation)
8. [Software: quick start](#software-quick-start)
9. [Repository structure](#repository-structure)
10. [Roadmap](#roadmap)

---

## How it works

A red line laser projects a thin stripe across the part. The camera views the stripe from a position
offset by the **baseline** *b* ≈ 56 mm. Wherever the surface rises, the stripe shifts sideways in the image.
After calibration, every stripe pixel is turned into a 3D point by intersecting its viewing ray with the
**laser plane**. One image gives one complete cross-section (profile) of the surface.

```mermaid
flowchart LR
    A[Checkerboard photos] --> B[Camera calibration<br/>K, distortion]
    B --> C[Laser OFF / ON pairs<br/>on the board]
    C --> D[Laser-plane fit<br/>n·X + d = 0]
    B --> E
    D --> E
    F[One photo of the part] --> G[Red-stripe detection<br/>sub-pixel centres]
    G --> E[Ray–plane triangulation<br/>3D profile]
    E --> H[Base line + peak + edges]
    H --> I[Width · Height · Area<br/>in mm + confidence]
```

---

## Hardware

| Part | Specification |
|---|---|
| Camera | Arducam UC-852 USB module, 1280 × 800, board 38 × 38 mm, holes 5 mm from the edges |
| Laser | Red line laser, Ø 11 mm × 35 mm, cylindrical |
| Fixture | 3D-printed (PETG/PLA), camera–laser spacing fixed at 55 mm by CAD |
| Mount | Torch neck of a welding robot (Ø 16–65 mm, ratchet straps) |
| Calibration target | Printed checkerboard, 9 × 6 inner corners, 25.0 mm squares (checked: 4 squares = 100 mm), glued to rigid board |

<p align="center">
<img src="docs/images/hw_camera_front.jpg" height="200" alt="Camera front"/>
<img src="docs/images/hw_camera_back.jpg" height="200" alt="Camera back"/>
<img src="docs/images/hw_laser.jpg" height="200" alt="Line laser"/>
<img src="docs/images/hw_robot.jpg" height="200" alt="Welding robot torch"/>
</p>

---

## CAD fixture design

The fixture is fully **parametric (OpenSCAD)**. It went through three design iterations. The final kit is
printable with no metal screws: pins, locking forks, a snap-on laser clip and ratchet straps are all printed.

### Design iterations

| v1: first fit-check | v2: separate carrier + battery saddle | v3 (final): side-by-side, tilting yoke |
|:---:|:---:|:---:|
| <img src="docs/images/cad_v1.jpg" width="260"/> | <img src="docs/images/cad_v2.jpg" width="260"/> | <img src="docs/images/cad_v3_side.jpg" width="260"/> |

### Final design (v3)

| Camera tilted to 45° | Print orientation | Printed kit on the print bed |
|:---:|:---:|:---:|
| <img src="docs/images/cad_v3_tilt45.jpg" width="260"/> | <img src="docs/images/cad_v3_print.jpg" width="260"/> | <img src="docs/images/kit_layout.jpg" width="260"/> |

- **Layout:** camera and laser side by side on one base plate, **55 mm apart** (the triangulation baseline). The laser points perpendicular to the plate.
- **Camera tilt:** the camera sits on a yoke that pivots in the board plane. **Angle-lock plates** (0–45° in 5° steps, LEFT/RIGHT) key into an arc slot, so the angle cannot drift with vibration.
- **Camera board:** held by four press-fit pins (28 mm hole pitch).
- **Laser:** 90° V-cradle plus a snap-on U-clip with a 0.6 mm preload (~40 N in PETG). Three clip sizes cover Ø 10.6–11.4 mm.
- **Torch mount:** V-saddle clamp block with printed ratchet straps (neck Ø 16–65 mm), joined to the base by four pins with sliding locking forks.
- **Verification:** every part was modelled in its installed position and checked by boolean intersection at all ten tilt angles. **ALL CHECKS PASS** ([`VERIFICATION_REPORT.txt`](cad/fixture_final/VERIFICATION_REPORT.txt)).

### Assembly (shop-screw version)

| Shopping list | 1. Clamp block | 2. Laser | 3. Camera holder + angle plates |
|:---:|:---:|:---:|:---:|
| <img src="cad/fixture_final/7_assembly_with_shop_screws/0_SHOPPING_LIST.png" width="200"/> | <img src="cad/fixture_final/7_assembly_with_shop_screws/step1_clamp_block.png" width="200"/> | <img src="cad/fixture_final/7_assembly_with_shop_screws/step2_laser.png" width="200"/> | <img src="cad/fixture_final/7_assembly_with_shop_screws/step3_camera_holder_and_angle_plates.png" width="200"/> |
| **4. Camera board** | **5. Mount on torch** | **6. Finished** | **Assembled with printed kit** |
| <img src="cad/fixture_final/7_assembly_with_shop_screws/step4_camera_board.png" width="200"/> | <img src="cad/fixture_final/7_assembly_with_shop_screws/step5_mount_on_torch.png" width="200"/> | <img src="cad/fixture_final/7_assembly_with_shop_screws/step6_finished.png" width="200"/> | <img src="docs/images/kit_assembled.jpg" width="200"/> |

Full instructions: [`cad/fixture_final/ASSEMBLY_GUIDE.pdf`](cad/fixture_final/ASSEMBLY_GUIDE.pdf). STL files: [`cad/fixture_final/`](cad/fixture_final/). Sources: [`cad/fixture_final/5_source_CAD/`](cad/fixture_final/5_source_CAD/).

---

## Camera calibration (checkerboard)

Zhang's method: several views of a planar checkerboard at **different tilts** give homographies, from
which the intrinsic matrix **K** and lens distortion are solved and then refined by minimising the
reprojection error (`cv2.calibrateCamera`, Brown–Conrady model, *k₃* fixed).

**Photo guide.** A beginner-friendly picture guide shows exactly where to place the board in each photo:

| Where to put the board | Flat | Edge on a book | Corner on a book |
|:---:|:---:|:---:|:---:|
| <img src="software/photos/HOW_TO/HOW_TO_TAKE_PHOTOS.png" width="200"/> | <img src="software/photos/HOW_TO/PAGE_1_A_flat.png" width="200"/> | <img src="software/photos/HOW_TO/PAGE_2_B_edge_on_book.png" width="200"/> | <img src="software/photos/HOW_TO/PAGE_3_C_corner_on_book.png" width="200"/> |

**Accepted views and coverage** (57 views, tilt 4.9°–35.9°):

<p align="center">
<img src="docs/images/calib_views.jpg" width="80%" alt="Accepted checkerboard views"/>
</p>

| Corner coverage of the image | Reprojected corners |
|:---:|:---:|
| <img src="docs/images/calib_coverage.jpg" width="420"/> | <img src="docs/images/calib_reprojection.jpg" width="420"/> |

| Per-view RMS reprojection error | Board-tilt distribution |
|:---:|:---:|
| <img src="docs/images/calib_errors.png" width="420"/> | <img src="docs/images/calib_tilts.png" width="420"/> |

**Result** ([`software/data/calibration/calibration.json`](software/data/calibration/calibration.json)):

| Parameter | Value |
|---|---|
| Focal length *f<sub>x</sub>*, *f<sub>y</sub>* | 939.61 px, 941.85 px |
| Principal point *c<sub>x</sub>*, *c<sub>y</sub>* | 689.00 px, 356.97 px |
| Distortion *k₁, k₂, p₁, p₂, k₃* | 0.0549, 0.0760, 0.0023, 0.0063, 0 (fixed) |
| RMS reprojection error | **0.467 px** (per view 0.23–0.76 px, median 0.38 px) |
| Views used | 57 (1280 × 800) |

Lessons learned in the first calibration round: a bent paper board and views that only rotate *within* the
floor plane gave 1.48 px RMS and a wrong focal length. The fix was a rigid board, real tilts and the picture guide above.

---

## Laser-plane calibration

For each pose the board is photographed **laser OFF** and **laser ON** without moving anything. The
difference image isolates the stripe. The board pose comes from PnP. Every stripe pixel's ray is intersected
with the board plane, giving 3D points that lie in the laser plane. A robust 3D line fit per pose rejects
stray points, and an SVD plane fit over all poses gives the laser plane.

<p align="center">
<img src="software/photos/HOW_TO/LASER_CALIBRATION_PHOTOS.png" width="60%" alt="Laser calibration photo guide"/>
</p>

**Laser orientation matters.** The stripe must be perpendicular to the camera–laser baseline (a "T"
shape). With the laser rotated 90° in its cradle, the 50 mm box shift grew from **1.9 px to 8.8 px**
(predicted: 7.6 px).

<p align="center"><img src="docs/images/laser_orientation.jpg" width="80%" alt="Laser orientation before/after"/></p>

| The six laser-ON calibration poses | Stripe extraction (OFF/ON subtraction) |
|:---:|:---:|
| <img src="docs/images/laser_poses.jpg" width="420"/> | <img src="docs/images/laser_extraction.jpg" width="420"/> |

| Laser points and fitted plane (3D) | Point-to-plane residuals |
|:---:|:---:|
| <img src="docs/images/laser_plane_3d.png" width="420"/> | <img src="docs/images/laser_residuals.png" width="420"/> |

| Quantity | Value |
|---|---|
| Plane *n·X + d = 0* | n = (−0.9287, 0.3292, −0.1708), d = −56.65 mm |
| Points / poses | 487 / 6 (100 % inliers) |
| RMS / max residual | **0.36 mm** / 1.12 mm |
| Leave-one-out RMS per pose | 0.31–0.58 mm |
| Camera-to-plane distance | 56.6 mm (CAD spacing 55 mm) |

---

## Measurement pipeline and key formulas

**1. Stripe detection:** red score per pixel and sub-pixel centre along each image row:

$$S(u,v) = R - \max(G, B), \qquad u^{*} = \frac{\sum_u u \, S(u,v)}{\sum_u S(u,v)}$$

**2. Pinhole projection with distortion** (Brown–Conrady, $r^2 = x^2 + y^2$):

$$s \begin{bmatrix} u \\ v \\ 1 \end{bmatrix} = \mathbf{K} \, [\mathbf{R} \mid \mathbf{t}] \begin{bmatrix} X \\ Y \\ Z \\ 1 \end{bmatrix}, \qquad x_d = x(1 + k_1 r^2 + k_2 r^4 + k_3 r^6) + 2p_1 xy + p_2(r^2 + 2x^2)$$

**3. Ray–plane triangulation:** undistorted pixel → ray $\mathbf{r} = \mathbf{K}^{-1}[u\ v\ 1]^T$, point on the laser plane:

$$\mathbf{X} = \lambda \, \mathbf{r}, \qquad \lambda = \frac{-d}{\mathbf{n} \cdot \mathbf{r}}$$

**4. Sensitivity and resolution** (stripe shift per mm of height at stand-off *Z*):

$$\frac{\Delta u}{\Delta h} \approx \frac{f_x \, b}{Z^2}, \qquad \delta h \approx \frac{Z^2}{f_x \, b}\,\delta u$$

**5. Geometry extraction:**
- **Base line:** a RANSAC line fitted to the profile on both sides of the feature.
- **Height:** the moving-median peak above the base line.
- **Width:** measured between the half-height edges (β = 0.5 for boxes, 0.05 for weld beads).
- **Area:** the integral of the profile above the base line.
- **Confidence:** a score from stripe coverage and fit quality. Results below the threshold are flagged.

The app refuses to report millimetres when the calibration file is missing or fails validation.

---

## Results and validation

### Reference box (true height 50.0 mm)

<p align="center"><img src="docs/images/box_profile.png" width="85%" alt="Height profile of the box"/></p>

| Evaluation | Height (mm) | Error | Confidence |
|---|:---:|:---:|:---:|
| Direct triangulation against the floor plane | **50.38** | **+0.38 mm (+0.8 %)** | – |
| Automatic pipeline, capture 1 | 52.04 | +2.04 mm (+4.1 %) | 0.99 |
| Automatic pipeline, capture 2 (box next to the stand foot) | 54.15 | +4.15 mm (+8.3 %) | 0.95 |

The single-point scatter on the box top was 1.45 mm (1σ) at a 592 mm stand-off, matching the predicted
≈2 mm resolution. The median over 121 points brings it well below 1 mm. In capture 2 the stripe crossed the stand foot,
which corrupted the base line on one side; the app warned about this.

### Synthetic beads (known geometry)

| True width | Measured | True height | Measured | Height error |
|:---:|:---:|:---:|:---:|:---:|
| 8.0 mm | 8.51 mm | 2.0 mm | 2.000 mm | 0.0 % |
| 6.0 mm | 6.40 mm | 1.2 mm | 1.205 mm | +0.4 % |
| 10.0 mm | 10.54 mm | 3.0 mm | 3.005 mm | +0.2 % |

Detection stayed reliable with noise, a weak laser, saturation, gaps, reflections, an off-centre bead and a tilted plate (confidence 0.74–1.00).

### Resolution vs stand-off

<p align="center"><img src="docs/images/sensitivity.png" width="70%" alt="Sensitivity vs stand-off"/></p>

| Stand-off *Z* | Sensitivity *f<sub>x</sub>b/Z²* | Height resolution (δu = 0.3 px) |
|:---:|:---:|:---:|
| 100 mm | 5.32 px/mm | **0.06 mm** |
| 150 mm | 2.36 px/mm | 0.13 mm |
| 200 mm | 1.33 px/mm | 0.23 mm |
| 300 mm | 0.59 px/mm | 0.51 mm |
| 592 mm (bench test) | 0.15 px/mm | 1.98 mm |

---

## Software: quick start

```bash
git clone https://github.com/PAWANPAHUNE/-Computer-Vision-Based-Laser-Line-Triangulation-Sensor-for-Weld-Bead-Geometry-Measurement.git
cd -Computer-Vision-Based-Laser-Line-Triangulation-Sensor-for-Weld-Bead-Geometry-Measurement/software
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

streamlit run app.py                                     # the measurement app
python scripts/capture_photos.py --mode checkerboard     # guided camera-calibration photos
python scripts/capture_photos.py --mode laser            # guided laser OFF/ON pairs
python scripts/run_synthetic_demo.py                     # full demo without hardware
python -m pytest                                         # 139 tests
```

**Two strictly separated modes**, chosen only by `calibration.enabled` in [`config/config.yaml`](software/config/config.yaml):

| Mode | Output |
|---|---|
| **Uncalibrated** | Stripe, profile and bead size in **pixels**. Works with no calibration. |
| **Calibrated** | **Millimetres** via ray–plane triangulation, only if the calibration file passes every check. Otherwise mm output is blocked. |

The capture tool helps beginners:
- it shows a live preview and saves only good photos;
- it rejects photos from the wrong camera by checking the resolution;
- it detects a board that moved between the OFF and ON photos from the corner shift;
- it warns when the laser was left on in both photos.

Detailed docs: [`software/README.md`](software/README.md) · [`software/Calibration.md`](software/Calibration.md) · [`software/HARDWARE_PARAMETERS.md`](software/HARDWARE_PARAMETERS.md)

---

## Repository structure

```
.
├── cad/
│   ├── fixture_final/                 # final printable kit (v3)
│   │   ├── 1_fixture_parts_ALREADY_PRINTED/   base, camera yoke, arm clamp (STL)
│   │   ├── 2_print_pins_clips_straps/         printed fasteners (STL)
│   │   ├── 3_print_angle_plates/              0–45° angle-lock plates (STL)
│   │   ├── 4_pictures/                        renders
│   │   ├── 5_source_CAD/                      OpenSCAD sources + design notes
│   │   ├── 6_optional_metal_screws/           shop-screw alternative
│   │   ├── 7_assembly_with_shop_screws/       step-by-step pictures + fit check
│   │   ├── ASSEMBLY_GUIDE.pdf / .md
│   │   └── VERIFICATION_REPORT.txt
│   └── design_history/v1, v2, v3/     # earlier iterations (SCAD, STL, previews)
├── software/
│   ├── app.py                         # Streamlit measurement app
│   ├── calibration/                   # checkerboard, camera, laser-plane, triangulation, validation
│   ├── vision/                        # camera I/O, laser detection, profile, weld measurement, pipeline
│   ├── utils/                         # config loader, photo capture, export, image I/O
│   ├── synthetic/                     # synthetic scene renderer for testing
│   ├── scripts/                       # capture_photos, generate_checkerboard, run_synthetic_demo
│   ├── config/                        # config.yaml + examples
│   ├── data/calibration/              # calibration.json + calibration report
│   ├── photos/                        # real calibration dataset + photo guides
│   ├── assets/                        # printable checkerboards (PDF/SVG)
│   └── tests/                         # 139 pytest tests
└── docs/images/                       # figures used in this README
```

---

## Roadmap

- [x] Parametric fixture, fit-verified kit, assembly guide
- [x] Camera calibration (0.47 px) and laser-plane calibration (0.36 mm)
- [x] Measurement app with calibrated / uncalibrated modes and validation on a reference object
- [ ] Mount on the robot torch at the design stand-off (100–200 mm) and re-calibrate
- [ ] Measure real MIG weld beads and compare with a weld gauge / sectioned samples
- [ ] Optical band-pass filter, heat and spatter shield for operation next to the arc
- [ ] Real-time profiling while the torch moves and closed-loop process feedback

---

<div align="center">

**Pawan Pahune** · Mechanical Engineering, IIT Kharagpur

</div>
