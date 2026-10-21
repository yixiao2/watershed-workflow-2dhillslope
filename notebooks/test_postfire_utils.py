"""Run with the watershed-workflow environment: python -m unittest test_postfire_utils."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

import netCDF4
import numpy as np

from config_utils import load_config
from scipy.io import loadmat
import h5py
import postfire_utils as u

CASE_SETTING = os.environ.get("NACHES_CASE_ROOT")
CASE = Path(CASE_SETTING).resolve() if CASE_SETTING else None
MSTK_SETTING = os.environ.get("MSTK_LIBRARY")
MSTK = Path(MSTK_SETTING) if MSTK_SETTING else None



@unittest.skipUnless(CASE_SETTING, "Set NACHES_CASE_ROOT for real-case integration tests")
class PostfirePermeabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(CASE / "notebooks/config.json")
        cls.site = cls.config['case']['site_name']
        cls.nx = cls.config['case']['meshsize_nx']
        cls.scenario = cls.config.get('fire_workflow', {}).get('scenario', 's1')
        mat = CASE / 'data-processed' / cls.site / f'm2_coords_{cls.site}.mat'
        layers = loadmat(mat)
        nz = layers['dzs_soil'].size + layers['dzs_geo'].size
        cls.mesh = u.mesh_first_layer(mat.parent / f'2dtransect_{cls.site}_nx{cls.nx}_nz{nz}.exo', mat, cls.nx)
        report = json.loads((CASE / f'caselambda-run2-postfire.{cls.scenario}/postfire_configuration_report.json').read_text())
        cls.forcing = {k: report[k] for k in
                       ("start_day", "end_day", "postfire_days", "forcing_files", "terminal_policy")}
        cls.burn = report["severity_map"]

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        (self.base / "data-processed").symlink_to(CASE / "data-processed", target_is_directory=True)
        parent = self.base / f"caselambda-run2-prefire.{self.scenario}"
        parent.mkdir()
        for path in (CASE / parent.name).glob("*.xml"):
            shutil.copy2(path, parent / path.name)
        shutil.copytree(CASE / parent.name / "reactions", parent / "reactions")

    def generate(self, severity):
        return u.generate_case(self.base, self.config, self.scenario, severity,
                               self.mesh, self.forcing, self.burn)

    def test_all_severities_preserve_doc_and_deeper_properties(self):
        for severity, (_, multiplier) in u.SEVERITY.items():
            with self.subTest(severity=severity):
                target, report = self.generate(severity)
                self.assertEqual(sum(r["first_layer_cells"] for r in report["permeability"]), self.nx)
                self.assertEqual(report["mesh"]["element_set_label"], 2000)
                affected = [r for r in report["permeability"] if r["first_layer_cells"]]
                for material in affected:
                    self.assertEqual(material["burned_region"], material["material"] + "-burned")
                    self.assertEqual(material["deeper_region"], material["material"] + "-deeper")
                for item in report["xml"]:
                    parent = ET.parse(item["parent"]).getroot()
                    xml = ET.parse(item["output"]).getroot()
                    u.xml_values(xml)  # rejects duplicate names
                    layer = u.child(xml, "regions", "postfire-first-layer")
                    self.assertIsNone(xml.find("./ParameterList[@name='postfire-first-layer']"))
                    self.assertEqual(len(layer), 5)
                    text = Path(item["output"]).read_text()
                    self.assertIn('    <ParameterList name="postfire-first-layer" type="ParameterList">\n'
                                  '      <Parameter name="region type"', text)
                    self.assertFalse(text.startswith("<?xml"))
                    for path in [("PKs",), ("state", "model parameters")]:
                        # Only the pre-existing restart parameter changes within PKs.
                        original = u.child(parent, *path)
                        updated = u.child(xml, *path)
                        for node in original.iter("Parameter"):
                            if node.get("name") == "restart file":
                                node.set("value", report["restart_path"])
                        self.assertEqual(u.xml_values(original), u.xml_values(updated))
                    for evaluator in ["base_porosity", "porosity"]:
                        self.assertEqual(u.xml_values(u.child(parent, "state", "evaluators", evaluator)),
                                         u.xml_values(u.child(xml, "state", "evaluators", evaluator)))
                    regions = {r.get("name"): r for r in u.child(xml, "regions")}
                    def resolve(name):
                        region = regions[name]
                        kind = u.child(region, "region type").get("value")
                        if kind == "labeled set":
                            label = int(u.child(region, "label").get("value"))
                            if label == 2000:
                                return set(self.mesh["top"].tolist())
                            return set(np.flatnonzero(self.mesh["materials"] == label).tolist())
                        names = u.child(region, "regions").get("value").strip("{}").split(", ")
                        left, right = map(resolve, names)
                        return left & right if u.child(region, "operation").get("value") == "intersect" else left - right
                    baseline = np.zeros(len(self.mesh["materials"]))
                    for function in u.child(parent, "state", "evaluators", "permeability", "function"):
                        indices = sorted(resolve(u.child(function, "region").get("value")))
                        baseline[indices] = float(u.child(function, "function", "value").get("value"))
                    actual, seen = np.zeros(len(self.mesh["materials"])), set()
                    for function in u.child(xml, "state", "evaluators", "permeability", "function"):
                        cells = resolve(u.child(function, "region").get("value"))
                        self.assertFalse(seen & cells)
                        seen |= cells
                        actual[sorted(cells)] = float(u.child(function, "function", "value").get("value"))
                    self.assertEqual(len(seen), len(self.mesh["materials"]))
                    expected = baseline.copy()
                    expected[self.mesh["top"]] *= multiplier
                    np.testing.assert_array_equal(actual, expected)
                    self.assertEqual(np.count_nonzero(actual != baseline), 0 if multiplier == 1 else self.nx)
                    for node in xml.iter("Parameter"):
                        if node.get("name") == "file" and node.get("value", "").endswith(".exo"):
                            resolved = (target / self.site / node.get("value")).resolve()
                            self.assertTrue(resolved.is_file())
                            self.assertEqual(resolved, Path(report["mesh"]["copy"] or report["mesh"]["original"]))
                before = [u.digest(i["output"]) for i in report["xml"]]
                mesh_hash = u.digest(report["mesh"]["copy"]) if report["mesh"]["copy"] else None
                _, repeated = self.generate(severity)
                self.assertEqual(before, [u.digest(i["output"]) for i in repeated["xml"]])
                if mesh_hash:
                    self.assertEqual(mesh_hash, u.digest(repeated["mesh"]["copy"]))
                self.assertFalse(report["runtime_ready"])

    def test_conflicting_set_label_is_rejected(self):
        original = self.base / "conflict.exo"
        shutil.copy2(self.mesh["mesh_path"], original)
        with netCDF4.Dataset(original, "r+") as mesh:
            labels = mesh["eb_prop1"][:]
            labels[0] = 2000
            mesh["eb_prop1"][:] = labels
        with self.assertRaisesRegex(ValueError, "conflicts"):
            u.copy_mesh_with_first_layer(dict(self.mesh, mesh_path=str(original)), self.base / "copy.exo")

    def test_wrong_checkpoint_time_is_rejected(self):
        folder = self.base / f'caselambda-run2-prefire.{self.scenario}' / self.site
        folder.mkdir()
        with h5py.File(folder / 'checkpoint_final.h5', 'w') as h:
            h.attrs['time'] = (self.forcing['start_day'] - 1) * 86400
        with self.assertRaisesRegex(ValueError, 'Checkpoint time'):
            self.generate('low')
        self.assertFalse((self.base / f'caselambda-run2-postfire.{self.scenario}').exists())

    @unittest.skipUnless(MSTK is not None and MSTK.is_file(), "Set MSTK_LIBRARY for native mesh-reader verification")
    def test_installed_mstk_reads_the_exact_set_and_original_materials(self):
        _, report = self.generate("low")
        # Isolate the ATS native library from Python's different NetCDF/HDF5 libraries.
        code = r'''
import ctypes as C, json, sys
lib = C.CDLL(sys.argv[1])
def function(name, result, args):
    f = getattr(lib, name); f.restype = result; f.argtypes = args; return f
function('MSTK_Init', None, [])()
mesh = function('MESH_New', C.c_void_p, [C.c_int])(0)
assert function('MESH_ImportFromExodusII', C.c_int,
                [C.c_void_p, C.c_char_p, C.c_void_p, C.c_int])(mesh, sys.argv[2].encode(), None, 0) == 1
lookup = function('MESH_MSetByName', C.c_void_p, [C.c_void_p, C.c_char_p])
size = function('MSet_Num_Entries', C.c_int, [C.c_void_p])
entry = function('MSet_Entry', C.c_void_p, [C.c_void_p, C.c_int])
identity = function('MEnt_ID', C.c_int, [C.c_void_p])
sets = {}
for name in ['elemset_2000'] + ['matset_' + str(m) for m in json.loads(sys.argv[3])]:
    s = lookup(mesh, name.encode()); assert s, name
    sets[name] = sorted(identity(entry(s, i)) for i in range(size(s)))
print(json.dumps(sets))
function('MESH_Delete', None, [C.c_void_p])(mesh)
'''
        result = subprocess.run(["/usr/bin/python3", "-c", code, str(MSTK), report["mesh"]["copy"], json.dumps(np.unique(self.mesh["materials"]).tolist())],
                                capture_output=True, text=True, check=True)
        sets = json.loads(result.stdout)
        self.assertEqual(sets["elemset_2000"], report["mesh"]["element_indices_1based"])
        for material in np.unique(self.mesh["materials"]):
            self.assertEqual(sets[f"matset_{material}"],
                             (np.flatnonzero(self.mesh["materials"] == material) + 1).tolist())


if __name__ == "__main__":
    unittest.main()
