"""Split painted colours into separate printable parts.

Colour 1 (the base colour) becomes the body. Every other colour becomes an
inlay part: its painted faces form the part's top, pushed `depth` into the
model to make a solid. The body gets a matching pocket that is larger than
the part by `tolerance` on every side, so the printed part fits in it.
"""

import bmesh
import bpy
import collections
import os

from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import paint

# printer -> (tolerance mm, depth mm) filled in when a preset is picked
PRESETS = {"RESIN": (0.05, 1.0), "FDM": (0.2, 1.5)}
MAX_SHELL = 3.0  # cap on even-thickness scaling at very sharp corners
_updating = False


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def _preset_update(self, context):
    global _updating
    _changed(self, context)
    values = PRESETS.get(self.printer)
    if values is None or _updating:
        return
    _updating = True
    try:
        self.tolerance, self.depth = values
    finally:
        _updating = False


def _changed(self, context):
    from . import preview
    preview.schedule()


def _value_update(self, context):
    # Editing a value by hand switches the preset to Custom.
    global _updating
    _changed(self, context)
    values = PRESETS.get(self.printer)
    if _updating or values is None:
        return
    if abs(self.tolerance - values[0]) > 1e-6 or abs(self.depth - values[1]) > 1e-6:
        _updating = True
        try:
            self.printer = "CUSTOM"
        finally:
            _updating = False


class BambuSplitSettings(bpy.types.PropertyGroup):
    printer: EnumProperty(
        name="Printer",
        items=[("RESIN", "Resin", "Resin printer: tight fit (tolerance 0.05 mm, depth 1 mm)"),
               ("FDM", "FDM", "Filament printer: looser fit (tolerance 0.2 mm, depth 1.5 mm)"),
               ("CUSTOM", "Custom", "Your own tolerance and depth")],
        default="RESIN", update=_preset_update)
    tolerance: FloatProperty(
        name="Tolerance", default=0.05, min=0.0, max=2.0, precision=3, step=0.5,
        description="Gap in mm between each part and its pocket in the body, on every side",
        update=_value_update)
    depth: FloatProperty(
        name="Depth", default=1.0, min=0.1, max=100.0, precision=2, step=10,
        description="How deep each colour part goes into the model, in mm",
        update=_value_update)
    flat_bottom: BoolProperty(
        name="Flat Bottom", default=True,
        description="Give each part a flat bottom (good bed adhesion, the part slides straight into "
                    "its pocket). Depth is then the part's thinnest spot. Off: the bottom follows "
                    "the surface at an even depth",
        update=_changed)
    uncut: EnumProperty(
        name="Uncut Colours",
        items=[("KEEP", "Keep Painted", "Colours that aren't cut stay painted on the body, e.g. to "
                                        "print the body with the AMS and the cut colours as parts"),
               ("BODY", "Body Colour", "Colours that aren't cut become the body colour")],
        default="KEEP", update=_changed)
    body_colour: IntProperty(
        name="Body Colour", default=0, min=0, max=64,
        description="Colour (number as in the Bambu Paint list) that becomes the body; the other "
                    "colours become parts. 0 = Auto: the colour with the largest painted area",
        update=_changed)
    mm_per_unit: FloatProperty(
        name="1 Blender unit =", default=1.0, min=0.0001, max=10000.0, precision=3,
        description="Millimetres per Blender unit in the printed model. Check the model size below",
        update=_changed)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def colour_areas(mesh):
    """Painted area per material slot."""
    slots = max(len(mesh.materials), 1)
    count = len(mesh.polygons)
    try:
        import numpy as np
        index = np.empty(count, dtype=np.int32)
        area = np.empty(count, dtype=np.float64)
        mesh.polygons.foreach_get("material_index", index)
        mesh.polygons.foreach_get("area", area)
        keep = index < slots
        return np.bincount(index[keep], weights=area[keep], minlength=slots)[:slots].tolist()
    except ImportError:
        areas = [0.0] * slots
        for p in mesh.polygons:
            if p.material_index < slots:
                areas[p.material_index] += p.area
        return areas


def wants_cut(mat):
    """Whether a colour is ticked to become a part (all are, by default)."""
    return mat is None or getattr(mat, "bambu_cut", True)


def pick_body(areas, choice):
    """Slot index of the body colour, or None if nothing is painted.

    choice is 1-based (0 = Auto): a chosen colour that isn't used falls back
    to Auto, the colour with the largest painted area (the lower number on a
    tie). In a model painted from colour 1 that is colour 1; in an imported
    model colour 1 may only be a detail.
    """
    if not any(areas):
        return None
    if 0 < choice <= len(areas) and areas[choice - 1] > 0:
        return choice - 1
    return max(range(len(areas)), key=lambda i: (areas[i], -i))


def _patch(mesh, mat_index):
    """BMesh with only the faces of one colour (world space mesh)."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != mat_index], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.normal_update()
    return bm


def _solid(patch, depth):
    """Closed solid: the patch as the top, a copy moved `depth` inward (against
    the surface normals, with even thickness) as the bottom, and walls along
    the patch's open edges."""
    bm = bmesh.new()
    top, bottom = {}, {}
    for v in patch.verts:
        shell = min(v.calc_shell_factor(), MAX_SHELL)
        top[v] = bm.verts.new(v.co)
        bottom[v] = bm.verts.new(v.co - v.normal * depth * shell)
    for f in patch.faces:
        for verts in ([top[v] for v in f.verts], [bottom[v] for v in reversed(f.verts)]):
            try:
                bm.faces.new(verts)
            except ValueError:  # duplicate face
                pass
    for e in patch.edges:
        if len(e.link_faces) == 1:
            a, b = e.verts
            try:
                bm.faces.new((top[a], top[b], bottom[b], bottom[a]))
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    return bm


def _islands(patch):
    """Lists of faces that are connected through edges."""
    seen, islands = set(), []
    for f in patch.faces:
        if f.index in seen:
            continue
        seen.add(f.index)
        stack, island = [f], []
        while stack:
            g = stack.pop()
            island.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        islands.append(island)
    return islands


def _report():
    """What a part looks like against the model, for warnings and the preview.

    worst: (model thickness, part depth + tolerance) at the worst spot or None;
    bad: positions of painted vertices where the part would go through;
    deepest: the part's greatest depth; margin: the smallest spare model
    thickness beyond the part and tolerance (negative = goes through).
    """
    return {"too_curved": False, "worst": None, "bad": set(), "deepest": 0.0, "margin": None}


def _check(report, co, need, have):
    report["deepest"] = max(report["deepest"], need)
    if have is None:
        return
    spare = have - need
    if report["margin"] is None or spare < report["margin"]:
        report["margin"] = spare
    if spare < 0:
        report["bad"].add(co.to_tuple(5))
        worst = report["worst"]
        if worst is None or need - have > worst[1] - worst[0]:
            report["worst"] = (have, need)


def _flat_solid(patch, depth, bvh=None, tolerance=0.0, eps=0.0):
    """Closed solid per island: the patch as the top, straight walls along the
    island's average normal and a flat bottom `depth` below its lowest point.

    Returns (bmesh, report), see _report().
    """
    patch.faces.index_update()
    bm = bmesh.new()
    report = _report()
    for island in _islands(patch):
        normal = Vector()
        for f in island:
            normal += f.normal * f.calc_area()
        if normal.length < 1e-12:
            continue
        normal.normalize()
        if any(f.normal.dot(normal) < 0.0 for f in island):
            report["too_curved"] = True  # it wraps round: a flat bottom can't sit under all of it
        verts = {v for f in island for v in f.verts}
        height = {v: v.co.dot(normal) for v in verts}
        floor = min(height.values()) - depth

        top = {v: bm.verts.new(v.co) for v in verts}
        for f in island:
            try:
                bm.faces.new([top[v] for v in f.verts])
            except ValueError:
                pass
        bottom = {}
        rim = []
        for f in island:
            for e in f.edges:
                if len(e.link_faces) == 1:
                    rim.append(e)
        for e in rim:
            for v in e.verts:
                if v not in bottom:
                    bottom[v] = bm.verts.new(v.co - normal * (height[v] - floor))
        floor_edges = []
        for e in rim:
            a, b = e.verts
            try:
                bm.faces.new((top[a], top[b], bottom[b], bottom[a]))
            except ValueError:
                pass
            edge = bm.edges.get((bottom[a], bottom[b]))
            if edge is not None:
                floor_edges.append(edge)
        if floor_edges:
            bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False,
                                    edges=floor_edges, normal=-normal)

        if bvh is not None:
            for v in verts:
                loc, _n, _i, dist = bvh.ray_cast(v.co - normal * eps, -normal)
                _check(report, v.co, height[v] - floor + tolerance, None if loc is None else dist + eps)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    return bm, report


def _grow(bm, dist):
    """Offset a closed solid outward by at least `dist` from every face.

    Each vertex starts along its normal and is pushed further out until it
    lies `dist` beyond the plane of every face around it, so the gap holds
    at corners too (an average normal alone falls short where a straight
    wall meets a curved top).
    """
    bm.normal_update()
    moves = []
    for v in bm.verts:
        normals = [f.normal for f in v.link_faces]
        move = v.normal * dist
        for _ in range(8):
            worst = min(normals, key=move.dot)
            short = dist - move.dot(worst)
            if short <= dist * 1e-3:
                break
            move += worst * short
        if move.length > dist * MAX_SHELL:
            move *= dist * MAX_SHELL / move.length
        moves.append((v, move))
    for v, move in moves:
        v.co += move


def _surface_report(patch, bvh, depth, tolerance, eps):
    """_report() for the surface-following part: depth + tolerance everywhere,
    measured inward along each vertex normal."""
    report = _report()
    for v in patch.verts:
        loc, _n, _i, dist = bvh.ray_cast(v.co - v.normal * eps, -v.normal)
        _check(report, v.co, depth + tolerance, None if loc is None else dist + eps)
    return report


def thinnest_spot(patch, bvh, eps):
    """Smallest model thickness under the patch: distance from each patch
    vertex, inward along its normal, to the next surface of the model."""
    thinnest = None
    for v in patch.verts:
        start = v.co - v.normal * eps
        loc, _n, _i, dist = bvh.ray_cast(start, -v.normal)
        if loc is not None:
            d = dist + eps
            thinnest = d if thinnest is None else min(thinnest, d)
    return thinnest


def _to_mesh(bm, name):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def _boolean_solver():
    items = {i.identifier for i in bpy.types.BooleanModifier.bl_rna.properties["solver"].enum_items}
    return "EXACT" if "EXACT" in items else next(iter(items))


def world_mesh(context, obj):
    """The object's evaluated mesh (modifiers applied) in world space, as a new mesh."""
    depsgraph = context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    mesh.transform(obj.matrix_world)
    if obj.matrix_world.determinant() < 0:
        mesh.flip_normals()
    return mesh


def build_parts(src, tolerance, depth, body_choice=0, flat_bottom=True, only_ticked=True):
    """Work out the body colour and every part, without changing anything.

    Returns (body_index, parts) where each part is a dict with index, name,
    material, shape (a closed BMesh the caller must free) and report.
    body_index is None when fewer than two colours are used. With only_ticked,
    colours that aren't ticked to cut (wants_cut) are left out.
    """
    materials = list(src.materials) or [None]
    areas = colour_areas(src)
    body_index = pick_body(areas, body_choice)
    if body_index is None or sum(1 for a in areas if a > 0) < 2:
        return None, []
    bvh = BVHTree.FromPolygons([v.co.copy() for v in src.vertices],
                               [tuple(p.vertices) for p in src.polygons])
    eps = max(depth, tolerance) * 1e-3
    parts = []
    for index in range(len(materials)):
        if index == body_index or areas[index] == 0:
            continue
        mat = materials[index]
        if only_ticked and not wants_cut(mat):
            continue
        patch = _patch(src, index)
        if flat_bottom:
            shape, report = _flat_solid(patch, depth, bvh, tolerance, eps)
        else:
            shape = _solid(patch, depth)
            report = _surface_report(patch, bvh, depth, tolerance, eps)
        patch.free()
        parts.append({"index": index, "name": mat.name if mat else "Colour %d" % (index + 1),
                      "material": mat, "shape": shape, "report": report, "area": areas[index]})
    return body_index, parts


def _clean(mesh, dist):
    """Tidy a boolean result for slicers, which join vertices by position: merge
    coincident vertices, dissolve zero-area faces, triangulate and drop
    triangle pairs that sit on top of each other (an inner double layer)."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=dist)
    # Triangles, as a slicer sees them: a folded n-gon can hide a doubled triangle.
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.verts.index_update()
    same = collections.defaultdict(list)
    for f in bm.faces:
        same[frozenset(v.index for v in f.verts)].append(f)
    doubled = [f for faces in same.values() if len(faces) > 1 for f in faces]
    if doubled:
        bmesh.ops.delete(bm, geom=doubled, context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context="EDGES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_edges], context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _subtract(context, target, cutter_bm, material=None):
    """Cut the closed solid `cutter_bm` (freed here) out of `target` with an exact
    boolean that also handles overlaps inside the cutter. The new faces (the
    pocket walls) get `material`."""
    cutter_mesh = _to_mesh(cutter_bm, "_bambu_cutter")
    if material:
        cutter_mesh.materials.append(material)
    cutter = bpy.data.objects.new("_bambu_cutter", cutter_mesh)
    context.scene.collection.objects.link(cutter)
    mod = target.modifiers.new("Bambu cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = _boolean_solver()
    mod.object = cutter
    if hasattr(mod, "use_self"):
        mod.use_self = True  # pockets of neighbouring colours overlap inside the cutter
    if material and hasattr(mod, "material_mode"):
        mod.material_mode = "TRANSFER"  # walls take the cutter's material, matched to the target's slot
    context.view_layer.update()
    depsgraph = context.evaluated_depsgraph_get()
    cut = bpy.data.meshes.new_from_object(target.evaluated_get(depsgraph))
    target.modifiers.remove(mod)
    old = target.data
    target.data = cut
    if old.users == 0:
        bpy.data.meshes.remove(old)
    cutter_mesh = cutter.data
    bpy.data.objects.remove(cutter)
    bpy.data.meshes.remove(cutter_mesh)
    return cut


def _single_material(mesh, mat):
    mesh.materials.clear()
    if mat:
        mesh.materials.append(mat)
    mesh.polygons.foreach_set("material_index", [0] * len(mesh.polygons))
    mesh.update()


def split_colors(context, obj, tolerance, depth, body_choice=0, flat_bottom=True, keep_uncut=True):
    """Create the body and one part per other colour. Distances are in Blender units.

    Returns (collection, body, parts, warnings, body_index).
    """
    src = world_mesh(context, obj)
    materials = list(src.materials) or [None]
    body_index, infos = build_parts(src, tolerance, depth, body_choice, flat_bottom)
    if not infos:
        bpy.data.meshes.remove(src)
        return None, None, [], [], body_index
    eps = max(depth, tolerance) * 1e-3

    coll = bpy.data.collections.new("%s parts" % obj.name)
    context.scene.collection.children.link(coll)
    body = bpy.data.objects.new("%s body" % obj.name, src)
    coll.objects.link(body)

    parts, warnings = [], []
    # All pockets go into one cutter: one boolean with every pocket keeps the
    # body closed where colours meet (separate booleans can leave tiny holes).
    # Bigger parts come first and stay whole; each smaller part is trimmed by
    # the pockets made so far, so neighbouring parts never overlap and keep
    # the tolerance between them too.
    pockets = bmesh.new()
    for info in sorted(infos, key=lambda i: -i["area"]):
        name, mat, shape, report = info["name"], info["material"], info["shape"], info["report"]
        if report["too_curved"]:
            warnings.append((name, "curved", None))
        if report["worst"]:
            warnings.append((name, "thin", report["worst"]))

        # The pocket: the part grown by the tolerance (a hair more when the
        # tolerance is 0, so the cut never lies exactly on the body surface).
        pocket = shape.copy()
        _grow(pocket, max(tolerance, eps))

        piece = _to_mesh(shape, "%s %s" % (obj.name, name))
        part = bpy.data.objects.new(piece.name, piece)
        coll.objects.link(part)
        if pockets.faces:
            piece = _subtract(context, part, pockets.copy())
            _clean(piece, eps * 0.1)
        _single_material(piece, mat)
        if piece.polygons:
            parts.append(part)
        else:
            warnings.append((name, "covered", None))
            bpy.data.objects.remove(part)
            bpy.data.meshes.remove(piece)

        tmp = _to_mesh(pocket, "_bambu_pocket")
        pockets.from_mesh(tmp)  # appends to the shared cutter
        bpy.data.meshes.remove(tmp)

    cut = _subtract(context, body, pockets, materials[body_index])
    _clean(cut, eps * 0.1)
    cut.name = body.name
    if keep_uncut:
        # Colours that weren't cut stay painted; anything left of a cut colour
        # and the pocket walls are the body colour.
        cut_slots = {info["index"] for info in infos}
        slots = len(cut.materials)
        body_slot = next((i for i, m in enumerate(cut.materials) if m == materials[body_index]), body_index)
        indices = [0] * len(cut.polygons)
        cut.polygons.foreach_get("material_index", indices)
        indices = [body_slot if i in cut_slots or i >= slots else i for i in indices]
        # Keep only the colours the body still shows, body colour first.
        used = sorted(set(indices), key=lambda i: (i != body_slot, i))
        remap = {old: new for new, old in enumerate(used)}
        kept = [cut.materials[i] for i in used]
        cut.materials.clear()
        for m in kept:
            cut.materials.append(m)
        cut.polygons.foreach_set("material_index", [remap[i] for i in indices])
        cut.update()
    else:
        _single_material(cut, materials[body_index])

    obj.hide_set(True)
    for o in context.selected_objects:
        o.select_set(False)
    for o in [body] + parts:
        o.select_set(True)
    context.view_layer.objects.active = body
    return coll, body, parts, warnings, body_index


# ---------------------------------------------------------------------------
# Operator and UI
# ---------------------------------------------------------------------------

def _can_split(obj):
    return obj is not None and obj.type == "MESH" and len(obj.material_slots) >= 2


class BAMBU_OT_split_colors(bpy.types.Operator):
    """Split the painted colours into separate parts that fit into pockets in the body"""
    bl_idname = "bambu.split_colors"
    bl_label = "Split Colours into Parts"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return paint._running is None and _can_split(context.active_object)

    def execute(self, context):
        from . import preview
        preview.stop()
        s = context.scene.bambu_split
        obj = context.active_object
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        tolerance, depth = s.tolerance / s.mm_per_unit, s.depth / s.mm_per_unit
        try:
            coll, body, parts, warnings, body_index = split_colors(
                context, obj, tolerance, depth, s.body_colour, s.flat_bottom, s.uncut == "KEEP")
        except Exception:
            paint.record_error("split colours")
            self.report({"ERROR"}, "Could not split the colours. Use 'Copy Error' in the Bambu Paint panel")
            return {"CANCELLED"}
        if not parts:
            if body_index is None:
                self.report({"WARNING"}, "Only one colour is used on the model, nothing to split")
            else:
                self.report({"WARNING"}, "No colour is ticked to cut, nothing to split")
            return {"FINISHED"}
        for name, kind, values in warnings:
            if kind == "thin":
                have, need = values
                self.report({"WARNING"}, "%s: the model is only %.2f mm thick where the part needs "
                            "%.2f mm (with tolerance), it may go through. Use a smaller depth."
                            % (name, have * s.mm_per_unit, need * s.mm_per_unit))
            elif kind == "covered":
                self.report({"WARNING"}, "%s is completely covered by neighbouring colours' parts, "
                            "no part was made for it." % name)
            else:
                self.report({"WARNING"}, "%s wraps round the model too far for a flat bottom: "
                            "check the part, or split that colour into smaller areas." % name)
        if s.body_colour and body_index != s.body_colour - 1:
            self.report({"WARNING"}, "Colour %d isn't used on the model, the body is colour %d"
                        % (s.body_colour, body_index + 1))
        self.report({"INFO"}, "Created '%s': body (colour %d) + %d part(s), tolerance %.3f mm, depth %.2f mm"
                    % (coll.name, body_index + 1, len(parts), s.tolerance, s.depth))
        return {"FINISHED"}


class BAMBU_OT_split_preview(bpy.types.Operator):
    """Show the parts the split would make, see-through in the model (red: goes through)"""
    bl_idname = "bambu.split_preview"
    bl_label = "Preview"

    def execute(self, context):
        from . import preview
        try:
            if preview.is_on():
                preview.stop()
            else:
                preview.start(context)
        except Exception:
            paint.record_error("split preview")
            preview.stop()
            self.report({"ERROR"}, "Could not show the preview. Use 'Copy Error' in the Bambu Paint panel")
            return {"CANCELLED"}
        return {"FINISHED"}


def _draw_preview(layout, s):
    from . import preview
    row = layout.row(align=True)
    on = preview.is_on()
    row.operator(BAMBU_OT_split_preview.bl_idname, text="Hide Preview" if on else "Preview",
                 icon="HIDE_OFF" if on else "HIDE_ON", depress=on)
    if not on:
        return
    state = preview.summary()
    box = layout.box().column(align=True)
    if state["message"]:
        box.label(text=state["message"], icon="INFO")
        return
    mm, tol = state["mm"], state["tolerance"]
    for part in state["parts"]:
        deepest = part["deepest"] * mm - tol
        box.label(text="%d %s: %.2f–%.2f mm deep" % (part["number"], part["name"], s.depth, max(deepest, s.depth)),
                  icon="ERROR" if part["through"] or part["too_curved"] else "CHECKMARK")
        if part["through"]:
            note = "goes through by %.2f mm (red)" % (-part["margin"] * mm)
        elif part["margin"] is not None:
            note = "fits, %.2f mm of model left" % (part["margin"] * mm)
        else:
            note = "fits"
        if part["too_curved"]:
            note += ", wraps round too far"
        box.label(text="    " + note)


def _export_targets(context):
    return [o for o in context.selected_objects if o.type == "MESH" and o.visible_get()]


class BAMBU_OT_export_parts(bpy.types.Operator):
    """Save every selected part to its own file in a folder (after a split, the body and
    all parts are selected), in millimetres"""
    bl_idname = "bambu.export_parts"
    bl_label = "Export Parts"

    directory: StringProperty(subtype="DIR_PATH")
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})
    file_format: EnumProperty(
        name="Format",
        items=[("STL", "STL", "One STL per part (any slicer, e.g. resin slicers)"),
               ("3MF", "3MF", "One 3MF per part, with the part's colour (Bambu Studio)")],
        default="STL")

    @classmethod
    def poll(cls, context):
        return bool(_export_targets(context))

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        self.layout.prop(self, "file_format", expand=True)

    def execute(self, context):
        from . import NO_MATERIAL, build_palette, collect_geometry, writers
        folder = bpy.path.abspath(self.directory)
        if not folder or not os.path.isdir(folder):
            self.report({"ERROR"}, "Choose a folder to save the parts in")
            return {"CANCELLED"}
        scale = context.scene.bambu_split.mm_per_unit
        ext = "." + self.file_format.lower()
        written = []
        try:
            for obj in _export_targets(context):
                vertices, triangles, _mats = collect_geometry(context, [obj], scale)
                if not triangles:
                    continue
                path = os.path.join(folder, writers.safe_filename(obj.name) + ext)
                if self.file_format == "STL":
                    writers.write_stl(path, vertices, triangles, obj.name)
                else:
                    # Keep every colour on the object (a body can keep painted colours).
                    used = list({(m.name if m else ""): m for m in _mats}.values())
                    palette, index_of = build_palette(used, 0.02)
                    tri_color = [index_of[m.name if m else NO_MATERIAL] for m in _mats]
                    writers.write_3mf(path, vertices, triangles, tri_color, palette, obj.name)
                written.append(os.path.basename(path))
        except Exception:
            paint.record_error("export parts")
            self.report({"ERROR"}, "Export failed. Use 'Copy Error' in the Bambu Paint panel")
            return {"CANCELLED"}
        if not written:
            self.report({"WARNING"}, "The selected objects have no faces")
            return {"CANCELLED"}
        self.report({"INFO"}, "Saved %d file(s) to %s: %s" % (len(written), folder, ", ".join(written)))
        return {"FINISHED"}


def _draw_cut_list(layout, s, obj, areas, body_index):
    from . import material_color_source
    box = layout.box()
    box.label(text="Colours to cut into parts:")
    col = box.column(align=True)
    for i, slot in enumerate(obj.material_slots):
        mat = slot.material
        if i >= len(areas) or areas[i] == 0 or mat is None:
            continue
        row = col.row(align=True)
        swatch = row.row(align=True)
        swatch.ui_units_x = 2.0
        owner, prop = material_color_source(mat)
        swatch.prop(owner, prop, text="")
        if i == body_index:
            row.label(text="%d  %s  (body)" % (i + 1, mat.name))
        else:
            row.prop(mat, "bambu_cut", text="%d  %s" % (i + 1, mat.name))
    box.prop(s, "uncut", expand=True)


class VIEW3D_PT_bambu_split(bpy.types.Panel):
    bl_label = "Bambu Split Parts"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bambu"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        try:
            self._draw(context, layout)
        except Exception:
            paint.record_error("split panel")
            layout.label(text="Panel error, see Copy Error in Bambu Paint", icon="ERROR")

    def _draw(self, context, layout):
        s = context.scene.bambu_split
        obj = context.active_object
        layout.operator("import_mesh.bambu_3mf", text="Import Coloured 3MF…", icon="IMPORT")
        col = layout.column(align=True)
        col.label(text="Each colour becomes a part that")
        col.label(text="fits into a pocket in the body.")

        layout.row().prop(s, "printer", expand=True)
        col = layout.column(align=True)
        col.prop(s, "tolerance", text="Tolerance (mm)")
        col.prop(s, "depth", text="Depth (mm)")
        layout.prop(s, "mm_per_unit", text="1 Blender unit (mm)")

        layout.prop(s, "flat_bottom")
        layout.prop(s, "body_colour", text="Body Colour (0 = Auto)")
        if _can_split(obj):
            areas = colour_areas(obj.data)
            index = pick_body(areas, s.body_colour)
            if index is None or sum(1 for a in areas if a > 0) < 2:
                layout.label(text="Only one colour used, nothing to split", icon="INFO")
            else:
                mat = obj.material_slots[index].material
                why = "chosen" if s.body_colour == index + 1 else "largest area"
                if s.body_colour and s.body_colour != index + 1:
                    why = "colour %d not used, %s" % (s.body_colour, why)
                layout.label(text="Body: %d %s (%s)" % (index + 1, mat.name if mat else "", why),
                             icon="MESH_UVSPHERE")
                _draw_cut_list(layout, s, obj, areas, index)
        if obj is not None and obj.type == "MESH":
            size = Vector(obj.dimensions) * s.mm_per_unit
            layout.label(text="Model: %.1f × %.1f × %.1f mm" % tuple(size), icon="OBJECT_DATA")
        if not _can_split(obj):
            layout.label(text="Select a painted mesh (2+ colours)", icon="INFO")
        _draw_preview(layout, s)
        row = layout.row()
        row.scale_y = 1.3
        row.operator(BAMBU_OT_split_colors.bl_idname, icon="MOD_BOOLEAN")
        count = len(_export_targets(context))
        layout.operator(BAMBU_OT_export_parts.bl_idname, icon="EXPORT",
                        text="Export %d Selected Part%s…" % (count, "" if count == 1 else "s")
                        if count else "Export Parts (select them first)")


classes = (
    BambuSplitSettings,
    BAMBU_OT_split_colors,
    BAMBU_OT_split_preview,
    BAMBU_OT_export_parts,
    VIEW3D_PT_bambu_split,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bambu_split = bpy.props.PointerProperty(type=BambuSplitSettings)
    bpy.types.Material.bambu_cut = BoolProperty(
        name="Cut", default=True, update=_changed,
        description="Cut this colour into its own part (untick to leave it on the body)")


def unregister():
    del bpy.types.Material.bambu_cut
    del bpy.types.Scene.bambu_split
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
