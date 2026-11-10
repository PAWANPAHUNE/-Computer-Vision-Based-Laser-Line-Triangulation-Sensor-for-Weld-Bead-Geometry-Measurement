# Welding seam sensor fixture — v3 (print-ready)

Camera on a lockable tilting yoke, laser fixed beside it, and a V-saddle clamp
that straps to the round neck/body of the robot MIG torch. All four STLs are
exported in their print orientation (flat face on the bed) and were mesh-checked
(watertight, single body) and collision-checked at camera tilts of -15°, 0°,
20° and 45°.

All dimensions are millimetres.

## What changed from v1 / v2

| Requirement from the brief | v3 |
|---|---|
| Camera and laser side by side like v1, but swapped | Camera is now on the tilting yoke, laser sits where the camera was, 55 mm apart, with a clear gap at every tilt angle |
| Good distance so they cannot clash | Closest approach between any camera part and the laser cradle is 10 mm (at 0°) and grows as you tilt |
| Camera very rotatable, settable to an angle for photos | Pivot axis passes through the board plane; -15° to +45° tilt, locked with two M4 bolts in arc slots, angle ticks every 15° engraved on both cheeks |
| Exact camera module size and holes | 38 × 38 board, holes 5 mm from each edge (28 mm pitch), M3 screws into 2.7 mm pilot bosses; board sits 8 mm off the carrier so the rear connector clears |
| Holes for wiring | Open window under the board + cable notch, zip-tie slots on the carrier, 20 × 8 cable slot in the plate under the camera, Ø8 wire hole under the laser, zip-tie slots beside it |
| Laser Ø11 × 35 | 90° V-cradle + bolted clamp bar. Accepts Ø10 to Ø13 without any change, so "approximately 11 mm" is fine |
| Something at the end to fix to the weld arm | V-saddle block + two stainless hose clamps; fits round sections from about Ø16 to Ø65 (swan neck or torch body). Bolted to the plate with 4 × M4 in captive nut traps |
| v2 could not be fixed to the arm | Replaced the flat backplate with the saddle above; the plate end is V-notched so the neck passes through |

## Files

| File | Print orientation (as exported) | Notes |
|---|---|---|
| `base.stl` | flat, plate on the bed | plate + camera cheeks + laser cradle + ribs, one piece, no supports |
| `camera_yoke.stl` | flat, bosses up | no supports |
| `laser_bar.stl` | flat | tiny, no supports |
| `arm_clamp.stl` | on its side (already rotated) | no supports; hose-clamp slots print vertically |
| `welding_sensor_fixture_v3.scad` | — | editable source. Open in OpenSCAD, set `PART`, F6, export |
| `preview_*.png` | — | renders of the assembly and of the print orientation |

Overall size of the base: 154 × 70 × 54 mm. Clamp block: 46 × 46 × 56 mm.

## No screws available? Printed hardware kit

`printed_hardware/` contains a complete kit of printed pins, locking forks, angle-lock plates, a
spring laser clip and ratchet straps that replaces every screw, nut and hose clamp above. It fits
the holes already in the four printed parts. Follow `printed_hardware/BUILD_PLAN.md`.

## Print settings

- Material: PETG preferred (tougher, a bit more heat tolerant). PLA works for a cold fit-check.
- 0.2 mm layers, 4 walls, 5 top/bottom layers, 40 % infill (base, clamp block), 60 % for the yoke and bar.
- No supports needed for any part in the exported orientation. Enable "bridging" defaults.
- Nozzle 0.4 mm. Hole sizes already include clearance; do not scale the parts.
- If your printer over-extrudes and the nuts are tight in their pockets, shave the pocket with a knife or use a horizontal expansion of -0.05 mm in the slicer.

## Hardware (buy list)

| Where | Qty | Item |
|---|---|---|
| Camera board to yoke | 4 | M3 × 8 pan-head screws (self-tap into the 2.7 mm bosses; the board's 3.5–4 mm holes are clearance) |
| Yoke pivot | 2 | M4 × 12 + M4 hex nut + M4 washer under the head |
| Yoke tilt lock | 2 | M4 × 12 + M4 hex nut + M4 washer under the head (the washer bridges the curved slot) |
| Laser clamp bar | 2 | M3 × 25 + M3 hex nut |
| Clamp block to base | 4 | M4 × 16 + M4 hex nut |
| Clamp block to torch | 2 | stainless worm-drive hose clamps, band 13 mm wide max. The band wraps around the clamp block AND the neck, so the clamp must be bigger than the neck: thin swan neck (16–30 mm) → **40–60 mm** clamp; neck 40 mm → 50–70 mm; thick torch body 50–65 mm → **60–80 mm** clamp |
| Cable management | ~6 | 2.5 mm zip ties |

Every M4/M3 nut sits in a printed pocket, so no spanner is needed on the nut side.

## Assembly

1. **Laser.** Drop the laser into the V on the cradle, brass knurled end (emitter) up, wires down through the Ø8 hole in the plate. The rear end rests on the plate. Put the two M3 nuts in the hex pockets on the back (camera side) of the cradle, fit the clamp bar on the front with its shallow V against the laser, and tighten the two M3 × 25 screws evenly. Zip-tie the wires on the underside using the two slots next to the hole.
2. **Camera.** Slide an M4 nut into each of the four hex pockets on the inside faces of the yoke ears (pivot and lock, both sides). Screw the Arducam board onto the four bosses with M3 × 8, lens up, with the rear cable connector facing the notch (toward the +X end of the plate, away from the laser). Route the cable out through the notch and zip-tie it to the two slots beside it.
3. **Yoke into cheeks.** Lower the yoke between the two cheeks on the base. Fit the two pivot bolts (M4 × 12, with a washer) through the round holes, then the two lock bolts through the curved slots. Tilt to the angle you want (ticks at -15, 0, 15, 30, 45°; positive = lens leaning toward the laser) and tighten the lock bolts.
4. **Clamp block.** Slide four M4 nuts into the side slots of the block (two from the back face, two from the sides) and bolt the base to the block from underneath with M4 × 16 through the four plate holes. The block's V must line up with the V-notch in the plate.
5. **On the torch.** Open the two hose clamps fully, thread each band through one slot in the block (the band passes through the block and around the neck), seat the V on the neck (or torch body), rotate the whole fixture around the neck until the sensors look where you want, and tighten the clamps. The plate's +Z face (sensor side) points along the neck toward the torch tip.
6. **Aim.** The laser beam is perpendicular to the plate. With the camera 55 mm beside it, the tilt angle to look at the laser spot at working distance D is atan(55 / D): about 17° at 180 mm, 24° at 120 mm. Set it with the ticks, fine-tune by looking at the image, lock.

## Geometry reference (for anyone editing the SCAD)

- Plate: 154 × 70 × 6, V-notch at the clamp end, 10 mm edge ribs.
- Camera centre x = 55, pivot height 39.5 above the plate bottom, lock radius 22, arc slot -15°…+45°, cheeks 4 mm with 0.6 mm clearance to the ears.
- Laser axis x = 0, V apex computed from `laser_d` so the beam stays on the axis.
- Clamp block V apex at x = -53, 90°, 30 mm wide at the face. Band slots 2.6 × 14 at 18 and 38 mm above the plate.
- Pockets: M4 nut 7.3 AF × 3.6; M3 nut 5.9 AF; pilots for M3 2.7 mm; M4 clearance 4.5; M3 clearance 3.4.

## Things to be aware of

- The parts are plastic. They are fine for setting up, calibration and trials with the torch cold, and for use clamped on the torch body away from the arc. Do not leave them where spatter lands or near the nozzle during real welding; PETG softens at about 80 °C.
- The torch neck diameter was not measurable from the photo. The hose-clamp saddle works for any size; pick the clamp from the table in the hardware list after measuring the neck.
- The laser V sets the beam parallel to the plate normal to within the print tolerance. If you need the laser exactly aligned after assembly, shim the bar side with a strip of tape.
- Re-calibrate camera/laser geometry whenever the tilt lock is moved.

Generated with OpenSCAD 2025.01 (manifold-checked with trimesh). Source and previews are in the zip.
