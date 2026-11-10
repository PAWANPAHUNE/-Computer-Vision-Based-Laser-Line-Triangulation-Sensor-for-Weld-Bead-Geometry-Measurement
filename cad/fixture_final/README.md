# Welding seam sensor fixture v3 (camera + line laser) with fully printed hardware

A 3D-printed mount that carries an Arducam UC-852 USB camera and an 11 mm line laser side by side on a
robot MIG torch, for laser-triangulation measurement of the weld bead. Every fastener is printed, so no
screws, nuts or hose clamps are needed.

**Start here:** `ASSEMBLY_GUIDE.pdf` (what to print, test print, step-by-step assembly, checks, safety).

## Contents

| Folder / file | What it is |
|---|---|
| `1_fixture_parts_ALREADY_PRINTED/` | The 3 fixture parts: base plate, camera holder (yoke), torch clamp block |
| `2_print_pins_clips_straps/` | Printed fasteners: camera pins, tilt pins, block pins and locking forks, laser clip (3 sizes), torch straps |
| `3_print_angle_plates/` | Camera angle-lock plates, 0-45 degrees in 5 degree steps, RIGHT and LEFT |
| `4_pictures/` | Renderings of the assembly and of the parts on the print bed |
| `5_source_CAD/` | Parametric OpenSCAD sources and the fixture design notes |
| `6_optional_metal_screws/` | Alternative: shop screws (list) + the laser bar used with screws |
| `7_assembly_with_shop_screws/` | Shopping list picture + step-by-step pictures for the shop-screw assembly, with fit check |
| `ASSEMBLY_GUIDE.pdf` / `.md` | Print and assembly instructions |
| `VERIFICATION_REPORT.txt` | Automated geometric fit checks of every part |

## Design summary

- **Layout.** The camera and laser sit side by side on one base plate, 55 mm apart (the triangulation
  baseline). The laser points perpendicular to the plate.
- **Camera tilt.** The camera tilts toward the laser on a yoke whose pivot axis lies in the board plane.
  Printed angle plates lock the tilt at a fixed angle between 0 and 45 degrees: each plate keys into
  the cheek's arc slot and pins both the pivot and the lock hole, so the angle cannot drift with
  vibration. A new angle needs a new pair of plates and a new calibration.
- **Camera board.** The 38 x 38 mm board, with holes 5 mm from each edge (28 mm pitch), is held by
  four press-fit pins in pilot holes in the printed posts.
- **Laser.** The laser (about 11 mm diameter) sits in a 90 degree V-cradle. A snap-on U-clip presses
  it in place with a spring beam preloaded by 0.6 mm (about 40 N in PETG). Three clip sizes cover
  laser diameters from 10.6 to 11.4 mm.
- **Torch mount.** The clamp block has a 90 degree V-saddle for a round torch neck. Two printed ratchet
  straps go through its slots, so any neck from 16 to 65 mm fits. The block is joined to the base
  plate by four pins, each locked by a fork that slides into the block's side slots.

## Verification

Each printed part was modelled in its installed position against the actual fixture geometry and
checked by boolean intersection. The camera tilt was checked at all ten plate angles.

The checks confirm:

- the pins clear their holes;
- the angle plates key into the slot;
- the forks lock the pins;
- the laser clip preload and spring travel are as designed;
- the strap passes through the clamp slots and its pawl engages the teeth;
- each printed angle plate is the correct hand for its side.

Overall result: **ALL CHECKS PASS**. Details are in `VERIFICATION_REPORT.txt`.

## Limitations

- **Not yet test-printed.** The kit has been verified in CAD only. A test print of the small parts on
  the target printer is the first step in the guide, because hole sizes vary between printers.
- **Printed fasteners are weaker than metal.** The fixture is intended for setup, calibration and
  trials. Keep it away from arc heat, spatter and the hot nozzle. A metal version, or the metal-screw
  option in `6_optional_metal_screws/`, is recommended for production welding.
- **Changing the camera angle** needs new angle plates, and the camera-laser calibration must be
  repeated after any change.
