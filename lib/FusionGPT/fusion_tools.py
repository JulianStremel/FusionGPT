"""OpenAI function-calling tool definitions for AI-driven Fusion 360 interactions.

Each tool is defined as an OpenAI tool schema plus a handler function that
executes the corresponding Fusion 360 API operation.
"""

import json
import math
import traceback

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    pass


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "create_sketch",
            "description": "Create a new sketch on a specified construction plane (XY, XZ, or YZ) of the root component.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plane": {
                        "type": "string",
                        "enum": ["XY", "XZ", "YZ"],
                        "description": "The construction plane to create the sketch on."
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional name for the sketch."
                    }
                },
                "required": ["plane"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "draw_rectangle",
            "description": "Draw a rectangle on an existing sketch by specifying two corner points (in cm).",
            "parameters": {
                "type": "object",
                "properties": {
                    "sketch_name": {
                        "type": "string",
                        "description": "Name of the sketch to draw on."
                    },
                    "x1": {"type": "number", "description": "X coordinate of first corner (cm)."},
                    "y1": {"type": "number", "description": "Y coordinate of first corner (cm)."},
                    "x2": {"type": "number", "description": "X coordinate of opposite corner (cm)."},
                    "y2": {"type": "number", "description": "Y coordinate of opposite corner (cm)."}
                },
                "required": ["sketch_name", "x1", "y1", "x2", "y2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "draw_circle",
            "description": "Draw a circle on an existing sketch by center point and radius (in cm).",
            "parameters": {
                "type": "object",
                "properties": {
                    "sketch_name": {
                        "type": "string",
                        "description": "Name of the sketch to draw on."
                    },
                    "center_x": {"type": "number", "description": "X coordinate of center (cm)."},
                    "center_y": {"type": "number", "description": "Y coordinate of center (cm)."},
                    "radius": {"type": "number", "description": "Radius of the circle (cm)."}
                },
                "required": ["sketch_name", "center_x", "center_y", "radius"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extrude_profile",
            "description": "Extrude the first profile of a sketch by a given distance to create a solid body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sketch_name": {
                        "type": "string",
                        "description": "Name of the sketch containing the profile."
                    },
                    "distance": {
                        "type": "number",
                        "description": "Extrusion distance in cm. Positive for one direction, negative for the other."
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["new_body", "join", "cut", "intersect"],
                        "description": "Boolean operation type. Default: new_body."
                    },
                    "profile_index": {
                        "type": "integer",
                        "description": "Index of the profile in the sketch (0-based). Default: 0."
                    }
                },
                "required": ["sketch_name", "distance"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_fillet",
            "description": "Add a fillet (rounded edge) to edges of a body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "body_name": {
                        "type": "string",
                        "description": "Name of the body to fillet."
                    },
                    "radius": {
                        "type": "number",
                        "description": "Fillet radius in cm."
                    },
                    "edge_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Indices of edges to fillet (0-based). If omitted, all edges are filleted."
                    }
                },
                "required": ["body_name", "radius"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_chamfer",
            "description": "Add a chamfer to edges of a body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "body_name": {
                        "type": "string",
                        "description": "Name of the body to chamfer."
                    },
                    "distance": {
                        "type": "number",
                        "description": "Chamfer distance in cm."
                    },
                    "edge_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Indices of edges to chamfer (0-based). If omitted, all edges are chamfered."
                    }
                },
                "required": ["body_name", "distance"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_parameter",
            "description": "Create or modify a user parameter in the design.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Parameter name."
                    },
                    "expression": {
                        "type": "string",
                        "description": "Value expression (e.g. '10 mm', '2.5 in', '45 deg')."
                    },
                    "unit": {
                        "type": "string",
                        "description": "Unit type (e.g. 'mm', 'cm', 'in', 'deg'). Default: 'cm'."
                    }
                },
                "required": ["name", "expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_design_info",
            "description": "Get detailed information about the current design including components, bodies, sketches, and parameters.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_component",
            "description": "Create a new component in the root of the design.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the new component."
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "revolve_profile",
            "description": "Revolve a sketch profile around an axis to create a solid body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sketch_name": {
                        "type": "string",
                        "description": "Name of the sketch containing the profile."
                    },
                    "axis": {
                        "type": "string",
                        "enum": ["X", "Y", "Z"],
                        "description": "Axis to revolve around."
                    },
                    "angle": {
                        "type": "number",
                        "description": "Revolution angle in degrees. 360 for full revolution."
                    },
                    "profile_index": {
                        "type": "integer",
                        "description": "Index of the profile (0-based). Default: 0."
                    }
                },
                "required": ["sketch_name", "axis", "angle"]
            }
        }
    },
]


def execute_tool(tool_name: str, arguments: dict) -> str:
    """Execute a Fusion 360 tool function and return the result as a string."""
    handlers = {
        "create_sketch": _create_sketch,
        "draw_rectangle": _draw_rectangle,
        "draw_circle": _draw_circle,
        "extrude_profile": _extrude_profile,
        "add_fillet": _add_fillet,
        "add_chamfer": _add_chamfer,
        "set_parameter": _set_parameter,
        "get_design_info": _get_design_info,
        "create_component": _create_component,
        "revolve_profile": _revolve_profile,
    }

    handler = handlers.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        result = handler(arguments)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e), "traceback": traceback.format_exc()})


def _get_root():
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        raise RuntimeError("No active Fusion 360 design. Please open or create a design first.")
    return design, design.rootComponent


def _get_plane(root, plane_name: str):
    planes = {
        "XY": root.xYConstructionPlane,
        "XZ": root.xZConstructionPlane,
        "YZ": root.yZConstructionPlane,
    }
    plane = planes.get(plane_name.upper())
    if not plane:
        raise ValueError(f"Invalid plane '{plane_name}'. Use XY, XZ, or YZ.")
    return plane


def _find_sketch(root, name: str):
    for i in range(root.sketches.count):
        sketch = root.sketches.item(i)
        if sketch.name == name:
            return sketch
    raise ValueError(f"Sketch '{name}' not found. Available sketches: {[root.sketches.item(i).name for i in range(root.sketches.count)]}")


def _find_body(root, name: str):
    for i in range(root.bRepBodies.count):
        body = root.bRepBodies.item(i)
        if body.name == name:
            return body
    raise ValueError(f"Body '{name}' not found. Available bodies: {[root.bRepBodies.item(i).name for i in range(root.bRepBodies.count)]}")


def _create_sketch(args: dict) -> dict:
    design, root = _get_root()
    plane = _get_plane(root, args["plane"])
    sketch = root.sketches.add(plane)
    if args.get("name"):
        sketch.name = args["name"]
    return {"success": True, "sketch_name": sketch.name, "message": f"Created sketch '{sketch.name}' on {args['plane']} plane."}


def _draw_rectangle(args: dict) -> dict:
    _, root = _get_root()
    sketch = _find_sketch(root, args["sketch_name"])
    lines = sketch.sketchCurves.sketchLines
    p1 = adsk.core.Point3D.create(args["x1"], args["y1"], 0)
    p2 = adsk.core.Point3D.create(args["x2"], args["y1"], 0)
    p3 = adsk.core.Point3D.create(args["x2"], args["y2"], 0)
    p4 = adsk.core.Point3D.create(args["x1"], args["y2"], 0)
    lines.addByTwoPoints(p1, p2)
    lines.addByTwoPoints(p2, p3)
    lines.addByTwoPoints(p3, p4)
    lines.addByTwoPoints(p4, p1)
    return {
        "success": True,
        "message": f"Drew rectangle on '{args['sketch_name']}' from ({args['x1']},{args['y1']}) to ({args['x2']},{args['y2']}).",
        "profiles_count": sketch.profiles.count,
    }


def _draw_circle(args: dict) -> dict:
    _, root = _get_root()
    sketch = _find_sketch(root, args["sketch_name"])
    center = adsk.core.Point3D.create(args["center_x"], args["center_y"], 0)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(center, args["radius"])
    return {
        "success": True,
        "message": f"Drew circle on '{args['sketch_name']}' at ({args['center_x']},{args['center_y']}) with radius {args['radius']}.",
        "profiles_count": sketch.profiles.count,
    }


def _extrude_profile(args: dict) -> dict:
    design, root = _get_root()
    sketch = _find_sketch(root, args["sketch_name"])
    profile_index = args.get("profile_index", 0)

    if sketch.profiles.count == 0:
        raise ValueError(f"Sketch '{args['sketch_name']}' has no closed profiles to extrude.")
    if profile_index >= sketch.profiles.count:
        raise ValueError(f"Profile index {profile_index} out of range. Sketch has {sketch.profiles.count} profiles.")

    profile = sketch.profiles.item(profile_index)
    extrudes = root.features.extrudeFeatures

    op_map = {
        "new_body": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
        "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
        "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
    }
    operation = op_map.get(args.get("operation", "new_body"), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

    distance = adsk.core.ValueInput.createByReal(args["distance"])
    extrude_input = extrudes.createInput(profile, operation)
    extent = adsk.fusion.DistanceExtentDefinition.create(distance)
    extrude_input.setOneSideExtent(extent, adsk.fusion.ExtentDirections.PositiveExtentDirection)

    extrude = extrudes.add(extrude_input)
    return {
        "success": True,
        "message": f"Extruded '{args['sketch_name']}' profile {profile_index} by {args['distance']} cm.",
        "feature_name": extrude.name,
    }


def _add_fillet(args: dict) -> dict:
    _, root = _get_root()
    body = _find_body(root, args["body_name"])

    edge_indices = args.get("edge_indices")
    edges = adsk.core.ObjectCollection.create()

    if edge_indices:
        for idx in edge_indices:
            if idx < body.edges.count:
                edges.add(body.edges.item(idx))
    else:
        for i in range(body.edges.count):
            edges.add(body.edges.item(i))

    if edges.count == 0:
        raise ValueError("No edges selected for fillet.")

    fillets = root.features.filletFeatures
    fillet_input = fillets.createInput()
    fillet_input.addConstantRadiusEdgeSet(edges, adsk.core.ValueInput.createByReal(args["radius"]), True)
    fillet = fillets.add(fillet_input)
    return {"success": True, "message": f"Added fillet (radius={args['radius']} cm) to {edges.count} edges on '{args['body_name']}'.", "feature_name": fillet.name}


def _add_chamfer(args: dict) -> dict:
    _, root = _get_root()
    body = _find_body(root, args["body_name"])

    edge_indices = args.get("edge_indices")
    edges = adsk.core.ObjectCollection.create()

    if edge_indices:
        for idx in edge_indices:
            if idx < body.edges.count:
                edges.add(body.edges.item(idx))
    else:
        for i in range(body.edges.count):
            edges.add(body.edges.item(i))

    if edges.count == 0:
        raise ValueError("No edges selected for chamfer.")

    chamfers = root.features.chamferFeatures
    chamfer_input = chamfers.createInput2()
    chamfer_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, adsk.core.ValueInput.createByReal(args["distance"]), True)
    chamfer = chamfers.add(chamfer_input)
    return {"success": True, "message": f"Added chamfer (distance={args['distance']} cm) to {edges.count} edges on '{args['body_name']}'.", "feature_name": chamfer.name}


def _set_parameter(args: dict) -> dict:
    design, _ = _get_root()
    unit = args.get("unit", "cm")
    name = args["name"]
    expression = args["expression"]

    existing = design.userParameters.itemByName(name)
    if existing:
        existing.expression = expression
        return {"success": True, "message": f"Updated parameter '{name}' = {expression}."}

    design.userParameters.add(name, adsk.core.ValueInput.createByString(expression), unit, "")
    return {"success": True, "message": f"Created parameter '{name}' = {expression} ({unit})."}


def _get_design_info(args: dict) -> dict:
    design, root = _get_root()

    bodies = [root.bRepBodies.item(i).name for i in range(root.bRepBodies.count)]
    sketches = [root.sketches.item(i).name for i in range(root.sketches.count)]
    params = []
    for i in range(design.userParameters.count):
        p = design.userParameters.item(i)
        params.append({"name": p.name, "expression": p.expression, "value": p.value, "unit": p.unit})

    return {
        "design_name": design.parentDocument.name if design.parentDocument else "Untitled",
        "design_type": "Parametric" if design.designType == adsk.fusion.DesignTypes.ParametricDesignType else "Direct",
        "units": design.unitsManager.defaultLengthUnits,
        "bodies": bodies,
        "sketches": sketches,
        "parameters": params,
        "component_count": root.occurrences.count + 1,
    }


def _create_component(args: dict) -> dict:
    _, root = _get_root()
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    comp.name = args["name"]
    return {"success": True, "message": f"Created component '{args['name']}'.", "component_name": comp.name}


def _revolve_profile(args: dict) -> dict:
    design, root = _get_root()
    sketch = _find_sketch(root, args["sketch_name"])
    profile_index = args.get("profile_index", 0)

    if sketch.profiles.count == 0:
        raise ValueError(f"Sketch '{args['sketch_name']}' has no closed profiles to revolve.")
    if profile_index >= sketch.profiles.count:
        raise ValueError(f"Profile index {profile_index} out of range.")

    profile = sketch.profiles.item(profile_index)

    axis_map = {
        "X": root.xConstructionAxis,
        "Y": root.yConstructionAxis,
        "Z": root.zConstructionAxis,
    }
    axis = axis_map.get(args["axis"].upper())
    if not axis:
        raise ValueError(f"Invalid axis '{args['axis']}'. Use X, Y, or Z.")

    revolves = root.features.revolveFeatures
    revolve_input = revolves.createInput(profile, axis, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

    angle_value = adsk.core.ValueInput.createByString(f"{args['angle']} deg")
    revolve_input.setAngleExtent(False, angle_value)

    revolve = revolves.add(revolve_input)
    return {"success": True, "message": f"Revolved '{args['sketch_name']}' around {args['axis']} axis by {args['angle']}°.", "feature_name": revolve.name}
