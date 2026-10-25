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

The load test alone does **not** validate Alembic file interchange. The old
dependencies and deprecated Maya APIs remain; this is an experimental port,
not a production-ready plugin.

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

Particles, cameras, dynamic topology and interactive Viewport 2.0 remain outside
this validation milestone.
