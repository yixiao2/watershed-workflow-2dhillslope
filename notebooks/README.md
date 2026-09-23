# S04S10 prefire/postfire workflow

This case uses schema-v2 `config.json`. Dates are inclusive ISO dates on a
no-leap calendar. `spinup` and `prefire_transient` are required;
`postfire_transient` is optional, so a prefire-only case omits that block.

```text
2012-10-01..2017-09-30 spinup forcing
  -> 2017-10-01..2021-08-03 prefire transient
  -> checkpoint/restart
  -> 2021-08-04..2023-10-01 postfire transient
```

The prefire coupled run retains merged cyclic-spinup + prefire forcing. The
postfire run uses phase-local forcing whose time axis starts at zero and the
final prefire checkpoint. `elm_root` and each phase's `elm_run` record the
ELM source.
