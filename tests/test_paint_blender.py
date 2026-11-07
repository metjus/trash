"""Paint-tool tests; need the `bpy` module (pip install bpy), skipped otherwise."""
import math
import os
import sys
import unittest

try:
    import bpy
except ImportError:
    bpy = None

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@unittest.skipIf(bpy is None, "bpy not installed")
class PaintTest(unittest.TestCase):
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
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16)
        self.obj = bpy.context.object
        for _ in range(3):
            self.paint.add_color(self.obj)
        self.session = self.paint.PaintSession(self.obj)
        self.polys = self.obj.data.polygons
        self.none = self.paint.symmetry_signs(False, False, False)

    def painted(self, index):
        return [p for p in self.polys if p.material_index == index]

    def test_add_color_first_is_base(self):
        self.assertEqual(self.obj.material_slots[0].material.name, "Base")
        self.assertEqual(self.obj.active_material_index, 2)

    def test_brush_symmetry_and_undo(self):
        face = max(self.polys, key=lambda p: p.center.x + 0.1 * p.center.y)
        self.session.begin_stroke()
        self.session.brush(face.center, face.normal, face.index, 0.25, 1, self.paint.symmetry_signs(True, False, False))
        self.session.end_stroke()
        pos = sorted(round(p.center.y, 3) for p in self.painted(1) if p.center.x > 0)
        neg = sorted(round(p.center.y, 3) for p in self.painted(1) if p.center.x < 0)
        self.assertTrue(pos)
        self.assertEqual(pos, neg)
        self.assertTrue(self.session.undo())
        self.assertEqual(self.painted(1), [])

    def test_stroke_changes_wait_for_flush(self):
        face = self.polys[100]
        self.session.begin_stroke()
        self.session.brush(face.center, face.normal, face.index, 0.3, 2, self.none)
        self.assertTrue(self.session.changes)  # drawn by the overlay meanwhile
        self.assertTrue(all(self.polys[f].material_index == 2 for f, _c in self.session.changes))
        self.session.end_stroke()
        self.session.flush()
        self.assertEqual(self.session.changes, [])

    def test_fill_stops_at_colour_and_sharp_edges(self):
        for p in self.polys:
            p.material_index = 1 if abs(p.center.z) < 0.1 else 0
        self.session.refresh()
        top = max(self.polys, key=lambda p: p.center.z)
        self.session.fill(top.center, top.normal, top.index, 2, self.none)
        self.assertTrue(all((p.material_index == 2) == (p.center.z > 0.1) for p in self.polys))

        bpy.ops.mesh.primitive_cube_add(size=2, location=(5, 0, 0))
        cube = bpy.context.object
        self.paint.add_color(cube)
        self.paint.add_color(cube)
        session = self.paint.PaintSession(cube)
        f = cube.data.polygons[0]
        session.fill(f.center, f.normal, f.index, 1, self.none, True, math.radians(30))
        self.assertEqual(sum(1 for p in cube.data.polygons if p.material_index == 1), 1)  # one side only

    def test_smooth_changes_only_under_brush(self):
        import random
        rng = random.Random(1)
        for p in self.polys:
            p.material_index = 1 if p.center.x + rng.uniform(-0.3, 0.3) < 0 else 0
        self.session.refresh()
        before = [p.material_index for p in self.polys]
        hit = min(self.polys, key=lambda p: p.center.x ** 2 + (p.center.z - 0.3) ** 2 - p.center.y)
        region = self.session._brush_faces(hit.center, hit.normal, hit.index, 0.6, self.none)
        self.session.begin_stroke()
        self.session.smooth(hit.center, hit.normal, hit.index, 0.6, self.none, 3)
        self.session.end_stroke()
        after = [p.material_index for p in self.polys]
        self.assertTrue(all(before[i] == after[i] for i in range(len(after)) if i not in region))
        self.assertTrue(self.session.undo())
        self.assertEqual([p.material_index for p in self.polys], before)

    def test_remove_color(self):
        for i, p in enumerate(self.polys):
            p.material_index = i % 3
        self.paint.remove_color(self.obj, 1)
        self.assertEqual(len(self.obj.material_slots), 2)
        self.assertEqual([p.material_index for p in self.polys], [{0: 0, 1: 0, 2: 1}[i % 3] for i in range(len(self.polys))])


if __name__ == "__main__":
    unittest.main()
