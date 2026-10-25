"""Camera, curve, particle and variable-topology acceptance tests in mayapy."""

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
import maya.OpenMaya as om
from ExocortexAlembic import _export


class FeatureRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cmds.loadPlugin(str(plugin), quiet=True)

    def setUp(self):
        cmds.file(new=True, force=True)
        cmds.currentUnit(time="film")
        cmds.evaluationManager(mode="off")
        self.directory = tempfile.TemporaryDirectory(prefix="crate-features-")
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(lambda: cmds.file(new=True, force=True))

    def key(self, plug, first, last, stepped=False):
        cmds.setKeyframe(plug, time=1, value=first)
        cmds.setKeyframe(plug, time=3, value=last)
        cmds.keyTangent(plug, inTangentType="linear", outTangentType="step" if stepped else "linear")

    def export(self, name, ogawa=True, dynamic=False):
        archive = Path(self.directory.name) / (name + ".abc")
        cmds.select("|" + name, replace=True)
        _export.doIt(archive.as_posix(), 1, 3, exUseOgawa=ogawa, exDynTopo=dynamic)
        self.assertGreater(archive.stat().st_size, 0)
        return archive

    def import_archive(self, archive, attach=False):
        cmds.ExocortexAlembic_import(j="filename={};attachToExisting={};normals=1;uvs=1;facesets=1".format(
            archive.as_posix(), int(attach)))

    def assert_values(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=5)

    def check_camera(self, attach, ogawa):
        camera, _ = cmds.camera()
        camera = cmds.rename(camera, "cacheCamera")
        shape = cmds.rename(cmds.listRelatives(camera, shapes=True, fullPath=True)[0], "cacheCameraShape")
        cmds.setAttr(shape + ".filmFit", 1)  # Crate bakes horizontal film fit into the aperture.
        channels = {
            "focalLength": (35, 70), "focusDistance": (10, 20),
            "lensSqueezeRatio": (1, 1.2), "horizontalFilmAperture": (1.4, 1.6),
            "verticalFilmAperture": (0.9, 1.1), "horizontalFilmOffset": (0.1, 0.3),
            "verticalFilmOffset": (-0.2, -0.4), "nearClipPlane": (0.2, 0.4),
            "farClipPlane": (500, 700), "fStop": (2.8, 5.6), "shutterAngle": (120, 180),
        }
        for channel, values in channels.items():
            self.key(shape + "." + channel, *values)
        expected = {}
        for frame in (1, 1.5, 2, 3):
            cmds.currentTime(frame)
            expected[frame] = [cmds.getAttr(shape + "." + c) for c in channels]
            expected[frame][list(channels).index("verticalFilmAperture")] = (
                cmds.getAttr(shape + ".horizontalFilmAperture") /
                cmds.getAttr("defaultResolution.deviceAspectRatio"))
        archive = self.export("cacheCamera", ogawa=ogawa)
        cmds.file(new=True, force=True)
        if attach:
            camera, _ = cmds.camera()
            camera = cmds.rename(camera, "cacheCamera")
            cmds.rename(cmds.listRelatives(camera, shapes=True, fullPath=True)[0], "cacheCameraShape")
        self.import_archive(archive, attach=attach)
        for mode in ("off", "serial", "parallel"):
            cmds.evaluationManager(mode=mode)
            for frame in (3, 1, 1.5, 2):
                cmds.currentTime(frame)
                for channel, value in zip(channels, expected[frame]):
                    with self.subTest(mode=mode, frame=frame, channel=channel):
                        self.assertAlmostEqual(cmds.getAttr("cacheCameraShape." + channel), value, places=5)

    def test_camera_ogawa(self):
        self.check_camera(attach=False, ogawa=True)

    def test_camera_hdf5(self):
        self.check_camera(attach=False, ogawa=False)

    def test_camera_attach(self):
        self.check_camera(attach=True, ogawa=True)

    def check_curve(self, degree, attach=False):
        cmds.curve(name="guide", degree=degree, point=[(0, 0, 0), (1, 1, 0), (2, 0, 0), (3, 1, 0)])
        cmds.rename(cmds.listRelatives("guide", shapes=True, fullPath=True)[0], "guideShape")
        self.key("guideShape.controlPoints[1].yValue", 1, 4)
        expected = {}
        for frame in (1, 1.25, 1.75, 2, 3):
            cmds.currentTime(frame)
            expected[frame] = cmds.xform("guideShape.cv[*]", query=True, objectSpace=True, translation=True)
        archive = self.export("guide")
        cmds.file(new=True, force=True)
        if attach:
            cmds.curve(name="guide", degree=degree, point=[(0, 0, 0), (1, 1, 0), (2, 0, 0), (3, 1, 0)])
            cmds.rename(cmds.listRelatives("guide", shapes=True, fullPath=True)[0], "guideShape")
        self.import_archive(archive, attach=attach)
        for mode in ("off", "serial", "parallel"):
            cmds.evaluationManager(mode=mode)
            for frame in (3, 1, 1.25, 1.75, 2):
                with self.subTest(mode=mode, frame=frame):
                    cmds.currentTime(frame)
                    self.assert_values(cmds.xform("guideShape.cv[*]", query=True, objectSpace=True,
                                                 translation=True), expected[frame])

    def test_linear_curve(self):
        self.check_curve(degree=1)

    def test_cubic_curve(self):
        self.check_curve(degree=3)

    def test_curve_attach(self):
        self.check_curve(degree=3, attach=True)

    def test_curve_locator_fractional_bounds(self):
        cmds.curve(name="guide", degree=1, point=[(0, 0, 0), (1, 1, 0)])
        cmds.rename(cmds.listRelatives("guide", shapes=True, fullPath=True)[0], "guideShape")
        self.key("guideShape.controlPoints[1].yValue", 1, 5)
        archive = self.export("guide")
        cmds.file(new=True, force=True)
        node = cmds.createNode("ExocortexAlembicCurvesLocator")
        cmds.setAttr(node + ".fileName", archive.as_posix(), type="string")
        cmds.setAttr(node + ".identifier", "/guide/guideShape", type="string")
        for frame, ymax in ((1.25, 1.5), (1.75, 2.5), (1, 1), (3, 5)):
            with self.subTest(frame=frame):
                cmds.setAttr(node + ".inTime", frame)
                self.assertAlmostEqual(cmds.exactWorldBoundingBox(node)[4], ymax, places=5)

    def test_dynamic_vertex_count(self):
        _, generator = cmds.polyCube(name="changing")
        self.key(generator + ".subdivisionsWidth", 1, 3, stepped=True)
        expected = {}
        for frame in (1, 2, 3):
            cmds.currentTime(frame)
            expected[frame] = cmds.polyEvaluate("changingShape", vertex=True)
        archive = self.export("changing", dynamic=True)
        cmds.file(new=True, force=True)
        self.import_archive(archive)
        self.assertFalse(cmds.ls(type="ExocortexAlembicPolyMeshDeform"))
        for frame in (3, 1, 2, 3):
            cmds.currentTime(frame)
            self.assertEqual(cmds.polyEvaluate("changingShape", vertex=True), expected[frame])

    def test_dynamic_connectivity_with_constant_face_counts(self):
        points = om.MFloatPointArray()
        for point in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)):
            points.append(om.MFloatPoint(*point))
        counts = om.MIntArray()
        for _ in range(4):
            counts.append(3)
        meshes = []
        for name, faces in (("sourceA", (0, 1, 2, 0, 3, 1, 0, 2, 3, 1, 3, 2)),
                            ("sourceB", (0, 2, 1, 0, 1, 3, 0, 3, 2, 1, 2, 3))):
            indices = om.MIntArray()
            for index in faces:
                indices.append(index)
            fn = om.MFnMesh()
            obj = fn.create(4, 4, points, counts, indices)
            meshes.append(cmds.rename(om.MFnDagNode(obj).fullPathName(), name))
        parent = cmds.createNode("transform", name="changing")
        target = cmds.createNode("mesh", name="changingShape", parent=parent)
        selector = cmds.createNode("choice")
        for i, mesh in enumerate(meshes):
            shape = cmds.listRelatives(mesh, shapes=True, fullPath=True)[0]
            cmds.connectAttr(shape + ".outMesh", selector + ".input[{}]".format(i))
        cmds.connectAttr(selector + ".output", target + ".inMesh")
        self.key(selector + ".selector", 0, 1, stepped=True)
        expected = {}
        for frame in (1, 3):
            cmds.currentTime(frame)
            expected[frame] = cmds.polyInfo(target + ".f[*]", faceToVertex=True)
        archive = self.export("changing", dynamic=True)
        cmds.file(new=True, force=True)
        self.import_archive(archive)
        self.assertFalse(cmds.ls(type="ExocortexAlembicPolyMeshDeform"))
        for frame in (3, 1, 3):
            cmds.currentTime(frame)
            self.assertEqual(cmds.polyInfo("changingShape.f[*]", faceToVertex=True), expected[frame])

    def test_particle_round_trip(self):
        _, shape = cmds.particle(name="cloud", position=[(0, 0, 0), (2, 1, 0)])
        expected = cmds.getParticleAttr(shape, attribute="position", array=True)
        archive = self.export("cloud")
        cmds.file(new=True, force=True)
        self.import_archive(archive)
        for frame in (1, 2, 3, 1):
            cmds.currentTime(frame)
            with self.subTest(frame=frame):
                self.assertEqual(cmds.particle("cloudShape", query=True, count=True), 2)
                self.assert_values(cmds.getParticleAttr("cloudShape", attribute="position", array=True), expected)

    def test_particle_reattach_at_same_frame(self):
        cmds.particle(name="cloud", position=[(0, 0, 0)])
        first = Path(self.directory.name) / "first.abc"
        self.export("cloud").rename(first)
        cmds.file(new=True, force=True)
        cmds.particle(name="cloud", position=[(5, 6, 7)])
        second = self.export("cloud")
        cmds.file(new=True, force=True)
        self.import_archive(first)
        cmds.currentTime(1)
        self.assert_values(cmds.getParticleAttr("cloudShape", attribute="position", array=True), [0, 0, 0])
        readers = cmds.ls(type="ExocortexAlembicPoints")
        self.import_archive(second, attach=True)
        self.assertEqual(cmds.ls(type="ExocortexAlembicPoints"), readers)
        self.assert_values(cmds.getParticleAttr("cloudShape", attribute="position", array=True), [5, 6, 7])

    def test_emitting_particles_round_trip(self):
        _, shape = cmds.particle(name="cloud", position=[(0, 0, 0), (2, 1, 0)])
        emitter = cmds.emitter(name="source", type="omni", rate=48, speed=1)[0]
        cmds.connectDynamic(shape, emitters=emitter)
        cmds.saveInitialState(shape)
        expected = {}
        for frame in (1, 2, 3):
            cmds.currentTime(frame)
            expected[frame] = cmds.getParticleAttr(shape, attribute="position", array=True)
        self.assertGreater(len(expected[3]), len(expected[1]))
        cmds.currentTime(1)
        archive = self.export("cloud")
        cmds.file(new=True, force=True)
        self.import_archive(archive)
        for frame in (1, 2, 3, 1, 3, 2):
            cmds.currentTime(frame)
            with self.subTest(frame=frame):
                self.assert_values(cmds.getParticleAttr("cloudShape", attribute="position", array=True),
                                   expected[frame])

    def test_subdivision_export_and_import(self):
        cmds.polyCube(name="cage")
        self.key("cageShape.pnts[0].pnty", 0, 2)
        cmds.ExocortexAlembic_meshToSubdiv(mesh="cage")
        self.assertEqual(cmds.nodeType("cageShape_SubD"), "subdiv")
        expected = {}
        for frame in (1, 1.25, 1.75, 2.25, 2.75, 3):
            cmds.currentTime(frame)
            expected[frame] = cmds.exactWorldBoundingBox("cage_SubD")
        archive = self.export("cage_SubD")
        cmds.file(new=True, force=True)
        self.import_archive(archive)
        for frame in (3, 1, 1.25, 1.75, 2.25, 2.75):
            cmds.currentTime(frame)
            with self.subTest(frame=frame):
                self.assert_values(cmds.exactWorldBoundingBox("cage_SubD"), expected[frame])


if __name__ == "__main__":
    try:
        program = unittest.main(argv=[sys.argv[0]] + remaining, exit=False)
    finally:
        maya.standalone.uninitialize()
    sys.exit(0 if program.result.wasSuccessful() else 1)
