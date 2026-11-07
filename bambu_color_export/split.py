"""Split painted colours into separate printable parts.

Colour 1 (the base colour) becomes the body. Every other colour becomes an
inlay part: its painted faces form the part's top, pushed `depth` into the
model to make a solid. The body gets a matching pocket that is larger than
the part by `tolerance` on every side, so the printed part fits in it.
"""

import bmesh
import bpy
from bpy.props import EnumProperty, FloatProperty
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
    values = PRESETS.get(self.printer)
    if values is None or _updating:
        return
    _updating = True
    try:
        self.tolerance, self.depth = values
    finally:
        _updating = False


def _value_update(self, context):
    # Editing a value by hand switches the preset to Custom.
    global _updating
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
    mm_per_unit: FloatProperty(
        name="1 Blender unit =", default=1.0, min=0.0001, max=10000.0, precision=3,
        description="Millimetres per Blender unit in the printed model. Check the model size below")


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

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


def _grow(bm, dist):
    """Offset a closed solid outward by `dist` (even thickness)."""
    bm.normal_update()
    moves = [(v, v.normal * dist * min(v.calc_shell_factor(), MAX_SHELL)) for v in bm.verts]
    for v, move in moves:
        v.co += move


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


def split_colors(context, obj, tolerance, depth):
    """Create the body and one part per colour. Distances are in Blender units.

    Returns (collection, body, parts, warnings).
    """
    depsgraph = context.evaluated_depsgraph_get()
    src = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    src.transform(obj.matrix_world)
    if obj.matrix_world.determinant() < 0:
        src.flip_normals()
    materials = list(src.materials)
    counts = [0] * len(materials)
    for p in src.polygons:
        if p.material_index < len(counts):
            counts[p.material_index] += 1

    bvh = BVHTree.FromPolygons([v.co.copy() for v in src.vertices],
                               [tuple(p.vertices) for p in src.polygons])
    eps = max(depth, tolerance) * 1e-3

    coll = bpy.data.collections.new("%s parts" % obj.name)
    context.scene.collection.children.link(coll)
    body = bpy.data.objects.new("%s body" % obj.name, src)
    coll.objects.link(body)

    parts, warnings = [], []
    # All pockets go into one cutter: one boolean with every pocket keeps the
    # body closed where colours meet (separate booleans can leave tiny holes).
    pockets = bmesh.new()
    for index in range(1, len(materials)):
        if counts[index] == 0:
            continue
        mat = materials[index]
        name = mat.name if mat else "Colour %d" % (index + 1)
        patch = _patch(src, index)
        thin = thinnest_spot(patch, bvh, eps)
        if thin is not None and thin < depth + tolerance:
            warnings.append((name, thin))

        piece = _to_mesh(_solid(patch, depth), "%s %s" % (obj.name, name))
        if mat:
            piece.materials.append(mat)
        part = bpy.data.objects.new(piece.name, piece)
        coll.objects.link(part)
        parts.append(part)

        # The pocket: the part grown by the tolerance (a hair more when the
        # tolerance is 0, so the cut never lies exactly on the body surface).
        pocket = _solid(patch, depth)
        _grow(pocket, max(tolerance, eps))
        patch.free()
        tmp = _to_mesh(pocket, "_bambu_pocket")
        pockets.from_mesh(tmp)  # appends to the shared cutter
        bpy.data.meshes.remove(tmp)

    if not parts:
        pockets.free()
        bpy.data.objects.remove(body)
        bpy.data.meshes.remove(src)
        bpy.data.collections.remove(coll)
        return None, None, [], []

    cutter = bpy.data.objects.new("_bambu_pockets", _to_mesh(pockets, "_bambu_pockets"))
    coll.objects.link(cutter)
    mod = body.modifiers.new("Bambu pockets", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = _boolean_solver()
    mod.object = cutter
    if hasattr(mod, "use_self"):
        mod.use_self = True  # pockets of neighbouring colours overlap inside the cutter
    context.view_layer.update()
    depsgraph = context.evaluated_depsgraph_get()
    cut = bpy.data.meshes.new_from_object(body.evaluated_get(depsgraph))
    body.modifiers.clear()
    body.data = cut
    bpy.data.meshes.remove(src)
    cutter_mesh = cutter.data
    bpy.data.objects.remove(cutter)
    bpy.data.meshes.remove(cutter_mesh)

    # The body is printed in the base colour only.
    cut.name = body.name
    cut.materials.clear()
    if materials and materials[0]:
        cut.materials.append(materials[0])
    cut.polygons.foreach_set("material_index", [0] * len(cut.polygons))
    cut.update()

    obj.hide_set(True)
    for o in context.selected_objects:
        o.select_set(False)
    for o in [body] + parts:
        o.select_set(True)
    context.view_layer.objects.active = body
    return coll, body, parts, warnings


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
        s = context.scene.bambu_split
        obj = context.active_object
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        tolerance, depth = s.tolerance / s.mm_per_unit, s.depth / s.mm_per_unit
        try:
            coll, body, parts, warnings = split_colors(context, obj, tolerance, depth)
        except Exception:
            paint.record_error("split colours")
            self.report({"ERROR"}, "Could not split the colours. Use 'Copy Error' in the Bambu Paint panel")
            return {"CANCELLED"}
        if not parts:
            self.report({"WARNING"}, "Only the base colour is used, nothing to split")
            return {"FINISHED"}
        for name, thin in warnings:
            self.report({"WARNING"}, "%s: the model is only %.2f mm thick in places, the part "
                        "(depth + tolerance %.2f mm) may go through. Use a smaller depth."
                        % (name, thin * s.mm_per_unit, s.depth + s.tolerance))
        self.report({"INFO"}, "Created '%s': body + %d part(s), tolerance %.3f mm, depth %.2f mm"
                    % (coll.name, len(parts), s.tolerance, s.depth))
        return {"FINISHED"}


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
        col = layout.column(align=True)
        col.label(text="Each colour becomes a part that")
        col.label(text="fits into a pocket in colour 1.")

        layout.row().prop(s, "printer", expand=True)
        col = layout.column(align=True)
        col.prop(s, "tolerance", text="Tolerance (mm)")
        col.prop(s, "depth", text="Depth (mm)")
        layout.prop(s, "mm_per_unit", text="1 Blender unit (mm)")

        if obj is not None and obj.type == "MESH":
            size = Vector(obj.dimensions) * s.mm_per_unit
            layout.label(text="Model: %.1f × %.1f × %.1f mm" % tuple(size), icon="OBJECT_DATA")
        if not _can_split(obj):
            layout.label(text="Select a painted mesh (2+ colours)", icon="INFO")
        row = layout.row()
        row.scale_y = 1.3
        row.operator(BAMBU_OT_split_colors.bl_idname, icon="MOD_BOOLEAN")


classes = (
    BambuSplitSettings,
    BAMBU_OT_split_colors,
    VIEW3D_PT_bambu_split,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bambu_split = bpy.props.PointerProperty(type=BambuSplitSettings)


def unregister():
    del bpy.types.Scene.bambu_split
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
