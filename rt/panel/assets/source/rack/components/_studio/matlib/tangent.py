"""World-space anisotropy tangents that need no UV map.

A Tangent node set to UV_MAP reads a named UV layer; on a mesh without that
layer it yields a ZERO tangent and an anisotropic metal renders black. These
build the tangent from object coordinates instead and carry it to world space
through a Vector Transform (Object -> World), which is the space Principled's
Tangent input expects. Link the returned socket into `bsdf.inputs["Tangent"]`.

    linear(nt, axis)  grain along one object axis (brushed plate)
    radial(nt, axis)  grain pointing away from an object axis (sunburst)
    spin(nt, axis)    grain circling an object axis (lathe-turned face)

`axis` is "X" | "Y" | "Z" or an object-space 3-vector.
"""

_AXES = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}


def _axis(axis):
    if isinstance(axis, str):
        return _AXES[axis.upper()]
    return tuple(float(c) for c in axis)


def _vmath(nt, op, a, b=None):
    n = nt.nodes.new("ShaderNodeVectorMath")
    n.operation = op
    for i, v in ((0, a), (1, b)):
        if v is None:
            continue
        if hasattr(v, "is_output"):
            nt.links.new(v, n.inputs[i])
        else:
            n.inputs[i].default_value = v
    return n.outputs["Value" if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else "Vector"]


def _to_world(nt, vec):
    xf = nt.nodes.new("ShaderNodeVectorTransform")
    xf.vector_type = "VECTOR"
    xf.convert_from = "OBJECT"
    xf.convert_to = "WORLD"
    if hasattr(vec, "is_output"):
        nt.links.new(vec, xf.inputs["Vector"])
    else:
        xf.inputs["Vector"].default_value = vec
    return _vmath(nt, "NORMALIZE", xf.outputs["Vector"])


def _object_position(nt):
    return nt.nodes.new("ShaderNodeTexCoord").outputs["Object"]


def linear(nt, axis="X"):
    """Tangent along an object axis, in world space."""
    return _to_world(nt, _axis(axis))


def radial(nt, axis="Z"):
    """Tangent from the object axis out through the shading point: P minus its
    projection onto the axis. Undefined on the axis itself."""
    a = _axis(axis)
    p = _object_position(nt)
    along = nt.nodes.new("ShaderNodeVectorMath")
    along.operation = "SCALE"
    along.inputs[0].default_value = a
    nt.links.new(_vmath(nt, "DOT_PRODUCT", p, a), along.inputs["Scale"])
    return _to_world(nt, _vmath(nt, "SUBTRACT", p, along.outputs["Vector"]))


def spin(nt, axis="Z"):
    """Tangent circling the object axis: axis x P."""
    return _to_world(nt, _vmath(nt, "CROSS_PRODUCT", _axis(axis), _object_position(nt)))
