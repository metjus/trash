"""Fill Gaps tests; need the `bpy` module (pip install bpy), skipped otherwise."""
import os
import random
import sys
import unittest

try:
    import bpy
    from mathutils import Vector
except ImportError:
    bpy = None

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@unittest.skipIf(bpy is None, "bpy not installed")
class FillGapsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import bambu_color_export
        from bambu_color_export import paint
        cls.addon, cls.paint = bambu_color_export, paint
        bambu_color_export.register()

    @classmethod
    def tearDownClass(cls):
        cls.addon.unregister()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=50, segments=128, ring_count=64)
        self.obj = obj = bpy.context.object
        for _ in range(3):
            self.paint.add_color(obj)  # 1 base, 2 hair, 3 eye
        polys = obj.data.polygons
        for p in polys:
            p.material_index = 1 if p.center.z > 0 else 0
        self.eye = {p.index for p in polys if (p.center - Vector((0, -35, 35))).length < 4}
        self.big = {p.index for p in polys if (p.center - Vector((0, 35, 35))).length < 14}
        rng = random.Random(4)
        hair = [p.index for p in polys if p.center.z > 10 and p.index not in self.eye | self.big]
        near = {g for i in self.eye | self.big for g in range(i - 130, i + 130)}  # keep holes apart from them
        self.holes = [i for i in rng.sample(hair, 80) if i not in near][:20]
        for i in self.holes:
            polys[i].material_index = 0
        for i in self.eye:
            polys[i].material_index = 2
        for i in self.big:
            polys[i].material_index = 0
        obj.active_material_index = 1
        self.s = bpy.context.scene.bambu_paint
        self.s.gap_max_area, self.s.gap_any_colour = 25.0, False

    def colours(self, faces):
        polys = self.obj.data.polygons
        return {polys[i].material_index for i in faces}

    def test_fills_small_unpainted_gaps_only(self):
        self.assertEqual(bpy.ops.bambu.fill_gaps(), {"FINISHED"})
        self.assertEqual(self.colours(self.holes), {1})
        self.assertEqual(self.colours(self.eye), {2})   # painted detail kept
        self.assertEqual(self.colours(self.big), {0})   # larger than Max Gap
        bottom = [p.index for p in self.obj.data.polygons if p.center.z < 0]
        self.assertEqual(self.colours(bottom), {0})

    def test_other_colours_only_when_asked_and_small(self):
        self.s.gap_any_colour = True
        self.s.gap_max_area = 2.0                     # smaller than the eye
        bpy.ops.bambu.fill_gaps()
        self.assertEqual(self.colours(self.eye), {2})
        self.s.gap_max_area = 200.0
        bpy.ops.bambu.fill_gaps()
        self.assertEqual(self.colours(self.eye), {1})

    def test_while_painting_one_undo(self):
        self.paint._running = type("Op", (), {"session": self.paint.PaintSession(self.obj)})()
        try:
            bpy.ops.bambu.fill_gaps()
            self.assertEqual(self.colours(self.holes), {1})
            self.assertTrue(self.paint._running.session.undo())
            self.assertEqual(self.colours(self.holes), {0})
        finally:
            self.paint._running = None


if __name__ == "__main__":
    unittest.main()
