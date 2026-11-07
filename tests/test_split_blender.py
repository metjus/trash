"""Split-into-parts tests; need the `bpy` module (pip install bpy), skipped otherwise."""
import collections
import os
import sys
import tempfile
import unittest

try:
    import bpy
    import bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
except ImportError:
    bpy = None

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def open_edges(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bad = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    faces = len(bm.faces)
    bm.free()
    return bad, faces


@unittest.skipIf(bpy is None, "bpy not installed")
class SplitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import bambu_color_export
        from bambu_color_export import paint, split
        cls.addon, cls.paint, cls.split = bambu_color_export, paint, split
        bambu_color_export.register()

    @classmethod
    def tearDownClass(cls):
        cls.addon.unregister()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.s = bpy.context.scene.bambu_split

    def sphere(self, colours):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=10, segments=64, ring_count=32)
        obj = bpy.context.object
        for _ in range(colours):
            self.paint.add_color(obj)
        return obj

    def test_presets_and_custom(self):
        self.s.printer = "FDM"
        self.assertAlmostEqual(self.s.tolerance, 0.2)
        self.assertAlmostEqual(self.s.depth, 1.5)
        self.s.depth = 4.0
        self.assertEqual(self.s.printer, "CUSTOM")
        self.assertAlmostEqual(self.s.depth, 4.0)
        self.s.printer = "RESIN"
        self.assertAlmostEqual(self.s.tolerance, 0.05)

    def test_part_fits_pocket_with_tolerance(self):
        obj = self.sphere(2)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 6 else 0
        self.s.tolerance, self.s.depth = 0.2, 2.0
        self.assertEqual(bpy.ops.bambu.split_colors(), {"FINISHED"})
        body = bpy.data.objects["Sphere body"]
        part = bpy.data.objects["Sphere Colour"]
        self.assertTrue(obj.hide_get())
        self.assertEqual(open_edges(part.data)[0], 0)
        self.assertEqual(open_edges(body.data)[0], 0)
        self.assertEqual([m.name for m in body.data.materials], ["Base"])
        # Every part vertex below the original surface sits `tolerance` from the body.
        bm = bmesh.new()
        bm.from_mesh(body.data)
        bvh = BVHTree.FromBMesh(bm)
        gaps = [bvh.find_nearest(v.co)[3] for v in part.data.vertices if v.co.length < 9.999]
        bm.free()
        self.assertTrue(gaps)
        self.assertGreater(min(gaps), 0.195)
        self.assertLess(sorted(gaps)[len(gaps) // 2], 0.22)

    def test_neighbouring_colours_keep_body_closed(self):
        obj = self.sphere(3)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 5 else (2 if p.center.x > 5 else 0)
        self.s.printer = "RESIN"
        bpy.ops.bambu.split_colors()
        for o in bpy.data.collections["Sphere parts"].objects:
            bad, faces = open_edges(o.data)
            self.assertGreater(faces, 0, o.name)
            self.assertEqual(bad, 0, o.name)

    def bottoms(self, part):
        """Plane offsets of each same-normal face group of 4+ faces (the flat bottoms)."""
        bm = bmesh.new()
        bm.from_mesh(part.data)
        groups = collections.defaultdict(list)
        for f in bm.faces:
            groups[tuple(round(c, 4) for c in f.normal)].append(f)
        planes = {n: {round(v.co.dot(fs[0].normal), 4) for f in fs for v in f.verts}
                  for n, fs in groups.items() if len(fs) >= 4}
        bm.free()
        return planes

    def test_flat_bottom_cap(self):
        obj = self.sphere(2)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 6 else 0
        self.s.tolerance, self.s.depth = 0.2, 1.5
        self.assertTrue(self.s.flat_bottom)
        bpy.ops.bambu.split_colors()
        part = bpy.data.objects["Sphere Colour"]
        self.assertEqual(open_edges(part.data)[0], 0)
        lowest = min(v.co.z for v in part.data.vertices if v.co.length > 9.999)
        planes = self.bottoms(part)
        self.assertIn((0.0, 0.0, -1.0), planes)
        self.assertEqual(planes[(0.0, 0.0, -1.0)], {round(-(lowest - 1.5), 4)})

    def test_flat_bottom_per_island_and_with_hole(self):
        obj = self.sphere(3)
        for p in obj.data.polygons:  # two eyes in colour 2, a ring round the pole in colour 3
            eye = p.center.y < -8 and abs(abs(p.center.x) - 3) < 2 and abs(p.center.z) < 2
            p.material_index = 1 if eye else (2 if 5 < p.center.z < 8.5 else 0)
        bpy.ops.bambu.split_colors()
        eyes = bpy.data.objects["Sphere Colour"]
        ring = bpy.data.objects["Sphere Colour.001"]
        # bottoms face into the model (+y for eyes on the -y side)
        planes = {n: d for n, d in self.bottoms(eyes).items() if n[1] > 0.5}
        self.assertEqual(len(planes), 2)  # one flat bottom per eye
        self.assertTrue(all(len(offsets) == 1 for offsets in planes.values()))
        for o in bpy.data.collections["Sphere parts"].objects:
            self.assertEqual(open_edges(o.data)[0], 0, o.name)
        self.assertEqual(len(self.bottoms(ring)[(0.0, 0.0, -1.0)]), 1)

    def test_surface_following_bottom_still_available(self):
        obj = self.sphere(2)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 6 else 0
        self.s.flat_bottom = False
        bpy.ops.bambu.split_colors()
        part = bpy.data.objects["Sphere Colour"]
        self.assertEqual(open_edges(part.data)[0], 0)
        self.assertNotIn((0.0, 0.0, -1.0), self.bottoms(part))

    def test_preview_shows_parts_and_red_where_too_deep(self):
        from bambu_color_export import preview
        obj = self.sphere(2)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 6 else 0
        self.s.tolerance, self.s.depth = 0.2, 1.5
        bpy.ops.bambu.split_preview()
        try:
            self.assertTrue(preview.is_on())
            part = preview.summary()["parts"][0]
            self.assertFalse(part["through"])
            self.assertNotIn(preview.RED, part["colours"])
            self.assertEqual(len(bpy.data.meshes), 1)  # nothing added to the file

            self.s.depth = 15.0  # into a 20 mm sphere from a 4 mm high cap: goes through
            preview._rebuild_later()
            part = preview.summary()["parts"][0]
            self.assertTrue(part["through"])
            self.assertLess(part["margin"], 0)
            self.assertIn(preview.RED, part["colours"])
        finally:
            preview.stop()
        self.assertFalse(preview.is_on())
        self.assertNotIn(preview._on_depsgraph, bpy.app.handlers.depsgraph_update_post)

    def test_split_turns_preview_off(self):
        from bambu_color_export import preview
        obj = self.sphere(2)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 6 else 0
        bpy.ops.bambu.split_preview()
        bpy.ops.bambu.split_colors()
        self.assertFalse(preview.is_on())

    def overlap_volume(self, a, b):
        tmp = bpy.data.objects.new("tmp", a.data.copy())
        bpy.context.scene.collection.objects.link(tmp)
        mod = tmp.modifiers.new("i", "BOOLEAN")
        mod.operation, mod.solver, mod.object = "INTERSECT", "EXACT", b
        bpy.context.view_layer.update()
        mesh = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bm = bmesh.new()
        bm.from_mesh(mesh)
        volume = bm.calc_volume()
        bm.free()
        bpy.data.objects.remove(tmp)
        return volume

    def test_neighbouring_parts_do_not_overlap_and_keep_tolerance(self):
        obj = self.sphere(3)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 6 else (2 if p.center.x > 6 else 0)
        self.s.tolerance, self.s.depth = 0.2, 2.0
        bpy.ops.bambu.split_colors()
        a, b = bpy.data.objects["Sphere Colour"], bpy.data.objects["Sphere Colour.001"]
        self.assertAlmostEqual(self.overlap_volume(a, b), 0.0, places=3)
        bm = bmesh.new()
        bm.from_mesh(b.data)
        bvh = BVHTree.FromBMesh(bm)
        gap = min(bvh.find_nearest(v.co)[3] for v in a.data.vertices)
        bm.free()
        self.assertGreater(gap, 0.195)

    def test_surface_parts_meet_without_overlap(self):
        # Neighbouring parts use the model's normals, so their walls meet exactly
        # and even the untrimmed parts (what the preview draws) don't overlap.
        obj = self.sphere(3)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 6 else (2 if p.center.x > 6 else 0)
        src = self.split.world_mesh(bpy.context, obj)
        _body, parts = self.split.build_parts(src, 0.2, 1.5, 0, flat_bottom=False)
        objects = []
        for info in parts:
            mesh = bpy.data.meshes.new(info["name"])
            info["shape"].to_mesh(mesh)
            info["shape"].free()
            o = bpy.data.objects.new(info["name"], mesh)
            bpy.context.scene.collection.objects.link(o)
            objects.append(o)
        self.assertAlmostEqual(self.overlap_volume(*objects), 0.0, places=3)

    def test_big_open_model_flat_bottom_refuses_without_changes(self):
        # Big models use the MANIFOLD solver, which can't cut meshes with holes.
        obj = self.sphere(2)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 6 else 0
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[0]], context="FACES_ONLY")  # punch a hole
        bm.to_mesh(obj.data)
        bm.free()
        limit = self.split.EXACT_MAX_FACES
        self.split.EXACT_MAX_FACES = 0  # treat this small sphere as big
        try:
            with self.assertRaises(RuntimeError):  # reported as an error
                bpy.ops.bambu.split_colors()
        finally:
            self.split.EXACT_MAX_FACES = limit
        self.assertNotIn("Sphere parts", bpy.data.collections)
        self.assertFalse(obj.hide_get())
        self.s.flat_bottom = False  # the boolean-free cut handles it
        self.assertEqual(bpy.ops.bambu.split_colors(), {"FINISHED"})

    def test_surface_cut_is_closed_and_exact(self):
        obj = self.sphere(3)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 6 else (2 if p.center.x > 6 else 0)
        self.s.tolerance, self.s.depth, self.s.flat_bottom = 0.2, 1.5, False
        bpy.ops.bambu.split_colors()
        objects = {o.name: o for o in bpy.data.collections["Sphere parts"].objects}
        for o in objects.values():
            self.assertEqual(open_edges(o.data)[0], 0, o.name)
        body = objects["Sphere body"]
        for name in ("Sphere Colour", "Sphere Colour.001"):
            self.assertAlmostEqual(self.overlap_volume(objects[name], body), 0.0, places=3)
        bm = bmesh.new()
        bm.from_mesh(body.data)
        bvh = BVHTree.FromBMesh(bm)
        part = objects["Sphere Colour"]
        gaps = [bvh.find_nearest(v.co)[3] for v in part.data.vertices if v.co.length < 9.99]
        bm.free()
        self.assertAlmostEqual(min(gaps), 0.2, delta=0.01)

    def ponytail(self, colours):
        """A ball with a tail pulled out of it (one closed mesh); the tail is colour 2."""
        bpy.ops.mesh.primitive_uv_sphere_add(radius=20, segments=64, ring_count=32)
        obj = bpy.context.object
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        region = [f for f in bm.faces if (f.calc_center_median() - Vector((0, -20, 0))).length < 7]
        moved = [v for v in bmesh.ops.extrude_face_region(bm, geom=region)["geom"] if isinstance(v, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=moved, vec=(0, -25, -10))
        bmesh.ops.delete(bm, geom=[f for f in region if f.is_valid], context="FACES_ONLY")
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(obj.data)
        bm.free()
        for _ in range(colours):
            self.paint.add_color(obj)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.y < -21 else 0
        obj.data.materials[1].bambu_cut_mode = "CUT_OFF"
        return obj

    def volume(self, o):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        v = bm.calc_volume(signed=True)
        bm.free()
        return v

    def test_cut_off_splits_the_model_exactly(self):
        obj = self.ponytail(2)
        total = self.volume(obj)
        self.s.flat_bottom = False
        self.assertEqual(bpy.ops.bambu.split_colors(), {"FINISHED"})
        body, tail = bpy.data.objects["Sphere body"], bpy.data.objects["Sphere Colour"]
        self.assertEqual(open_edges(body.data)[0], 0)
        self.assertEqual(open_edges(tail.data)[0], 0)
        self.assertAlmostEqual(self.volume(body) + self.volume(tail), total, places=1)
        self.assertAlmostEqual(self.overlap_volume(tail, body), 0.0, places=3)
        self.assertEqual([m.name for m in tail.data.materials], ["Colour"])

    def test_cut_off_with_flat_bottom_inlay_alongside(self):
        obj = self.ponytail(3)
        for p in obj.data.polygons:  # a stripe on the other side, inlaid
            if abs(p.center.z - 8) < 2 and p.center.y > 0:
                p.material_index = 2
        self.s.flat_bottom = True
        bpy.ops.bambu.split_colors()
        objects = {o.name: o for o in bpy.data.collections["Sphere parts"].objects}
        self.assertEqual(sorted(objects), ["Sphere Colour", "Sphere Colour.001", "Sphere body"])
        for o in objects.values():
            self.assertEqual(open_edges(o.data)[0], 0, o.name)
        self.assertAlmostEqual(self.overlap_volume(objects["Sphere Colour"], objects["Sphere body"]), 0.0, places=3)

    def test_preview_marks_cut_off_parts(self):
        from bambu_color_export import preview
        self.ponytail(2)
        preview.start(bpy.context)
        try:
            part = preview.summary()["parts"][0]
            self.assertTrue(part["cut_off"])
            self.assertFalse(part["through"])
            self.assertTrue(part["positions"])
        finally:
            preview.stop()

    def test_export_parts_writes_closed_stl_per_part(self):
        obj = self.sphere(3)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 6 else (2 if p.center.x > 6 else 0)
        bpy.ops.bambu.split_colors()
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(bpy.ops.bambu.export_parts(directory=folder, file_format="3MF"), {"FINISHED"})
            self.assertEqual(len(os.listdir(folder)), 3)
            self.assertEqual(bpy.ops.bambu.export_parts(directory=folder, file_format="STL"), {"FINISHED"})
            files = sorted(f for f in os.listdir(folder) if f.endswith(".stl"))
            self.assertEqual(files, ["Sphere Colour.001.stl", "Sphere Colour.stl", "Sphere body.stl"])
            for name in files:
                bpy.ops.wm.stl_import(filepath=os.path.join(folder, name))
                imported = bpy.context.selected_objects[0]
                bm = bmesh.new()
                bm.from_mesh(imported.data)
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
                self.assertEqual(sum(1 for e in bm.edges if len(e.link_faces) != 2), 0, name)
                bm.free()

    def three_colours_side_unticked(self):
        obj = self.sphere(3)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 6 else (2 if p.center.x > 6 else 0)
        obj.material_slots[2].material.bambu_cut = False
        return obj

    def body_face_colours(self):
        body = bpy.data.objects["Sphere body"]
        return {body.data.materials[p.material_index].name for p in body.data.polygons}

    def test_unticked_colour_stays_painted_on_body(self):
        self.three_colours_side_unticked()
        self.s.uncut = "KEEP"
        bpy.ops.bambu.split_colors()
        names = sorted(o.name for o in bpy.data.collections["Sphere parts"].objects)
        self.assertEqual(names, ["Sphere Colour", "Sphere body"])
        self.assertEqual(self.body_face_colours(), {"Base", "Colour.001"})
        body = bpy.data.objects["Sphere body"]
        self.assertEqual(open_edges(body.data)[0], 0)
        pocket = {body.data.materials[p.material_index].name for p in body.data.polygons if p.center.length < 9.9}
        self.assertEqual(pocket, {"Base"})

    def test_unticked_colour_can_become_body_colour(self):
        self.three_colours_side_unticked()
        self.s.uncut = "BODY"
        bpy.ops.bambu.split_colors()
        self.assertEqual(self.body_face_colours(), {"Base"})

    def test_nothing_ticked_creates_nothing(self):
        obj = self.three_colours_side_unticked()
        obj.material_slots[1].material.bambu_cut = False
        bpy.ops.bambu.split_colors()
        self.assertNotIn("Sphere parts", bpy.data.collections)
        self.assertFalse(obj.hide_get())

    def test_overlapping_shells_are_not_thin(self):
        # A sculpt-like mesh: a strand sphere pushed into a head sphere, its top
        # only 0.5 mm under the head's surface. The head is 40 mm thick there.
        from bambu_color_export import preview
        bpy.ops.mesh.primitive_uv_sphere_add(radius=20, segments=64, ring_count=32)
        head = bpy.context.object
        head_faces = len(head.data.polygons)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=7.5, segments=48, ring_count=24, location=(0, 0, 12))
        head.select_set(True)
        bpy.context.view_layer.objects.active = head
        bpy.ops.object.join()
        obj = bpy.context.object
        self.paint.add_color(obj)
        self.paint.add_color(obj)
        for p in obj.data.polygons:
            p.material_index = 1 if p.index < head_faces and p.center.z > 12 else 0
        self.s.printer, self.s.flat_bottom = "FDM", False
        preview.start(bpy.context)
        try:
            part = preview.summary()["parts"][0]
            self.assertFalse(part["through"])
            self.assertGreater(part["margin"], 35.0)
        finally:
            preview.stop()

    def paint_all(self, obj):
        # No face left in colour 1: colour 3 has the larger area.
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 3 else 2

    def test_fully_painted_uses_largest_colour_as_body(self):
        obj = self.sphere(3)
        self.paint_all(obj)
        self.s.printer = "FDM"
        self.assertEqual(self.split.pick_body(self.split.colour_areas(obj.data), 0), 2)
        bpy.ops.bambu.split_colors()
        objects = {o.name: o for o in bpy.data.collections["Sphere parts"].objects}
        self.assertEqual(sorted(objects), ["Sphere Colour", "Sphere body"])
        body = objects["Sphere body"]
        self.assertEqual([m.name for m in body.data.materials], ["Colour.001"])
        bad, faces = open_edges(body.data)
        self.assertEqual(bad, 0)
        self.assertGreater(faces, 0)

    def test_chosen_body_colour(self):
        obj = self.sphere(3)
        self.paint_all(obj)
        self.s.body_colour = 2
        bpy.ops.bambu.split_colors()
        objects = {o.name: o for o in bpy.data.collections["Sphere parts"].objects}
        self.assertEqual(sorted(objects), ["Sphere Colour.001", "Sphere body"])
        self.assertEqual([m.name for m in objects["Sphere body"].data.materials], ["Colour"])

    def test_pick_body_rules(self):
        pick = self.split.pick_body
        self.assertEqual(pick([9.0, 1.0, 5.0], 0), 0)    # auto: the largest area
        self.assertEqual(pick([5.0, 1.0, 9.0], 0), 2)    # even when colour 1 is used
        self.assertEqual(pick([5.0, 1.0, 5.0], 0), 0)    # tie: the lower number
        self.assertEqual(pick([5.0, 1.0, 9.0], 2), 1)    # chosen colour
        self.assertEqual(pick([5.0, 0.0, 9.0], 2), 2)    # chosen but unused -> auto
        self.assertIsNone(pick([0.0, 0.0], 0))

    def test_single_colour_creates_nothing(self):
        obj = self.sphere(3)
        for p in obj.data.polygons:
            p.material_index = 2
        bpy.ops.bambu.split_colors()
        self.assertFalse(obj.hide_get())
        self.assertNotIn("Sphere parts", bpy.data.collections)

    def test_thin_model_warns(self):
        bpy.ops.mesh.primitive_cube_add(size=10)
        obj = bpy.context.object
        obj.scale.z = 0.05  # 0.5 mm plate
        bpy.ops.object.transform_apply(scale=True)
        self.paint.add_color(obj)
        self.paint.add_color(obj)
        for p in obj.data.polygons:
            p.material_index = 1 if p.normal.z > 0.5 else 0
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        patch = self.split._patch(obj.data, 1)
        bvh = BVHTree.FromBMesh(bm)
        self.assertAlmostEqual(self.split.thinnest_spot(patch, bvh, 1e-4), 0.5, places=3)
        patch.free()
        bm.free()


if __name__ == "__main__":
    unittest.main()
