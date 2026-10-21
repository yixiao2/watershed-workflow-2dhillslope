"""Focused spatial, cyclic-clock, ratio-support, and forcing-conservation tests."""
from pathlib import Path
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import h5py
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

import artificial_fire_utils as u
from config_utils import load_config
import postfire_utils as p

CASE_SETTING=os.environ.get("NACHES_CASE_ROOT")
CASE=Path(CASE_SETTING).resolve() if CASE_SETTING else None


class ArtificialFireTests(unittest.TestCase):
    def test_exact_intersections_ignore_invalid_codes_and_resolve_ties(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"classes.tif"
            with rasterio.open(path,"w",driver="GTiff",height=1,width=4,count=1,
                               dtype="uint8",transform=from_origin(0,1,1,1),crs="EPSG:5070") as h:
                h.write(np.array([[1,4,5,0]],dtype="uint8"),1)
            with rasterio.open(path) as h:
                np.testing.assert_array_equal(u.severity_areas(box(.5,0,3.8,1),h),[.5,0,0,1])
                values=u.severity_areas(box(0,0,2,1),h)
                self.assertEqual(np.flatnonzero(values==values.max())[-1]+1,4)

    def test_calendar_repetition_and_seasonal_pattern_have_no_recovery(self):
        config=load_config(Path(__file__).parent/"config.json")
        year,indices=u.template_indices(config)
        self.assertEqual(len(year),365)
        self.assertEqual(len(indices),789)
        pre,after,offset=u.canonical_dates(config)
        timeline=pre.append(after)
        for index,date in zip(indices,after):
            actual=timeline[index-offset]
            self.assertEqual((actual.year,actual.month,actual.day),(2021,date.month,date.day))
        dates=u.noleap_dates("2021-01-01","2023-12-31")
        curve=u.annual_multiplier(np.arange(1,13)/10,dates)
        np.testing.assert_array_equal(curve[:365],curve[365:730])
        np.testing.assert_array_equal(curve[:365],curve[730:])
        np.testing.assert_array_equal(u.annual_multiplier(np.ones(12),dates),np.ones(len(dates)))

    def test_bootstrap_requires_independent_spatial_blocks(self):
        self.assertIsNone(u.bootstrap_medians(np.arange(10),["a"]*10))
        blocks=[str(i//2) for i in range(10)]
        a=u.bootstrap_medians(np.arange(10),blocks,replicates=30)
        np.testing.assert_array_equal(a,u.bootstrap_medians(np.arange(10),blocks,replicates=30))

    def test_unsupported_severity_is_not_generated(self):
        rows=[dict(severity=c,period=m,ratio=1 if c==1 else np.nan) for c in u.CLASSES for m in range(1,13)]
        result=dict(seasonal=pd.DataFrame(rows),low_evidence={"significant":False})
        with tempfile.TemporaryDirectory() as d:
            patterns,rejected=u.select_patterns({v:result for v in u.VEGETATION},result,Path(d))
        self.assertEqual(set(patterns),{"A0"})
        self.assertEqual(set(rejected),{"A1","A2","A3"})

    def test_class_ratios_are_normalized_and_low_effect_uses_spatial_evidence(self):
        window=("2021-08-04","2022-08-03")
        dates=u.noleap_dates(*window)
        spatial=pd.DataFrame({"severity":np.repeat([1,2,3,4],10),
                              "block":[str(i//2) for i in range(40)]})
        response=pd.DataFrame(np.tile(np.repeat([.8,.6,.4,.2],10),(len(dates),1)),index=dates)
        denominator=pd.DataFrame(np.tile(np.repeat([1.,2.,4.,6.],10),(len(dates),1)),index=dates)
        with tempfile.TemporaryDirectory() as d:
            result=u.response_tables(response,response*denominator,denominator,spatial,"DOC",Path(d),window)
        for code,expected in [(1,1),(2,.75),(3,.5),(4,.25)]:
            np.testing.assert_allclose(result["seasonal"].query("severity == @code").ratio,expected)
        self.assertTrue(result["low_evidence"]["significant"])
        self.assertEqual(result["low_evidence"]["low_blocks"],5)

    @unittest.skipUnless(CASE_SETTING, "Set NACHES_CASE_ROOT for real-case integration tests")
    def test_case_isolation_and_region_names_containing_slashes(self):
        config=load_config(CASE/"notebooks/config.json")
        from scipy.io import loadmat
        site=config['case']['site_name'];nx=config['case']['meshsize_nx']
        scenario=config.get('fire_workflow',{}).get('scenario','s1')
        mat=CASE/'data-processed'/site/f'm2_coords_{site}.mat'
        layers=loadmat(mat);nz=layers['dzs_soil'].size+layers['dzs_geo'].size
        mesh=p.mesh_first_layer(mat.parent/f'2dtransect_{site}_nx{nx}_nz{nz}.exo',mat,nx)
        report=json.loads((CASE/f'caselambda-run2-postfire.{scenario}/postfire_configuration_report.json').read_text())
        pattern={v:np.ones(12) for v in [*u.VEGETATION,'DOC']}
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);(base/'data-processed').symlink_to(CASE/'data-processed',target_is_directory=True)
            source=base/f'caselambda-run2-prefire.{scenario}';source.mkdir()
            for f in (CASE/source.name).glob('*.xml'):shutil.copy2(f,source/f.name)
            shutil.copytree(CASE/source.name/'reactions',source/'reactions')
            # Exercise the real mesh and both XML writers; forcing conservation
            # is separately tested above without copying the large real bundle.
            with patch.object(u,'write_case_forcing',return_value=({},{})):
                cases=u.generate_artificial_cases(base,config,scenario,mesh,report,report['severity_map'],{'A0':pattern},base)
            self.assertFalse((base/f'caselambda-run2-postfire.{scenario}').exists())
            target=Path(cases['A0'])
            self.assertEqual(target.name,f'caselambda-run2-artificial-A0.{scenario}')
            saved=json.loads((target/'postfire_configuration_report.json').read_text())
            self.assertEqual(len(saved['xml']),2)
            self.assertTrue(any('/Shrub/Scrub/file' in c['path'] for c in saved['xml'][0]['changes']))
            before=[p.digest(item['output']) for item in saved['xml']]
            mesh_hash=p.digest(saved['mesh']['copy'])
            with patch.object(u,'write_case_forcing',return_value=({},{})):
                u.generate_artificial_cases(base,config,scenario,mesh,report,report['severity_map'],{'A0':pattern},base)
            self.assertEqual(before,[p.digest(item['output']) for item in saved['xml']])
            self.assertEqual(mesh_hash,p.digest(saved['mesh']['copy']))

    def test_forcing_prefix_boundary_solutes_and_carbon_are_preserved(self):
        # Small full timeline, but real calendar lookup: source and boundary DOC
        # changes must not alter NH4, clocks, coordinates, or restart history.
        config={"spinup":{"cyclic_years":0},"prefire_transient":{"start_date":"2021-01-01","end_date":"2021-08-03"},
                "postfire_transient":{"start_date":"2021-08-04","end_date":"2022-12-31"}}
        _,after,_=u.canonical_dates(config);start=215;end=start+len(after)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/"source";source.mkdir();target=root/"case";target.mkdir()
            files=[]
            lai=source/"site_MODIS_LAI.h5"
            with h5py.File(lai,"w") as h:
                h["time [s]"]=np.arange(end)*86400
                for v in u.VEGETATION:h[f"NLCD {v} LAI [-]"]=np.arange(end)/100+1
            files.append(str(lai))
            for name in ["DOC_source","DOC_source_lambda10"]:
                path=source/f"site_{name}.h5"
                with h5py.File(path,"w") as h:
                    h["time [s]"]=np.arange(end)*86400;h["x [m]"]=[0,1];h["y [m]"]=[0,1]
                    keys={p.DOC_KEY:1}
                    if "lambda" in name:keys.update({f"DOC production {s} [mol m^-3 s^-1]":1/10/c for s,c in zip(p.SPECIES,p.CARBON)})
                    for key,factor in keys.items():
                        group=h.create_group(key)
                        for i in range(end):group[str(i)]=np.full((2,2),(i+1)*factor,dtype=float)
                files.append(str(path))
            for name in ["CNbc_conc","CNbc_conc_lambda10"]:
                path=source/f"site_{name}.h5"
                with h5py.File(path,"w") as h:
                    h["Time"]=np.arange(end)*86400;h[p.CN_KEY]=np.arange(end)+1.;h["NH4+ mol water basis [molS molH^-1]"]=np.arange(end)*3.
                    if "lambda" in name:
                        for s,c in zip(p.SPECIES,p.CARBON):h[f"{s} mol water basis [molS molH^-1]"]=(np.arange(end)+1)/10/c
                files.append(str(path))
            hashes={f:p.digest(f) for f in files}
            pattern={v:np.full(12,.4) for v in [*u.VEGETATION,"DOC"]}
            mapping,_=u.write_case_forcing(target,config,dict(start_day=start,end_day=end,forcing_files=files),pattern)
            _,ids=u.template_indices(config)
            with h5py.File(lai) as original,h5py.File(mapping[str(lai.resolve())]) as copied:
                key="NLCD Evergreen Forest LAI [-]"
                np.testing.assert_array_equal(copied[key][:start],original[key][:start])
                np.testing.assert_allclose(copied[key][start:],original[key][:][ids]*.4)
            self.assertEqual(hashes,{f:p.digest(f) for f in files})
            before={f:p.digest(f) for f in mapping.values()}
            u.write_case_forcing(target,config,dict(start_day=start,end_day=end,forcing_files=files),pattern)
            self.assertEqual(before,{f:p.digest(f) for f in mapping.values()})


if __name__=="__main__":unittest.main()
