# Maya 2024 Windows build

This standalone CMake entry point builds only the Maya plugin and its dependencies.
The root CMake project still serves the historical application versions.

## Requirements

- Maya 2024, including its C++ headers, import libraries and `mayapy`.
- Visual Studio 2022 C++ Build Tools (v143), x64, with a Windows SDK.
- CMake 3.22 or newer.
- Boost 1.80.0 sources. Only Filesystem and Regex are compiled; Boost.Python is not used.

The first build retains the vendored Alembic 1.5.0, HDF5 1.8.9, IlmBase 1.0.2
and zlib 1.2.5. These libraries are linked statically into the plugin, with the
dynamic MSVC runtime (`/MD` for Release). The build restores the old STL types
required by Alembic through `_HAS_AUTO_PTR_ETC`; this is a compatibility measure,
not a migration to modern Alembic.

## Build and stage

Run from the repository root in PowerShell:

```powershell
New-Item -ItemType Directory -Force .deps | Out-Null
Invoke-WebRequest https://archives.boost.io/release/1.80.0/source/boost_1_80_0.tar.bz2 -OutFile .deps/boost_1_80_0.tar.bz2
if ((Get-FileHash .deps/boost_1_80_0.tar.bz2 -Algorithm SHA256).Hash -ne '1e19565d82e43bc59209a168f5ac899d3ba471d55c7610c677d4ccf2c9c500c0') { throw 'Boost checksum mismatch' }
tar -xf .deps/boost_1_80_0.tar.bz2 -C .deps

cmake -S Maya/2024 -B build/maya2024 -G 'Visual Studio 17 2022' -A x64
cmake --build build/maya2024 --config Release --target MayaExocortexAlembic --parallel 6
cmake --install build/maya2024 --config Release --prefix build/maya2024/stage
```

Use `-DMAYA_ROOT=...` or `-DBOOST_ROOT=...` at configure time to override the
default locations. The initial HDF5 configuration runs platform probes and can
take several minutes. The old invalid printf probe is bypassed using MSVC's
supported `I64` format.

Staging produces `build/maya2024/stage/Maya2024ExocortexAlembic.mod` and
`Module/plug-ins/MayaExocortexAlembic.mll`, scripts and UI files. It does not
install anything into Maya or the user's module directory. Dependency downloads,
build outputs and the isolated test profile are ignored by Git.

## Validation

```powershell
& 'C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe' -B tests/maya/test_python3_package.py
$env:MAYA_APP_DIR = "$PWD/build/maya2024/test-profile"
& 'C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe' -B tests/maya/test_plugin_load.py --plugin build/maya2024/stage/Module/plug-ins/MayaExocortexAlembic.mll
```

The plugin test runs in a separate Maya standalone process. It loads the native
AbcImport/AbcExport plugins, checks registration of all 12 Crate node types and
12 commands, evaluates the time controller, and checks two load/unload cycles.
No user scene is opened or saved.

The load test alone does **not** validate Alembic file interchange. Run the
round-trip and viewport suites below as well. Old dependencies and some
deprecated Maya APIs remain; passing these fixtures does not establish
production readiness.

The duplicate-name export regression can be run separately:

```powershell
& 'C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe' -B tests/maya/test_export_duplicate_names.py --plugin build/maya2024/stage/Module/plug-ins/MayaExocortexAlembic.mll
```

It exports two static meshes with the same shape leaf name and verifies their
geometry and explicit face sets. HDF5 is read with Crate; Ogawa is imported with
Maya's native AbcImport. This does not exercise an animated production asset.

## Animated mesh validation

```powershell
& 'C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe' -B tests/maya/test_animated_mesh.py --plugin build/maya2024/stage/Module/plug-ins/MayaExocortexAlembic.mll
```

This suite verifies HDF5 and Ogawa export/import of a cube with animated
transforms, vertex deformation, two UV sets, explicit face sets and a custom
attribute. Geometry and attribute values are checked while scrubbing in DG,
EM serial and EM parallel, including fractional frames. Imported scenes are
also saved and reopened. This small scene does not establish general thread
safety, Cached Playback support or correctness on production rigs.

The suite also exercises attachment and switching an existing reader to a
different archive identifier. Custom attributes retain Crate's floor-sample
behavior between frames; geometry is interpolated. Attachment remains strictly
by vertex index: it preserves destination connectivity and leaves vertices
outside the cache's position array unchanged. Matching counts alone do not
establish a correct correspondence, and there is no spatial transfer.

## Cameras, curves, particles and changing topology

```powershell
& 'C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe' -B tests/maya/test_feature_roundtrip.py --plugin build/maya2024/stage/Module/plug-ins/MayaExocortexAlembic.mll
& 'C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe' -B tests/maya/test_viewport2.py --plugin build/maya2024/stage/Module/plug-ins/MayaExocortexAlembic.mll
```

The feature suite covers 11 animated camera channels (including vertical film
offset, f-stop and clipping planes), camera attachment, linear/cubic curves,
curve attachment at fractional frames, locator bounds, changing vertex counts,
changing connectivity with constant face counts, static and emitting particles,
reattachment of particles at the same frame, and a legacy subdivision surface
exported from a converted polygon cage.
Camera export retains the existing film-fit baking into aperture values.
Camera and curve scrubbing is checked in DG, EM serial and EM parallel.

The curve locator now has a native VP2 draw override. Its draw data owns a
snapshot of positions, indices and colors. The viewport test uses hardware
rendering and compares pixels for hidden, visible and animated states; a GPU
and working OpenGL driver are required. This validates the OpenGL path on this
machine, not DirectX 11 or every interactive viewport configuration.

## Evaluation policy and remaining limits

Crate readers share mutable archive state. Maya 2024 readers/deformers/locators
declare `kGloballySerial`; the particle emitter declares `kUntrusted` because
it also modifies its connected Maya particle system. EM parallel can remain
enabled for the scene, but these nodes do not promise parallel execution.
Cached Playback is explicitly disabled for these nodes. Full concurrency and
Cached Playback require a separate redesign of archive ownership and outputs.

The Maya scripts use Python 3 directly, without Boost.Python. The separate
historical `Python/` extension is not built by this Maya target. VS2022 v143
is the toolchain tested here; VS2019 has not been validated.

The tests do not certify large production scenes, particle instancing and all
per-particle attributes, grouped/multiple curves, subdivision creases, archive
layers or malformed/untrusted Alembic files. Particle IDs are not restored to
Maya's native particle IDs; positions are assigned by sample-array order.
The old Alembic/HDF5 dependencies remain statically linked; coexistence with
native Maya Alembic passes the load test, but does not prove compatibility with
every third-party Alembic plugin.

## Run the complete acceptance suite

```powershell
./tests/maya/run_maya2024_tests.ps1 -Plugin build/maya2024/stage/Module/plug-ins/MayaExocortexAlembic.mll
```

This runs 27 tests in six independent mayapy processes and writes logs under
`build/maya2024/test-results`. It uses an isolated Maya profile and leaves any
interactive Maya session alone.

## Load the packaged module in Maya

Extract the package to a permanent folder. Add the folder containing
`Maya2024ExocortexAlembic.mod` to `MAYA_MODULE_PATH` in Maya 2024's `Maya.env`,
preserving existing entries. For the local final stage, for example:

```text
MAYA_MODULE_PATH=C:/Users/Usuario/repo/exocortex/ExocortexCrate-maya2024/build/maya2024/stage-complete
```

Restart Maya, then enable `MayaExocortexAlembic.mll` in Plug-in Manager. The
Alembic menu is registered on load. Restart before switching from an older
build: a loaded plugin DLL must not be overwritten or replaced in a live scene.
The package includes the original license; keep it with redistributed copies.
