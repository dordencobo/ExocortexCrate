#include "stdafx.h"

#if MAYA_API_VERSION >= 20240000
#include "AlembicCurvesDrawOverride.h"
#include "AlembicCurves.h"
#include <maya/MColorArray.h>
#include <maya/MHWGeometryUtilities.h>
#include <maya/MUIDrawManager.h>
#include <maya/MUintArray.h>
#include <maya/MUserData.h>

namespace {
class CurvesDrawData : public MUserData {
 public:
  MPointArray positions;
  MUintArray indices;
  MColorArray colors;
  MColor wireColor;
};
}

AlembicCurvesDrawOverride::AlembicCurvesDrawOverride(const MObject &object)
    : MHWRender::MPxDrawOverride(object, nullptr, true) {}

MHWRender::MPxDrawOverride *AlembicCurvesDrawOverride::creator(const MObject &object)
{
  return new AlembicCurvesDrawOverride(object);
}

MHWRender::DrawAPI AlembicCurvesDrawOverride::supportedDrawAPIs() const
{
  return MHWRender::kOpenGL | MHWRender::kOpenGLCoreProfile | MHWRender::kDirectX11;
}

MBoundingBox AlembicCurvesDrawOverride::boundingBox(const MDagPath &path, const MDagPath &) const
{
  auto *node = dynamic_cast<AlembicCurvesLocatorNode *>(MFnDependencyNode(path.node()).userNode());
  return node ? node->boundingBox() : MBoundingBox();
}

MUserData *AlembicCurvesDrawOverride::prepareForDraw(
    const MDagPath &path, const MDagPath &, const MHWRender::MFrameContext &, MUserData *oldData)
{
  auto *data = dynamic_cast<CurvesDrawData *>(oldData);
  if (!data) data = new CurvesDrawData();  // Ownership is transferred to Maya.
  data->positions.clear();
  data->indices.clear();
  data->colors.clear();
  data->wireColor = MHWRender::MGeometryUtilities::wireframeColor(path);
  auto *node = dynamic_cast<AlembicCurvesLocatorNode *>(MFnDependencyNode(path.node()).userNode());
  if (!node) return data;
  node->updated();
  for (const auto &position : node->mPositions)
    data->positions.append(MPoint(position.x, position.y, position.z));
  for (unsigned int index : node->mIndices)
    if (index < data->positions.length()) data->indices.append(index);
  if (node->mColors.size() == node->mPositions.size())
    for (const auto &color : node->mColors)
      data->colors.append(MColor(color.r, color.g, color.b, color.a));
  return data;
}

void AlembicCurvesDrawOverride::addUIDrawables(
    const MDagPath &, MHWRender::MUIDrawManager &manager,
    const MHWRender::MFrameContext &, const MUserData *userData)
{
  const auto *data = dynamic_cast<const CurvesDrawData *>(userData);
  if (!data || data->indices.length() < 2) return;
  manager.beginDrawable();
  manager.setColor(data->wireColor);
  manager.mesh(MHWRender::MUIDrawManager::kLines, data->positions, nullptr,
               data->colors.length() ? &data->colors : nullptr, &data->indices);
  manager.endDrawable();
}
#endif
