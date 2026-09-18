# S04S10 ATS–PFLOTRAN notebook workflow

This directory builds a two-dimensional Naches hillslope ending at a known stream location, then adds the S04_SED-1 10-bin lambda-PFLOTRAN reaction model. The active case is `S04S10`.

Site selection and transect delineation require human judgement. Review the maps, heads, drainage area, and hillslope geometry before proceeding.

## Guidance for users and agents

Run notebooks from this directory so their relative paths resolve correctly. Do not run the sequence blindly or overwrite a selected hillslope merely because an earlier notebook can be re-run. Before each downstream stage, confirm that upstream geometry, forcing files, and XML inputs are for `S04S10` and match the dates in `config.json`.

For an AI agent, inspect the selected-hillslope output and required HDF5/XML inputs before modifying or running a downstream notebook. The lambda and cybernetic reaction workflows are alternatives; do not combine their outputs.

## Configuration

[`config.json`](config.json) is the shared source of basic case inputs. Changing it changes derived HDF5 filenames, model run directories, and time periods expected by later notebooks.

| Setting | Current value | Role |
| --- | --- | --- |
| `watershed_name`, `hucs`, `site_name` | `Naches`, `17030002`, `S04S10` | Identifies the watershed and hillslope case. |
| `meshsize_nx` | `100` | Number of along-hillslope cells in the 2D mesh. |
| `start_year_spinup`, `end_year_spinup` | `2011`–`2015` | Typical-year forcing period used for spinup. |
| `nyears_steadystate_spinup`, `nyears_cyclic_spinup` | `10`, `10` | Hydrologic steady-state and cyclic-spinup durations. |
| `start_year_transient`, `end_year_transient` | `2016`–`2020` | Transient forcing and simulation period. |
| `elm_run` | `2024-07-14-142626` | ELM realization used by DOC processing. |

## Primary lambda workflow

### 1. Select and review the stream endpoint

Run [`site_selection.Naches.v4.s1-latloninput.ipynb`](site_selection.Naches.v4.s1-latloninput.ipynb), then [`site_selection.Naches.v4.s2-checkBChead.ipynb`](site_selection.Naches.v4.s2-checkBChead.ipynb).

- The first notebook produces local views of the river network, DEM, burn severity, and LAI change around user-provided latitude/longitude locations.
- The second plots 3D ATS ponded-water-depth/head information around candidate stream endpoints.

Together, these provide an expectation for the physically plausible hillslope direction before a transect is selected.

### 2. Delineate and approve the hillslope transect

Run [`0a-transect_latlon.Naches.v4.D8.ipynb`](0a-transect_latlon.Naches.v4.D8.ipynb). It uses D8 analysis to delineate the drainage area associated with the chosen river segment and identify a candidate hillslope start point. This is an interactive review step, not a fully automatic selector.

Then run [`0b-checkBChead.Naches.v4.s1-2.ipynb`](0b-checkBChead.Naches.v4.s1-2.ipynb). With the candidate start point, endpoint, and DEM-derived shape known, it checks start/end water-head boundary conditions. Use this review to decide whether the hillslope location or geometry needs adjustment before generating the production case.

**Handoff:** approved hillslope coordinates, transect geometry, and selected start/end metadata under `data-processed/S04S10/`.

### 3. Build hydrologic forcing

Complete these preprocessing notebooks after approving the transect.

- Run only the applicable 3D ATS extraction notebooks among [`get_BChead.Naches.s1-0.ipynb`](get_BChead.Naches.s1-0.ipynb), [`get_BChead.Naches.s1-1.ipynb`](get_BChead.Naches.s1-1.ipynb), [`get_BChead.Naches.s1-2.ipynb`](get_BChead.Naches.s1-2.ipynb), and [`get_BChead.Naches.s1-3.ipynb`](get_BChead.Naches.s1-3.ipynb), according to the available 3D ATS time segment. Then run [`get_BChead.Naches.s2.ipynb`](get_BChead.Naches.s2.ipynb) to concatenate spinup and transient boundary-head results using `config.json` dates.
- Run [`get_Daymet.daymet.ipynb`](get_Daymet.daymet.ipynb) for DayMet forcing and [`get_MODIS-LAI.ipynb`](get_MODIS-LAI.ipynb) for LAI forcing.
- Run [`ELM_outputs_process/get_docflux_from_ELM_3D.ipynb`](ELM_outputs_process/get_docflux_from_ELM_3D.ipynb) to create total-DOC injection and boundary-concentration forcing from ELM.

**Handoff:** start/end head HDF5 files, meteorology, LAI, and unbinned total-DOC/CN boundary HDF5 files in `data-processed/S04S10/`.

### 4. Generate the ATS 1.5 hydrologic case

Run [`1a-main_workflow_Naches.ats1.5.ipynb`](1a-main_workflow_Naches.ats1.5.ipynb). It creates the 2D hillslope mesh and ATS 1.5 hydrologic configuration. It intentionally stops partway through so required `get_*` preprocessing can be run. After completing prerequisites, inspect the expected HDF5 files, ignore the earlier intentional interruption, and continue from the appropriate later cells.

The ATS 1.5 templates used by this stage are:

- `caseflow-steadystate-template.ats1.5.xml` for run 0;
- `caseflow-cyclic_steadystate-template.ats1.5.xml` for run 1; and
- `caseflow-transient-template.ats1.5.xml` for run 2.

**Handoff:** ATS 1.5 flow XML files and `caseflow-run0`, `caseflow-run1`, and `caseflow-run2` directories.

### 5. Convert flow XML to ATS 1.6

Run [`1b-convert_atsflow_xml.ipynb`](1b-convert_atsflow_xml.ipynb). It converts flow XML files to ATS 1.6 (`*.v1.6.xml`), completing the integrated surface–subsurface hydrologic configuration used by the coupled chemistry workflow.

**Handoff:** ATS 1.6 flow XML inputs.

### 6. Add S04_SED-1 lambda-PFLOTRAN chemistry

Run [`2-add_reaction_lambda.ipynb`](2-add_reaction_lambda.ipynb). It uses `atspflotranutils/pflotranate_2d_lambda/` to create ATS–PFLOTRAN XML for the S04_SED-1 lambda network with ten donor bins:

`C38`, `C35`, `C29`, `C27`, `C25`, `C23`, `C20`, `C19`, `C18`, and `C13`.

The notebook partitions total DOC as equal molC shares (one tenth per bin), then converts each share to mol species with S04 average carbon counts. It adds donor fields to spinup forcing for run 1 and writes them to merged spinup/transient forcing for run 2.

**Handoff:** `caselambda-run1` and `caselambda-run2` ATS–PFLOTRAN XML files; spinup and merged DOC-source/CN-boundary HDF5 files containing all ten donor headers.

### 7. Configure outlet observations

Run [`3-configure_obs_for_boundary_mass_flux.lambda.ipynb`](3-configure_obs_for_boundary_mass_flux.lambda.ipynb) on the lambda run-2 XML. It adds outlet-column observations for boundary-face water flux and adjacent-cell component concentrations.

It does not directly output carbon mass flux. Calculate it afterward from the water flux, donor concentrations, and the S04 carbon counts for the ten bins.

**Handoff:** `*.obs4massflux.xml` for the ATS–PFLOTRAN run and observation output files.

## Runtime environments and external data

This workflow spans two ATS generations:

- **watershed-workflow 1.5 with ATS 1.5:** selection, transect setup, and the ATS 1.5 hydrologic case in notebook 1a.
- **watershed-workflow 2.0 with ATS 1.6:** XML conversion and the ATS–PFLOTRAN preparation/observation notebooks (1b, 2, and 3).

The notebooks use `amanzi_xml`; when it is not importable directly, they expect `AMANZI_SRC_DIR` to locate its tools. Boundary-head selection and processing require read access to the NERSC 3D ATS output referenced in the `get_BChead` notebooks. DayMet, MODIS, and ELM processing require their respective downloaded/raw inputs or prior processed products.

## Optional and reference notebooks

- [`get_Daymet.aorc.ipynb`](get_Daymet.aorc.ipynb) is an alternate meteorology path; use it instead of, not in addition to, the DayMet path when appropriate.
- `modes/legacy-site-selection/` contains earlier/reference site-selection workflows and is not part of the active v4 S04S10 sequence.
- `modes/cybernetic-reaction/` is a different reaction-mode workflow. Do not mix its chemistry configuration or outputs with the lambda workflow.
