"""Import a coloured 3MF as Blender objects with one material per colour."""

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ImportHelper
from mathutils import Matrix

from . import paint, reader3mf


def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear(hex_colour):
    h = hex_colour.lstrip("#")
    return tuple(_srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def _matrix(t, unit_mm):
    """3MF 3x4 row-vector transform -> Blender Matrix (translation in mm)."""
    return Matrix(((t[0], t[3], t[6], t[9] * unit_mm),
                   (t[1], t[4], t[7], t[10] * unit_mm),
                   (t[2], t[5], t[8], t[11] * unit_mm),
                   (0.0, 0.0, 0.0, 1.0)))


def _order(key):
    # Filaments first and in order, so filament 1 becomes colour 1 (the body).
    return (0, key[1], "") if key[0] == "filament" else (1, 0, key[1])


def import_3mf(context, path, keep_position=True):
    """Create the objects; returns (objects, imported)."""
    data = reader3mf.read_3mf(path)
    materials = {}
    for key in sorted(data.colours, key=_order):
        hex_colour = data.colours[key]
        materials[key] = paint.new_color_material(reader3mf.colour_name(key, hex_colour), _linear(hex_colour))

    unit_mm = 1.0
    created = []
    collection = context.collection or context.scene.collection
    for item in data.objects:
        mesh = bpy.data.meshes.new(item.name)
        mesh.from_pydata(item.vertices, [], item.faces)
        keys = sorted(set(item.face_colour), key=_order)
        slot = {key: i for i, key in enumerate(keys)}
        for key in keys:
            mesh.materials.append(materials[key])
        mesh.polygons.foreach_set("material_index", [slot[k] for k in item.face_colour])
        mesh.validate(clean_customdata=False)
        mesh.update()
        obj = bpy.data.objects.new(item.name, mesh)
        collection.objects.link(obj)
        if keep_position:
            obj.matrix_world = _matrix(item.transform, unit_mm)
        created.append(obj)

    for o in context.selected_objects:
        o.select_set(False)
    for obj in created:
        obj.select_set(True)
    if created:
        context.view_layer.objects.active = created[0]
    return created, data


class IMPORT_OT_bambu_3mf(bpy.types.Operator, ImportHelper):
    """Import a coloured 3MF (Bambu Studio, PrusaSlicer or standard): every colour becomes a
    material, ready for painting, export and Split Colours into Parts"""
    bl_idname = "import_mesh.bambu_3mf"
    bl_label = "Import Coloured 3MF"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".3mf"
    filter_glob: StringProperty(default="*.3mf", options={"HIDDEN"})
    keep_position: BoolProperty(
        name="Keep Plate Position", default=True,
        description="Place objects where they sit on the slicer's plate (off: at the world origin)")

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            created, data = import_3mf(context, self.filepath, self.keep_position)
        except Exception:
            paint.record_error("import 3mf")
            self.report({"ERROR"}, "Could not import the 3MF. Use 'Copy Error' in the Bambu Paint panel")
            return {"CANCELLED"}
        if not created:
            self.report({"WARNING"}, "No meshes found in the 3MF")
            return {"CANCELLED"}
        split = sum(o.split_triangles for o in data.objects)
        source = {"bambu": "Bambu Studio", "prusa": "PrusaSlicer"}.get(data.source, "3MF")
        self.report({"INFO"}, "Imported %d object(s) from %s with %d colour(s)%s"
                    % (len(created), source, len(data.colours),
                       ", %d painted triangles refined" % split if split else ""))
        return {"FINISHED"}


def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_bambu_3mf.bl_idname, text="Coloured 3MF for Bambu (.3mf)")


def register():
    bpy.utils.register_class(IMPORT_OT_bambu_3mf)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(IMPORT_OT_bambu_3mf)
