# Build plan: assemble fixture v3 with ONLY 3D-printed parts

No metal screws, nuts or hose clamps are needed. Every part below fits the holes and slots
that are already in your 4 printed v3 parts. You do not reprint them.

You already have:

| v3 part | Used? |
|---|---|
| `base.stl` (plate + camera cheeks + laser holder) | Yes |
| `camera_yoke.stl` (the tilting camera holder) | Yes |
| `arm_clamp.stl` (the block that sits on the torch) | Yes |
| `laser_bar.stl` (the small bar) | **No.** The new laser clip replaces it. Keep it as a spare. |

Total extra plastic: about 40 g. Look at `preview_assembled_front.png` and
`preview_kit_print_layout.png` to see what the parts look like.

---

## Step 1. Print a TEST set first (about 30 minutes)

Small parts are sensitive to your printer. Test them before printing everything.

Print one of each:

- `stl/yoke_pin.stl`
- `stl/camera_pin.stl`
- `stl/block_pin.stl` and `stl/block_fork_side.stl`
- `stl/laser_clip_size2.stl`

Then try them:

1. Push the **yoke pin** through a round hole in a camera cheek. It should slide in with light force.
2. Push the **camera pin** into one of the 4 small posts on the camera holder. It should need a firm push.
3. Push the **block pin** up through a plate hole into the clamp block. Slide the **fork** into the side slot. It should click over the pin.
4. Put the laser in its V-holder. Push the **laser clip** on from the front. It should click and hold the laser tight.

| If | Do this |
|---|---|
| A pin will not go in | Your printer makes holes small. Lightly sand the pin, or set "XY hole compensation" / "horizontal expansion" to -0.1 mm and reprint. |
| A pin is loose | Add one drop of superglue when you assemble it. |
| The laser clip is loose | Print `laser_clip_size3.stl` (for a thicker laser). |
| The laser clip will not go on | Print `laser_clip_size1.stl` (for a thinner laser). |
| A pin or fork snaps | Use PETG instead of PLA, and 100% infill. |

---

## Step 2. Print everything

Print settings for all parts:

- Material: **PETG** (best). PLA also works, but it is more brittle, so print the spares.
- Layer height 0.2 mm. Use 0.12–0.16 mm for the pins if your printer allows.
- **100% infill**, 4 walls.
- **No supports.** Every STL is already lying in the correct print orientation. Do not rotate them.
- Print small pins several at a time, so each layer has time to cool.

| File | How many | What it does |
|---|---|---|
| `stl/camera_pin.stl` | 6 (4 + 2 spare) | Holds the camera board |
| `stl/yoke_pin.stl` | 6 (4 + 2 spare) | Camera tilt pivots (2) and locks (2) |
| `stl/angle_plates/angle_plate_XXdeg_RIGHT.stl` | 1 | Locks the camera angle, right side |
| `stl/angle_plates/angle_plate_XXdeg_LEFT.stl` | 1 | Locks the camera angle, left side |
| `stl/block_pin.stl` | 5 (4 + 1 spare) | Joins the clamp block to the base plate |
| `stl/block_fork_rear.stl` | 3 (2 + 1 spare) | Locks the 2 rear block pins |
| `stl/block_fork_side.stl` | 3 (2 + 1 spare) | Locks the 2 front block pins |
| `stl/laser_clip_size2.stl` | 1 (size from Step 1) | Holds the laser |
| `stl/strap_short.stl` | 2 | Straps the fixture to the torch (neck 16–35 mm thick) |
| `stl/strap_long.stl` | 2, only if needed | For a thick torch part, 35–65 mm. Needs a 220 × 220 mm bed; print it diagonally. |

### Which angle plate (XX)?

The angle plates set how far the camera leans toward the laser. Choose from the working distance
(fixture plate to the metal):

| Working distance | Plate |
|---|---|
| 250 mm or more | `10deg` |
| about 200 mm | `15deg` |
| about 150 mm | `20deg` |
| about 120 mm | `25deg` |
| about 100 mm | `30deg` |
| about 80 mm | `35deg` |

(Rule: angle ≈ atan(55 / working distance).)
Not sure? Print 15, 20 and 25. Each pair is small. Try them and keep the one where the red line sits in the middle of the camera picture.

Plates exist for 0, 5, 10 … 45 degrees. The number is engraved on each plate.

---

## Step 3. Assemble (in this order)

```
   camera end                                    torch end
   +-----------------------------------------------------+
   | [cheeks + camera yoke]   [laser holder]  [clamp block]|  <- base plate
   +-----------------------------------------------------+
```

### 3a. Clamp block onto the base plate

1. Put the clamp block on the plate, at the end with the V-notch. Line up the V of the block with the V-notch in the plate.
2. Turn the base over. Four holes in the plate line up with four holes in the block.
3. Push a **block pin** into each hole from the underside, flat head against the plate, all the way in.
4. Look at the block: each pin passes through a small rectangular slot (2 on the side faces, 2 on the back face).
5. Slide a **side fork** into each slot on the side faces, open end first, until it clicks over the pin.
6. Slide a **rear fork** into each slot on the back face, until it clicks.
7. Check: the block must not move when you pull on it.

### 3b. Laser

1. Check the laser's voltage and current **before** connecting any power (see Safety).
2. Lay the laser in the V of the laser holder. The brass (light) end points **away** from the plate, toward the metal. The wires go down through the round hole in the plate.
3. Push the **laser clip** onto the holder from the front (the side where the laser is visible). The V of the clip goes against the laser.
4. Push until both hooks click behind the holder.
5. Check: the laser must not turn or slide when you twist it gently.

### 3c. Camera onto the camera yoke

1. Put the camera board on the 4 posts of the yoke, lens up. The cable connector points toward the open notch in the yoke.
2. Push a **camera pin** through each corner hole of the board into the post below. Press firmly with your thumb. Do not press on the lens.
3. Optional: one drop of superglue in each post before pressing, if a pin feels loose.
4. Run the camera cable out through the notch.

### 3d. Camera yoke into the cheeks, and lock the angle

1. Lower the yoke (with the camera) between the two cheeks. Its holes line up with the round hole and the curved slot in each cheek.
2. Take the two **angle plates** with the same number.
3. Put one plate on the outside of a cheek. The raised curved key on the plate must drop into the curved slot. Both plate holes must line up with the cheek holes.
4. If the key does not fit, use the other plate on this side (RIGHT and LEFT are mirror images).
5. Tilt the camera until the plate's second hole lines up with the yoke hole showing in the curved slot.
6. Push a **yoke pin** through the plate's round-hole end (the pivot), through the cheek, into the yoke, until it clicks.
7. Push a second **yoke pin** through the plate's other hole (the lock) until it clicks.
8. Do the same on the other cheek.
9. Check: the camera must not tilt at all now.

To change the angle later: pull the pins out with pliers while squeezing their split tips from inside, or cut them and use spares. Then fit other plates. **Recalibrate the camera-laser measurement after any angle change.**

### 3e. Fix the fixture to the torch

Do this with the robot OFF and the welding OFF.

1. Push the tail of a **strap** through one of the two narrow slots in the clamp block, from one side to the other.
2. Put the V of the clamp block against the round neck of the torch.
3. Wrap the strap around the neck, with the **toothed side facing out**, away from the neck.
4. Push the tail into the strap's head from the flat underside (the side that was on the print bed), so the teeth face the small tongue inside. It clicks as you pull.
5. Pull tight by hand.
6. Do the same with the second strap in the other slot.
7. Turn the whole fixture around the neck until the camera and laser look at the weld area. Then tighten both straps fully.
8. Leave about 20 mm of tail; cut off the rest.

To remove a strap, cut it and print a new one.

### 3f. Cables

1. Tape the laser wires and the camera cable along the torch, away from the nozzle and any moving joint. Electrical tape works.
2. Leave a small loop of slack at the fixture so nothing pulls on the camera connector.

---

## Step 4. Final checks

- [ ] Shake the fixture by hand: nothing rattles or moves.
- [ ] The camera does not tilt.
- [ ] The laser does not turn.
- [ ] The fixture does not turn on the torch neck.
- [ ] Jog the robot slowly (welding OFF): no cable snags, nothing hits the part or the table.

---

## Safety

- Never look into the laser. Check its voltage/current rating before connecting power.
- Printed plastic softens with heat (PLA at about 55 °C, PETG at about 75 °C). Keep the fixture away from the arc, spatter and the hot nozzle. For trials near real welding, ask your lab supervisor about a metal mount.
- Printed straps and pins are weaker than metal. Check them before every session. Replace any that are cracked or white-stressed.
- Do setup and calibration with welding stopped.

---

## Files

| File | Purpose |
|---|---|
| `printed_hardware_v3.scad` | Source. Change `ANGLE` or `SIZE` for other angle plates or clip sizes. |
| `stl/` | All printable parts, already in print orientation. |
| `preview_*.png` | Pictures of the kit and of the assembled fixture. |

How these parts were checked: each one was modelled against the real v3 geometry and tested for
collisions at camera tilts of 0°, 20° and 45°. Pins sit in their holes, plate keys sit in the slot,
forks lock the pins, and the laser clip presses the laser with about 0.6 mm of spring preload.
Real fit still depends on your printer, which is why Step 1 is a test print.
