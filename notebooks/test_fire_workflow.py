"""Portable configuration, mesh, checkpoint, and notebook restart regression tests."""
import copy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import h5py
import netCDF4
import numpy as np
from scipy.io import savemat

import artificial_fire_utils as af
import config_utils as cfg
import postfire_utils as post

NOTEBOOKS = Path(__file__).resolve().parent


def tiny_mesh(root, nx):
    """Two-layer NFACED columns with nonconsecutive surface element indices."""
    mat, path = root / 'layers.mat', root / 'mesh.exo'
    savemat(mat, {'dzs_soil': [0.05], 'dzs_geo': [1.]})
    xyz, faces, cells = [], [], []
    for x in range(nx):
        for top, bottom in [(0., -.05), (-.05, -1.05)]:
            n = len(xyz)
            xyz.extend([(x,0,bottom),(x+1,0,bottom),(x+1,1,bottom),(x,1,bottom),
                        (x,0,top),(x+1,0,top),(x+1,1,top),(x,1,top)])
            first = len(faces)
            faces.extend([[n+i+1 for i in f] for f in
                          [(0,1,2,3),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]])
            cells.extend(range(first+1,first+7))
    with netCDF4.Dataset(path, 'w') as h:
        dimensions = {'num_nodes':len(xyz), 'face_entries':len(faces)*4,
                      'num_faces':len(faces), 'cell_entries':len(cells),
                      'num_elem':nx*2, 'num_el_blk':1, 'num_side_sets':1,
                      'num_sides':nx, 'len_name':32}
        for name,size in dimensions.items(): h.createDimension(name,size)
        def put(name, dtype, dims, values): h.createVariable(name,dtype,dims)[:] = values
        for i,key in enumerate(('coordx','coordy','coordz')): put(key,'f8',('num_nodes',),np.array(xyz)[:,i])
        put('fbconn1','i4',('face_entries',),np.ravel(faces))
        put('fbepecnt1','i4',('num_faces',),np.full(len(faces),4))
        put('facconn1','i4',('cell_entries',),cells)
        put('ebepecnt1','i4',('num_elem',),np.full(nx*2,6))
        put('eb_prop1','i4',('num_el_blk',),[100])
        put('elem_ss1','i4',('num_sides',),np.arange(nx)*2+1)
        names=np.zeros((1,32),dtype='S1');names[0,:7]=np.frombuffer(b'surface',dtype='S1')
        put('ss_names','S1',('num_side_sets','len_name'),names)
    return post.mesh_first_layer(path,mat,nx)


class FireWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.config=cfg.load_config(NOTEBOOKS/'config.json')

    def test_prefire_only_remains_valid_and_fire_stage_requires_postfire(self):
        del self.config['postfire_transient']
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.json';p.write_text(json.dumps(self.config))
            self.assertNotIn('postfire_transient',cfg.load_config(p))
            with self.assertRaisesRegex(ValueError,'postfire_transient'):
                cfg.load_fire_workflow(self.config,d)
            with self.assertRaisesRegex(ValueError,'postfire_transient'):
                post.validate_forcing(self.config,Path(d),Path(d)/'parent.xml')

    def test_relative_sources_defaults_and_stage_specific_validation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'burn.tif').touch()
            self.config['fire_workflow']={'burn_raster':'burn.tif','scenario':'s2'}
            settings=cfg.load_fire_workflow(self.config,root)
            self.assertEqual(settings['burn_raster'],root/'burn.tif')
            self.assertEqual(settings['scenario'],'s2')
            self.assertEqual(settings['severity'],'low')
            for key in ('perimeter','modis_lai','modis_landcover'):
                (root/key).touch();self.config['fire_workflow'][key]=key
            self.config['elm_root']='elm'
            with self.assertRaisesRegex(ValueError,'Missing paired ELM'):
                cfg.load_fire_workflow(self.config,root,artificial=True)
            for run in (self.config['postfire_transient']['elm_run'],'2024-11-20-220109'):
                (root/'elm'/f'ELM_MOSART_CONUS.{run}'/'run').mkdir(parents=True)
            settings=cfg.load_fire_workflow(self.config,root,artificial=True)
            self.assertEqual(settings['elm_root'],root/'elm')
            for key in ('perimeter','modis_lai','modis_landcover'):
                (root/key).unlink()
                with self.assertRaisesRegex(ValueError,'Missing fire source input '+key):
                    cfg.load_fire_workflow(self.config,root,artificial=True)
                (root/key).touch()
            (root/'burn.tif').unlink()
            with self.assertRaisesRegex(ValueError,'Missing fire source input burn_raster'):
                cfg.load_fire_workflow(self.config,root)

    def test_invalid_fire_settings(self):
        for block in ([],{'scenario':'../bad'},{'severity':'extreme'}):
            self.config['fire_workflow']=block
            with self.assertRaises(ValueError):cfg.load_fire_workflow(self.config,'.')
        for year in (True,2021.5,'2021',0):
            self.config['fire_workflow']={'artificial_baseline_year':year}
            with self.assertRaises(ValueError):af.template_indices(self.config)

    def test_shifted_window_and_leap_baseline(self):
        self.config['prefire_transient'].update(start_date='2023-01-01',end_date='2024-02-27')
        self.config['postfire_transient'].update(start_date='2024-02-28',end_date='2025-12-31')
        self.config['spinup']['cyclic_years']=2
        self.config['fire_workflow']={'artificial_baseline_year':2024}
        start,end=cfg.first_postfire_year(self.config)
        self.assertEqual((start,end),(date(2024,2,28),date(2025,2,27)))
        self.assertEqual(len(af.noleap_dates(start,end)),365)
        year,indices=af.template_indices(self.config)
        pre,after,offset=af.canonical_dates(self.config);timeline=pre.append(after)
        self.assertEqual(len(year),365)
        for index,day in zip(indices,after):
            actual=timeline[index-offset]
            self.assertEqual((actual.year,actual.month,actual.day),(2024,day.month,day.day))
        self.config['fire_workflow']['artificial_baseline_year']=2022
        with self.assertRaisesRegex(ValueError,'complete observed 2022'):af.template_indices(self.config)

    def test_response_statistics_follow_shifted_first_year(self):
        import pandas as pd
        window=(date(2023,8,4),date(2024,8,3))
        dates=af.noleap_dates('2023-08-04','2025-08-03')
        spatial=pd.DataFrame({'severity':[1,2,3,4], 'block':['a','b','c','d']})
        values=np.tile([1.,.75,.5,.25],(len(dates),1))
        values[365:,1:]=1.5  # Later recovery must not enter the seasonal template.
        response=pd.DataFrame(values,index=dates)
        denominator=response*0+1
        with tempfile.TemporaryDirectory() as d:
            result=af.response_tables(response,response,denominator,spatial,'DOC',Path(d),window)
        np.testing.assert_allclose(result['seasonal'].query('severity == 2').ratio,.75)
        self.assertAlmostEqual(result['low_evidence']['integrated_ratio'],.75)

    def test_alternate_mesh_sizes_and_label_conflict(self):
        for nx in (3,7):
            with self.subTest(nx=nx), tempfile.TemporaryDirectory() as d:
                root=Path(d);mesh=tiny_mesh(root,nx)
                np.testing.assert_array_equal(mesh['top'],np.arange(nx)*2)
                report=post.copy_mesh_with_first_layer(mesh,root/'copied.exo')
                self.assertEqual(report['element_indices_1based'],list(range(1,nx*2,2)))
                with netCDF4.Dataset(mesh['mesh_path'],'r+') as h:h['eb_prop1'][:]=[2000]
                with self.assertRaisesRegex(ValueError,'conflicts'):
                    post.copy_mesh_with_first_layer(mesh,root/'conflict.exo')

    def test_alternate_case_clock_generation_and_checkpoint_validation(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);mesh=tiny_mesh(base,3)
            config=copy.deepcopy(self.config);config['case'].update(site_name='Example',meshsize_nx=3)
            parent=base/'caselambda-run2-prefire.s9';(parent/'reactions').mkdir(parents=True)
            (parent/'reactions'/'chem.in').write_text('chemistry unchanged\n')
            (parent/'Example').mkdir()
            root=ET.Element('ParameterList',name='root')
            cycle=ET.SubElement(root,'ParameterList',name='cycle driver')
            for k,v in [('start time',730),('end time',748),('restart from checkpoint file','old')]:post.parameter(cycle,k,'string',v)
            region=ET.SubElement(ET.SubElement(root,'ParameterList',name='regions'),'ParameterList',name='mat')
            post.parameter(region,'label','string',100)
            state=ET.SubElement(root,'ParameterList',name='state')
            evaluators=ET.SubElement(state,'ParameterList',name='evaluators')
            functions=ET.SubElement(ET.SubElement(evaluators,'ParameterList',name='permeability'),'ParameterList',name='function')
            function=ET.SubElement(functions,'ParameterList',name='mat');post.parameter(function,'region','string','mat')
            post.parameter(ET.SubElement(function,'ParameterList',name='function'),'value','double',1.e-12)
            stem='Example_nx3_nz2.run2.v1.6_pflotran'
            for suffix in ('.xml','.obs4massflux.xml'):ET.ElementTree(root).write(parent/(stem+suffix))
            forcing={'start_day':748,'end_day':767};burn={'dominant_class':2}
            target,report=post.generate_case(base,config,'s9','moderate',mesh,forcing,burn)
            self.assertEqual(report['permeability'][0]['first_layer_cells'],3)
            self.assertEqual(report['permeability'][0]['deeper_cells'],3)
            self.assertEqual(report['permeability'][0]['postfire_first_layer_k_m2'],4.e-13)
            self.assertEqual(report['restart_path'],'../../caselambda-run2-prefire.s9/Example/checkpoint_final.h5')
            self.assertFalse(report['runtime_ready'])
            with h5py.File(parent/'Example/checkpoint_final.h5','w') as h:h.attrs['time']=747*86400
            with self.assertRaisesRegex(ValueError,'Checkpoint time'):
                post.generate_case(base,config,'s9','low',mesh,forcing,burn)
            with h5py.File(parent/'Example/checkpoint_final.h5','r+') as h:h.attrs['time']=748*86400
            _,report=post.generate_case(base,config,'s9','low',mesh,forcing,burn)
            self.assertTrue(report['checkpoint_present']);self.assertFalse(report['runtime_ready'])

    def test_prefire_restart_cell_is_repeatable(self):
        # Run the actual insertion snippet with the same amanzi_xml API as notebook 2.
        import amanzi_xml.utils.search as asearch
        from amanzi_xml.common.parameter import Parameter
        from amanzi_xml.common.parameter_list import ParameterList
        nb=json.loads((NOTEBOOKS/'2-add_reaction_lambda.ipynb').read_text())
        source=next(''.join(c['source']) for c in nb['cells'] if 'restart_name =' in ''.join(c['source']))
        snippet=source[source.index('cycle_driver ='):source.index('aio.toFile')]
        xml=ParameterList(name='root');driver=ParameterList(name='cycle driver');xml.append(driver)
        driver.append(Parameter(name='end cycle',ptype='int',value='20'))
        for value in ('old1','old2'):driver.append(Parameter(name='restart from checkpoint file',ptype='string',value=value))
        namespace=dict(xml=xml,asearch=asearch,Parameter=Parameter,flag_scenario='s9',site_name='Example')
        for _ in range(2):exec(snippet,namespace)
        restarts=[n for n in driver if n.get('name')=='restart from checkpoint file']
        self.assertEqual(len(restarts),1)
        self.assertEqual(restarts[0].get('value'),'../../caselambda-run1.s9/Example/checkpoint_final.h5')


if __name__=='__main__':unittest.main()
