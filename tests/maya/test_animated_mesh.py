"""Animated mesh round-trip and attach tests in Maya 2024 standalone."""

import argparse
import math
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
from ExocortexAlembic import _export


SHAPE = "|cacheMesh|cacheMeshShape"
FRAMES = (1, 2, 3, 1.5)


class AnimatedMeshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cmds.loadPlugin(str(plugin_path), quiet=True)

    def setUp(self):
        cmds.file(new=True, force=True)
        cmds.currentUnit(time="film")
        cmds.evaluationManager(mode="off")
        self.directory = tempfile.TemporaryDirectory(prefix="crate-animation-")
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(lambda: cmds.file(new=True, force=True))

    def create_source(self):
        cmds.polyCube(name="cacheMesh", constructionHistory=False)
        cmds.polyUVSet(SHAPE, copy=True, uvSet="map1", newUVSet="detailUV")
        cmds.addAttr(SHAPE, longName="FACESET_panel", dataType="Int32Array")
        cmds.setAttr(SHAPE + ".FACESET_panel", [0, 2], type="Int32Array")
        cmds.addAttr(SHAPE, longName="density", attributeType="double", keyable=True)
        for plug, start, end in (
            ("|cacheMesh.translateX", 0, 4),
            (SHAPE + ".pnts[0].pnty", 0, 2),
            (SHAPE + ".density", 1, 5),
        ):
            cmds.setKeyframe(plug, time=1, value=start)
            cmds.setKeyframe(plug, time=3, value=end)
            cmds.keyTangent(plug, inTangentType="linear", outTangentType="linear")
        expected = {}
        for frame in FRAMES:
            cmds.currentTime(frame)
            expected[frame] = (
                cmds.xform(SHAPE + ".vtx[*]", query=True, worldSpace=True, translation=True),
                cmds.getAttr(SHAPE + ".density"),
            )
        return expected

    def export_source(self, ogawa):
        expected = self.create_source()
        archive = Path(self.directory.name) / "mesh.abc"
        cmds.select("|cacheMesh", replace=True)
        _export.doIt(archive.as_posix(), 1, 3, exUseOgawa=ogawa, userAttrs="density")
        self.assertGreater(archive.stat().st_size, 0)
        cmds.file(new=True, force=True)
        return archive, expected

    def assert_animation(self, expected):
        for mode in ("off", "serial", "parallel"):
            cmds.evaluationManager(mode=mode)
            for frame in (3, 1, 2, 1.5, 3):
                with self.subTest(mode=mode, frame=frame):
                    cmds.currentTime(frame)
                    positions = cmds.xform(SHAPE + ".vtx[*]", query=True, worldSpace=True, translation=True)
                    self.assertEqual(len(positions), len(expected[frame][0]))
                    for actual, reference in zip(positions, expected[frame][0]):
                        self.assertAlmostEqual(actual, reference, places=5)
                    # Custom properties use floor samples; only geometry is interpolated.
                    self.assertAlmostEqual(cmds.getAttr(SHAPE + ".density"), expected[math.floor(frame)][1], places=5)

    def check_import(self, ogawa):
        archive, expected = self.export_source(ogawa)
        cmds.ExocortexAlembic_import(j="filename={};normals=1;uvs=1;facesets=1".format(archive.as_posix()))
        self.assertTrue(cmds.objExists(SHAPE))
        self.assertEqual(set(cmds.polyUVSet(SHAPE, query=True, allUVSets=True)), {"map1", "detailUV"})
        self.assertEqual(cmds.getAttr(SHAPE + ".FACESET_panel"), [0, 2])
        self.assert_animation(expected)

    def test_ogawa_round_trip(self):
        self.check_import(ogawa=True)

    def test_hdf5_round_trip(self):
        self.check_import(ogawa=False)

    def test_attach_to_existing_mesh(self):
        archive, expected = self.export_source(ogawa=True)
        cmds.polyCube(name="cacheMesh", constructionHistory=False)
        cmds.addAttr(SHAPE, longName="density", attributeType="double", keyable=True)
        cmds.ExocortexAlembic_import(j="filename={};attachToExisting=1;facesets=1".format(archive.as_posix()))
        self.assertEqual(len(cmds.ls(type="mesh")), 2)  # visible shape plus deformer input
        self.assertEqual(len(cmds.ls(type="ExocortexAlembicPolyMeshDeform")), 1)
        self.assertEqual(cmds.getAttr(SHAPE + ".FACESET_panel"), [0, 2])
        self.assert_animation(expected)

    def test_reattach_updates_archive_identifiers(self):
        first_archive, _ = self.export_source(ogawa=True)
        self.create_source()
        cmds.rename("|cacheMesh", "otherMesh")
        second_archive = Path(self.directory.name) / "other.abc"
        cmds.select("|otherMesh", replace=True)
        _export.doIt(second_archive.as_posix(), 1, 3, exUseOgawa=True, userAttrs="density")
        cmds.file(new=True, force=True)
        cmds.polyCube(name="cacheMesh", constructionHistory=False)
        cmds.addAttr(SHAPE, longName="density", attributeType="double", keyable=True)
        cmds.ExocortexAlembic_import(j="filename={};attachToExisting=1".format(first_archive.as_posix()))
        deformers = cmds.ls(type="ExocortexAlembicPolyMeshDeform")
        cmds.ExocortexAlembic_import(j=(
            "filename={};attachToExisting=1;search=otherMesh;replace=cacheMesh"
        ).format(second_archive.as_posix()))
        self.assertEqual(cmds.ls(type="ExocortexAlembicPolyMeshDeform"), deformers)
        self.assertEqual(cmds.getAttr(deformers[0] + ".identifier"), "/otherMesh/otherMeshShape")
        transform_reader = cmds.ls(type="ExocortexAlembicXform")[0]
        self.assertEqual(cmds.getAttr(transform_reader + ".identifier"), "/otherMesh")
        cmds.currentTime(3)
        self.assertAlmostEqual(cmds.getAttr("|cacheMesh.translateX"), 4)

    def test_imported_scene_can_be_saved_and_reopened(self):
        archive, expected = self.export_source(ogawa=True)
        cmds.ExocortexAlembic_import(j="filename={}".format(archive.as_posix()))
        scene = Path(self.directory.name) / "cached_scene.ma"
        cmds.file(rename=str(scene))
        cmds.file(save=True, type="mayaAscii", force=True)
        cmds.file(new=True, force=True)
        cmds.file(str(scene), open=True, force=True, prompt=False)
        self.assert_animation(expected)

    def test_attach_preserves_destination_topology_and_maps_by_index(self):
        archive, expected = self.export_source(ogawa=True)
        for subdivisions in (1, 3):
            with self.subTest(subdivisions=subdivisions):
                cmds.file(new=True, force=True)
                cmds.polyPlane(name="cacheMesh", subdivisionsX=subdivisions,
                               subdivisionsY=subdivisions, constructionHistory=False)
                count = cmds.polyEvaluate(SHAPE, vertex=True)
                faces = cmds.polyEvaluate(SHAPE, face=True)
                original = cmds.xform(SHAPE + ".vtx[*]", query=True, objectSpace=True, translation=True)
                cmds.addAttr(SHAPE, longName="density", attributeType="double")
                cmds.ExocortexAlembic_import(j=(
                    "filename={};attachToExisting=1;facesets=0"
                ).format(archive.as_posix()))
                cmds.currentTime(3)
                actual = cmds.xform(SHAPE + ".vtx[*]", query=True, worldSpace=True, translation=True)
                self.assertEqual(cmds.polyEvaluate(SHAPE, vertex=True), count)
                self.assertEqual(cmds.polyEvaluate(SHAPE, face=True), faces)
                mapped_values = min(len(actual), len(expected[3][0]))
                for value, reference in zip(actual[:mapped_values], expected[3][0][:mapped_values]):
                    self.assertAlmostEqual(value, reference, places=5)
                # Indices beyond the eight cached vertices retain their input
                # positions, transformed by the cached translateX of four.
                for index in range(mapped_values, len(actual)):
                    reference = original[index] + (4 if index % 3 == 0 else 0)
                    self.assertAlmostEqual(actual[index], reference, places=5)


if __name__ == "__main__":
    try:
        program = unittest.main(argv=[sys.argv[0]] + remaining, exit=False)
    finally:
        maya.standalone.uninitialize()
    sys.exit(0 if program.result.wasSuccessful() else 1)
