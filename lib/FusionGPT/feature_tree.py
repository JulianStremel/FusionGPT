"""Extract the Fusion 360 design feature tree as structured context for the AI."""

import json
import traceback

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    pass


def get_feature_tree_context() -> str:
    """Extract the current design's feature tree and return it as a structured string
    suitable for inclusion in AI system prompts."""
    try:
        app = adsk.core.Application.get()
        if not app:
            return ""

        product = app.activeProduct
        if not product or not isinstance(product, adsk.fusion.Design):
            return "(No active Fusion 360 design open)"

        design: adsk.fusion.Design = product
        root = design.rootComponent

        info = {
            "designName": design.parentDocument.name if design.parentDocument else "Untitled",
            "designType": "Parametric" if design.designType == adsk.fusion.DesignTypes.ParametricDesignType else "Direct",
            "units": design.unitsManager.defaultLengthUnits,
            "components": _extract_component(root),
            "timeline": _extract_timeline(design),
            "parameters": _extract_parameters(design),
        }

        lines = ["=== Current Fusion 360 Design Context ==="]
        lines.append(f"Design: {info['designName']}")
        lines.append(f"Type: {info['designType']}")
        lines.append(f"Units: {info['units']}")
        lines.append("")

        lines.append("--- Component Tree ---")
        lines.append(_format_component_tree(info["components"]))

        if info["timeline"]:
            lines.append("--- Timeline ---")
            for item in info["timeline"]:
                lines.append(f"  [{item['index']}] {item['type']}: {item['name']}")
            lines.append("")

        if info["parameters"]:
            lines.append("--- User Parameters ---")
            for p in info["parameters"]:
                lines.append(f"  {p['name']} = {p['expression']} ({p['unit']})")
            lines.append("")

        return "\n".join(lines)

    except Exception:
        return f"(Error extracting feature tree: {traceback.format_exc()})"


def _extract_component(component, depth=0) -> dict:
    """Recursively extract component hierarchy."""
    result = {
        "name": component.name,
        "bodies": [],
        "sketches": [],
        "joints": [],
        "occurrences": [],
        "features": [],
    }

    for i in range(component.bRepBodies.count):
        body = component.bRepBodies.item(i)
        result["bodies"].append({
            "name": body.name,
            "visible": body.isVisible,
            "faces": body.faces.count,
            "edges": body.edges.count,
        })

    for i in range(component.sketches.count):
        sketch = component.sketches.item(i)
        result["sketches"].append({
            "name": sketch.name,
            "profileCount": sketch.profiles.count,
            "curveCount": sketch.sketchCurves.count,
            "isFullyConstrained": sketch.isFullyConstrained if hasattr(sketch, 'isFullyConstrained') else None,
        })

    for i in range(component.joints.count):
        joint = component.joints.item(i)
        result["joints"].append({
            "name": joint.name,
            "type": str(joint.jointMotion.jointType) if joint.jointMotion else "unknown",
        })

    try:
        features = component.features
        for i in range(features.count):
            feat = features.item(i)
            result["features"].append({
                "name": feat.name,
                "type": feat.objectType.split("::")[-1] if feat.objectType else "Unknown",
                "isSuppressed": feat.isSuppressed if hasattr(feat, 'isSuppressed') else False,
                "errorOrWarning": feat.errorOrWarningMessage if hasattr(feat, 'errorOrWarningMessage') else None,
            })
    except Exception:
        pass

    for i in range(component.occurrences.count):
        occ = component.occurrences.item(i)
        child = _extract_component(occ.component, depth + 1)
        child["occurrenceName"] = occ.name
        result["occurrences"].append(child)

    return result


def _extract_timeline(design) -> list:
    """Extract the design timeline."""
    items = []
    try:
        timeline = design.timeline
        for i in range(timeline.count):
            item = timeline.item(i)
            entity = item.entity
            items.append({
                "index": i,
                "name": entity.name if entity and hasattr(entity, 'name') else f"Item {i}",
                "type": entity.objectType.split("::")[-1] if entity and hasattr(entity, 'objectType') else "Unknown",
            })
    except Exception:
        pass
    return items


def _extract_parameters(design) -> list:
    """Extract user-defined parameters."""
    params = []
    try:
        for i in range(design.userParameters.count):
            param = design.userParameters.item(i)
            params.append({
                "name": param.name,
                "expression": param.expression,
                "value": param.value,
                "unit": param.unit,
            })
    except Exception:
        pass
    return params


def _format_component_tree(comp, indent=0) -> str:
    """Format component hierarchy as indented text."""
    prefix = "  " * indent
    lines = [f"{prefix}Component: {comp['name']}"]

    if comp.get("occurrenceName"):
        lines[-1] = f"{prefix}Occurrence: {comp['occurrenceName']} -> {comp['name']}"

    if comp["bodies"]:
        for b in comp["bodies"]:
            vis = "" if b["visible"] else " [hidden]"
            lines.append(f"{prefix}  Body: {b['name']}{vis} ({b['faces']} faces, {b['edges']} edges)")

    if comp["sketches"]:
        for s in comp["sketches"]:
            constrained = ""
            if s["isFullyConstrained"] is not None:
                constrained = " [fully constrained]" if s["isFullyConstrained"] else " [under-constrained]"
            lines.append(f"{prefix}  Sketch: {s['name']} ({s['profileCount']} profiles, {s['curveCount']} curves){constrained}")

    if comp["features"]:
        for f in comp["features"]:
            suppressed = " [suppressed]" if f["isSuppressed"] else ""
            error = f" [!{f['errorOrWarning']}]" if f.get("errorOrWarning") else ""
            lines.append(f"{prefix}  Feature: {f['name']} ({f['type']}){suppressed}{error}")

    if comp["joints"]:
        for j in comp["joints"]:
            lines.append(f"{prefix}  Joint: {j['name']} ({j['type']})")

    for occ in comp["occurrences"]:
        lines.append(_format_component_tree(occ, indent + 1))

    lines.append("")
    return "\n".join(lines)
