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
simulate the postfire tail. A future postfire reactive run must use local,
zero-based postfire forcing and restart from the final prefire checkpoint.

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
unchanged. It configures reactive cyclic spinup (`caselambda-run1`) and the
prefire transient (`caselambda-run2`); a postfire restart XML is deliberately
not created by this notebook.

**Handoff:** lambda ATS–PFLOTRAN XML files (`*.v1.6_pflotran.xml`) and separate
spinup/prefire DOC-source and CN-boundary HDF5 products containing all ten donor
headers.

### 7. Configure outlet observations

Run
[`3-configure_obs_for_boundary_mass_flux.lambda.ipynb`](3-configure_obs_for_boundary_mass_flux.lambda.ipynb)
on the lambda run-2 XML. It adds outlet-column observations for boundary-face
water flux and adjacent-cell component concentrations.

It does not directly write carbon mass flux. Calculate that afterward from
water flux, donor concentrations, and the S04 carbon counts for the ten bins.

**Handoff:** `*.obs4massflux.xml` and the resulting observation output files.

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
