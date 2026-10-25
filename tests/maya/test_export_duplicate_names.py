"""Exercise face-set export with duplicate DAG leaf names in Maya standalone."""

import argparse
import os
from pathlib import Path
import sys
import tempfile
import unittest

parser = argparse.ArgumentParser()
parser.add_argument("--plugin", type=Path, required=True)
options, remaining = parser.parse_known_args()
plugin_path = options.plugin.resolve()
scripts = plugin_path.parent.parent / "scripts"
sys.path.insert(0, str(scripts))
os.environ["MAYA_SCRIPT_PATH"] = str(scripts) + os.pathsep + os.environ.get("MAYA_SCRIPT_PATH", "")

import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds
import maya.OpenMaya as om
from ExocortexAlembic import _export


class DuplicateNameExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cmds.loadPlugin(str(plugin_path), quiet=True)
        cmds.loadPlugin("AbcImport", quiet=True)

    def tearDown(self):
        cmds.file(new=True, force=True)

    def test_ogawa_exports_duplicate_shape_names(self):
        self.check_duplicate_shape_export(use_ogawa=True)

    def test_hdf5_exports_duplicate_shape_names(self):
        self.check_duplicate_shape_export(use_ogawa=False)

    def check_duplicate_shape_export(self, use_ogawa):
        cmds.file(new=True, force=True)
        transforms = []
        for name, width in (("jacket_A", 1), ("jacket_B", 3)):
            transform = cmds.polyCube(name=name, width=width, constructionHistory=False)[0]
            shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
            cmds.rename(shape, "jacket_GEOShape")
            shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
            cmds.addAttr(shape, longName="FACESET_panel", dataType="Int32Array")
            cmds.setAttr(shape + ".FACESET_panel", [0], type="Int32Array")
            transforms.append("|" + transform)

        messages = []
        callback = om.MCommandMessage.addCommandOutputCallback(
            lambda message, message_type, *_: messages.append(str(message))
        )
        try:
            with tempfile.TemporaryDirectory(prefix="crate-duplicate-names-") as directory:
                archive = Path(directory) / "duplicate_names.abc"
                cmds.select(transforms, replace=True)
                _export.doIt(archive.as_posix(), 1, 1, exUseOgawa=use_ogawa)
                self.assertTrue(archive.is_file())
                self.assertGreater(archive.stat().st_size, 0)
                self.assertFalse(
                    any("More than one object matches name" in message for message in messages),
                    "\n".join(messages),
                )
                cmds.file(new=True, force=True)
                if use_ogawa:
                    cmds.AbcImport(archive.as_posix(), mode="import")
                else:
                    # Validate HDF5 through Crate's reader, independently of the
                    # optional backends included in Maya's native AbcImport.
                    for transform in transforms:
                        parent = cmds.createNode("transform", name=transform[1:])
                        shape = cmds.createNode("mesh", name="jacket_GEOShape", parent=parent)
                        reader = cmds.createNode("ExocortexAlembicPolyMesh")
                        cmds.setAttr(reader + ".fileName", archive.as_posix(), type="string")
                        identifier = transform.replace("|", "/") + "/jacket_GEOShape"
                        cmds.setAttr(reader + ".identifier", identifier, type="string")
                        cmds.connectAttr(reader + ".outMesh", transform + "|jacket_GEOShape.inMesh")
                for transform, width in zip(transforms, (1, 3)):
                    shape = transform + "|jacket_GEOShape"
                    self.assertTrue(cmds.objExists(shape), shape)
                    self.assertEqual(cmds.polyEvaluate(shape, vertex=True), 8)
                    bounds = cmds.exactWorldBoundingBox(shape)
                    self.assertAlmostEqual(bounds[3] - bounds[0], width)
                    cmds.ExocortexAlembic_createFaceSets(
                        f=archive.as_posix(), i=shape.replace("|", "/"), o=shape,
                    )
                    self.assertEqual(cmds.getAttr(shape + ".FACESET_panel"), [0])
                cmds.file(new=True, force=True)
        finally:
            om.MMessage.removeCallback(callback)


if __name__ == "__main__":
    try:
        program = unittest.main(argv=[sys.argv[0]] + remaining, exit=False)
    finally:
        maya.standalone.uninitialize()
    sys.exit(0 if program.result.wasSuccessful() else 1)
