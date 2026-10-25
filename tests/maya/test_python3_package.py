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
    def test_package_loads_its_own_helpers(self):
        package = importlib.import_module("ExocortexAlembic")
        self.assertIs(package._import.fnt, package._functions)
        self.assertIs(package._attach.fnt, package._functions)
        self.assertNotIn("_functions", sys.modules)

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
