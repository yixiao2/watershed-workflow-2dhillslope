# S04_SED-1 lambda forcing contract

This package uses the S04_SED-1 medoid 10-bin network.  Its donor species,
in bin order, are:

`C38-DONOR`, `C35-DONOR`, `C29-DONOR`, `C27-DONOR`, `C25-DONOR`,
`C23-DONOR`, `C20-DONOR`, `C19-DONOR`, `C18-DONOR`, and `C13-DONOR`.

The notebook `notebooks/2-add_reaction_lambda.ipynb` reads these total-DOC
S04S10 inputs:

- `../../data-processed/S04S10/S04S10_DOC_source_spinup_10yr_2011_2015_fdom001.h5`
- `../../data-processed/S04S10/S04S10_CNbc_conc_spinup_10yr_2011_2015_fdom001_k15.h5`

It adds the ten donor fields to the spinup inputs for run 1 and writes the
same fields to the merged spinup/transient files for run 2. It preserves the
existing source/boundary HDF5 time and spatial axes, units, and file layout.
The source fields are `DOC production <DONOR> [mol m^-3 s^-1]`; boundary
fields are `<DONOR> mol water basis [molS molH^-1]`.

The notebook allocates total DOC as equal molC shares (1/10 per donor), then
converts to mol species using the S04_SED-1 average carbon counts. It replaces
any existing legacy donor fields rather than renaming C28...C10 fields.

The kinetic constants are the NSE-selected S04_SED-1 posterior realization
R18.  `k_deg = 0` and the NH4 smoothstep threshold of `1e-8 M` remain ATS
assumptions: the calibration held `k_deg` and `C_inhibit` inactive.
