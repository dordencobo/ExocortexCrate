#ifndef CRATE_CURVES_DRAW_OVERRIDE_H
#define CRATE_CURVES_DRAW_OVERRIDE_H

#if MAYA_API_VERSION >= 20240000
#include <maya/MPxDrawOverride.h>

class AlembicCurvesDrawOverride : public MHWRender::MPxDrawOverride {
 public:
  explicit AlembicCurvesDrawOverride(const MObject &object);
  static MHWRender::MPxDrawOverride *creator(const MObject &object);
  MHWRender::DrawAPI supportedDrawAPIs() const override;
  bool hasUIDrawables() const override { return true; }
  bool isBounded(const MDagPath &, const MDagPath &) const override { return true; }
  MBoundingBox boundingBox(const MDagPath &path, const MDagPath &) const override;
  MUserData *prepareForDraw(const MDagPath &path, const MDagPath &camera,
                          const MHWRender::MFrameContext &context, MUserData *oldData) override;
  void addUIDrawables(const MDagPath &path, MHWRender::MUIDrawManager &manager,
                     const MHWRender::MFrameContext &context, const MUserData *data) override;
};
#endif
#endif
