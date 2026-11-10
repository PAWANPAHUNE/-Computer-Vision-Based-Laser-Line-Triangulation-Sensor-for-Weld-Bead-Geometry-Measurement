# Adjustable camera + vertical laser welding-sensor fixture — v2

**Status: parametric prototype / cold fit-check only. Not validated for installation during live welding.**

This package revises the earlier concept around the requirements in the supplied photos:

- The small Arducam PCB is mounted in an open square carrier. Its rear cable connector/pigtail has clearance, and a small bridge is provided as a tie point for strain relief.
- The camera carrier rotates in pitch on two side pivots. Two bolts follow curved adjustment slots, so the angle can be set and locked. The model currently has one adjustable axis (up/down pitch); it does not have yaw/pan adjustment.
- The laser barrel is held vertically with its emitting aperture down and cable leads at the top. Its collar itself is fixed to the laser bracket; it is not an angle-adjustable laser mount.
- A rear battery saddle is attached to the backplate with two M4 fasteners. Two strap slots and shallow rails retain a battery pack; terminals are oriented upward in the visual proxy.
- The main backplate has elongated strap slots for a pair of metal bands and optional M6-ish slots for a compatible mounting interface.

The assembly view includes *visual-only proxies* for the camera PCB/lens/cable plug, laser, and a common 9 V battery. The saved front preview uses a 35° pitch override solely to make the adjustment geometry easier to see; the editable model default is 70°. These proxy shapes are illustrative and are not additional printed parts.

## Package contents

| File | Purpose |
|---|---|
| `welding_sensor_fixture_v2.scad` | Parametric source; edit measured parameters at the top, then press F5/F6 in OpenSCAD |
| `base.stl` | Backplate, fixed camera shelf, and gussets as one printed part |
| `camera_yoke.stl` | Fixed pitch-adjustment side cheeks and shelf interface |
| `camera_carrier.stl` | Open frame that carries the camera PCB and provides the two-axis pivot/locking bosses |
| `laser_bracket.stl` | Fixed vertical laser holder, mounting flange, integrated split collar, and wire strain-relief feature |
| `battery_saddle.stl` | Rear-mounted strap saddle for a battery pack |
| `laser_collar_test_gauge.stl` | Optional separate collar gauge for testing the assumed laser diameter. Do not print this as another installed collar if using `laser_bracket.stl`; that part already includes the collar |
| `assembly_preview_front.png` | Sensor-side concept view; a 35° camera-pitch override is used for this illustrative render |
| `assembly_preview_back.png` | Rear/backplate view showing the battery saddle; default CAD camera pitch is used |
| `assembly_preview_default_angle.png` | Additional assembly view using the default 70° camera pitch |

All CAD dimensions are millimetres.

## Important provisional dimensions to measure before printing

The photographs do not provide reliable dimensional references. The values below are adjustable starting values, not confirmed dimensions of the exact hardware.

- Camera PCB outer size: 38 × 38 mm provisionally.
- Camera mounting-hole pitch: 31 mm provisionally; measure centre-to-centre in X and Z.
- Camera mounting slots: 2.8 mm nominal; verify whether your board needs M2, M2.5 or different fasteners.
- Laser smooth barrel diameter: 12.0 mm provisionally; collar bore uses 0.5 mm diametral clearance. Measure the actual smooth barrel with calipers.
- Battery saddle: intended as a prototype for a common rectangular 9 V battery, about 48.5 × 26.5 × 17.5 mm. Measure your actual battery/pack and adjust the parameters.
- Main backplate mounting: two 82 × 10.5 mm slots are intended for metal bands no wider than 10 mm. Use only around an appropriate rigid, cool mounting member, not around hoses, cables, a torch neck that needs to move, or an unverified robot part.
- Actual robot-arm / torch attachment interface: **not measured and not modeled as a machine-specific bolt pattern**. Verify with the welding-machine owner/technician before any attachment.

To change dimensions, edit the variables near the top of the SCAD file, especially `camera_board_w`, `camera_hole_pitch`, `camera_hole_d`, `laser_barrel_d`, `battery_proxy_w`, `battery_proxy_t`, `battery_proxy_h`, `battery_mount_x`, and the backplate slot parameters. Re-export the relevant parts after edits.

## Mechanical assembly suggestion for a cold fit-check

1. Print `base.stl`, `camera_yoke.stl`, `camera_carrier.stl`, `laser_bracket.stl`, and `battery_saddle.stl` only after measuring the parts and editing the SCAD parameters. Print `laser_collar_test_gauge.stl` first if you want a low-cost bore-fit test.
2. Attach the camera yoke to the base shelf using four M4 bolts, washers and locking nuts (nominal clearance holes are 4.5 mm). Confirm the holes align and that the yoke sits flat.
3. Place the camera carrier between the yoke cheeks. Use two M4 fasteners as side pivots. Use two additional M4 fasteners through the curved slots to lock the selected pitch. Tighten only enough to hold position without crushing printed features.
4. Fit the laser into the integrated split collar. Use the M3 pinch bolt to gently retain it after verifying the barrel diameter. The output/aperture points down; the wire end stays up.
5. Attach the battery saddle to the rear of the base using two M4 bolts and secure the battery with two narrow straps or hook-and-loop straps. Keep terminals from contacting the metal backplate or fasteners.
6. Route camera and laser wires away from the moving torch, hinge slots, sharp edges and hot surfaces. Add independent cable strain relief; do not let a cable carry the load of the connector.
7. Check full robot movement **with welding power off**, using the robot's approved jog procedure and a supervisor/technician. Check for collisions and cable snagging before any powered operation.

Fastener lengths depend on actual washers, nut style, print tolerances and whether inserts are used; choose them after a dry assembly. The printed threaded/pinch features should not be relied on as structural fasteners. Use metal bolts and nuts.

## Printing recommendations for a cold fit-check

- Material: PLA or PETG only for room-temperature fit-checks, away from welding. They are not approved here for a live welding environment.
- Suggested starting settings: 0.2 mm layers, 4–6 walls, 40–60% infill, and supports only where your slicer needs them. These are prototype settings, not a structural qualification.
- Orient `base.stl` with its broad flat backplate face on the bed. Orient `camera_carrier.stl` with the broad frame face on the bed. For the yoke and laser bracket, inspect the curved slots, collar split and cable clip in slicer preview and add supports if required. Print the battery saddle with its broad plate face on the bed.
- Print and test the `laser_collar_test_gauge.stl` before printing the full bracket if the laser barrel diameter is uncertain. Its bore is intentionally provisional.
- Check all holes, slot movement, clearance to the real PCB lens/connector, and battery retention before mounting it on the machine.

## Safety and scope boundary

A 3D-printed plastic fixture close to welding can soften, ignite, crack or release the sensor during motion due to heat, arc radiation, spatter, vibration or collision. This package is **not a live-welding-ready or safety-certified fixture**. Use it only for a cold, stationary fit-check. A real welding trial needs a reviewed metal mount or a protected, sufficiently cool mounting location, clearance/collision checks, cable management, and approval from the responsible welding/robotics engineer.

The laser label in the supplied photo appears to indicate a red 650 nm Class IIIA module, but its exact model, output power, and supply rating could not be confirmed from the picture. Do not connect it to a 9 V battery merely because one is available. Confirm the module's rated voltage/current first; an incorrect supply can destroy the laser or create a safety hazard. Do not look into the aperture or at specular reflections.

## How to view and export

1. Install OpenSCAD from https://openscad.org/.
2. Open `welding_sensor_fixture_v2.scad`.
3. Leave `PART = "assembly"` to inspect the assembly. Press F5 for a preview and use the mouse to rotate, pan and zoom.
4. To change parts for export, set `PART` to one of `base`, `camera_yoke`, `camera_carrier`, `laser_bracket`, or `battery_saddle`, then press F6 and use **File → Export → Export as STL**. The standalone `laser_collar` mode is only for the optional test gauge.

This version was exported to STL with OpenSCAD and mesh-checked. That does not validate fit to the physical board, battery, laser or welding robot; physical measurements and a cold fit-check are still required.
