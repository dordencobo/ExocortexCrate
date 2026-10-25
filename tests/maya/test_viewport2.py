"""Render the Crate curve locator with VP2 in an isolated mayapy process."""

import argparse
import os
from pathlib import Path
import sys
import tempfile
import unittest

parser = argparse.ArgumentParser()
parser.add_argument("--plugin", type=Path, required=True)
options, remaining = parser.parse_known_args()
plugin = options.plugin.resolve()
scripts = plugin.parent.parent / "scripts"
sys.path.insert(0, str(scripts))
os.environ["MAYA_SCRIPT_PATH"] = str(scripts) + os.pathsep + os.environ.get("MAYA_SCRIPT_PATH", "")

import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds
from PySide2.QtGui import QImage
from ExocortexAlembic import _export


class Viewport2Tests(unittest.TestCase):
    def test_locator_is_drawn_and_updates(self):
        cmds.loadPlugin(str(plugin), quiet=True)
        cmds.file(new=True, force=True)
        cmds.currentUnit(time="film")
        temp = tempfile.TemporaryDirectory(prefix="crate-vp2-")
        self.addCleanup(temp.cleanup)
        self.addCleanup(lambda: cmds.file(new=True, force=True))
        directory = temp.name
        archive = Path(directory) / "guide.abc"
        cmds.curve(name="guide", degree=1, point=[(-2, -1, 0), (0, 1, 0), (2, -1, 0)])
        cmds.rename(cmds.listRelatives("guide", shapes=True)[0], "guideShape")
        cmds.setKeyframe("guideShape.controlPoints[1].yValue", time=1, value=1)
        cmds.setKeyframe("guideShape.controlPoints[1].yValue", time=3, value=-0.5)
        cmds.select("guide", replace=True)
        _export.doIt(archive.as_posix(), 1, 3)
        cmds.file(new=True, force=True)
        locator = cmds.createNode("ExocortexAlembicCurvesLocator")
        cmds.setAttr(locator + ".fileName", archive.as_posix(), type="string")
        cmds.setAttr(locator + ".identifier", "/guide/guideShape", type="string")
        camera, _ = cmds.camera(orthographic=True, orthographicWidth=6)
        cmds.setAttr(camera + ".translateZ", 10)
        cmds.setAttr("defaultRenderGlobals.imageFormat", 32)
        names = cmds.getAttr("hardwareRenderingGlobals.objectTypeFilterNameArray")
        # Enable the UI parent filter and locators, without unrelated UI ornaments.
        filters = [int(name in ("UI", "Locators")) for name in names]
        cmds.setAttr("hardwareRenderingGlobals.objectTypeFilterValueArray", filters, type="Int32Array")

        def render(label):
            cmds.setAttr("defaultRenderGlobals.imageFilePrefix",
                         (Path(directory) / label).as_posix(), type="string")
            filename = cmds.ogsRender(camera=camera, width=160, height=120)
            image = QImage(filename)
            self.assertFalse(image.isNull(), filename)
            return [image.pixel(x, y) for y in range(image.height()) for x in range(image.width())]

        cmds.setAttr(locator + ".visibility", False)
        background = render("hidden")
        cmds.setAttr(locator + ".visibility", True)
        cmds.setAttr(locator + ".inTime", 1)
        first = render("frame1")
        cmds.setAttr(locator + ".inTime", 3)
        last = render("frame3")
        self.assertGreater(sum(a != b for a, b in zip(background, first)), 50)
        self.assertGreater(sum(a != b for a, b in zip(first, last)), 50)
        cmds.file(new=True, force=True)


if __name__ == "__main__":
    try:
        program = unittest.main(argv=[sys.argv[0]] + remaining, exit=False)
    finally:
        maya.standalone.uninitialize()
    sys.exit(0 if program.result.wasSuccessful() else 1)
