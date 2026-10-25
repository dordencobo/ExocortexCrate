"""Run with Maya 2024's mayapy -B; does not load the Crate plugin."""

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SCRIPTS = Path(__file__).resolve().parents[2] / "Maya" / "MEL"
# Only expose the package parent: sibling modules must resolve relatively.
sys.path.insert(0, str(SCRIPTS))


class Python3PackageTests(unittest.TestCase):
    def test_batch_progress_does_not_access_gui(self):
        functions = importlib.import_module("ExocortexAlembic._functions")
        commands = Mock()
        commands.about.return_value = True
        with patch.object(functions, "cmds", commands), patch.object(functions, "mel") as mel:
            functions.progressBar_init(10)
            functions.progressBar_start()
            functions.progressBar_incr()
            functions.progressBar_stop()
            self.assertEqual(functions.progressBar_isCancelled(), 0)
        mel.eval.assert_not_called()
        commands.progressBar.assert_not_called()

    def test_package_loads_its_own_helpers(self):
        package = importlib.import_module("ExocortexAlembic")
        self.assertIs(package._import.fnt, package._functions)
        self.assertIs(package._attach.fnt, package._functions)
        self.assertNotIn("_functions", sys.modules)

    def test_reattach_changes_identifier_for_existing_readers(self):
        attach = importlib.import_module("ExocortexAlembic._attach")
        job = SimpleNamespace(filenode="replacementFile", timeCtrl="cacheTime")
        for name in ("attachXform", "attachPolyMesh", "attachCamera", "attachCurves", "attachPoints"):
            with self.subTest(helper=name):
                commands = Mock()
                commands.listConnections.return_value = ["existingReader"]
                commands.connectionInfo.return_value = ""
                commands.objectType.side_effect = lambda node: (
                    "mesh" if node == "target" else "ExocortexAlembicXform"
                )
                with patch.object(attach, "cmds", commands):
                    result = getattr(attach, name)("target", "/replacement/object", job)
                self.assertEqual(result, ["existingReader"])
                commands.setAttr.assert_any_call(
                    "existingReader.identifier", "/replacement/object", type="string",
                )
                commands.connectAttr.assert_any_call(
                    "replacementFile.outFileName", "existingReader.fileName",
                )

    def test_imports_every_curve_in_a_multi_curve_cache(self):
        importer = importlib.import_module("ExocortexAlembic._import")
        commands = Mock()
        commands.createNode.return_value = "curveReader"
        job = SimpleNamespace(filenode="cacheFile", timeCtrl="cacheTime")

        with patch.object(importer, "cmds", commands), patch.object(
            importer.fnt, "alembicCreateNode",
            side_effect=["curveShape", "curveShape_1", "curveShape_2"],
        ) as create_shape:
            result = importer.importCurves(
                "curveShape", "/curves", job, nbCurves=3,
            )

        self.assertEqual(result, ["curveShape_2", "curveReader"])
        self.assertEqual(create_shape.call_count, 3)
        for index, shape in enumerate(
            ["curveShape", "curveShape_1", "curveShape_2"]
        ):
            commands.connectAttr.assert_any_call(
                "curveReader.outCurve[{}]".format(index), shape + ".create",
            )


if __name__ == "__main__":
    unittest.main()
