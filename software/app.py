"""Streamlit app: laser-triangulation weld bead measurement.

Run:  streamlit run app.py
The operating mode comes ONLY from config/config.yaml (calibration.enabled).
"""
from __future__ import annotations

import copy
import time
from datetime import datetime

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import ui_labels as L
from calibration.calibration_file import (camera_section, laser_section, load_calibration_json, new_calibration,
                                          save_calibration)
from calibration.camera_calibration import calibrate_intrinsics, detect_view
from calibration.checkerboard import CheckerboardSpec, draw_corners
from calibration.checkerboard_print import checkerboard_pdf, checkerboard_svg, layout
from calibration.laser_plane_calibration import fit_laser_plane, process_laser_pose
from calibration.validation import MODE_UNCALIBRATED, flat_plate_check, resolve_mode, validate_calibration_file
from utils.config_loader import (PARAMETER_SOURCES, PHYSICAL_PARAMETERS, ConfigError, get_path, load_config,
                                 resolve_project_path, save_config, set_path)
from utils.export import result_to_csv, result_to_json, save_result_files
from utils.image_io import bgr_to_rgb, decode_image, draw_stripe_overlay, mask_to_bgr, save_image
from vision.camera import CameraError, grab_frame, open_camera, read_frame, scan_cameras
from vision.laser_detection import LaserDetectionParams
from vision.pipeline import ReferenceScale, run_measurement

st.set_page_config(page_title=L.APP_TITLE, layout="wide")
SS = st.session_state


# ----------------------------------------------------------------- state
def init_state() -> None:
    defaults = {"image": None, "image_name": None, "detect_requested": False, "views": [], "poses": [],
                "intrinsics": None, "laser_result": None, "off_img": None, "on_img": None,
                "flat_off": None, "flat_on": None, "pdf": None, "svg": None, "camera_scan": None}
    for k, v in defaults.items():
        SS.setdefault(k, v)


def load_everything():
    report = load_config()
    mode = resolve_mode(report.config) if report.ok else None
    return report, mode


def camera_kwargs(cfg) -> dict:
    cam = cfg["camera"]
    return {"backend": cam["backend"], "width": cam["resolution"]["width"], "height": cam["resolution"]["height"]}


def capture(cfg) -> np.ndarray | None:
    try:
        frame = grab_frame(int(SS.get("camera_index", cfg["camera"]["device_index"])),
                           warmup=cfg["camera"]["warmup_frames"], **camera_kwargs(cfg))
        want = (cfg["camera"]["resolution"]["width"], cfg["camera"]["resolution"]["height"])
        got = (frame.shape[1], frame.shape[0])
        if got != want:
            st.error(f"This picture is {got[0]}x{got[1]}, but the measuring camera gives {want[0]}x{want[1]}. "
                     "This is probably the MacBook's own camera: the Arducam is not connected (re-plug its USB "
                     "cable, then check with Scan Cameras) or it has another camera index.")
            return None
        return frame
    except CameraError as exc:
        st.error(str(exc))
    except Exception as exc:  # noqa: BLE001 - never crash the UI on a driver problem
        st.error(f"Camera error: {exc}")
    return None


def show(img_bgr: np.ndarray, caption: str) -> None:
    st.image(bgr_to_rgb(img_bgr), caption=caption, width="stretch")


# ----------------------------------------------------------------- sidebar
def sidebar(report, mode) -> None:
    st.sidebar.title(L.APP_TITLE)
    if st.sidebar.button(L.RELOAD_CONFIG):
        st.rerun()
    if not report.ok:
        st.sidebar.error("CONFIGURATION INVALID - nothing can run until config/config.yaml is fixed.")
        for e in report.errors:
            st.sidebar.write("- " + e)
        return
    if mode.mode == MODE_UNCALIBRATED:
        st.sidebar.info(f"**{mode.label}**")
    elif mode.metric_allowed:
        st.sidebar.success(f"**{mode.label}**")
    else:
        st.sidebar.error(f"**{mode.label}**")
    for w in report.warnings:
        st.sidebar.warning(w)
    st.sidebar.caption(f"Config: {report.path}")
    st.sidebar.divider()
    cfg = report.config
    SS.setdefault("camera_index", int(cfg["camera"]["device_index"]))
    st.sidebar.number_input(L.CAMERA_INDEX, min_value=0, max_value=16, step=1, key="camera_index",
                            help="Index 0 is often the MacBook's own camera. Use Scan Cameras.")
    if st.sidebar.button(L.SCAN_CAMERAS):
        with st.sidebar:
            with st.spinner("Scanning camera indices 0-4..."):
                SS.camera_scan = scan_cameras(5, cfg["camera"]["backend"])
    if SS.camera_scan:
        for c in SS.camera_scan:
            st.sidebar.write(f"Index {c.index}: " + (f"OK {c.width}x{c.height}" if c.opened else c.message))
        st.sidebar.caption("An index that opens is not proof it is the Arducam: check the picture.")
        if not any(c.opened for c in SS.camera_scan):
            st.sidebar.warning("No camera opened. Check the USB data cable/adapter, close other camera apps, and "
                               "allow camera access for Terminal or VS Code in System Settings > Privacy & Security "
                               "> Camera (then restart the app).")


def mode_banner(mode) -> None:
    if mode.mode == MODE_UNCALIBRATED:
        st.info(f"**{mode.label}** - results are image-space pixels, NOT millimetres.")
    elif mode.metric_allowed:
        st.success(f"**{mode.label}** - calibration passed all checks.")
    else:
        st.error(f"**{mode.label}**")
        for m in mode.messages[1:]:
            st.write("- " + m)


# ----------------------------------------------------------------- measure tab
def profile_chart(result) -> alt.Chart | None:
    pix = result.pixel
    use_mm = bool(result.metric and result.metric.get("validated"))
    if use_mm:
        x, y = result.metric_s, np.asarray(result.metric_height_curve, dtype=float)
        m = result.metric
        units, xlab = "mm", "position along the laser line (mm)"
        lb, rb = m.get("left_boundary_x"), m.get("right_boundary_x")
    else:
        x, y = result.profile.x, np.array(pix.height_curve or [], dtype=float)
        units, xlab = "px", "position along the laser line (px)"
        lb, rb = pix.left_boundary_x, pix.right_boundary_x
    if y.size == 0:
        return None
    df = pd.DataFrame({"x": x, "height": y}).dropna()
    if df.empty:
        return None
    line = alt.Chart(df).mark_line(color="#d62728").encode(
        x=alt.X("x:Q", title=xlab), y=alt.Y("height:Q", title=f"height above reference ({units})"))
    layers = [line, alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="gray", strokeDash=[4, 4]).encode(y="y:Q")]
    if lb is not None and rb is not None:
        layers.append(alt.Chart(pd.DataFrame({"x": [lb, rb]})).mark_rule(color="#e6a700").encode(x="x:Q"))
    return alt.layer(*layers).properties(height=280)


def measure_tab(report, mode) -> None:
    cfg = report.config
    mode_banner(mode)
    if not mode.processing_allowed:
        st.error("Processing is blocked because calibrated mode is enabled and the calibration is invalid "
                 "(require_valid_calibration: true). Fix the calibration, or set calibration.enabled: false.")
        return

    source = st.radio(L.IMAGE_SOURCE, [L.SRC_UPLOAD, L.SRC_CAPTURE, L.SRC_BROWSER, L.SRC_SYNTHETIC], horizontal=True)
    if source == L.SRC_UPLOAD:
        up = st.file_uploader(L.UPLOAD_IMAGE, type=["jpg", "jpeg", "png", "bmp"], key="measure_upload")
        if up is not None and SS.image_name != up.name + str(up.size):
            try:
                SS.image, SS.image_name, SS.detect_requested = decode_image(up.getvalue()), up.name + str(up.size), False
            except ValueError as exc:
                st.error(str(exc))
    elif source == L.SRC_CAPTURE:
        c1, c2 = st.columns(2)
        if c1.button(L.CAPTURE_FRAME):
            frame = capture(cfg)
            if frame is not None:
                SS.image, SS.image_name, SS.detect_requested = frame, f"camera_{datetime.now():%H%M%S}", False
        if c2.button(L.START_PREVIEW):
            live_preview(cfg)
    elif source == L.SRC_BROWSER:
        st.caption("Uses the browser's camera picker. Prefer Capture from Camera for full-resolution frames.")
        snap = st.camera_input(L.TAKE_PHOTO)
        if snap is not None and SS.image_name != "browser" + str(snap.size):
            SS.image, SS.image_name, SS.detect_requested = decode_image(snap.getvalue()), "browser" + str(snap.size), False
    else:
        st.caption("SYNTHETIC image with a known 8 mm x 2 mm bead. It tests the software, not your hardware.")
        from synthetic.demo import SYNTHETIC_FIXTURE_ID, demo_rig
        from synthetic.scene import BeadSpec, SyntheticRig, render_weld_image
        rig = SyntheticRig()
        allowed = True
        if mode.mode != MODE_UNCALIBRATED:
            hw = ((mode.report.data or {}).get("hardware") or {}) if mode.report else {}
            allowed = hw.get("fixture_id") == SYNTHETIC_FIXTURE_ID
            rig = demo_rig()
            if not allowed:
                st.error("Synthetic images do not match a real calibration, so mm results would be meaningless. "
                         "Use config/config.example.synthetic_calibrated.yaml to try calibrated mode on synthetic data.")
        if allowed and st.button(L.GENERATE_DEMO):
            img, _ = render_weld_image(rig, BeadSpec(8.0, 2.0, 5.0, 160.0), seed=int(time.time()) % 1000)
            SS.image, SS.image_name, SS.detect_requested = img, "synthetic_demo", False

    lc = cfg["laser"]
    with st.expander(L.DETECTION_SETTINGS, expanded=False):
        c1, c2, c3 = st.columns(3)
        methods = ["red_channel_difference", "hsv_red", "red_channel_tophat"]
        method = c1.selectbox(L.DETECTION_METHOD, methods, index=methods.index(lc["detection_method"]))
        threshold = c1.slider(L.THRESHOLD, 1, 255, int(lc["threshold"]),
                              help="Lower finds a weaker line but also more noise.")
        min_area = c2.number_input(L.MIN_AREA, 1, 100000, int(lc["minimum_component_area"]))
        smoothing = c2.slider(L.SMOOTHING, 1, 31, int(lc["smoothing_window"]), step=2)
        max_w = c3.number_input(L.MAX_WIDTH, 1, 500, int(lc["max_stripe_width_px"]))
        axes = ["auto", "image_columns", "image_rows"]
        axis = c3.selectbox(L.PROFILE_AXIS, axes, index=axes.index(cfg["measurement"]["profile_axis"]),
                            help="image_columns: the red line runs left-right. image_rows: it runs top-bottom.")
        dirs = ["auto", "positive", "negative"]
        direction = c3.selectbox(L.BEAD_DIRECTION, dirs, index=dirs.index(cfg["measurement"]["bead_direction"]),
                                 help="Pixel mode only: which way the bead pushes the stripe.")
        st.caption("These settings apply to this session. Store permanent values in config.yaml.")
    params = LaserDetectionParams.from_config({**lc, "detection_method": method, "threshold": threshold,
                                               "minimum_component_area": int(min_area),
                                               "smoothing_window": int(smoothing), "max_stripe_width_px": max_w})

    reference = None
    if mode.mode == MODE_UNCALIBRATED and mode.experimental_allowed:
        with st.expander(L.EXPERIMENTAL_REF, expanded=False):
            st.warning("EXPERIMENTAL. Valid only near the reference, at the same distance, on a flat surface. "
                       "Not a calibrated measurement.")
            c1, c2 = st.columns(2)
            wmm = c1.number_input(L.REF_WIDTH_MM, min_value=0.0, value=0.0)
            wpx = c1.number_input(L.REF_WIDTH_PX, min_value=0.0, value=0.0)
            hmm = c2.number_input(L.REF_STEP_MM, min_value=0.0, value=0.0)
            hpx = c2.number_input(L.REF_STEP_PX, min_value=0.0, value=0.0)
            if (wmm > 0 and wpx > 0) or (hmm > 0 and hpx > 0):
                reference = ReferenceScale(wmm / wpx if wmm > 0 and wpx > 0 else None,
                                           hmm / hpx if hmm > 0 and hpx > 0 else None,
                                           f"width {wmm} mm = {wpx} px; step {hmm} mm = {hpx} px")

    if SS.image is None:
        st.info("Load an image first (choose an Image source above).")
        return
    if st.button(L.DETECT, type="primary"):
        SS.detect_requested = True
    if not SS.detect_requested:
        show(SS.image, L.ORIGINAL)
        return
    try:
        result = run_measurement(SS.image, cfg, mode, params, axis, direction, reference)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Measurement failed: {exc}")
        return
    show_result(result, cfg)


def show_result(result, cfg) -> None:
    pix = result.pixel
    uv = result.profile.image_uv()
    bounds, peak = [], None
    if pix.status == "ok":
        from vision.profile_extraction import PixelProfile
        bp = PixelProfile(result.profile.axis, np.array([pix.left_boundary_x, pix.right_boundary_x, pix.peak_x]),
                          np.array([pix.left_boundary_y, pix.right_boundary_y, pix.peak_y]), np.ones(3)).image_uv()
        bounds, peak = [bp[0], bp[1]], bp[2]
    overlay = draw_stripe_overlay(SS.image, uv, bounds, peak)
    c1, c2, c3 = st.columns(3)
    with c1:
        show(SS.image, L.ORIGINAL)
    with c2:
        show(mask_to_bgr(result.stripe.mask), L.MASK)
    with c3:
        show(overlay, L.OVERLAY)

    st.subheader(L.PROFILE)
    ch = profile_chart(result)
    if ch is not None:
        st.altair_chart(ch, width="stretch")
    det = result.stripe.summary()
    st.caption(f"Scan axis used: {det['axis']} | coverage {det['coverage']:.0%} | segments {det['segments']} | "
               f"detection confidence {det['detection_confidence']:.2f}")

    st.subheader("Results")
    metric = result.metric
    if metric and metric.get("validated"):
        st.success("Validated calibrated measurement (mm). One image = one cross-section.")
        c = st.columns(4)
        c[0].metric("Bead width (mm)", f"{metric['width']:.3f}")
        c[1].metric("Bead height (mm)", f"{metric['height']:.3f}")
        c[2].metric("Cross-section area (mm²)", f"{metric['area']:.3f}")
        c[3].metric("Measurement confidence", f"{metric['confidence']:.2f}")
        st.caption(metric["height_definition"])
    elif result.blocked_reason:
        (st.info if result.mode == MODE_UNCALIBRATED else st.error)(result.blocked_reason)
    st.write("**Image-space measurement (pixels, not millimetres)**")
    c = st.columns(4)
    c[0].metric("Apparent width (px)", "-" if pix.width is None else f"{pix.width:.1f}")
    c[1].metric("Apparent height (px)", "-" if pix.height is None else f"{pix.height:.2f}",
                help="Stripe displacement caused by the bead. Not a physical height.")
    c[2].metric("Detection confidence", f"{result.stripe.overall_confidence:.2f}")
    c[3].metric("Measurement confidence", f"{pix.confidence:.2f}")
    if pix.status != "ok":
        st.warning(f"Bead status: {pix.status}")
    for est in result.experimental_estimates:
        with st.container(border=True):
            st.write(f"**{est['label']}**")
            if est.get("available") is False:
                st.write(est.get("reason", ""))
                continue
            cc = st.columns(2)
            cc[0].metric("Estimated width (mm, EXPERIMENTAL)", "-" if est.get("width_mm") is None else f"{est['width_mm']:.2f}")
            cc[1].metric("Estimated height (mm, EXPERIMENTAL)", "-" if est.get("height_mm") is None else f"{est['height_mm']:.2f}")
            st.caption("Assumptions: " + " ".join(est.get("assumptions", [])))
    for w in result.warnings:
        st.warning(w)

    c1, c2, c3 = st.columns(3)
    c1.download_button(L.DOWNLOAD_JSON, result_to_json(result), file_name="weld_measurement.json",
                       mime="application/json")
    c2.download_button(L.DOWNLOAD_CSV, result_to_csv(result), file_name="weld_profile.csv", mime="text/csv")
    if c3.button(L.SAVE_RESULTS):
        files = save_result_files(result, resolve_project_path(cfg["output"]["directory"]),
                                  {"original": SS.image, "mask": mask_to_bgr(result.stripe.mask), "overlay": overlay},
                                  cfg)
        st.success("Saved: " + ", ".join(str(f) for f in files))


def live_preview(cfg) -> None:
    seconds = float(cfg["camera"]["preview_seconds"])
    slot = st.empty()
    try:
        cap = open_camera(int(SS.camera_index), **camera_kwargs(cfg))
    except CameraError as exc:
        st.error(str(exc))
        return
    frame = None
    try:
        end = time.time() + seconds
        while time.time() < end:
            frame = read_frame(cap)
            slot.image(bgr_to_rgb(frame), caption=f"Live preview ({end - time.time():.0f} s left). The last frame is kept.",
                       width="stretch")
            time.sleep(0.05)
    except CameraError as exc:
        st.error(str(exc))
    finally:
        cap.release()
    if frame is not None:
        SS.image, SS.image_name, SS.detect_requested = frame, f"preview_{datetime.now():%H%M%S}", False


# ----------------------------------------------------------------- parameters tab
def parameters_tab(report) -> None:
    cfg = copy.deepcopy(report.config)
    st.write("Physical parameters with their units and where each value came from. Leave a value **empty** when it "
             "is unknown. Never type a guess as *verified* or *measured*.")
    st.caption(f"Operating mode is set only in config.yaml: calibration.enabled = {cfg['calibration']['enabled']}.")
    rows = []
    for key, meta in PHYSICAL_PARAMETERS.items():
        src = cfg["parameter_sources"].get(key, {"source": "unknown", "note": ""})
        c1, c2, c3 = st.columns([2, 1, 3])
        val = c1.number_input(f"{meta['label']} ({meta['unit']})", min_value=float(meta["min"]),
                              max_value=float(meta["max"]), value=get_path(cfg, key), placeholder="unknown",
                              key=f"p_{key}", format="%.4f")
        source = c2.selectbox("Source", PARAMETER_SOURCES, index=PARAMETER_SOURCES.index(src["source"]),
                              key=f"s_{key}")
        note = c3.text_input("Note", src.get("note", ""), key=f"n_{key}")
        set_path(cfg, key, None if val is None else float(val))
        cfg["parameter_sources"][key] = {"source": source, "note": note}
        rows.append({"parameter": key, "value": val, "unit": meta["unit"], "source": source})
    st.write("**Fixture** (stored in the calibration; changing it invalidates the calibration)")
    c1, c2, c3 = st.columns(3)
    cfg["fixture"]["fixture_id"] = c1.text_input("Fixture id", cfg["fixture"]["fixture_id"])
    tilt = c2.number_input("Camera tilt setting (deg)", min_value=-90.0, max_value=90.0,
                           value=cfg["fixture"]["camera_tilt_setting_deg"], placeholder="unknown")
    cfg["fixture"]["camera_tilt_setting_deg"] = None if tilt is None else float(tilt)
    cfg["fixture"]["notes"] = c3.text_input("Fixture notes", cfg["fixture"]["notes"])

    c1, c2, c3 = st.columns(3)
    if c1.button(L.VALIDATE_PARAMS):
        from utils.config_loader import validate_config
        rep = validate_config(copy.deepcopy(cfg))
        if rep.ok:
            st.success("Parameters are valid.")
        for e in rep.errors:
            st.error(e)
        for w in rep.warnings:
            st.warning(w)
    if c2.button(L.SAVE_CONFIG, type="primary"):
        try:
            path = save_config(cfg, report.path)
            st.success(f"Saved {path} (backup: {path.name}.bak). Press Reload Configuration.")
        except ConfigError as exc:
            st.error(str(exc))
    confirm = c3.checkbox(L.RESET_CONFIRM)
    if c3.button(L.RESET_DEFAULTS, disabled=not confirm):
        for key in PHYSICAL_PARAMETERS:
            set_path(cfg, key, None)
            cfg["parameter_sources"][key] = {"source": "unknown", "note": ""}
            SS.pop(f"p_{key}", None)
            SS.pop(f"s_{key}", None)
            SS.pop(f"n_{key}", None)
        cfg["geometry"]["camera_yaw_deg"] = None
        cfg["geometry"]["camera_roll_deg"] = None
        try:
            save_config(cfg, report.path)
            st.success("All optical and geometry parameters reset to unknown and saved.")
            st.rerun()
        except ConfigError as exc:
            st.error(str(exc))
    st.dataframe(pd.DataFrame(rows), hide_index=True)


# ----------------------------------------------------------------- calibration tab
def board_spec_inputs(cfg) -> CheckerboardSpec:
    cb = cfg["calibration"]["checkerboard"]
    SS.setdefault("cb_cols", int(cb["inner_corners_cols"]))
    SS.setdefault("cb_rows", int(cb["inner_corners_rows"]))
    SS.setdefault("cb_square", float(cb["square_size_mm"]))
    return CheckerboardSpec(int(SS.cb_cols), int(SS.cb_rows), float(SS.cb_square))


def step_board(report) -> None:
    cfg = report.config
    spec = board_spec_inputs(cfg)
    st.write("Inner corners are where four squares meet. A board with **10 x 7 squares** has **9 x 6 inner corners**.")
    c1, c2, c3 = st.columns(3)
    c1.number_input(L.CB_COLS, 3, 50, step=1, key="cb_cols")
    c2.number_input(L.CB_ROWS, 3, 50, step=1, key="cb_rows")
    c3.number_input(L.CB_SQUARE, 1.0, 200.0, step=0.5, key="cb_square", format="%.2f")
    spec = CheckerboardSpec(int(SS.cb_cols), int(SS.cb_rows), float(SS.cb_square))
    cb = cfg["calibration"]["checkerboard"]
    if spec.to_dict() != {k: (float(v) if k == "square_size_mm" else int(v)) for k, v in cb.items()}:
        st.warning("These values differ from config.yaml. Press Save Checkerboard Settings so the config, the printed "
                   "board and the calibration all agree.")
    if st.button(L.SAVE_CB):
        new = copy.deepcopy(cfg)
        new["calibration"]["checkerboard"] = spec.to_dict()
        try:
            save_config(new, report.path)
            st.success("Checkerboard settings saved to config.yaml.")
        except ConfigError as exc:
            st.error(str(exc))
    st.write(f"Squares to print: **{spec.squares[0]} x {spec.squares[1]}**, each **{spec.square_size_mm:g} mm**.")
    st.caption("The WHOLE board must fit in the camera picture at your working distance. If it does not, use "
               "smaller squares (e.g. 10 mm) and save the new size.")
    if st.button(L.GENERATE_PDF):
        try:
            SS.pdf, SS.svg = checkerboard_pdf(spec), checkerboard_svg(spec)
            st.success(f"Board fits on {layout(spec)['page']} landscape.")
        except ValueError as exc:
            st.error(str(exc))
    if SS.pdf:
        stem = f"checkerboard_{spec.inner_corners_cols}x{spec.inner_corners_rows}_{spec.square_size_mm:g}mm"
        c1, c2 = st.columns(2)
        c1.download_button(L.DOWNLOAD_PDF, SS.pdf, file_name=stem + ".pdf", mime="application/pdf")
        c2.download_button(L.DOWNLOAD_SVG, SS.svg, file_name=stem + ".svg", mime="image/svg+xml")


def coverage_grid(views) -> str:
    cells = set()
    for v in views:
        if v.ok:
            cells |= set(v.cells)
    rows = []
    for r in range(3):
        rows.append(" ".join("■" if (r, c) in cells else "□" for c in range(3)))
    return "\n".join(rows)


def step_intrinsics(report) -> None:
    cfg = report.config
    spec = board_spec_inputs(cfg)
    pol = cfg["calibration"]["camera_intrinsics"]
    st.write(f"Board: **{spec.inner_corners_cols} x {spec.inner_corners_rows} inner corners, "
             f"{spec.square_size_mm:g} mm squares** (change in 1. Checkerboard).")
    good = [v for v in SS.views if v.ok]
    st.progress(min(1.0, len(good) / pol["recommended_views"]),
                text=f"Accepted views: {len(good)} (minimum {pol['min_views']}, target {pol['recommended_views']})")
    c1, c2 = st.columns([2, 1])
    with c1:
        ups = st.file_uploader(L.UPLOAD_CB_IMAGES, type=["jpg", "jpeg", "png", "bmp"], accept_multiple_files=True,
                               key="cb_uploads")
        if st.button(L.ADD_UPLOADED) and ups:
            for u in ups:
                try:
                    img = decode_image(u.getvalue())
                except ValueError as exc:
                    st.error(f"{u.name}: {exc}")
                    continue
                SS.views.append(detect_view(img, spec, u.name))
            st.rerun()
        if st.button(L.CAPTURE_VIEW):
            frame = capture(cfg)
            if frame is not None:
                name = f"capture_{len(SS.views) + 1:03d}"
                v = detect_view(frame, spec, name)
                SS.views.append(v)
                folder = resolve_project_path("data/calibration/camera_views")
                save_image(frame, folder / f"{datetime.now():%Y%m%d_%H%M%S}_{name}.png")
                if v.ok:
                    st.success(f"{name}: corners found.")
                    show(draw_corners(frame, spec, v.corners, True), "Detected corners")
                else:
                    st.error(f"{name}: {v.reason}")
    with c2:
        st.write("Board coverage of the image (■ = covered):")
        st.code(coverage_grid(SS.views))
        if st.button(L.REMOVE_REJECTED):
            SS.views = [v for v in SS.views if v.ok]
            st.rerun()
        if st.button(L.CLEAR_VIEWS):
            SS.views, SS.intrinsics = [], None
            st.rerun()
    if SS.views:
        st.dataframe(pd.DataFrame([{"view": v.name, "accepted": v.ok, "size": f"{v.image_size[0]}x{v.image_size[1]}",
                                    "board area %": round(100 * v.board_area_fraction, 1),
                                    "sharpness": round(v.sharpness), "message": v.reason} for v in SS.views]),
                     hide_index=True)
    if st.button(L.RUN_CAMERA_CAL, type="primary"):
        with st.spinner("Calibrating..."):
            SS.intrinsics = calibrate_intrinsics(SS.views, spec, pol)
    res = SS.intrinsics
    if res is None:
        return
    if res.camera_matrix is not None:
        c = st.columns(4)
        c[0].metric("Reprojection error (px)", f"{res.rms_px:.3f}")
        c[1].metric("fx (px)", f"{res.camera_matrix[0, 0]:.1f}")
        c[2].metric("Coverage (of 9)", res.coverage_cells)
        c[3].metric("Tilt range (deg)", f"{res.tilt_range_deg:.1f}")
    for e in res.errors:
        st.error(e)
    for w in res.warnings:
        st.warning(w)
    if res.needs_more_views:
        st.info("Add more views as described above, then press Run Camera Calibration again.")
    if res.ok:
        st.success("Camera calibration passed. Saving creates a NEW calibration file; any old laser plane is removed "
                   "because it belonged to the old camera calibration.")
        if st.button(L.SAVE_CAMERA_CAL):
            data = new_calibration(cfg)
            data["camera"] = camera_section(res)
            path = save_calibration(data, resolve_project_path(cfg["calibration"]["calibration_file"]))
            st.success(f"Saved {path}. Next: 3. Laser Plane.")


def _image_slot(label: str, key: str, capture_label: str, cfg) -> None:
    up = st.file_uploader(label, type=["jpg", "jpeg", "png", "bmp"], key=f"up_{key}")
    if up is not None:
        try:
            SS[key] = decode_image(up.getvalue())
        except ValueError as exc:
            st.error(str(exc))
    if st.button(capture_label, key=f"cap_{key}"):
        frame = capture(cfg)
        if frame is not None:
            SS[key] = frame
    if SS.get(key) is not None:
        show(SS[key], label)


def step_laser(report) -> None:
    cfg = report.config
    pol = cfg["calibration"]["laser_plane"]
    cal_report = validate_calibration_file(cfg)
    if not cal_report.camera_ok:
        st.error("Valid camera intrinsics are required first (2. Camera Intrinsics, then Save Camera Calibration).")
        for e in cal_report.errors:
            st.write("- " + e)
        return
    data = cal_report.data
    spec = CheckerboardSpec(**data["camera"]["checkerboard"])
    st.success(f"Camera intrinsics OK ({cal_report.image_size[0]}x{cal_report.image_size[1]}, board "
               f"{spec.inner_corners_cols}x{spec.inner_corners_rows} @ {spec.square_size_mm:g} mm).")
    wd = cfg["geometry"]["working_distance_mm"]
    st.write(f"For each pose: put the board where the laser line crosses the squares, take one picture with the "
             f"laser OFF and one with the laser ON **without moving anything**, then press Add Pose. "
             f"You need **{pol['min_poses']} or more** poses at different distances and tilts"
             + (f" around your working distance of {wd:g} mm." if wd else "."))
    one = st.checkbox(L.ONE_IMAGE)
    c1, c2 = st.columns(2)
    with c1:
        _image_slot(L.LASER_OFF_IMAGE, "off_img", L.CAPTURE_OFF, cfg)
    if not one:
        with c2:
            _image_slot(L.LASER_ON_IMAGE, "on_img", L.CAPTURE_ON, cfg)
    if st.button(L.ADD_POSE):
        if SS.off_img is None or (not one and SS.on_img is None):
            st.error("Load both images first.")
        else:
            name = f"pose_{len(SS.poses) + 1}"
            params = LaserDetectionParams.from_config(cfg["laser"])
            pose = process_laser_pose(SS.off_img, None if one else SS.on_img, cal_report.camera_matrix,
                                      cal_report.dist_coeffs, cal_report.image_size, spec, params, pol, name,
                                      cfg["measurement"]["min_ray_plane_angle_deg"])
            SS.poses.append(pose)
            folder = resolve_project_path("data/calibration/laser_poses")
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_image(SS.off_img, folder / f"{stamp}_{name}_off.png")
            if not one:
                save_image(SS.on_img, folder / f"{stamp}_{name}_on.png")
            SS.off_img, SS.on_img = None, None
            (st.success if pose.ok else st.error)(f"{name}: " + ("accepted" if pose.ok else pose.reason))
    good = [p for p in SS.poses if p.ok]
    st.progress(min(1.0, len(good) / pol["min_poses"]), text=f"Good poses: {len(good)} / {pol['min_poses']}")
    if SS.poses:
        st.dataframe(pd.DataFrame([{"pose": p.name, "accepted": p.ok,
                                    "board distance (mm)": None if p.distance_mm is None else round(p.distance_mm, 1),
                                    "laser points": p.n_points,
                                    "pose error (px)": None if p.pnp_error_px is None else round(p.pnp_error_px, 3),
                                    "line RMS (mm)": None if p.line_rms_mm is None else round(p.line_rms_mm, 3),
                                    "message": p.reason} for p in SS.poses]), hide_index=True)
    c1, c2 = st.columns(2)
    if c2.button(L.CLEAR_POSES):
        SS.poses, SS.laser_result = [], None
        st.rerun()
    if c1.button(L.FIT_PLANE, type="primary"):
        SS.laser_result = fit_laser_plane(SS.poses, pol)
    res = SS.laser_result
    if res is None:
        return
    if res.plane is not None:
        c = st.columns(4)
        c[0].metric("Plane RMS (mm)", f"{res.rms_mm:.3f}")
        c[1].metric("Max residual (mm)", f"{res.max_abs_mm:.3f}")
        c[2].metric("Pose spread (mm)", f"{res.pose_spread_mm:.1f}")
        c[3].metric("Points", res.num_points)
        a, b, cc, d = res.plane
        st.code(f"{a:+.6f}*X {b:+.6f}*Y {cc:+.6f}*Z {d:+.4f} = 0   (camera frame, mm)")
    for e in res.errors:
        st.error(e)
    for w in res.warnings:
        st.warning(w)
    if res.ok and st.button(L.SAVE_LASER_CAL):
        data = load_calibration_json(cal_report.path)
        data["laser_plane"] = laser_section(res, spec, data["camera"])
        path = save_calibration(data, cal_report.path)
        st.success(f"Saved laser plane to {path}. Next: 4. Validation.")


def step_validation(report) -> None:
    cfg = report.config
    if st.button(L.VALIDATE_FILE):
        rep = validate_calibration_file(cfg)
        st.dataframe(pd.DataFrame([{"check": c.name, "passed": c.passed, "detail": c.detail} for c in rep.checks]),
                     hide_index=True)
        (st.success if rep.metric_ready else st.error)(
            "Calibration is VALID for metric measurement." if rep.metric_ready else "Calibration is NOT valid.")
        for w in rep.warnings:
            st.warning(w)
    st.divider()
    st.write("**Flat plate check**: place the board at a NEW position, take a laser OFF and a laser ON picture. The "
             "laser points measured with the calibrated plane must lie on the board.")
    c1, c2 = st.columns(2)
    with c1:
        _image_slot(L.FLAT_OFF, "flat_off", L.CAPTURE_OFF, cfg)
    with c2:
        _image_slot(L.FLAT_ON, "flat_on", L.CAPTURE_ON, cfg)
    if st.button(L.RUN_FLAT):
        rep = validate_calibration_file(cfg)
        if SS.flat_off is None or SS.flat_on is None:
            st.error("Load both images first.")
        else:
            spec = CheckerboardSpec(**rep.data["camera"]["checkerboard"]) if rep.data and rep.data.get("camera") \
                else board_spec_inputs(cfg)
            out = flat_plate_check(SS.flat_off, SS.flat_on, rep, spec, LaserDetectionParams.from_config(cfg["laser"]),
                                   cfg)
            if "error" in out:
                st.error(out["error"])
            else:
                (st.success if out["passed"] else st.error)(
                    f"RMS distance to the board {out['rms_mm']:.3f} mm (limit {out['limit_mm']} mm), max "
                    f"{out['max_abs_mm']:.3f} mm, {out['points']} points, board at {out['board_distance_mm']:.0f} mm.")


def step_status(report) -> None:
    cfg = report.config
    path = resolve_project_path(cfg["calibration"]["calibration_file"])
    st.write(f"Calibration file: `{path}`")
    st.button(L.RELOAD_CAL)
    if not path.exists():
        st.warning("No calibration file yet.")
        return
    rep = validate_calibration_file(cfg)
    data = rep.data or {}
    cam, lp = data.get("camera") or {}, data.get("laser_plane") or {}
    c = st.columns(3)
    c[0].metric("Camera intrinsics", "valid" if rep.camera_ok else "invalid / missing")
    c[1].metric("Laser plane", "valid" if rep.laser_ok else "invalid / missing")
    c[2].metric("Metric ready", "yes" if rep.metric_ready else "no")
    if cam:
        st.write(f"Camera: {cam.get('image_width')}x{cam.get('image_height')}, reprojection error "
                 f"{cam.get('reprojection_error_px')} px, {cam.get('num_views')} views, calibrated "
                 f"{cam.get('calibrated_utc')}")
    if lp:
        st.write(f"Laser plane: RMS {lp.get('rms_residual_mm')} mm, {lp.get('num_poses')} poses, calibrated "
                 f"{lp.get('calibrated_utc')}")
    for e in rep.errors:
        st.error(e)
    st.download_button(L.DOWNLOAD_CAL, path.read_bytes(), file_name=path.name, mime="application/json")


def calibration_tab(report) -> None:
    st.caption("Calibration is optional. Uncalibrated mode works without it. Camera intrinsics alone are not "
               "enough for mm: the laser plane must also be calibrated.")
    step = st.radio(L.CAL_STEP, [L.STEP_BOARD, L.STEP_INTRINSICS, L.STEP_LASER, L.STEP_VALIDATION, L.STEP_STATUS],
                    horizontal=True)
    {L.STEP_BOARD: step_board, L.STEP_INTRINSICS: step_intrinsics, L.STEP_LASER: step_laser,
     L.STEP_VALIDATION: step_validation, L.STEP_STATUS: step_status}[step](report)


# ----------------------------------------------------------------- main
def main() -> None:
    init_state()
    report, mode = load_everything()
    sidebar(report, mode)
    st.title(L.APP_TITLE)
    if not report.ok:
        st.error("config/config.yaml has problems. Fix them and press Reload Configuration:")
        for e in report.errors:
            st.write("- " + e)
        return
    t1, t2, t3 = st.tabs([L.TAB_MEASURE, L.TAB_PARAMETERS, L.TAB_CALIBRATION])
    with t1:
        measure_tab(report, mode)
    with t2:
        parameters_tab(report)
    with t3:
        calibration_tab(report)


main()
