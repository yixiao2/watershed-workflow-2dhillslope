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


def first_postfire_year(config):
    """Inclusive 365-day no-leap response window, independent of run length."""
    if 'postfire_transient' not in config:
        raise ValueError('postfire_transient is required for the fire workflow')
    start = phase_period(config, 'postfire_transient')[0]
    end, count = start, 1
    while count < 365:
        end += timedelta(days=1)
        if (end.month, end.day) != (2, 29):
            count += 1
    return start, end


def artificial_baseline_year(config):
    value = config.get('fire_workflow', {}).get('artificial_baseline_year', 2021)
    if type(value) is not int or not 1 <= value <= 9999:
        raise ValueError('fire_workflow.artificial_baseline_year must be a valid integer year')
    return value


def load_fire_workflow(config, base_dir, artificial=False):
    """Resolve stage-specific inputs from the case root; keep schema-v2 optional."""
    first_postfire_year(config)
    settings = config.get('fire_workflow', {})
    if not isinstance(settings, dict):
        raise ValueError('fire_workflow must be an object')
    base = Path(base_dir).resolve()
    mtbs = '../../MaterialsData/MTBS_fire_WA_2021/MTBS_fire_shp_files/2021/wa4684012114620210804/'
    stem = 'wa4684012114620210804_20210725_20220728'
    modis = f"notebooks/MODIS_raw/{config['case']['watershed_name']}/{config['case']['watershed_name']}-square/"
    values = dict(scenario='s1', severity='low', burn_raster=mtbs + stem + '_dnbr6.tif',
                  perimeter=mtbs + stem + '_burn_bndy.shp',
                  modis_lai=modis + 'MCD15A3H.061_500m_aid0001.nc',
                  modis_landcover=modis + 'MCD12Q1.061_500m_aid0001.nc',
                  fire_elm_run=config['postfire_transient']['elm_run'],
                  nofire_elm_run='2024-11-20-220109',
                  artificial_baseline_year=2021)
    values.update(settings)
    if not isinstance(values['scenario'], str) or not values['scenario'].isalnum():
        raise ValueError('fire_workflow.scenario must be an alphanumeric folder suffix')
    if values['severity'] not in ('unburned/no-low', 'low', 'moderate', 'high'):
        raise ValueError('Invalid fire_workflow.severity')
    keys = ['burn_raster']
    if artificial:
        artificial_baseline_year(config)
        keys += ['perimeter', 'modis_lai', 'modis_landcover']
        for key in ('fire_elm_run', 'nofire_elm_run'):
            if not isinstance(values[key], str) or not values[key] or Path(values[key]).name != values[key]:
                raise ValueError(f'fire_workflow.{key} must be an ELM realization name')
        values['elm_root'] = (base / config['elm_root']).resolve()
        for key in ('fire_elm_run', 'nofire_elm_run'):
            path = values['elm_root'] / f"ELM_MOSART_CONUS.{values[key]}" / 'run'
            if not path.is_dir():
                raise ValueError(f'Missing paired ELM input directory: {path}')
    for key in keys:
        if not isinstance(values[key], str) or not values[key]:
            raise ValueError(f'fire_workflow.{key} must be a source file path')
        values[key] = (base / values[key]).resolve()
        if not values[key].is_file():
            raise ValueError(f'Missing fire source input {key}: {values[key]}')
    return values
