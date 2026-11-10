# Calibration guide (simple steps)

This guide tells you exactly what to click and what you should see.
Button names are written like this: **"Run Camera Calibration"**. They are the real names in the app.

Contents:

- Part A. What are we doing?
- Part B. Before starting
- Part C. Camera calibration
- Part D. Laser-plane calibration
- Part E. Turn on calibrated mode
- Part F. Use uncalibrated mode
- Part G. Test the accuracy
- Part H. Troubleshooting
- Part I. Safety

---

## Part A. What are we doing?

1. The camera takes a picture.
2. The laser draws a thin red line on the metal.
3. Where the weld bead is, the red line bends.
4. The app finds the red line in the picture.
5. From the bend, the app works out the shape of the bead.

```
   camera            laser
     \                 |
      \                |   red line on the metal
       \               |
  ______\______/‾‾‾‾\__|________   <- the line bends over the weld bead
                bead
```

A picture is made of tiny dots called **pixels**.
The app can always measure the bead in pixels.
Pixels are **not** millimetres.

**Calibration** teaches the app how pixels turn into real millimetres.
It has **two separate jobs**:

| Job | What it learns | What you use |
|---|---|---|
| Camera calibration | How the lens bends and scales the picture | A printed checkerboard |
| Laser-plane calibration | Exactly where the laser light is, in front of the camera | The same checkerboard, with the laser on it |

You need **both** jobs before the app shows millimetres.
Camera calibration alone is not enough.

One picture gives **one cross-section** of the bead (one slice).
To measure the whole seam you need many pictures plus the robot position for each one.

---

## Part B. Before starting

### Things you need

- [ ] The camera and laser on the fixture, with all screws tight.
- [ ] A MacBook and a USB data cable or adapter for the camera.
- [ ] This project folder with its Python environment (see Part C, steps 1-3).
- [ ] A printed checkerboard (see below).
- [ ] A ruler or calliper.
- [ ] A flat, stiff board (foam board, acrylic or metal) to glue the checkerboard on.
- [ ] Glue stick or spray glue.
- [ ] Some books or blocks to hold the board at different heights.
- [ ] A way to switch the laser on and off without moving anything (a switch on its power wire).

### Squares and inner corners

An **inner corner** is a point where four squares touch.
The app counts inner corners, not squares.

```
  squares across: 10          inner corners across: 9
  +--+--+--+--+--+--+--+--+--+--+
  |##|  |##|  |##|  |##|  |##|  |      x = inner corner
  +--x--x--x--x--x--x--x--x--x--+
  |  |##|  |##|  |##|  |##|  |##|
  +--x--x--x--x--x--x--x--x--x--+
  ...
```

Rule: **inner corners = squares - 1**, in each direction.

The app is set up for:

- **9 x 6 inner corners** (that is 10 x 7 squares);
- squares of **25 mm**.

These values live in `config/config.yaml` under `calibration.checkerboard`
(`inner_corners_cols`, `inner_corners_rows`, `square_size_mm`).

### Choose the board size

The **whole** checkerboard must fit inside the camera picture at your working distance.

- Ready-made 25 mm board: `assets/checkerboard_9x6_25mm.pdf` (A4 landscape).
- Ready-made 10 mm board: `assets/checkerboard_9x6_10mm.pdf`. Use it if the camera is close to the metal.

If you use the 10 mm board, change the square size to 10 in the app (Part C, step 7) and press **"Save Checkerboard Settings"**.

You can also make any board with this command:

```bash
python scripts/generate_checkerboard.py --cols 9 --rows 6 --square-mm 10
```

### Print it correctly

1. Open the PDF.
2. Press Cmd + P.
3. Set the scale to **100%** or **Actual size**.
4. Turn **off** "Fit to page" and "Shrink to fit".
5. Print.
6. Measure 4 squares in a row with a ruler. For 25 mm squares they must measure **100 mm**. For 10 mm squares, **40 mm**.
7. If the number is wrong, print again. Do not continue with a wrong print.
8. Glue the paper completely flat on the stiff board. No bubbles. No curl.

### Set up the camera before calibrating

1. Mount the fixture so it cannot move.
2. Set the camera tilt on the yoke. Lock both lock bolts.
3. Read the angle from the tick marks. Write it down.
4. Focus the lens so the metal at your working distance is sharp. Then do not touch the lens again.
5. In the app, open the **"Parameters"** tab.
6. Type the angle into "Camera tilt setting (deg)".
7. Press **"Save Configuration"**.
8. Press **"Reload Configuration"** in the left sidebar.

The angle is saved inside the calibration. If you later change the tilt and the angle in the config, the app refuses the old calibration. That is on purpose.

---

## Part C. Camera calibration (exact steps)

### Start the app

1. Open VS Code.
2. Click File, then Open Folder, then choose `CAD MODEL/Laser_Triangulation_project`.
3. Open the terminal: View, then Terminal.
4. Turn on the Python environment:

   ```bash
   source .venv/bin/activate
   ```

   You should see `(.venv)` at the start of the line.
   If `.venv` does not exist yet, first run `python3 -m venv .venv`, then repeat this step.

5. Install the packages (only needed once):

   ```bash
   python -m pip install -r requirements.txt
   ```

   You should see "Successfully installed" or "Requirement already satisfied".

6. Start the app:

   ```bash
   streamlit run app.py
   ```

   You should see: a browser tab opens at `http://localhost:8501`.
   The left sidebar shows **UNCALIBRATED MODE (pixel measurements)** in blue.

   If macOS asks for camera permission for Terminal or VS Code, click Allow.
   If you clicked Deny, see Part H, "Camera not detected".

### Find the camera

7. Plug in the camera.
8. In the sidebar, press **"Scan Cameras"**.
9. You should see a list like `Index 0: OK 1280x720` and `Index 1: OK 1280x800`.
10. Index 0 is usually the MacBook's own camera. Try the other one first.
11. Type that number into **"Camera index"**.
12. Check it: open the **"Measure"** tab, choose **"Capture from Camera"**, press **"Capture Frame"**.
13. You should see the picture from the Arducam, not your face.
14. If you see your face, change **"Camera index"** and try again.

### Enter the checkerboard

15. Open the **"Calibration"** tab.
16. Under **"Calibration step"**, choose **"1. Checkerboard"**.
17. Type the corners across into **"Inner corners across (columns)"**. For the supplied board: **9**.
18. Type the corners down into **"Inner corners down (rows)"**. For the supplied board: **6**.
19. Type your **measured** square size into **"Square size (mm)"**.
20. If the app shows a yellow note that the values differ from config.yaml, press **"Save Checkerboard Settings"**.
21. Optional: press **"Generate Checkerboard PDF"**, then **"Download Checkerboard PDF"**, to print a matching board.

### Collect the views

22. Choose **"2. Camera Intrinsics"**.
23. You should see "Accepted views: 0 (minimum 12, target 20)".
24. Hold the board in front of the camera. The whole board must be in the picture.
25. Hold it still. Press **"Capture Calibration View"**.
26. You should see green: "capture_001: corners found", with coloured dots on every corner.
27. If you see red "Checkerboard ... not found", the view is not counted. Fix the cause (whole board visible? sharp? no glare?) and capture again.
28. Move the board to a new place and angle. Capture again.
29. Repeat until you have **at least 12** accepted views. **20 is better.**

Use this list of positions. Tick each one:

- [ ] centre, flat (facing the camera)
- [ ] top-left corner of the picture
- [ ] top-right corner
- [ ] bottom-left corner
- [ ] bottom-right corner
- [ ] left edge, middle
- [ ] right edge, middle
- [ ] top edge, middle
- [ ] bottom edge, middle
- [ ] tilted left about 20-30°
- [ ] tilted right about 20-30°
- [ ] tilted up about 20-30°
- [ ] tilted down about 20-30°
- [ ] closer to the camera (board fills most of the picture)
- [ ] farther away (board smaller, still sharp)

The small grid on the right shows which parts of the picture the board has covered:

```
■ ■ □
■ ■ □      ■ = covered, □ = not yet
■ □ □
```

Fill at least 6 of the 9 boxes. All 9 is best.

You can also use photos you already have:
press **"Upload checkerboard images"**, choose the files, then press **"Add Uploaded Images"**.
All photos must have the same size as the camera's live picture.

If some views were rejected, press **"Remove Rejected Views"** to tidy the list.
To start over, press **"Clear All Views"**.

### Another way: the capture tool (photos in a folder)

Instead of capturing inside the app, you can take all photos first with a small tool.
It shows the camera picture, tells you where to hold the board, and saves only good photos:

```bash
python scripts/capture_photos.py --mode checkerboard --camera 1
```

Press SPACE for each photo and Q to finish. The photos are saved as `photos/1_checkerboard/view_01.png`, `view_02.png` …
Then load them in the app with **"Upload checkerboard images"** and **"Add Uploaded Images"**.
For Part D use `--mode laser` (press O with the laser off, then L with the laser on), and `--mode check` for the flat plate check.

### Calibrate

30. Press **"Run Camera Calibration"**.
31. You should see four numbers: "Reprojection error (px)", "fx (px)", "Coverage (of 9)", "Tilt range (deg)".
32. Good result: a green box "Camera calibration passed".

What the checks mean:

| Check | Must be | If not |
|---|---|---|
| Accepted views | at least 12 | Capture more views |
| Coverage | at least 6 of 9 | Capture views in the empty areas named in the red message |
| Tilt range | at least 15° | Capture more tilted views |
| Reprojection error | at most 1.0 px | Remove views listed as "fit much worse", capture sharper ones |

These limits are in `config/config.yaml` under `calibration.camera_intrinsics`.
If a check fails, the app tells you what to add. Add the views, then press **"Run Camera Calibration"** again.

The number of views needed is not the same for every camera.
12 is the minimum this app accepts. 20 is the target. If the checks fail, add more.

### Save

33. Press **"Save Camera Calibration"**.
34. You should see "Saved .../data/calibration/calibration.json".
35. Choose **"5. Status & Files"**.
36. You should see "Camera intrinsics: valid" and "Laser plane: invalid / missing". That is correct for now.

---

## Part D. Laser-plane calibration (exact steps)

### How the app knows where the board is

You do **not** type any positions or angles.

The app knows the exact size of the printed squares.
From the picture of the squares, it measures where the board is and how it is tilted.
This needs the camera calibration from Part C.

Then the app looks at the red line on the same board.
The red line lies on the board, so the app now knows real 3D points of the laser.
After a few board positions, it fits the flat "sheet" of laser light. That sheet is the **laser plane**.

The only things you measure by hand are the printed square size and that the board is flat.

```
            camera   laser
               \       |
                \      |  laser sheet
                 \     |
     pose 1   ====\=====|====      (near)
     pose 2      ======\|=======   (middle, tilted)
     pose 3   ==========|\=====    (far)
                        ^ red line crosses the squares
```

### Prepare

1. Check that the camera calibration is valid: Part C, step 36.
2. Do not move the camera, lens or laser from now on.
3. Turn down the room light a little. The red line should look **red**, not white.
4. Look at the laser only on the board. Never into the laser. See Part I.

### Each pose (do this at least 3 times, 4 is better)

5. Under **"Calibration step"**, choose **"3. Laser Plane"**.
6. You should see a green box "Camera intrinsics OK".
7. Put the board under the fixture so the red line **crosses the printed squares**.
8. Make sure the board cannot move. Rest it on books or blocks.
9. Switch the laser **off**.
10. Press **"Capture Laser OFF Image"**. You should see the checkerboard picture appear.
11. Switch the laser **on**. Do not touch the board.
12. Press **"Capture Laser ON Image"**. You should see the same picture with the red line.
13. Press **"Add Pose"**.
14. You should see green "pose_1: accepted" and a table row with "board distance (mm)", "laser points", "pose error (px)" and "line RMS (mm)".
15. If you see red, read the message. Common reasons:
    - "Checkerboard not found": the laser line hides corners or the board is cut off. Take the OFF picture again.
    - "Only N laser points found": the red line does not cross the squares, or it is too weak.
    - "not a straight line": the board is bent, or there is a red reflection.
16. Change the board position for the next pose. Use this plan:

| Pose | Where | Tilt |
|---|---|---|
| 1 | at your working distance | flat |
| 2 | about 20 mm closer | tilted about 10° |
| 3 | about 20 mm farther | tilted about 10° the other way |
| 4 | at the working distance | tilted about 15° sideways |

Distances are measured by the app and shown in the table. You only need to make them different.
Keep every pose near the working distance you will measure at.

If you cannot switch the laser off without moving something, tick
**"Use one image for both (corners are still found with the laser on)"**.
Then load only the **"Laser OFF image (checkerboard)"** picture, with the laser on.
This works only if the corners are still found. Two pictures are more accurate.

You can also upload saved pictures with **"Laser OFF image (checkerboard)"** and **"Laser ON image (same position)"**.

To start again, press **"Clear All Poses"**.

### Fit the plane

17. When the progress bar shows at least 3 good poses, press **"Fit Laser Plane"**.
18. You should see "Plane RMS (mm)", "Max residual (mm)", "Pose spread (mm)", "Points", and the plane equation `a*X + b*Y + c*Z + d = 0`.
19. Good result: no red messages.

| Check | Must be | If not |
|---|---|---|
| Good poses | at least 3 | Add poses |
| Pose spread | at least 15 mm | Make poses more different in distance and tilt |
| Plane RMS | at most 0.5 mm | Check board flatness; make sure nothing moved |
| Laser plane away from camera | yes | The camera and laser need a baseline (side-by-side distance) |

These limits are in `config/config.yaml` under `calibration.laser_plane`.

20. Press **"Save Laser Plane Calibration"**.
21. You should see "Saved laser plane to .../calibration.json".

### Check the calibration

22. Choose **"4. Validation"**.
23. Press **"Validate Calibration File"**.
24. You should see a table where every row says passed = true, and a green box "Calibration is VALID for metric measurement".
25. Flat plate check: put the board in a **new** position (not one used above).
26. Under "Flat plate check: Laser OFF image", press **"Capture Laser OFF Image"** with the laser off.
27. Under "Flat plate check: Laser ON image", press **"Capture Laser ON Image"** with the laser on.
28. Press **"Run Flat Plate Check"**.
29. Good result: green "RMS distance to the board ... mm (limit 0.5 mm)".
30. If it is red, repeat Part D. If it is still red, repeat Part C and then Part D.

---

## Part E. Turn on calibrated mode

1. In VS Code, open `config/config.yaml`.
2. Find the lines at the top:

   ```yaml
   calibration:
     enabled: false
   ```

3. Change `false` to `true`:

   ```yaml
   calibration:
     enabled: true
     calibration_file: "data/calibration/calibration.json"
   ```

4. Use spaces, not tabs. Keep the two spaces in front of `enabled`.
5. Save the file: Cmd + S.
6. In the app sidebar, press **"Reload Configuration"**. (Restarting the app also works.)
7. You should see a green **CALIBRATED MODE (mm)** in the sidebar.
8. In the **"Measure"** tab, results now show "Bead width (mm)" and "Bead height (mm)".

If you see red **CALIBRATED MODE - BLOCKED (calibration invalid)**:

- Read the list under it. It says exactly what is wrong.
- The app does **not** switch back to pixels by itself. You decide.
- Fix the problem (usually: calibrate again), or set `enabled: false` to work in pixels.

The setting `require_valid_calibration` controls what happens while blocked:

- `true`: nothing is processed until the calibration is fixed.
- `false`: pixel results are shown, millimetres stay blocked.

A full example is in `config/config.example.calibrated.yaml`.

Even in calibrated mode, mm values are hidden if the measurement confidence is below `measurement.minimum_confidence` (0.5). The app then says "mm result withheld".

---

## Part F. Use uncalibrated mode

Uncalibrated mode needs no calibration at all.

```yaml
calibration:
  enabled: false
  calibration_file: "data/calibration/calibration.json"
  require_valid_calibration: true
  allow_uncalibrated_metric_estimates: false
```

A full example is in `config/config.example.uncalibrated.yaml`.

What still works:

- Upload or capture a picture.
- Find the red line.
- See the mask, the line and the profile.
- Measure the bead in **pixels**: "Apparent width (px)" and "Apparent height (px)".
- Download JSON and CSV.

Pixels are **not** millimetres.
"Apparent height (px)" is how far the red line moved in the picture. It is not the real height.

### Optional: experimental mm estimates

Only if you set `allow_uncalibrated_metric_estimates: true`, the **"Measure"** tab shows **"Experimental reference-scale estimate"**:

- Width: put something of known width on the metal, under the laser line, at the same distance as the bead. Measure its length along the line in pixels. Type both into **"Known width reference (mm)"** and **"Its length along the laser line (px)"**.
- Height: put a part with a known step height (for example a feeler gauge) under the line. Type the step in mm and the stripe shift in pixels into **"Known step height (mm)"** and **"Its stripe displacement (px)"**.

These estimates are **only** valid near the reference, at the same distance, on a flat surface.
One scale is never right for the whole picture, because of perspective.
They are always labelled EXPERIMENTAL.

If the focal length, pixel pitch (or sensor width), baseline and all angles are known and entered in the
**"Parameters"** tab (see `HARDWARE_PARAMETERS.md`), the app also shows a "nominal geometry" estimate.
It is also EXPERIMENTAL and assumes a perfect lens.

---

## Part G. Test the accuracy

Do not trust a number until you have tested it.
This app makes no accuracy promise. Your tests decide the accuracy.

Write every result in this table:

| Test | True value (mm) | Measured (mm) | Error (mm) |
|---|---|---|---|
| Flat plate height | 0 | | |
| Step / gauge height | | | |
| Known strip width | | | |
| Repeat 1 | | | |
| ... | | | |

### Flat plate

1. Put a clean flat metal plate under the laser.
2. Capture and press **"Detect Laser Line"**.
3. Expected: "Bead status: no_bead", or a height close to 0.

### Known step height

1. Measure a gauge, washer or flat bar thickness with a calliper.
2. Put it on the flat plate under the laser line.
3. Capture and press **"Detect Laser Line"**.
4. Compare "Bead height (mm)" with the calliper value.

### Known width

1. Use a flat bar or strip with a measured width (for example 10 mm).
2. Lay it across the laser line.
3. Compare "Bead width (mm)" with the calliper value.

### Repeatability

1. Do not move anything.
2. Capture and measure 10 times.
3. Work out the average and the spread (largest minus smallest).

The edges of a bead can only be located to about half the thickness of the red line.
A thinner, well-focused red line gives better widths.

---

## Part H. Troubleshooting

| Problem | What to do |
|---|---|
| Camera not detected | Press **"Scan Cameras"**. Try other indexes. Use a data cable/adapter (not charge-only). Close FaceTime, Zoom and Photo Booth. Allow camera access: System Settings > Privacy & Security > Camera > turn on Terminal or VS Code, then restart the app. |
| Black image | Remove the lens cap. Add light. Wait 2 seconds and capture again. |
| Laser line not detected | Is the laser on? Open **"Laser detection settings"** and lower **"Threshold"** (try 20). Darken the room. |
| Too much red reflection | Raise **"Threshold"**. Lower **"Max stripe width (px)"**. Tilt the part a little. Avoid shiny spots. |
| Line looks white in the middle | It is saturated. Lower the laser power or room light. |
| Checkerboard corners not found | The whole board must be visible. Check the corner numbers (inner corners, not squares). Sharpen the focus. Avoid glare. |
| Calibration error too high | Remove views marked "fit much worse". Capture sharp, still views. Make sure the paper is flat. |
| Laser-plane fitting error too high | Board bent? Something moved between poses? Recapture all poses with **"Clear All Poses"**. |
| Missing calibration JSON | Do Parts C and D. Check `calibration.calibration_file` in `config/config.yaml`. |
| YAML parsing error | The app shows the line number. Use spaces, not tabs. Every key needs a colon: `enabled: true`. |
| Camera resolution mismatch | Use the same resolution as during calibration (`camera.resolution`). Or calibrate again. |
| Metric measurements disabled | Check that `calibration.enabled` is `true` and the sidebar is green. Read the red list. Low confidence also hides mm. |
| Invalid laser-plane intersections | The point is far outside the calibrated distance range, or the view is almost edge-on to the laser. Measure near the working distance used during calibration. |
| Results change after moving the camera or laser | Expected. Moving anything breaks the calibration. Update `fixture.camera_tilt_setting_deg` and do Parts C and D again. |
| "integrity hash mismatch" | The calibration file was edited by hand. Calibrate again, or restore a `.bak` file from `data/calibration/`. |

Run the automatic tests to check the software itself:

```bash
python -m pytest
```

Expected: all tests pass. These tests use synthetic pictures. They check the software, not your hardware.

Try everything with synthetic data, without hardware:

```bash
python scripts/run_synthetic_demo.py
LASER_TRI_CONFIG=config/config.example.synthetic_calibrated.yaml streamlit run app.py
```

The demo writes practice pictures to `outputs/synthetic_demo/images`. You can upload them in Parts C and D
(with the 12 mm board settings from `config/config.example.synthetic_calibrated.yaml`).

---

## Part I. Safety

- **Never look into the laser.** Not directly, not through a lens, not in a mirror.
- Keep the laser away from eyes. Point it down at the work.
- Shiny metal reflects the laser. Watch where reflections go.
- Check the laser's voltage and current on its datasheet **before** connecting power. The wrong supply can destroy it.
- The camera and the 3D-printed plastic fixture must not get welding heat, sparks or spatter.
- Do all setup and calibration with the welding **stopped**.
- Never run the robot with a loose fixture or hanging cables.
- Before any live welding, check robot clearance, cable routing and heat protection with the person responsible for the robot cell.
