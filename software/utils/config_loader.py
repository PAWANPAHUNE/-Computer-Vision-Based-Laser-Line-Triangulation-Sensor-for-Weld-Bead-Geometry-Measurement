"""Load, validate and save ``config/config.yaml``.

The YAML file is the single source of truth for the operating mode. This module
never changes the mode on its own: it only reports what the file requests and
what is wrong with it.
"""
from __future__ import annotations

import copy
import math
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"
CONFIG_ENV_VAR = "LASER_TRI_CONFIG"  # optional: path to another config file (tests, demos)


def active_config_path() -> Path:
    env = os.environ.get(CONFIG_ENV_VAR)
    return Path(env) if env else DEFAULT_CONFIG_PATH

PARAMETER_SOURCES = ("verified", "measured", "estimated", "unknown")

# Physical parameters shown in the Parameters tab. Each has a unit and a range.
PHYSICAL_PARAMETERS: dict[str, dict[str, Any]] = {
    "camera.focal_length_mm": {"unit": "mm", "min": 0.3, "max": 100.0, "label": "Lens focal length"},
    "camera.sensor_width_mm": {"unit": "mm", "min": 0.5, "max": 40.0, "label": "Sensor width"},
    "camera.sensor_height_mm": {"unit": "mm", "min": 0.5, "max": 40.0, "label": "Sensor height"},
    "camera.pixel_pitch_um": {"unit": "um", "min": 0.5, "max": 20.0, "label": "Pixel pitch"},
    "geometry.camera_to_laser_baseline_mm": {"unit": "mm", "min": 1.0, "max": 1000.0, "label": "Camera-to-laser baseline"},
    "geometry.camera_pitch_deg": {"unit": "deg", "min": -80.0, "max": 80.0, "label": "Camera pitch (tilt toward laser)"},
    "geometry.camera_yaw_deg": {"unit": "deg", "min": -45.0, "max": 45.0, "label": "Camera yaw"},
    "geometry.camera_roll_deg": {"unit": "deg", "min": -180.0, "max": 180.0, "label": "Camera roll"},
    "geometry.laser_plane_angle_deg": {"unit": "deg", "min": -60.0, "max": 60.0, "label": "Laser plane angle"},
    "geometry.working_distance_mm": {"unit": "mm", "min": 5.0, "max": 2000.0, "label": "Working distance"},
}


class ConfigError(Exception):
    """Raised when the configuration file cannot be used at all."""


# ---------------------------------------------------------------- defaults
DEFAULT_CONFIG: dict[str, Any] = {
    "calibration": {
        "enabled": False,
        "calibration_file": "data/calibration/calibration.json",
        "require_valid_calibration": True,
        "allow_uncalibrated_metric_estimates": False,
        "allow_intrinsic_resolution_scaling": False,
        "checkerboard": {"inner_corners_cols": 9, "inner_corners_rows": 6, "square_size_mm": 25.0},
        "camera_intrinsics": {
            "min_views": 12,
            "recommended_views": 20,
            "max_reprojection_error_px": 1.0,
            "min_coverage_cells": 6,
            "min_tilt_range_deg": 15.0,
            "fix_k3": False,
        },
        "laser_plane": {
            "min_poses": 3,
            "min_points_per_pose": 40,
            "max_plane_rms_mm": 0.5,
            "max_pose_line_rms_mm": 1.0,
            "line_inlier_threshold_mm": 1.5,
            "min_line_inlier_fraction": 0.75,
            "min_pose_spread_mm": 15.0,
            "max_pnp_reprojection_error_px": 2.0,
            "region_margin_mm": 5.0,
            "min_camera_to_plane_distance_mm": 5.0,
        },
        "validation": {"max_flat_plate_rms_mm": 0.5},
    },
    "camera": {
        "backend": "auto",
        "device_index": 1,
        "resolution": {"width": 1280, "height": 800},
        "warmup_frames": 5,
        "preview_seconds": 10,
        "focal_length_mm": None,
        "sensor_width_mm": None,
        "sensor_height_mm": None,
        "pixel_pitch_um": None,
    },
    "geometry": {
        "camera_to_laser_baseline_mm": None,
        "camera_pitch_deg": None,
        "camera_yaw_deg": 0.0,
        "camera_roll_deg": 0.0,
        "laser_plane_angle_deg": None,
        "working_distance_mm": None,
    },
    "fixture": {"fixture_id": "welding_sensor_fixture_v3", "camera_tilt_setting_deg": None, "notes": ""},
    "laser": {
        "type": "line",
        "color": "red",
        "detection_method": "red_channel_difference",
        "threshold": 30,
        "minimum_component_area": 5,
        "smoothing_window": 5,
        "blur_kernel": 3,
        "max_stripe_width_px": 40,
        "outlier_threshold_px": 6.0,
        "saturation_level": 250,
    },
    "measurement": {
        "reference_surface": "local_background",
        "profile_axis": "auto",
        "bead_direction": "auto",
        "minimum_confidence": 0.5,
        "boundary_fraction": 0.05,
        "peak_smoothing_points": 1,
        "min_bead_height_px": 3.0,
        "min_bead_height_mm": 0.2,
        "min_depth_mm": 20.0,
        "max_depth_mm": 1000.0,
        "min_ray_plane_angle_deg": 2.0,
    },
    "output": {"directory": "outputs", "save_debug_images": True, "save_profiles": True, "save_json": True},
    "parameter_sources": {
        **{key: {"source": "unknown", "note": ""} for key in PHYSICAL_PARAMETERS},
        "geometry.camera_yaw_deg": {"source": "estimated", "note": "Fixture design is 0; not measured."},
        "geometry.camera_roll_deg": {"source": "estimated", "note": "Fixture design is 0; not measured."},
    },
}

# Keys that MUST be present in the file (no silent defaults for these).
REQUIRED_KEYS = (
    "calibration.enabled",
    "calibration.calibration_file",
    "calibration.require_valid_calibration",
    "calibration.allow_uncalibrated_metric_estimates",
)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _num(lo: float | None = None, hi: float | None = None, integer: bool = False, nullable: bool = False,
         odd: bool = False) -> Callable[[Any], str | None]:
    def check(value: Any) -> str | None:
        if value is None:
            return None if nullable else "must be a number, not empty/null"
        if not _is_number(value):
            return f"must be a number (got {value!r})"
        if integer and float(value) != int(value):
            return f"must be a whole number (got {value!r})"
        if lo is not None and value < lo:
            return f"must be >= {lo} (got {value})"
        if hi is not None and value > hi:
            return f"must be <= {hi} (got {value})"
        if odd and int(value) % 2 == 0:
            return f"must be an odd number (got {value})"
        return None
    return check


def _bool(value: Any) -> str | None:
    return None if isinstance(value, bool) else f"must be true or false (got {value!r})"


def _choice(*options: str) -> Callable[[Any], str | None]:
    def check(value: Any) -> str | None:
        return None if value in options else f"must be one of {list(options)} (got {value!r})"
    return check


def _string(value: Any) -> str | None:
    return None if isinstance(value, str) else f"must be text in quotes (got {value!r})"


def _nonempty_string(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return f"must be a non-empty text value (got {value!r})"
    return None


RULES: dict[str, Callable[[Any], str | None]] = {
    "calibration.enabled": _bool,
    "calibration.calibration_file": _nonempty_string,
    "calibration.require_valid_calibration": _bool,
    "calibration.allow_uncalibrated_metric_estimates": _bool,
    "calibration.allow_intrinsic_resolution_scaling": _bool,
    "calibration.checkerboard.inner_corners_cols": _num(3, 50, integer=True),
    "calibration.checkerboard.inner_corners_rows": _num(3, 50, integer=True),
    "calibration.checkerboard.square_size_mm": _num(1.0, 200.0),
    "calibration.camera_intrinsics.min_views": _num(5, 200, integer=True),
    "calibration.camera_intrinsics.recommended_views": _num(5, 200, integer=True),
    "calibration.camera_intrinsics.max_reprojection_error_px": _num(0.05, 10.0),
    "calibration.camera_intrinsics.min_coverage_cells": _num(1, 9, integer=True),
    "calibration.camera_intrinsics.min_tilt_range_deg": _num(0.0, 80.0),
    "calibration.camera_intrinsics.fix_k3": _bool,
    "calibration.laser_plane.min_poses": _num(2, 100, integer=True),
    "calibration.laser_plane.min_points_per_pose": _num(5, 100000, integer=True),
    "calibration.laser_plane.max_plane_rms_mm": _num(0.001, 20.0),
    "calibration.laser_plane.max_pose_line_rms_mm": _num(0.001, 20.0),
    "calibration.laser_plane.line_inlier_threshold_mm": _num(0.1, 20.0),
    "calibration.laser_plane.min_line_inlier_fraction": _num(0.3, 1.0),
    "calibration.laser_plane.min_pose_spread_mm": _num(0.1, 2000.0),
    "calibration.laser_plane.max_pnp_reprojection_error_px": _num(0.05, 20.0),
    "calibration.laser_plane.region_margin_mm": _num(0.0, 200.0),
    "calibration.laser_plane.min_camera_to_plane_distance_mm": _num(0.0, 1000.0),
    "calibration.validation.max_flat_plate_rms_mm": _num(0.001, 20.0),
    "camera.backend": _choice("auto", "avfoundation", "default"),
    "camera.device_index": _num(0, 64, integer=True),
    "camera.resolution.width": _num(64, 10000, integer=True),
    "camera.resolution.height": _num(64, 10000, integer=True),
    "camera.warmup_frames": _num(0, 120, integer=True),
    "camera.preview_seconds": _num(1, 600),
    "fixture.fixture_id": _nonempty_string,
    "fixture.camera_tilt_setting_deg": _num(-90, 90, nullable=True),
    "fixture.notes": _string,
    "laser.type": _choice("line"),
    "laser.color": _choice("red"),
    "laser.detection_method": _choice("red_channel_difference", "hsv_red", "red_channel_tophat"),
    "laser.threshold": _num(1, 255),
    "laser.minimum_component_area": _num(1, 100000, integer=True),
    "laser.smoothing_window": _num(1, 101, integer=True, odd=True),
    "laser.blur_kernel": _num(1, 31, integer=True, odd=True),
    "laser.max_stripe_width_px": _num(1, 500),
    "laser.outlier_threshold_px": _num(0.5, 500),
    "laser.saturation_level": _num(1, 255),
    "measurement.reference_surface": _choice("local_background", "global_line"),
    "measurement.profile_axis": _choice("auto", "image_columns", "image_rows"),
    "measurement.bead_direction": _choice("auto", "positive", "negative"),
    "measurement.minimum_confidence": _num(0.0, 1.0),
    "measurement.boundary_fraction": _num(0.0, 0.9),
    "measurement.peak_smoothing_points": _num(1, 51, integer=True, odd=True),
    "measurement.min_bead_height_px": _num(0.1, 1000),
    "measurement.min_bead_height_mm": _num(0.001, 100),
    "measurement.min_depth_mm": _num(0.0, 100000),
    "measurement.max_depth_mm": _num(1.0, 100000),
    "measurement.min_ray_plane_angle_deg": _num(0.0, 45.0),
    "output.directory": _nonempty_string,
    "output.save_debug_images": _bool,
    "output.save_profiles": _bool,
    "output.save_json": _bool,
}
for _key, _meta in PHYSICAL_PARAMETERS.items():
    RULES[_key] = _num(_meta["min"], _meta["max"], nullable=True)


def get_path(cfg: dict[str, Any], dotted: str, default: Any = KeyError) -> Any:
    node: Any = cfg
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            if default is KeyError:
                raise KeyError(dotted)
            return default
        node = node[part]
    return node


def set_path(cfg: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    node = cfg
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict) and key != "parameter_sources":
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


@dataclass
class ConfigReport:
    config: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    defaults_applied: list[str] = field(default_factory=list)
    path: Path | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_config(raw: dict[str, Any]) -> ConfigReport:
    """Validate a parsed config. Missing optional keys get documented defaults (reported)."""
    report = ConfigReport(config={})
    if not isinstance(raw, dict):
        report.errors.append("The configuration file must contain YAML sections like 'calibration:' and 'camera:'.")
        report.config = copy.deepcopy(DEFAULT_CONFIG)
        return report

    for key in REQUIRED_KEYS:
        try:
            get_path(raw, key)
        except KeyError:
            report.errors.append(f"Missing required setting '{key}'. Add it to config/config.yaml "
                                 f"(see config/config.example.uncalibrated.yaml).")

    merged = copy.deepcopy(DEFAULT_CONFIG)
    flat_raw = _flatten(raw)
    known = set(_flatten(DEFAULT_CONFIG)) | {"parameter_sources"}
    for key, value in flat_raw.items():
        if key not in known and not key.startswith("parameter_sources"):
            report.warnings.append(f"Unknown setting '{key}' is ignored. Check the spelling.")
            continue
        set_path(merged, key, value)
    for key in _flatten(DEFAULT_CONFIG):
        if key not in flat_raw and key not in REQUIRED_KEYS and not key.startswith("parameter_sources"):
            report.defaults_applied.append(key)

    for key, rule in RULES.items():
        try:
            value = get_path(merged, key)
        except KeyError:
            continue
        problem = rule(value)
        if problem:
            report.errors.append(f"'{key}' {problem}.")

    # Cross-field checks
    if not report.errors:
        ci = merged["calibration"]["camera_intrinsics"]
        if ci["recommended_views"] < ci["min_views"]:
            report.errors.append("'calibration.camera_intrinsics.recommended_views' must be >= 'min_views'.")
        m = merged["measurement"]
        if m["max_depth_mm"] <= m["min_depth_mm"]:
            report.errors.append("'measurement.max_depth_mm' must be greater than 'measurement.min_depth_mm'.")
        cam = merged["camera"]
        width = cam["resolution"]["width"]
        if cam["sensor_width_mm"] is not None and cam["pixel_pitch_um"] is not None:
            implied = width * cam["pixel_pitch_um"] / 1000.0
            if abs(implied - cam["sensor_width_mm"]) / cam["sensor_width_mm"] > 0.05:
                report.warnings.append(
                    f"sensor_width_mm ({cam['sensor_width_mm']}) does not match resolution width x pixel pitch "
                    f"({implied:.3f} mm). One of the optical specifications is probably wrong.")

    # Parameter sources
    sources = merged.get("parameter_sources") or {}
    if not isinstance(sources, dict):
        report.errors.append("'parameter_sources' must be a mapping of parameter name to {source, note}.")
        sources = {}
    for key in PHYSICAL_PARAMETERS:
        entry = sources.get(key)
        if entry is None:
            sources[key] = {"source": "unknown", "note": ""}
            entry = sources[key]
        if not isinstance(entry, dict) or entry.get("source") not in PARAMETER_SOURCES:
            report.errors.append(f"parameter_sources['{key}'].source must be one of {list(PARAMETER_SOURCES)}.")
            continue
        value = get_path(merged, key, None)
        if value is not None and entry["source"] == "unknown":
            report.errors.append(
                f"'{key}' has a value ({value}) but its source is 'unknown'. Mark it verified, measured or "
                f"estimated, or set the value back to null.")
    merged["parameter_sources"] = sources
    report.config = merged
    return report


def load_config(path: str | Path | None = None) -> ConfigReport:
    """Read and validate the YAML file. Never raises for content problems: errors are in the report."""
    cfg_path = Path(path) if path else active_config_path()
    if not cfg_path.exists():
        report = ConfigReport(config=copy.deepcopy(DEFAULT_CONFIG), path=cfg_path)
        report.errors.append(f"Configuration file not found: {cfg_path}. Copy "
                             f"config/config.example.uncalibrated.yaml to config/config.yaml.")
        return report
    try:
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        report = ConfigReport(config=copy.deepcopy(DEFAULT_CONFIG), path=cfg_path)
        report.errors.append(f"YAML syntax error in {cfg_path.name}{where}: {getattr(exc, 'problem', exc)}. "
                             f"Check indentation (spaces only, no tabs) and the colon after each key.")
        return report
    report = validate_config(raw if raw is not None else {})
    report.path = cfg_path
    return report


def resolve_project_path(relative: str) -> Path:
    p = Path(relative)
    return p if p.is_absolute() else PROJECT_ROOT / p


def save_config(cfg: dict[str, Any], path: str | Path | None = None) -> Path:
    """Validate then write the config. A backup ``config.yaml.bak`` is kept. Returns the path written."""
    report = validate_config(copy.deepcopy(cfg))
    if not report.ok:
        raise ConfigError("Not saved. Fix these problems first:\n- " + "\n- ".join(report.errors))
    cfg_path = Path(path) if path else active_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if cfg_path.exists():
        shutil.copy2(cfg_path, cfg_path.with_suffix(cfg_path.suffix + ".bak"))
    header = ("# Laser-triangulation weld measurement configuration.\n"
              "# Saved by the application. Comments were removed; see config/config.example.*.yaml\n"
              "# and Calibration.md for an explanation of every setting. Previous file: config.yaml.bak\n")
    text = yaml.safe_dump(report.config, sort_keys=False, default_flow_style=False, allow_unicode=True)
    cfg_path.write_text(header + text, encoding="utf-8")
    return cfg_path


def safe_defaults() -> dict[str, Any]:
    """Safe defaults: uncalibrated mode, every unknown physical value null."""
    return copy.deepcopy(DEFAULT_CONFIG)
