cmake_minimum_required(VERSION 3.22)
project(ExocortexCrateMaya2024 VERSION 1.1.151 LANGUAGES C CXX)

if(NOT WIN32 OR NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "This Maya 2024 build requires 64-bit Windows and MSVC.")
endif()

get_filename_component(CRATE_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
set(MAYA_ROOT "C:/Program Files/Autodesk/Maya2024" CACHE PATH "Maya 2024 SDK root")
set(BOOST_ROOT "${CRATE_ROOT}/.deps/boost_1_80_0" CACHE PATH "Boost 1.80.0 source root")
if(NOT EXISTS "${MAYA_ROOT}/include/maya/MFnPlugin.h" OR
   NOT EXISTS "${MAYA_ROOT}/lib/OpenMaya.lib")
    message(FATAL_ERROR "MAYA_ROOT must contain the Maya 2024 headers and libraries.")
endif()
file(STRINGS "${MAYA_ROOT}/include/maya/MTypes.h" maya_api REGEX "^#define MAYA_API_VERSION ")
if(NOT maya_api MATCHES "2024[0-9]+")
    message(FATAL_ERROR "MAYA_ROOT must point to Maya 2024.")
endif()
if(NOT EXISTS "${BOOST_ROOT}/boost/version.hpp")
    message(FATAL_ERROR "Set BOOST_ROOT to an extracted Boost 1.80.0 source distribution.")
endif()
file(STRINGS "${BOOST_ROOT}/boost/version.hpp" boost_version REGEX "^#define BOOST_VERSION ")
if(NOT boost_version MATCHES "108000$")
    message(FATAL_ERROR "This build has been prepared for Boost 1.80.0.")
endif()

set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded$<$<CONFIG:Debug>:Debug>DLL)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# The vendored HDF5 build predates CMake's current minimum policy version.
set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "Static third-party libraries" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "Disable third-party tests" FORCE)

file(GLOB zlib_sources CONFIGURE_DEPENDS "${CRATE_ROOT}/Shared/zlib-1.2.5/*.c")
list(FILTER zlib_sources EXCLUDE REGEX "/(example|minigzip)\\.c$")
add_library(crate_zlib STATIC ${zlib_sources})
configure_file("${CRATE_ROOT}/Shared/zlib-1.2.5/zconf.h.cmakein" "${CMAKE_CURRENT_BINARY_DIR}/zlib/zconf.h")
target_include_directories(crate_zlib PUBLIC "${CRATE_ROOT}/Shared/zlib-1.2.5" "${CMAKE_CURRENT_BINARY_DIR}/zlib")
target_compile_definitions(crate_zlib PRIVATE _CRT_SECURE_NO_WARNINGS)
set(H5_ZLIB_HEADER "zlib.h")
set(ZLIB_LIBRARIES crate_zlib)
set(ZLIB_INCLUDE_DIRS "${CRATE_ROOT}/Shared/zlib-1.2.5" "${CMAKE_CURRENT_BINARY_DIR}/zlib")

set(HDF5_BUILD_CPP_LIB OFF CACHE BOOL "" FORCE)
set(HDF5_BUILD_FORTRAN OFF CACHE BOOL "" FORCE)
set(HDF5_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(HDF5_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(HDF5_BUILD_HL_LIB ON CACHE BOOL "" FORCE)
set(HDF5_ENABLE_Z_LIB_SUPPORT ON CACHE BOOL "" FORCE)
set(HDF5_ENABLE_SZIP_SUPPORT OFF CACHE BOOL "" FORCE)
set(HDF5_ENABLE_THREADSAFE ON CACHE BOOL "" FORCE)
set(HDF5_NO_PACKAGES ON CACHE BOOL "" FORCE)
set(HDF5_EXTERNALLY_CONFIGURED ON)
# The old printf probe invokes invalid format strings and opens a CRT dialog.
set(H5_PRINTF_LL_WIDTH "\"I64\"" CACHE INTERNAL "MSVC 64-bit printf format")
add_subdirectory("${CRATE_ROOT}/Shared/hdf5-1.8.9" hdf5 EXCLUDE_FROM_ALL)

add_library(crate_dependencies INTERFACE)
target_compile_definitions(crate_dependencies INTERFACE
    NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS BOOST_ALL_NO_LIB
    # Alembic 1.5 still exposes std::auto_ptr in public headers.
    _HAS_AUTO_PTR_ETC=1)
target_compile_options(crate_dependencies INTERFACE /Zc:__cplusplus /MP)
target_include_directories(crate_dependencies INTERFACE
    "${BOOST_ROOT}"
    "${CRATE_ROOT}/Shared/alembic-1.5.0"
    "${CRATE_ROOT}/Shared/ilmbase-1.0.2/Half"
    "${CRATE_ROOT}/Shared/ilmbase-1.0.2/Iex"
    "${CRATE_ROOT}/Shared/ilmbase-1.0.2/Imath"
    "${CRATE_ROOT}/Shared/ilmbase-1.0.2/IlmThread"
    "${CRATE_ROOT}/Shared/ilmbase-1.0.2/config.windows"
    "${CRATE_ROOT}/Shared/hdf5-1.8.9/src"
    "${CRATE_ROOT}/Shared/hdf5-1.8.9/hl/src"
    "${CMAKE_CURRENT_BINARY_DIR}/hdf5")

# Build only the two compiled Boost components used by CommonUtils.
file(GLOB boost_regex_sources CONFIGURE_DEPENDS "${BOOST_ROOT}/libs/regex/src/*.cpp")
file(GLOB boost_filesystem_sources CONFIGURE_DEPENDS "${BOOST_ROOT}/libs/filesystem/src/*.cpp")
add_library(crate_boost STATIC ${boost_regex_sources} ${boost_filesystem_sources})
target_link_libraries(crate_boost PRIVATE crate_dependencies)
target_compile_definitions(crate_boost PRIVATE BOOST_FILESYSTEM_STATIC_LINK BOOST_REGEX_STATIC_LINK
    BOOST_FILESYSTEM_NO_CXX20_ATOMIC_REF)

file(GLOB ilmbase_sources CONFIGURE_DEPENDS
    "${CRATE_ROOT}/Shared/ilmbase-1.0.2/Half/*.cpp"
    "${CRATE_ROOT}/Shared/ilmbase-1.0.2/Iex/*.cpp"
    "${CRATE_ROOT}/Shared/ilmbase-1.0.2/Imath/*.cpp"
    "${CRATE_ROOT}/Shared/ilmbase-1.0.2/IlmThread/*.cpp")
list(FILTER ilmbase_sources EXCLUDE REGEX "Posix\\.cpp$")
add_library(crate_ilmbase STATIC ${ilmbase_sources})
target_link_libraries(crate_ilmbase PRIVATE crate_dependencies)

file(GLOB_RECURSE alembic_sources CONFIGURE_DEPENDS
    "${CRATE_ROOT}/Shared/alembic-1.5.0/Alembic/*.cpp")
list(FILTER alembic_sources EXCLUDE REGEX "/Tests/")
add_library(crate_alembic STATIC ${alembic_sources})
target_link_libraries(crate_alembic PUBLIC crate_dependencies crate_ilmbase hdf5 hdf5_hl)

file(GLOB common_sources CONFIGURE_DEPENDS "${CRATE_ROOT}/Shared/CommonUtils/*.cpp")
add_library(crate_common STATIC ${common_sources})
target_include_directories(crate_common PUBLIC "${CRATE_ROOT}/Shared/CommonUtils")
target_link_libraries(crate_common PUBLIC crate_alembic crate_boost)
target_compile_definitions(crate_common PUBLIC
    crate_MAJOR_VERSION=1 crate_MINOR_VERSION=1 crate_BUILD_VERSION=151
    crate_Maya_Version=2024 alembic_ver=alembic-1.5.0 hdf_ver=hdf5-1.8.9 crate_ver=crate-1.1.151)

file(GLOB maya_sources CONFIGURE_DEPENDS "${CRATE_ROOT}/Maya/*.cpp")
add_library(MayaExocortexAlembic MODULE ${maya_sources})
target_include_directories(MayaExocortexAlembic PRIVATE "${MAYA_ROOT}/include")
target_compile_definitions(MayaExocortexAlembic PRIVATE NT_PLUGIN REQUIRE_IOSTREAM _BOOL)
target_link_libraries(MayaExocortexAlembic PRIVATE crate_common opengl32)
foreach(component Foundation OpenMaya OpenMayaAnim OpenMayaFX OpenMayaRender OpenMayaUI)
    find_library(maya_${component} NAMES ${component} PATHS "${MAYA_ROOT}/lib" NO_DEFAULT_PATH REQUIRED)
    target_link_libraries(MayaExocortexAlembic PRIVATE "${maya_${component}}")
endforeach()
target_link_options(MayaExocortexAlembic PRIVATE /export:initializePlugin /export:uninitializePlugin)
set_target_properties(MayaExocortexAlembic PROPERTIES PREFIX "" SUFFIX ".mll")

install(TARGETS MayaExocortexAlembic LIBRARY DESTINATION Module/plug-ins
    RUNTIME DESTINATION Module/plug-ins)
install(DIRECTORY "${CRATE_ROOT}/Maya/MEL/" DESTINATION Module/scripts
    PATTERN "__pycache__" EXCLUDE PATTERN "*.pyc" EXCLUDE)
install(DIRECTORY "${CRATE_ROOT}/Maya/UI/" DESTINATION Module/ui)
install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/Maya2024ExocortexAlembic.mod" DESTINATION .)
install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/README.md" DESTINATION . RENAME README-MAYA2024.md)
install(FILES "${CRATE_ROOT}/LICENSE.txt" DESTINATION .)
