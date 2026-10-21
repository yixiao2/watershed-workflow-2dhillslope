# S04S10 ATS–PFLOTRAN prefire/postfire notebook workflow

This directory builds the two-dimensional S04S10 Naches hillslope ending at a
reviewed stream location, generates ATS hydrologic inputs, and prepares the
S04_SED-1 ten-bin lambda-PFLOTRAN reaction model. The shared configuration is
schema-v2 [`config.json`](config.json).

Site selection and transect delineation require human judgement. Review maps,
heads, drainage area, and hillslope geometry before producing a case. Do not
re-run a selection notebook blindly or overwrite an approved hillslope.

## Guidance for users and agents

Run notebooks from this directory so relative paths resolve correctly. Before a
downstream stage, confirm that its geometry, HDF5 forcing, XML inputs, case name,
and phase dates agree with `config.json`.

For an AI agent, inspect the approved hillslope output and every required
HDF5/XML input before modifying or running a downstream notebook. The lambda
and cybernetic reaction workflows are alternatives: never mix their chemistry
configuration, forcing products, XML files, or outputs.

## Configuration: schema-v2

[`config.json`](config.json) is the authoritative source for case identity,
calendar, forcing periods, spinup durations, and ELM provenance. It must use
`"schema_version": 2` and `"calendar": "noleap"`; dates are inclusive ISO
dates and Feb. 29 is excluded. `spinup` and `prefire_transient` are required;
`postfire_transient` is optional for a prefire-only case. Adjacent configured
phases must be contiguous.

| Block / setting | Current value | Role |
| --- | --- | --- |
| `case` | `Naches`, `17030002`, `S04S10`, `meshsize_nx: 100` | Watershed, HUC, case identifier, and along-hillslope mesh cells. |
| `spinup.source_period` | 2012-10-01 to 2017-09-30 | Five source water years used to construct representative spinup forcing. |
| `spinup.steady_state_years`, `spinup.cyclic_years` | 10, 10 | Hydrologic steady-state and cyclic-spinup durations. |
| `spinup.elm_run` | `2024-07-14-142626` | ELM realization for spinup DOC processing. |
| `prefire_transient` | 2017-10-01 to 2021-08-03; ELM `2024-07-14-142626` | Prefire transient phase. |
| `postfire_transient` | 2021-08-04 to 2023-10-01; ignition-day ELM `2024-08-27-132724`; ELM `2024-11-20-210107` | Configured postfire phase and ELM provenance. |
| `elm_root` | `/pscratch/sd/x/xiao284/elmbyhuilin/elm` | Root containing phase-specific ELM outputs. |

The phase sequence for the current case is:

```text
2012-10-01..2017-09-30  spinup source forcing
        -> 10-year cyclic spinup
        -> 2017-10-01..2021-08-03  prefire transient
        -> checkpoint / restart
        -> 2021-08-04..2023-10-01  postfire transient
```

Phase-local forcing records date provenance under
`data-processed/S04S10/forcing/baseline/`. The canonical model-facing directory
is `full_timeline_spinup10y_prefire_postfire`. The prefire coupled run reads that
timeline but ends after cyclic spinup plus the prefire period; it does not
simulate the postfire tail. Postfire reactive runs continue the same canonical clock and restart from the final
prefire checkpoint. With the default phase dates, postfire starts at day 5052
and ends at day 5841; the final forcing sample at day 5840 is held through
the end time. Do not reset the forcing clock to zero.

## Primary lambda workflow

### 1. Select and review the stream endpoint

Run [`site_selection.Naches.v4.s1-latloninput.ipynb`](site_selection.Naches.v4.s1-latloninput.ipynb), then
[`site_selection.Naches.v4.s2-checkBChead.ipynb`](site_selection.Naches.v4.s2-checkBChead.ipynb).

- The first notebook creates local views of the river network, DEM, burn
  severity, and LAI change around supplied latitude/longitude locations.
- The second plots 3D ATS ponded-water-depth/head information near candidate
  stream endpoints.

Use these results to establish a physically plausible hillslope direction.

### 2. Delineate and approve the hillslope transect

Run [`0a-transect_latlon.Naches.v4.D8.ipynb`](0a-transect_latlon.Naches.v4.D8.ipynb), which uses D8 analysis to delineate the drainage area for the selected river segment and propose a hillslope start point. Then run
[`0b-checkBChead.Naches.v4.s1-2.ipynb`](0b-checkBChead.Naches.v4.s1-2.ipynb) to review start/end water-head boundary conditions against the candidate geometry.

This is an approval step, not an automatic selector. Adjust the location or
geometry if the review indicates it is needed.

**Handoff:** approved coordinates, transect geometry, and selected start/end
metadata in `data-processed/S04S10/`.

### 3. Build phase-aware hydrologic and biogeochemical forcing

Complete preprocessing only after the transect is approved.

- Run the applicable 3D ATS extraction notebooks among
  [`get_BChead.Naches.s1-0.ipynb`](get_BChead.Naches.s1-0.ipynb),
  [`get_BChead.Naches.s1-1.ipynb`](get_BChead.Naches.s1-1.ipynb),
  [`get_BChead.Naches.s1-2.ipynb`](get_BChead.Naches.s1-2.ipynb), and
  [`get_BChead.Naches.s1-3.ipynb`](get_BChead.Naches.s1-3.ipynb), according to
  the available 3D ATS segment. Then run
  [`get_BChead.Naches.s2.ipynb`](get_BChead.Naches.s2.ipynb) to assemble the
  schema-v2 phase products.
- Run [`get_Daymet.daymet.ipynb`](get_Daymet.daymet.ipynb) for meteorology and
  [`get_MODIS-LAI.ipynb`](get_MODIS-LAI.ipynb) for LAI. Both write phase-local
  products and the canonical merged timeline. Inspect and clean implausible LAI
  spikes before saving the local daily series.
- Run
  [`ELM_outputs_process/get_docflux_from_ELM_3D.ipynb`](ELM_outputs_process/get_docflux_from_ELM_3D.ipynb)
  to create phase-specific total-DOC injection and boundary-concentration
  forcing from the configured ELM runs.

**Handoff:** start/end head HDF5, meteorology, LAI, and unbinned total-DOC/CN
boundary HDF5 products in the case forcing tree. Keep baseline products as
total-carbon inputs; lambda donor-bin datasets are written later as separate
copies.

### 4. Generate the ATS 1.5 hydrologic case

Run [`1a-main_workflow_Naches.ats1.5.ipynb`](1a-main_workflow_Naches.ats1.5.ipynb). It creates the 2D mesh and ATS 1.5 hydrologic configuration. It intentionally stops partway through so preprocessing can be completed. Inspect the expected forcing files, then resume from the appropriate later cells rather than treating that interruption as an error.

The ATS 1.5 templates are:

- `caseflow-steadystate-template.ats1.5.xml` for run 0;
- `caseflow-cyclic_steadystate-template.ats1.5.xml` for run 1; and
- `caseflow-transient-template.ats1.5.xml` for run 2 (the prefire transient).

**Handoff:** flow XML files and `caseflow-run0`, `caseflow-run1`, and
`caseflow-run2` directories. Run 0 is steady state, run 1 is cyclic spinup, and
run 2 ends at the configured prefire end date.

### 5. Convert flow XML to ATS 1.6

Run [`1b-convert_atsflow_xml.ipynb`](1b-convert_atsflow_xml.ipynb). It converts
the flow XML files in the three `caseflow-run*` directories to ATS 1.6
(`*.v1.6.xml`), which the coupled chemistry preparation uses.

**Handoff:** ATS 1.6 flow XML inputs.

### 6. Add S04_SED-1 lambda-PFLOTRAN chemistry

Run [`2-add_reaction_lambda.ipynb`](2-add_reaction_lambda.ipynb). It uses
`atspflotranutils/pflotranate_2d_lambda/` to create ATS–PFLOTRAN inputs for the
S04_SED-1 lambda network with ten donor bins:

`C38`, `C35`, `C29`, `C27`, `C25`, `C23`, `C20`, `C19`, `C18`, and `C13`.

The notebook partitions total DOC into equal molC shares (one tenth per bin),
then converts each share to mol species using the S04 average carbon counts. It
writes lambda-ready copies of the forcing, leaving baseline total-carbon files
unchanged. It configures reactive cyclic spinup (`caselambda-run1.<scenario>`) and the
prefire transient (`caselambda-run2-prefire.<scenario>`). The cyclic case is
`caselambda-run1.<scenario>`. Both the prefire initial-condition restart and
cycle-driver restart point to the final reactive cyclic-spinup checkpoint.
Notebook 4 creates the postfire restart XML.

**Handoff:** lambda ATS–PFLOTRAN XML files (`*.v1.6_pflotran.xml`) and separate
full-timeline DOC-source and CN-boundary HDF5 products containing all ten donor
headers, under the canonical forcing directory’s `lambda/` subdirectory.

### 7. Configure outlet observations

Run
[`3-configure_obs_for_boundary_mass_flux.lambda.ipynb`](3-configure_obs_for_boundary_mass_flux.lambda.ipynb)
on the lambda run-2 XML. It adds outlet-column observations for boundary-face
water flux and adjacent-cell component concentrations.

It does not directly write carbon mass flux. Calculate that afterward from
water flux, donor concentrations, and the S04 carbon counts for the ten bins.

**Handoff:** `*.obs4massflux.xml` and the resulting observation output files.

## Postfire and artificial scenario stages

### 8. Configure realistic postfire (notebook 4)

Run `4-configure_postfire_lambda.ipynb` after notebooks 2 and 3. It reviews the
selected transect against MTBS, plots canonical LAI/DOC, and creates
`caselambda-run2-postfire.<scenario>` from both prefire XML variants and their
reaction files. Actual LAI/DOC already include fire effects and receive no
additional multiplier. Severity defaults to low; the explicit selection remains
authoritative if it differs from the map-derived dominant class.

All severities copy the original Exodus mesh and add element set 2000 for the
surface-adjacent subsurface cells. The first layer must be 0.05 m thick. Exactly
nx cells are identified from connectivity and the surface side set, independent
of material ordering. Existing set-label conflicts are rejected. Original mesh
content, observations, chemistry, other material properties, and deeper
permeability remain unchanged. First-layer factors are no-low/low ×1,
moderate ×0.40, and high ×0.20; retain these scientific assumptions when changing
mesh resolution. The vegetation crosswalk and chemistry remain specific to the
S04S10 lambda model; arbitrary meshes or vegetation systems are not supported
merely by changing the site name.

### 9. Analyze and generate artificial scenarios (notebook 5)

Run `5-configure_artificial_fire_lambda.ipynb` after notebook 3 (notebook 4 is
recommended for review, but its generated case is not an input dependency).
Native MODIS pixels and paired ELM cells are classified inside the configured
fire perimeter. MODIS uses the year preceding postfire start for land cover
and the three preceding complete years for its seasonal reference. Preserve the
Evergreen Forest/MODIS 1 and Shrub Scrub/MODIS 10 crosswalk.

The seasonal response uses the first 365 no-leap days from configured postfire
start. Existing rules remain: LAI reference >=0.2; response bounds [0.05,2];
DOC near-zero threshold 10^-6 of each class's positive no-fire median; 2000
spatial-block bootstrap replicates with seed 42 and at least five blocks;
low-effect evidence requires a >=10% effect and a 95% interval excluding 1.
Missing class support is not filled with invented patterns. Only genuinely
dormant LAI months can receive the existing factor-1 fallback.

- **A0:** repeat the observed complete baseline year (default 2021), factor-1
  permeability. The default year includes the actual fire; A0 is not a no-fire
  counterfactual.
- **A1:** low severity, generated only when effect/uncertainty and seasonal
  support criteria pass; permeability ×1.
- **A2/A3:** supported moderate/high seasonal patterns, first-layer permeability
  ×0.40/×0.20. Unsupported cases are omitted with reasons.

Cases are named `caselambda-run2-artificial-A0.<scenario>` through A3. Each has
isolated full-timeline LAI/DOC copies; prefire samples, weather, heads, unrelated
solutes, and clocks are unchanged. DOC source and boundary multipliers agree,
and the ten donor bins preserve equal carbon shares. Seasonal responses repeat
without recovery, even though the analysis also displays recovery diagnostics.
Reports and figures remain case-local outputs.

### Optional schema-v2 fire settings

Existing configurations need no migration. Add a `fire_workflow` object to
`config.json` to override defaults. All relative source paths resolve from the
case root, regardless of notebook working directory. Example settings:

```json
{
  "scenario": "s1",
  "severity": "low",
  "burn_raster": "../../MaterialsData/MTBS_fire_WA_2021/MTBS_fire_shp_files/2021/wa4684012114620210804/wa4684012114620210804_20210725_20220728_dnbr6.tif",
  "perimeter": "../../MaterialsData/MTBS_fire_WA_2021/MTBS_fire_shp_files/2021/wa4684012114620210804/wa4684012114620210804_20210725_20220728_burn_bndy.shp",
  "modis_lai": "notebooks/MODIS_raw/Naches/Naches-square/MCD15A3H.061_500m_aid0001.nc",
  "modis_landcover": "notebooks/MODIS_raw/Naches/Naches-square/MCD12Q1.061_500m_aid0001.nc",
  "fire_elm_run": "2024-11-20-210107",
  "nofire_elm_run": "2024-11-20-220109",
  "artificial_baseline_year": 2021
}
```

The example object is the **value of `fire_workflow`**, not a replacement for
the full config. Scenario defaults to s1 and is shared by notebooks 2–5. The
fire ELM realization defaults to `postfire_transient.elm_run`; no-fire defaults
to the realization above. MTBS and MODIS defaults are the S04S10 inputs shown.
`elm_root` remains a top-level setting and is also resolved from the case root.
Notebook 4 validates its raster input; notebook 5 additionally requires the
perimeter, MODIS files, paired ELM directories, and complete baseline-year
coverage in canonical forcing. Missing paired ELM days are recorded in QC;
insufficient seasonal support blocks the corresponding severity case.
Prefire-only configs remain valid for upstream stages; stages 4–5 require
`postfire_transient`.

### Regeneration, testing, and runtime acceptance

From any working directory, run `bash /path/to/repo/prepare_dev_test.sh /new/case`
to create a fresh workspace with helpers, tests, documentation, templates, and
external-data symlinks. The destination must not already exist. Supply approved
geometry and forcing, edit case-local config, and run notebooks from its
`notebooks/` directory. Lambda run directories are generated by the notebooks;
archived cybernetic cases are not copied. Never regenerate inside a running
case. Stages 4–5 always clone prefire inputs, avoiding compounded scaling.

Use the watershed-workflow 2.0 Python environment with `amanzi_xml`, NumPy,
SciPy, pandas, h5py, netCDF4, xarray/cftime, rasterio, geopandas, shapely,
pyproj, matplotlib, and IPython. Loading the existing site-selection pickle
also requires Fiona, because it contains a serialized Fiona CRS object. The
installed 2.0 environment lacks Fiona; use an environment with this dependency
for stages 4–5. The existing 1.5 environment can run these stages when its
`PROJ_DATA` points to its own `share/proj` directory. Upstream ATS 1.6 conversion
and the portable restart test still require `amanzi_xml` in the 2.0 environment.

```bash
# Portable suite, from the repository root; real-case tests skip by default.
python -m unittest discover -s notebooks -p 'test_*fire*.py' -v
# Real-case integration: every write goes to temporary directories.
NACHES_CASE_ROOT=/path/to/reference-case python -m unittest discover -s notebooks -p 'test_*fire*.py' -v
# Optional native Exodus-reader check also requires an explicit library:
NACHES_CASE_ROOT=/path/to/reference-case MSTK_LIBRARY=/path/to/libmstk.so python -m unittest discover -s notebooks -p 'test_*fire*.py' -v
```

Run 2 prefire restarts from `../../caselambda-run1.<scenario>/<site>/checkpoint_final.h5`;
postfire and artificial cases restart from
`../../caselambda-run2-prefire.<scenario>/<site>/checkpoint_final.h5`, relative
to the target site's execution directory. If present, checkpoint time must
match configured phase start. A missing checkpoint permits configuration
review, but generated reports keep `runtime_ready` false.

A short ATS/PFLOTRAN restart remains a separate acceptance step: use identical
MPI ranks/partition settings and verify pressure, saturation, canopy/snow and
reactive-state continuity, correct forcing time, first-layer permeability,
unchanged deeper permeability, and water balance. Configuration/mesh tests do
not establish runtime compatibility. These notebooks do not launch simulations.

## Runtime environments and external data

The workflow spans two ATS generations:

- **watershed-workflow 1.5 with ATS 1.5:** geometry setup and the hydrologic
  case in notebook 1a.
- **watershed-workflow 2.0 with ATS 1.6:** XML conversion, lambda preparation,
  and observation configuration (notebooks 1b, 2, and 3).

Notebooks use `amanzi_xml`; if it is not importable directly, they expect
`AMANZI_SRC_DIR` to locate its tools. Boundary-head processing requires access
to the referenced NERSC 3D ATS output. DayMet, MODIS, and ELM stages require
their downloaded/raw inputs or the corresponding prior processed products.

## Optional and reference notebooks

- [`get_Daymet.aorc.ipynb`](get_Daymet.aorc.ipynb) is an older alternate
  meteorology path. It still uses legacy top-level configuration keys, so do not
  use it with schema-v2 without migrating it; use the DayMet notebook above for
  this case.
- `modes/legacy-site-selection/` contains earlier/reference selection workflows
  and is not part of the active v4 S04S10 sequence.
- `modes/cybernetic-reaction/` is a different reaction-mode workflow. Do not
  combine it with the lambda workflow.
