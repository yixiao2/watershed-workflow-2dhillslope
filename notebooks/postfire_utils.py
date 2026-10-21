"""Case-local checks and XML edits for the postfire configuration notebook."""

import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import h5py
import netCDF4
import numpy as np
from scipy.io import loadmat

from config_utils import phase_dates, full_timeline_forcing_dir, first_postfire_year

SEVERITY = {"unburned/no-low": (1, 1.0), "low": (2, 1.0),
            "moderate": (3, 0.4), "high": (4, 0.2)}
CLASS_LABELS = {0: "Non-processing", 1: "Unburned/no-low", 2: "Low",
                3: "Moderate", 4: "High", 5: "Increased greenness"}
SPECIES = ["C38-DONOR", "C35-DONOR", "C29-DONOR", "C27-DONOR", "C25-DONOR",
           "C23-DONOR", "C20-DONOR", "C19-DONOR", "C18-DONOR", "C13-DONOR"]
CARBON = [38.92, 35.42, 29.79591836734694, 27.7, 25.79591836734694,
          23.66, 20.52, 19.632653061224488, 18.183673469387756, 13.22]
DOC_KEY = "DOC production [molC m^-3 s^-1]"
CN_KEY = "DOC mol water basis v1 [molS molH^-1]"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def child(root, *names):
    for name in names:
        matches = [e for e in root if e.get("name") == name]
        require(len(matches) == 1, f"Expected exactly one XML child {name!r}")
        root = matches[0]
    return root


def mesh_first_layer(mesh_path, mat_path, nx):
    """Use the surface side set and NFACED connectivity, not an ID stride."""
    mat = loadmat(mat_path)
    dz = np.r_[mat["dzs_soil"].ravel(), mat["dzs_geo"].ravel()]
    require(np.isclose(dz[0], 0.05), "The first subsurface layer must be 0.05 m")
    with netCDF4.Dataset(mesh_path) as mesh:
        xyz = np.column_stack([mesh[k][:] for k in ("coordx", "coordy", "coordz")])
        faces = np.split(np.asarray(mesh["fbconn1"][:], int) - 1,
                         np.cumsum(mesh["fbepecnt1"][:])[:-1])
        cells, materials = [], []
        for block, material in enumerate(mesh["eb_prop1"][:], 1):
            face_ids = np.split(np.abs(np.asarray(mesh[f"facconn{block}"][:], int)) - 1,
                                np.cumsum(mesh[f"ebepecnt{block}"][:])[:-1])
            cells.extend([np.unique(np.concatenate([faces[f] for f in fs])) for fs in face_ids])
            materials.extend([int(material)] * len(face_ids))
        centroids = np.array([xyz[nodes].mean(axis=0) for nodes in cells])
        names = [b"".join(row.compressed()).decode().rstrip("\x00") for row in mesh["ss_names"][:]]
        require(names.count("surface") == 1, "Need exactly one surface side set")
        top = np.asarray(mesh[f"elem_ss{names.index('surface') + 1}"][:], int) - 1
        require(len(np.unique(top)) == nx, f"Expected {nx} distinct first-layer cells")
        require(len(cells) == nx * len(dz), "Mesh dimensions disagree with MAT layer data")
        # Each vertical node pair in a top cell has a 5 cm separation.
        for index in top:
            points = xyz[cells[index]]
            xy, inverse = np.unique(points[:, :2], axis=0, return_inverse=True)
            thickness = [np.ptp(points[inverse == i, 2]) for i in range(len(xy))]
            require(np.allclose(thickness, dz[0], atol=1e-8, rtol=0),
                    f"Cell {index + 1} does not have 5 cm vertical thickness")
        return {"mesh_path": str(Path(mesh_path).resolve()),
                "top": top, "materials": np.array(materials), "centroids": centroids,
                "thickness_m": float(dz[0]), "nz": len(dz)}


def burn_review(raster_path, summary_path, source_crs):
    import rasterio
    from rasterio.windows import from_bounds, Window
    from shapely.geometry import LineString, Polygon
    from pyproj import Transformer

    with Path(summary_path).open() as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == 1, "Expected one selected transect in the summary CSV")
    row = rows[0]
    endpoints = [(float(row[f"{p}_x"]), float(row[f"{p}_y"])) for p in ("start", "end")]
    with rasterio.open(raster_path) as src:
        transformer = Transformer.from_crs(source_crs, src.crs, always_xy=True)
        line = LineString([transformer.transform(*p) for p in endpoints])
        xmin, ymin, xmax, ymax = line.bounds
        window = from_bounds(xmin - 150, ymin - 150, xmax + 150, ymax + 150, src.transform)
        window = window.round_offsets().round_lengths().intersection(Window(0, 0, src.width, src.height))
        data = src.read(1, window=window)
        transform = src.window_transform(window)
        lengths = {i: 0.0 for i in range(1, 5)}
        for r, c in np.ndindex(data.shape):
            code = int(data[r, c])
            if code in lengths:
                polygon = Polygon([transform * (c, r), transform * (c + 1, r),
                                   transform * (c + 1, r + 1), transform * (c, r + 1)])
                lengths[code] += line.intersection(polygon).length
        total = sum(lengths.values())
        require(total > 0, "No valid burn-class pixels intersect the transect")
        dominant = max(lengths, key=lambda code: (lengths[code], code))
        fractions = {str(code): lengths[code] / total for code in lengths}
        return data, transform, line, {
            "class_fractions": fractions, "dominant_class": dominant,
            "length_weighted_class": sum(int(k) * v for k, v in fractions.items()),
            "non_dominant_fraction": 1 - max(fractions.values()),
            "tie": bool(sum(np.isclose(v, max(lengths.values()), rtol=0, atol=1e-8)
                            for v in lengths.values()) > 1),
            "valid_length_m": total, "transect_length_m": line.length,
            "raster": str(Path(raster_path).resolve()), "raster_crs": str(src.crs),
        }


def finite_hdf(path, expected_days):
    """Check all stored numeric values, group indices, and the canonical clock."""
    with h5py.File(path) as hdf:
        key = "Time" if "Time" in hdf else "time [s]"
        require(np.array_equal(hdf[key][:], np.arange(expected_days) * 86400),
                f"Incorrect canonical daily clock: {path}")
        def check(name, item):
            if isinstance(item, h5py.Dataset) and np.issubdtype(item.dtype, np.number):
                require(np.isfinite(item[:]).all(), f"Nonfinite values: {path}/{name}")
            elif isinstance(item, h5py.Group):
                require(set(item) == {str(i) for i in range(expected_days)},
                        f"Missing daily fields: {path}/{name}")
                shapes = {item[k].shape for k in item}
                require(len(shapes) == 1, f"Inconsistent spatial shapes: {path}/{name}")
        hdf.visititems(check)


def validate_forcing(config, base_dir, parent_xml):
    first_postfire_year(config)
    pre, post = phase_dates(config, "prefire_transient"), phase_dates(config, "postfire_transient")
    start = config["spinup"]["cyclic_years"] * 365 + len(pre)
    end = start + len(post)
    root = full_timeline_forcing_dir(config, base_dir / "data-processed")
    site = config["case"]["site_name"]
    files = [root / name for name in ("startpt_head.h5", "endpt_head.h5",
             f"{site}_DayMet.h5", f"{site}_MODIS_LAI.h5", f"{site}_DOC_source.h5",
             f"{site}_CNbc_conc.h5", f"lambda/{site}_DOC_source_lambda10.h5",
             f"lambda/{site}_CNbc_conc_lambda10.h5")]
    for path in files:
        require(path.is_file(), f"Missing forcing file: {path}")
        finite_hdf(path, end)
    parent = ET.parse(parent_xml).getroot()
    # Every actual HDF reference must point into this canonical forcing bundle,
    # and every XML header must exist with the time dimension expected by ATS.
    execution_dir = Path(parent_xml).parent / site
    referenced = set()
    for section in parent.iter("ParameterList"):
        params = {e.get("name"): e.get("value") for e in section if e.tag == "Parameter"}
        if params.get("file", "").endswith(".h5"):
            path = (execution_dir / params["file"]).resolve()
            require(path in {p.resolve() for p in files}, f"Unexpected forcing reference: {path}")
            referenced.add(path)
            with h5py.File(path) as h:
                for header in ("x header", "y header", "time header", "value header", "row header", "column header",
                               "variable name", "variable name 1", "variable name 2"):
                    if header in params:
                        require(params[header] in h, f"Missing {header}: {path}/{params[header]}")
                        value = h[params[header]]
                        if isinstance(value, h5py.Dataset) and header not in ("row header", "column header"):
                            require(value.shape[0] == end, f"Wrong daily dimension: {path}/{params[header]}")
                if params.get("function type") == "bilinear and time":
                    shape = (len(h[params["row header"]]), len(h[params["column header"]]))
                    require(h[params["value header"]]["0"].shape == shape,
                            f"Spatial coordinates disagree with field dimensions: {path}")
    require(len(referenced) == 6, "Expected six canonical model forcing references")
    doc, cn = files[-2:]
    with h5py.File(doc) as h:
        for i in range(end):
            total = h[DOC_KEY][str(i)][:]
            recovered = sum(h[f"DOC production {s} [mol m^-3 s^-1]"][str(i)][:] * c
                            for s, c in zip(SPECIES, CARBON))
            require(np.allclose(recovered, total, rtol=1e-10, atol=1e-25),
                    f"Source donor-carbon check failed at day {i}")
    with h5py.File(cn) as h:
        recovered = sum(h[f"{s} mol water basis [molS molH^-1]"][:] * c
                        for s, c in zip(SPECIES, CARBON))
        require(np.allclose(recovered, h[CN_KEY][:], rtol=1e-10, atol=1e-25),
                "Boundary donor-carbon check failed")
    require(float(child(parent, "cycle driver", "end time").get("value")) == start,
            "Prefire XML does not stop at the configured postfire start")
    return {"start_day": start, "end_day": end, "postfire_days": len(post),
            "forcing_files": [str(p.resolve()) for p in files],
            "terminal_policy": "Last sample at end_day - 1; ATS tabular/from-file readers hold it through end_day"}


def copy_mesh_with_first_layer(mesh_info, target):
    """Append an Exodus element set without rebuilding blocks or cell numbering."""
    original = Path(mesh_info["mesh_path"])
    element_ids = np.sort(mesh_info["top"] + 1).astype("i4")
    with netCDF4.Dataset(original) as src:
        require("num_elem_sets" not in src.dimensions,
                "Parent mesh already has element sets; inspect before appending the first-layer set")
        for name in src.variables:
            if name.endswith("_prop1"):
                require(2000 not in src[name][:], f"Element-set label 2000 conflicts with {name}")
    shutil.copy2(original, target)
    with netCDF4.Dataset(target, "r+") as mesh:
        mesh.createDimension("num_elem_sets", 1)
        mesh.createDimension("num_ele_els1", len(element_ids))
        mesh.createVariable("els_status", "i4", ("num_elem_sets",))[:] = [1]
        labels = mesh.createVariable("els_prop1", "i4", ("num_elem_sets",))
        labels.setncattr("name", "ID")
        labels[:] = [2000]
        names = mesh.createVariable("els_names", "S1", ("num_elem_sets", "len_name"))
        name = np.zeros((1, len(mesh.dimensions["len_name"])), dtype="S1")
        encoded = np.frombuffer(b"postfire-first-layer", dtype="S1")
        name[0, :len(encoded)] = encoded
        names[:] = name
        mesh.createVariable("elem_els1", "i4", ("num_ele_els1",))[:] = element_ids
    with netCDF4.Dataset(original) as src, netCDF4.Dataset(target) as dst:
        src.set_auto_mask(False)
        dst.set_auto_mask(False)
        require(src.data_model == dst.data_model, "Changed Exodus storage format")
        require(set(dst.dimensions) - set(src.dimensions) == {"num_elem_sets", "num_ele_els1"},
                "Unexpected new mesh dimensions")
        require(set(dst.variables) - set(src.variables) ==
                {"els_status", "els_prop1", "els_names", "elem_els1"}, "Unexpected new mesh variables")
        require(src.ncattrs() == dst.ncattrs(), "Changed global mesh attributes")
        for attr in src.ncattrs():
            require(np.array_equal(src.getncattr(attr), dst.getncattr(attr)), f"Changed mesh attribute {attr}")
        for name, dim in src.dimensions.items():
            require(len(dim) == len(dst.dimensions[name]) and
                    dim.isunlimited() == dst.dimensions[name].isunlimited(), f"Changed dimension {name}")
        for name, var in src.variables.items():
            other = dst[name]
            require(var.dtype == other.dtype and var.dimensions == other.dimensions and
                    np.array_equal(var[:], other[:]), f"Changed original mesh variable {name}")
            require(var.ncattrs() == other.ncattrs(), f"Changed attributes on {name}")
            for attr in var.ncattrs():
                require(np.array_equal(var.getncattr(attr), other.getncattr(attr)),
                        f"Changed attribute {name}/{attr}")
        require(np.array_equal(dst["elem_els1"][:], element_ids), "Incorrect first-layer set membership")
    return {"original": str(original), "original_sha256": digest(original),
            "copy": str(Path(target).resolve()), "copy_sha256": digest(target),
            "element_set_name": "postfire-first-layer", "element_set_label": 2000,
            "element_indices_1based": element_ids.tolist(),
            "original_mesh_content_unchanged": True}


def parameter(parent, name, kind, value):
    return ET.SubElement(parent, "Parameter", name=name, type=kind, value=str(value))


def scale_first_layer(xml, mesh_info, multiplier, mesh_reference=None):
    functions = child(xml, "state", "evaluators", "permeability", "function")
    regions = child(xml, "regions")
    top = set(mesh_info["top"].tolist())
    require(mesh_reference is not None, "A copied mesh with the first-layer element set is required")
    layer = ET.SubElement(regions, "ParameterList", name="postfire-first-layer", type="ParameterList")
    for name, kind, value in [("region type", "string", "labeled set"),
                              ("label", "string", "2000"), ("file", "string", mesh_reference),
                              ("format", "string", "Exodus II"), ("entity", "string", "CELL")]:
        parameter(layer, name, kind, value)
    changes = []
    for material in np.unique(mesh_info["materials"]):
        matched = [r for r in regions if any(p.get("name") == "label" and
                   p.get("value") == str(material) for p in r)]
        require(len(matched) == 1, f"Missing/ambiguous subsurface material {material}")
        name = matched[0].get("name")
        function = child(functions, name)
        baseline = float(child(function, "function", "value").get("value"))
        cells = np.flatnonzero(mesh_info["materials"] == material)
        upper = np.array([i for i in cells if i in top], int)
        deeper = np.array([i for i in cells if i not in top], int)
        changes.append({"material": name, "first_layer_cells": len(upper),
                        "deeper_cells": len(deeper), "prefire_k_m2": baseline,
                        "postfire_first_layer_k_m2": baseline * multiplier,
                        "burned_region": f"{name}-burned" if len(upper) else None,
                        "deeper_region": f"{name}-deeper" if len(upper) and len(deeper) else None})
        if not len(upper):
            continue
        position = list(functions).index(function)
        functions.remove(function)
        for suffix, subset, factor, operation in [("burned", upper, multiplier, "intersect"),
                                                  ("deeper", deeper, 1.0, "subtract")]:
            if not len(subset):
                continue
            region_name = f"{name}-{suffix}"
            region = ET.SubElement(regions, "ParameterList", name=region_name, type="ParameterList")
            parameter(region, "region type", "string", "logical")
            parameter(region, "operation", "string", operation)
            parameter(region, "regions", "Array(string)", f"{{{name}, postfire-first-layer}}")
            replacement = copy.deepcopy(function)
            replacement.set("name", region_name)
            child(replacement, "region").set("value", region_name)
            child(replacement, "function", "value").set("value", str(baseline * factor))
            functions.insert(position, replacement)
            position += 1
    require(sum(c["first_layer_cells"] for c in changes) == len(top), "Incomplete first-layer coverage")
    return changes


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def xml_values(root):
    out = {}
    def visit(node, path):
        path = path + (node.get("name", node.tag),)
        require(path not in out, f"Duplicate XML entry: {'/'.join(path)}")
        out[path] = dict(node.attrib)
        for sub in node:
            visit(sub, path)
    visit(root, ())
    return out


def generate_case(base_dir, config, scenario, severity_class, mesh_info,
                  forcing_report, burn_report, case_name=None):
    require(severity_class in SEVERITY, f"Choose one of {list(SEVERITY)}")
    require(scenario.isalnum(), "Scenario must be an alphanumeric folder suffix")
    code, multiplier = SEVERITY[severity_class]
    site, nx = config["case"]["site_name"], config["case"]["meshsize_nx"]
    source = base_dir / f"caselambda-run2-prefire.{scenario}"
    require(case_name is None or Path(case_name).name == case_name,
            "Case name must be a single folder name")
    target = base_dir / (case_name or f"caselambda-run2-postfire.{scenario}")
    stem = f"{site}_nx{nx}_nz{mesh_info['nz']}.run2.v1.6_pflotran"
    restart = f"../../caselambda-run2-prefire.{scenario}/{site}/checkpoint_final.h5"
    checkpoint = source / site / "checkpoint_final.h5"
    checkpoint_time = None
    if checkpoint.exists():
        with h5py.File(checkpoint) as h:
            require("time" in h.attrs, "Checkpoint is missing ATS time attribute")
            checkpoint_time = float(np.asarray(h.attrs["time"]).item()) / 86400
        require(np.isclose(checkpoint_time, forcing_report["start_day"], rtol=0, atol=1e-8),
                "Checkpoint time does not match postfire start")
    target.mkdir(exist_ok=True)
    original_mesh = Path(mesh_info["mesh_path"])
    # Use the same region structure for every class, including factor-1 low/no-low.
    copied_mesh = target / f"{original_mesh.stem}.postfire-first-layer.exo"
    mesh_report = copy_mesh_with_first_layer(mesh_info, copied_mesh)
    mesh_reference = f"../{copied_mesh.name}"
    generated = []
    for suffix in (".xml", ".obs4massflux.xml"):
        parent_path = source / (stem + suffix)
        parent = ET.parse(parent_path).getroot()
        root = copy.deepcopy(parent)
        child(root, "cycle driver", "start time").set("value", str(forcing_report["start_day"]))
        child(root, "cycle driver", "end time").set("value", str(forcing_report["end_day"]))
        restart_nodes = [e for e in root.iter("Parameter") if e.get("name") in
                         ("restart file", "restart from checkpoint file")]
        require(restart_nodes, "Parent XML has no restart references")
        for node in restart_nodes:
            node.set("value", restart)
        if mesh_reference is not None:
            for node in root.iter("Parameter"):
                if node.get("name") == "file" and node.get("value", "").endswith(".exo"):
                    resolved = (source / site / node.get("value")).resolve()
                    require(resolved == original_mesh.resolve(), f"Unexpected mesh reference: {resolved}")
                    node.set("value", mesh_reference)
        permeability = scale_first_layer(root, mesh_info, multiplier, mesh_reference)
        before, after = xml_values(parent), xml_values(root)
        differences = [{"path": "/".join(p), "before": before.get(p), "after": after.get(p)}
                       for p in sorted(before.keys() | after.keys()) if before.get(p) != after.get(p)]
        for change in differences:
            path = change["path"]
            require(path.endswith(("/cycle driver/start time", "/cycle driver/end time",
                                   "/restart file", "/restart from checkpoint file")) or
                    ("/state/evaluators/permeability/function/" in path or
                                         "/regions/" in path and
                                         ("postfire-first-layer" in path or "-burned" in path or "-deeper" in path) or
                                         path.endswith("/file") and change["before"] is not None and
                                         change["before"].get("value", "").endswith(".exo") and
                                         change["after"]["value"] == mesh_reference),
                    f"Unexpected XML change: {path}")
        generated.append((parent_path, target / parent_path.name, root, differences))
    # Always clone parent inputs; never run ATS or change parent files.
    (target / site).mkdir(exist_ok=True)
    shutil.copytree(source / "reactions", target / "reactions", dirs_exist_ok=True)
    reaction_hashes = {}
    source_reactions = {p.relative_to(source / "reactions") for p in (source / "reactions").rglob("*") if p.is_file()}
    target_reactions = {p.relative_to(target / "reactions") for p in (target / "reactions").rglob("*") if p.is_file()}
    require(source_reactions == target_reactions, "Unexpected files in target reactions directory")
    for relative in sorted(source_reactions):
        require(digest(source / "reactions" / relative) == digest(target / "reactions" / relative),
                f"Reaction copy differs: {relative}")
        reaction_hashes[str(relative)] = digest(source / "reactions" / relative)
    for _, output, root, _ in generated:
        ET.indent(root, space="  ")
        ET.ElementTree(root).write(output, encoding="UTF-8", xml_declaration=False)
    report = {**forcing_report, "severity_selected": severity_class, "severity_code": code,
              "severity_map": burn_report, "severity_disagrees_with_map": code != burn_report["dominant_class"],
              "permeability_multiplier": multiplier, "first_layer_thickness_m": mesh_info["thickness_m"],
              "permeability": permeability, "config": config, "restart_path": restart,
              "checkpoint_present": checkpoint.exists(), "checkpoint_time_day": checkpoint_time,
              "configuration_valid": True, "restart_smoke_test": "not run",
              "runtime_ready": False,
              "readiness": "checkpoint verified; short restart verification still required" if checkpoint.exists()
                           else "pending prefire checkpoint and short restart verification",
              "mesh": mesh_report,
              "region_definitions": [dict(e.attrib, parameters={p.get("name"): p.get("value")
                                     for p in e if p.tag == "Parameter"})
                                     for e in child(generated[0][2], "regions")
                                     if e.get("name") == "postfire-first-layer" or
                                     e.get("name", "").endswith(("-burned", "-deeper"))],
              "reaction_sha256": reaction_hashes,
              "xml": [{"parent": str(p), "parent_sha256": digest(p), "output": str(o),
                       "output_sha256": digest(o), "changes": d} for p, o, _, d in generated]}
    (target / "postfire_configuration_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return target, report
