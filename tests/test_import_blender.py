"""3MF import tests in Blender; need the `bpy` module (pip install bpy), skipped otherwise."""
import os
import sys
import tempfile
import unittest

try:
    import bpy
    import bmesh
except ImportError:
    bpy = None

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)


@unittest.skipIf(bpy is None, "bpy not installed")
class ImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import bambu_color_export
        cls.addon = bambu_color_export
        bambu_color_export.register()

    @classmethod
    def tearDownClass(cls):
        cls.addon.unregister()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_bambu_project(self):
        from test_reader3mf import BambuProjectTest
        with tempfile.TemporaryDirectory() as d:
            path = BambuProjectTest.build(None, d)
            self.assertEqual(bpy.ops.import_mesh.bambu_3mf(filepath=path), {"FINISHED"})
        obj = bpy.data.objects["Kitty"]
        self.assertEqual([m.name for m in obj.data.materials],
                         ["Filament 1", "Filament 2", "Filament 3", "Filament 4"])
        self.assertEqual(len(obj.data.polygons), 21)
        self.assertEqual(tuple(obj.location), (120.0, 110.0, 0.0))
        black = obj.data.materials[1]
        self.assertEqual(tuple(round(c, 3) for c in black.diffuse_color[:3]), (0.0, 0.0, 0.0))

    def test_round_trip_with_paint_and_split(self):
        from bambu_color_export import paint
        bpy.ops.mesh.primitive_uv_sphere_add(radius=10, segments=32, ring_count=16)
        obj = bpy.context.object
        paint.add_color(obj)
        paint.add_color(obj)
        for p in obj.data.polygons:
            p.material_index = 1 if p.center.z > 6 else 0
        obj.data.calc_loop_triangles()
        expected = {}
        for t in obj.data.loop_triangles:  # the export writes triangles
            name = obj.data.materials[t.material_index].name
            expected[name] = expected.get(name, 0) + 1
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ball.3mf")
            bpy.ops.export_mesh.bambu_3mf(filepath=path)
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_mesh.bambu_3mf(filepath=path)
        ball = bpy.context.view_layer.objects.active
        counts = {}
        for p in ball.data.polygons:
            name = ball.data.materials[p.material_index].name
            counts[name] = counts.get(name, 0) + 1
        # colours come back as their sRGB hex; the white base is most of the ball
        self.assertEqual(sorted(counts.values()), sorted(expected.values()))
        self.assertEqual(max(counts, key=counts.get), "#E7E7E7")
        bm = bmesh.new()
        bm.from_mesh(ball.data)
        self.assertEqual(sum(1 for e in bm.edges if len(e.link_faces) != 2), 0)
        bm.free()
        self.assertEqual(bpy.ops.bambu.split_colors(), {"FINISHED"})


if __name__ == "__main__":
    unittest.main()
