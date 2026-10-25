"""Run in mayapy -B with --plugin pointing to the staged Maya 2024 .mll."""

import argparse
import os
from pathlib import Path
import sys
import unittest


parser = argparse.ArgumentParser()
parser.add_argument("--plugin", type=Path, required=True)
options, remaining = parser.parse_known_args()
PLUGIN = options.plugin.resolve()
SCRIPTS = PLUGIN.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
os.environ["MAYA_SCRIPT_PATH"] = str(SCRIPTS) + os.pathsep + os.environ.get("MAYA_SCRIPT_PATH", "")

import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds
import maya.mel as mel


NODE_SUFFIXES = (
    "TimeControl", "File", "Xform", "Camera", "PolyMesh", "SubD",
    "PolyMeshDeform", "SubDDeform", "Points", "Curves", "CurvesDeform", "CurvesLocator",
)
COMMAND_SUFFIXES = (
    "export", "import", "resolvePath", "createMetaData", "createFaceSets",
    "assignFaceSets", "postImportPoints", "profileBegin", "profileEnd",
    "profileStats", "profileReset", "meshToSubdiv",
)


class PluginLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cmds.loadPlugin("AbcImport", quiet=True)
        cmds.loadPlugin("AbcExport", quiet=True)

    def test_register_evaluate_unload_and_reload(self):
        self.assertTrue(20240000 <= cmds.about(apiVersion=True) < 20250000)
        self.assertTrue(PLUGIN.is_file(), str(PLUGIN))
        for cycle in range(2):
            with self.subTest(cycle=cycle):
                plugin = cmds.loadPlugin(str(PLUGIN), quiet=True)[0]
                try:
                    self.assertEqual(
                        set(cmds.pluginInfo(plugin, query=True, dependNode=True)),
                        {"ExocortexAlembic" + suffix for suffix in NODE_SUFFIXES},
                    )
                    self.assertEqual(
                        set(cmds.pluginInfo(plugin, query=True, command=True)),
                        {"ExocortexAlembic_" + suffix for suffix in COMMAND_SUFFIXES},
                    )
                    timer = cmds.createNode("ExocortexAlembicTimeControl")
                    cmds.setAttr(timer + ".timeUnit", 1)
                    cmds.setAttr(timer + ".inTime", 10)
                    cmds.setAttr(timer + ".factor", 2)
                    cmds.setAttr(timer + ".offset", 3)
                    self.assertAlmostEqual(cmds.getAttr(timer + ".outTime"), 23)
                    cmds.delete(timer)
                finally:
                    cmds.file(new=True, force=True)
                    cmds.unloadPlugin(plugin)
                for suffix in COMMAND_SUFFIXES:
                    self.assertFalse(mel.eval('exists "ExocortexAlembic_{}"'.format(suffix)))
                self.assertTrue(cmds.pluginInfo("AbcImport", query=True, loaded=True))
                self.assertTrue(cmds.pluginInfo("AbcExport", query=True, loaded=True))


if __name__ == "__main__":
    try:
        program = unittest.main(argv=[sys.argv[0]] + remaining, exit=False)
    finally:
        maya.standalone.uninitialize()
    sys.exit(0 if program.result.wasSuccessful() else 1)
