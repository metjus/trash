"""Split-into-parts tests; need the `bpy` module (pip install bpy), skipped otherwise."""
import collections
import os
import sys
import unittest

try:
    import bpy
    import bmesh
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
        self.assertGreater(min(gaps), 0.18)
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
        self.assertEqual(pick([5.0, 1.0, 9.0], 0), 0)    # colour 1 used -> colour 1
        self.assertEqual(pick([0.0, 1.0, 9.0], 0), 2)    # else the largest area
        self.assertEqual(pick([5.0, 1.0, 9.0], 2), 1)    # chosen colour
        self.assertEqual(pick([5.0, 0.0, 9.0], 2), 0)    # chosen but unused -> auto
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
