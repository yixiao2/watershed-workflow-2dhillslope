"""Shared schema-v2 dates and names for the prefire/postfire workflow."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path


REQUIRED_PHASES = ("spinup", "prefire_transient")


def _parse_date(value, field):
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD)") from exc
    if parsed.month == 2 and parsed.day == 29:
        raise ValueError(f"{field} cannot be Feb. 29 in a no-leap case")
    return parsed


def _period(block, name):
    period = block.get("source_period", block)
    start = _parse_date(period.get("start_date"), f"{name}.start_date")
    end = _parse_date(period.get("end_date"), f"{name}.end_date")
    if end < start:
        raise ValueError(f"{name} end_date precedes start_date")
    return start, end


def load_config(path="config.json"):
    """Load and validate a schema-v2 config without accepting legacy year keys."""
    with Path(path).open() as handle:
        config = json.load(handle)

    if config.get("schema_version") != 2:
        raise ValueError("config.json must use schema_version 2")
    if config.get("calendar") != "noleap":
        raise ValueError("calendar must be 'noleap'")
    if not config.get("elm_root"):
        raise ValueError("elm_root is required")
    if not isinstance(config.get("case"), dict):
        raise ValueError("case block is required")
    for key in ("watershed_name", "hucs", "site_name", "meshsize_nx"):
        if key not in config["case"]:
            raise ValueError(f"case.{key} is required")
    for phase in REQUIRED_PHASES:
        if not isinstance(config.get(phase), dict):
            raise ValueError(f"{phase} block is required")
        _period(config[phase], phase)
        if not config[phase].get("elm_run"):
            raise ValueError(f"{phase}.elm_run is required")
    if "postfire_transient" in config:
        postfire = config["postfire_transient"]
        if not isinstance(postfire, dict):
            raise ValueError("postfire_transient must be an object or be omitted")
        _period(postfire, "postfire_transient")
        if not postfire.get("elm_run"):
            raise ValueError("postfire_transient.elm_run is required")
        if "ignition_day_elm_run" in postfire and not postfire["ignition_day_elm_run"]:
            raise ValueError("postfire_transient.ignition_day_elm_run cannot be empty")

    spinup_end = phase_period(config, "spinup")[1]
    prefire_start, prefire_end = phase_period(config, "prefire_transient")
    if spinup_end + timedelta(days=1) != prefire_start:
        raise ValueError("spinup and prefire_transient must be contiguous")
    if "postfire_transient" in config:
        postfire_start, _ = phase_period(config, "postfire_transient")
        if prefire_end + timedelta(days=1) != postfire_start:
            raise ValueError("prefire_transient and postfire_transient must be contiguous")
    return config


def phase_period(config, phase):
    return _period(config[phase], phase)


def phase_dates(config, phase):
    """Inclusive daily dates, with Feb. 29 omitted."""
    start, end = phase_period(config, phase)
    days = []
    current = start
    while current <= end:
        if not (current.month == 2 and current.day == 29):
            days.append(current)
        current += timedelta(days=1)
    return days


def phase_label(config, phase):
    start, end = phase_period(config, phase)
    return f"{start.isoformat()}_{end.isoformat()}"


def baseline_forcing_root(config, base_dir="../data-processed"):
    """Return the case-local baseline forcing directory."""
    return Path(base_dir) / config["case"]["site_name"] / "forcing" / "baseline"


def phase_forcing_dir(config, phase, base_dir="../data-processed"):
    """Return the labelled provenance directory for one forcing phase."""
    if phase == "spinup":
        name = f"spinup_source_{phase_label(config, phase)}"
    elif phase == "prefire_transient":
        name = f"prefire_{phase_label(config, phase)}"
    elif phase == "postfire_transient":
        name = f"postfire_{phase_label(config, phase)}"
    else:
        raise ValueError(f"Unknown forcing phase: {phase}")
    return baseline_forcing_root(config, base_dir) / name


def full_timeline_forcing_dir(config, base_dir="../data-processed"):
    """Return the stable canonical forcing directory used by model XML."""
    years = config["spinup"]["cyclic_years"]
    return baseline_forcing_root(config, base_dir) / f"full_timeline_spinup{years}y_prefire_postfire"


def phase_names(config):
    names = list(REQUIRED_PHASES)
    if "postfire_transient" in config:
        names.append("postfire_transient")
    return names


def noleap_day_of_year(day):
    """Zero-based no-leap day index within day.year."""
    return (day - date(day.year, 1, 1)).days - (1 if day.month > 2 and _is_leap(day.year) else 0)


def _is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
