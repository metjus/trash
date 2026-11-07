"""Live preview of Split Colours into Parts.

The parts are worked out exactly as the split would make them and drawn
see-through in the viewport, tinted red where a part would go through the
model. Nothing is added to the file, so the preview never ends up in an
export or in the undo history. It is rebuilt shortly after the settings,
the selection or the painted model change.
"""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from . import paint, split

ALPHA = 0.35
RED = (1.0, 0.08, 0.05, 0.75)

_on = False
_draw_handle = None
_pending = False
_batches = None  # GPU batches, built while drawing from _state
_state = {"object": None, "parts": [], "body": None, "message": "", "mm": 1.0, "tolerance": 0.0}


def is_on():
    return _on


def summary():
    return _state


def _redraw():
    for window in getattr(bpy.context.window_manager, "windows", []):
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

def rebuild(context):
    """Work out the parts for the active object and keep what is needed to draw them."""
    global _batches
    from . import material_linear_color
    _batches = None
    _state.update(object=None, parts=[], body=None, message="")
    obj = context.view_layer.objects.active
    s = context.scene.bambu_split
    if obj is None or obj.type != "MESH" or len(obj.material_slots) < 2:
        _state["message"] = "Select a painted mesh (2+ colours)"
        _redraw()
        return
    _state["object"] = obj.name
    _state["mm"] = s.mm_per_unit
    _state["tolerance"] = s.tolerance
    src = split.world_mesh(context, obj)
    try:
        body_index, infos = split.build_parts(src, s.tolerance / s.mm_per_unit, s.depth / s.mm_per_unit,
                                              s.body_colour, s.flat_bottom)
        materials = list(src.materials)
    finally:
        bpy.data.meshes.remove(src)
    if not infos:
        _state["message"] = ("Only one colour used, nothing to split" if body_index is None
                             else "No colour is ticked to cut")
        _redraw()
        return
    body_mat = materials[body_index] if body_index < len(materials) else None
    _state["body"] = (body_index + 1, body_mat.name if body_mat else "")

    for info in infos:
        shape, report, mat = info["shape"], info["report"], info["material"]
        rgb = material_linear_color(mat) if mat else (0.8, 0.8, 0.8)
        colour = (*rgb, ALPHA)
        bad = report["bad"]
        positions, colours = [], []
        for tri in shape.calc_loop_triangles():
            cos = [loop.vert.co.copy() for loop in tri]
            through = bad and any(co.to_tuple(5) in bad for co in cos)
            positions.extend(cos)
            colours.extend([RED if through else colour] * 3)
        shape.free()
        _state["parts"].append({
            "number": info["index"] + 1,
            "name": info["name"],
            "positions": positions,
            "colours": colours,
            "deepest": report["deepest"],
            "margin": report["margin"],
            "through": bool(bad),
            "too_curved": report["too_curved"],
        })
    _redraw()


def _rebuild_later():
    global _pending
    _pending = False
    if not _on:
        return None
    if paint._running is not None:
        schedule(0.5)  # don't slow painting down; try again once it pauses
        return None
    try:
        rebuild(bpy.context)
    except Exception:
        paint.record_error("split preview")
        stop()
    return None


def schedule(delay=0.15):
    """Rebuild soon (changes in quick succession are rebuilt once)."""
    global _pending
    if not _on or _pending:
        return
    _pending = True
    bpy.app.timers.register(_rebuild_later, first_interval=delay)


def _on_depsgraph(scene, depsgraph):
    name = _state["object"]
    active = bpy.context.view_layer.objects.active if bpy.context.view_layer else None
    if (active.name if active else None) != name:
        schedule()
        return
    obj = bpy.data.objects.get(name) if name else None
    if obj is None:
        return
    watched = {obj.as_pointer(), obj.data.as_pointer()}
    watched |= {slot.material.as_pointer() for slot in obj.material_slots if slot.material}
    for update in depsgraph.updates:
        if update.id.original.as_pointer() in watched:
            schedule()
            return


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def _draw():
    global _batches, _on
    if not _on or not _state["parts"]:
        return
    try:
        shader = gpu.shader.from_builtin("SMOOTH_COLOR")
        if _batches is None:
            _batches = [batch_for_shader(shader, "TRIS", {"pos": p["positions"], "color": p["colours"]})
                        for p in _state["parts"] if p["positions"]]
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("NONE")  # see the parts through the model
        gpu.state.depth_mask_set(False)
        gpu.state.face_culling_set("NONE")
        shader.bind()
        for batch in _batches:
            batch.draw(shader)
        gpu.state.depth_mask_set(True)
        gpu.state.blend_set("NONE")
    except Exception:
        paint.record_error("split preview drawing")
        _on = False  # handlers are removed outside drawing
        bpy.app.timers.register(stop, first_interval=0.0)


# ---------------------------------------------------------------------------
# On / off
# ---------------------------------------------------------------------------

def start(context):
    global _on, _draw_handle
    if _on:
        return
    _on = True
    _draw_handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
    rebuild(context)


def stop():
    global _on, _draw_handle, _batches
    _on = False
    if _draw_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, "WINDOW")
        except Exception:
            pass
        _draw_handle = None
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
    _batches = None
    _state.update(object=None, parts=[], body=None, message="")
    _redraw()
    return None  # also used as a one-shot timer


@bpy.app.handlers.persistent
def _on_load(*_args):
    stop()


def register():
    bpy.app.handlers.load_pre.append(_on_load)


def unregister():
    stop()
    if _on_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_on_load)
