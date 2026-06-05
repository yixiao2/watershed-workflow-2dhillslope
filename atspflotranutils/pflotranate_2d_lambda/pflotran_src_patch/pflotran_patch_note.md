## recompile

**Recommended procedure after editing PFLOTRAN source**
### 1. replace the build-tree PFLOTRAN source

source code for PFLOTRAN LAMBDA Reaction Sandbox:

```text
amanzi_tpls-build-master-Release/pflotran/pflotran-5.0.0-source/src/pflotran/reaction_sandbox_pnnl_lambda.F90
```

### 2. Remove stale PFLOTRAN object/library

For a source file like `reaction_sandbox_pnnl_lambda.F90`, remove the corresponding object and old library in the PFLOTRAN build tree:

```bash
rm -f amanzi_tpls-build-master-Release/pflotran/pflotran-5.0.0-source/src/pflotran/reaction_sandbox_pnnl_lambda.o
rm -f amanzi_tpls-build-master-Release/pflotran/pflotran-5.0.0-source/src/pflotran/libpflotranchem.a
```

### 3. Remove PFLOTRAN SuperBuild stamp files

From the TPL build directory, e.g.:

```bash
cd /path/to/ats/amanzi_tpls-build-master-Release
```

remove:

```bash
rm -f pflotran/pflotran-timestamps/pflotran-build \
      pflotran/pflotran-timestamps/pflotran-install \
      pflotran/pflotran-timestamps/pflotran-done
```

This forces the SuperBuild to rerun PFLOTRAN build/install.

### 4. Remove Alquimia build/cache/stamp files

Because ATS uses Alquimia to interface with PFLOTRAN, after changing and reinstalling PFLOTRAN it is safer to also force Alquimia to reconfigure/rebuild. This avoids stale Alquimia configuration or stale links to the old PFLOTRAN/PETSc state.

From the same TPL build directory:

```bash
cd /path/to/ats/amanzi_tpls-build-master-Release
```

remove:

```bash
rm -rf alquimia/alquimia-1.2.0-build
rm -f alquimia/alquimia-timestamps/alquimia-configure \
      alquimia/alquimia-timestamps/alquimia-build \
      alquimia/alquimia-timestamps/alquimia-install \
      alquimia/alquimia-timestamps/alquimia-done
```

### 5. recompile ATS again
```
cd $AMANZI_SRC_DIR
sh build_ATS_generic.sh
```

