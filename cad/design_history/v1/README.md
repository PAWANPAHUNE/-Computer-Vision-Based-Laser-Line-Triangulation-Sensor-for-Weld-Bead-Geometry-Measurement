# Welding camera + laser carrier — first CAD fit-check

## Deliverables
- `welding_sensor_fixture.scad` — editable parametric OpenSCAD design.
- `fixture_base_fitcheck.stl` — base plate, camera standoffs, and fixed angle-adjustment cheeks.
- `fixture_laser_yoke_fitcheck.stl` — separate moving laser collar/yoke.
- `welding_sensor_fixture_preview.png` — assembly preview with non-printable camera/lens/laser proxies.

## Critical limitation
The photos show the intended sensor arrangement, but they do not provide the robot/torch mounting-hole pattern, torch dimensions, exact laser barrel diameter, working distance, or collision envelope. Therefore this is **not an exact machine-specific fixture**. Its base has four generic slots intended to attach to a separately measured/approved adapter plate. They are not verified to match the robot or torch.

**Never use an FDM-printed plastic part on a live welding setup.** Heat, arc UV/IR, molten spatter, fumes, mechanical vibration, and collisions can damage/melt plastic and create a hazard. These STLs are only for a cold layout/fit-check. The final fixture close to the torch needs a properly designed metal mount, optical protection, and review by the lab/robot supervisor.

## Current defaults — verify before printing
- Carrier: 130 × 100 × 6 mm.
- Camera board: 38 × 38 mm; outer mounting-hole pitch 34 mm; hole diameter assumed 2.8 mm.
- Laser clamp bore: 12.5 mm after clearance, based on an unverified 12.0 mm barrel assumption.
- Mechanical angle adjustment: nominal displayed angle 25°, with an arc slot from 0° to 45°.
- Camera/lase lateral offset depends on angle and the 15 mm pivot-to-collar radius.
- Four generic 18 × 6.6 mm carrier slots; no machine fit is implied.

These are design defaults, not measurements of the user's actual parts or robot. Measure the straight portion of the laser barrel with calipers, check the Arducam mounting hole pitch/diameter, and identify the correct robot-side adapter.

## How to inspect and export
1. Install OpenSCAD and open `welding_sensor_fixture.scad`.
2. Choose `PART = "assembly"` for the combined preview, `PART = "base"` for the fixed part, or `PART = "yoke"` for the moving laser holder.
3. Press F5 for preview; F6 for full render.
4. Use the commands below to export the separate parts. The dummy board/lens/laser are not included in these part exports.

```bash
openscad -o fixture_base_fitcheck.stl -D 'PART="base"' -D 'show_proxies=false' welding_sensor_fixture.scad
openscad -o fixture_laser_yoke_fitcheck.stl -D 'PART="yoke"' -D 'show_proxies=false' welding_sensor_fixture.scad
```

The laser collar angle can be changed in the source using `laser_angle_deg`; the physical design uses a pivot plus an arc slot and can be adjusted after assembly with bolts. Hardware and the fit should be verified before any robot movement. For a cold model, print the two STLs separately and assemble with suitable M4 pivot/slot bolts plus an M3 collar-clamping bolt; do not overtighten the printed yoke. The laser's actual diameter must be measured first.

## Before any final revision, collect these measurements
1. Camera PCB outside dimensions, thickness, hole pitch in X/Y, hole diameter, and the side where the USB connector/cable exits.
2. Laser straight-barrel diameter where it will be clamped; barrel length; emitting end; cable exit direction; and a clear label photo showing wavelength, rated power and required voltage/current.
3. The exact machine interface: robot wrist/tool-holder or existing bracket model, bolt-hole spacing, thread size, available mounting face, and allowed protrusion. Do not clamp to a gas nozzle, consumable neck, cooling line, or moving robot joint without approval.
4. Lens-to-target working distance, target seam/weld-tip relationship, and which direction the camera should face.
5. Front and side photos of the proposed mount location with a ruler/caliper visible.

## Optical/calibration note
After mechanically setting and locking the camera/laser geometry, calibrate the camera intrinsics and laser plane/triangulation geometry. Moving either sensor after calibration changes the geometry. A red ~650 nm laser generally benefits from a properly specified narrow-band filter and protection in welding conditions; a random tinted cover is not an adequate substitute. Never look into the laser aperture or at specular reflections.
