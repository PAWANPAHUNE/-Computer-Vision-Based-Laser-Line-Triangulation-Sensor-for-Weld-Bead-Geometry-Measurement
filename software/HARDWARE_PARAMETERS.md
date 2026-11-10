# Hardware parameter checklist

Status meanings:

- **Verified**: confirmed from documentation or clearly readable markings.
- **Measured**: measured by hand on the real part (accuracy as stated).
- **Estimated**: a design value or an educated guess. Never use it as a measurement.
- **Unknown**: not known yet. Leave it `null` in `config/config.yaml`.

Calibrated mode does **not** need any of the optical values below. The camera and laser-plane
calibration measure everything they need. The optical values matter only for the optional,
clearly-labelled experimental estimates in uncalibrated mode.

## Camera

| Item | Value | Status | How to get or confirm it |
|---|---|---|---|
| Camera module | Arducam UC-852 Rev.A | Verified (printed on the PCB in the photo) | — |
| Interface | USB cable, 4 wires | Verified (photo) | — |
| PCB outline | 38 × 38 mm | Measured (approx.) | Calliper |
| Mounting-hole spacing | 28 × 28 mm (holes 5 mm from each edge) | Measured (approx.) | Calliper, hole centre to hole centre |
| Mounting-hole diameter | 3.5–4 mm | Measured (approx.) | Calliper |
| Image sensor | OV9782 | Verified (macOS reports the device as "Arducam OV9782 USB Camera", USB vendor 3141 / product 25446) | `system_profiler SPCameraDataType` |
| Resolution | 1280 × 800 requested in config | Estimated | The app reads the real frame size from every image. Check with **Scan Cameras**. |
| Lens focal length | — | Unknown | Lens marking or vendor data. Do NOT derive from the PCB size. |
| Sensor width / height | — | Unknown | OV9782 datasheet (sensor now confirmed) |
| Pixel pitch | — | Unknown | OV9782 datasheet (sensor now confirmed) |
| Focus | adjustable M12 lens assumed | Estimated | Look at the lens. Lock focus before calibrating. |

## Laser

| Item | Value | Status | How to get or confirm it |
|---|---|---|---|
| Body diameter | ≈ 11 mm | Measured (approx.) | Calliper |
| Body length | ≈ 35 mm | Measured (approx.) | Calliper |
| Beam type | line (fan) | Stated by the user | Project it on a wall |
| Colour / wavelength | red, label suggests 650 nm | Estimated (label not fully readable) | Vendor data |
| Laser class / power | label suggests Class IIIA | Estimated | Vendor data. Required for safety. |
| Supply voltage / current | — | Unknown | Vendor data. **Required before powering it.** |
| Fan angle | — | Unknown | Vendor data, or measure line length at a known distance |

## Fixture (welding_sensor_fixture_v3) and geometry

| Item | Value | Status | How to get or confirm it |
|---|---|---|---|
| Camera-to-laser baseline | 55 mm between camera centre and laser axis | Estimated (CAD design value) | Measure the assembled fixture; the optical centre is not exactly the PCB centre. |
| Camera pitch | −15° to +45°, tick marks every 15° | Estimated (design) | Read the ticks after locking the yoke. Write it in `fixture.camera_tilt_setting_deg`. |
| Camera yaw / roll | 0° | Estimated (design) | Not measured |
| Laser plane angle | 0° (laser perpendicular to the plate) | Estimated (design) | Not measured |
| Working distance | — | Unknown | Measure after mounting: fixture plate to workpiece along the laser beam |

## What changes the calibration

Recalibrate both the camera and the laser plane after any of these:

- refocusing or touching the lens;
- changing the camera resolution;
- loosening or moving the camera tilt, the laser, or the fixture;
- reprinting the checkerboard at another size.

When you move the camera tilt, also change `fixture.camera_tilt_setting_deg`. The app then refuses
the old calibration automatically.
