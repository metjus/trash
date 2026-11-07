import collections
import os
import random
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bambu_color_export"))
import reader3mf  # noqa: E402
import writers  # noqa: E402
from reader3mf import decode_paint, encode_paint, split_leaves  # noqa: E402
from writers import PaletteEntry  # noqa: E402

CUBE_V = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0), (0, 0, 10), (10, 0, 10), (10, 10, 10), (0, 10, 10)]
CUBE_T = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
          (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]


def random_tree(rng, depth=0):
    if depth > 3 or rng.random() < 0.4:
        return rng.choice([0, 1, 2, 3, 4, 7, 16, 20])
    sides = rng.randint(1, 3)
    special = 0 if sides == 3 else rng.randint(0, 2)
    return (sides, special, [random_tree(rng, depth + 1) for _ in range(sides + 1)])


def watertight(faces):
    """Every directed edge of a closed, consistently wound mesh has its reverse."""
    edges = collections.Counter()
    for f in faces:
        for i in range(len(f)):
            edges[(f[i], f[(i + 1) % len(f)])] += 1
    return all(c == 1 and edges.get((b, a)) == 1 for (a, b), c in edges.items())


def mesh_xml(vertices, triangles, paint=None, oid="1", extra=""):
    v = "".join('<vertex x="%g" y="%g" z="%g"/>' % p for p in vertices)
    t = "".join('<triangle v1="%d" v2="%d" v3="%d"%s/>' % (a, b, c, ' paint_color="%s"' % paint[i] if paint and paint[i] else "")
                for i, (a, b, c) in enumerate(triangles))
    return '<object id="%s" type="model"%s><mesh><vertices>%s</vertices><triangles>%s</triangles></mesh></object>' % (oid, extra, v, t)


MODEL_HEAD = ('<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" '
              'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
              'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06">')


class PaintCodeTest(unittest.TestCase):
    def test_simple_codes(self):
        self.assertEqual([decode_paint(c) for c in ("4", "8", "0C", "1C", "DC")], [1, 2, 3, 4, 16])

    def test_round_trip_random_trees(self):
        rng = random.Random(7)
        for _ in range(300):
            tree = random_tree(rng)
            self.assertEqual(decode_paint(encode_paint(tree)), tree)

    def test_matches_writer_encoding(self):
        for n in range(1, 17):
            self.assertEqual(decode_paint(writers.paint_color_code(n)), n)

    def test_truncated(self):
        with self.assertRaises(ValueError):
            decode_paint("3")  # a split triangle with no children

    def test_split_leaves_cover_the_triangle(self):
        rng = random.Random(3)
        for _ in range(100):
            verts = [(0.0, 0.0, 0.0), (8.0, 0.0, 0.0), (0.0, 6.0, 0.0)]
            mids = {}

            def midpoint(i, j):
                key = tuple(sorted((i, j)))
                if key not in mids:
                    a, b = verts[i], verts[j]
                    verts.append(tuple((x + y) / 2 for x, y in zip(a, b)))
                    mids[key] = len(verts) - 1
                return mids[key]

            leaves = split_leaves((0, 1, 2), random_tree(rng), midpoint)

            def area(a, b, c):
                (ax, ay, _), (bx, by, _), (cx, cy, _) = verts[a], verts[b], verts[c]
                return ((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2
            self.assertAlmostEqual(sum(area(a, b, c) for a, b, c, _ in leaves), 24.0)
            self.assertTrue(all(area(a, b, c) > 0 for a, b, c, _ in leaves))  # same winding


class BambuProjectTest(unittest.TestCase):
    """A small Bambu Studio style project built by hand."""

    def build(self, d):
        paint = [""] * 12
        paint[2] = encode_paint(2)                                   # top: filament 2
        paint[3] = encode_paint((3, 0, [2, 0, 4, (1, 1, [0, 2])]))   # split, filaments 2 / own / 4
        paint[4] = encode_paint((1, 2, [3, 0]))                      # side split in two
        sub = (MODEL_HEAD + "<resources>" + mesh_xml(CUBE_V, CUBE_T, paint, "1")
               + mesh_xml([(20, 0, 0), (22, 0, 0), (20, 2, 0), (20, 0, 2)],
                          [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)], None, "3")
               + mesh_xml([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)],
                          [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)], None, "4")
               + "</resources><build/></model>")
        root = (MODEL_HEAD + '<metadata name="Application">BambuStudio-02.01.00.00</metadata><resources>'
                '<object id="2" type="model"><components>'
                '<component p:path="/3D/Objects/object_1.model" objectid="1" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
                '<component p:path="/3D/Objects/object_1.model" objectid="3" transform="1 0 0 0 1 0 0 0 1 0 0 5"/>'
                '<component p:path="/3D/Objects/object_1.model" objectid="4" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
                '</components></object></resources>'
                '<build><item objectid="2" transform="1 0 0 0 1 0 0 0 1 120 110 0"/></build></model>')
        settings = ('<?xml version="1.0" encoding="UTF-8"?><config><object id="2">'
                    '<metadata key="name" value="Kitty"/><metadata key="extruder" value="1"/>'
                    '<part id="1" subtype="normal_part"><metadata key="extruder" value="1"/></part>'
                    '<part id="3" subtype="normal_part"><metadata key="extruder" value="3"/></part>'
                    '<part id="4" subtype="modifier_part"><metadata key="extruder" value="2"/></part>'
                    '</object></config>')
        path = os.path.join(d, "kitty.3mf")
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("3D/3dmodel.model", root)
            zf.writestr("3D/Objects/object_1.model", sub)
            zf.writestr("Metadata/model_settings.config", settings)
            zf.writestr("Metadata/project_settings.config",
                        '{"filament_colour": ["#FFFFFF", "#000000", "#E72727", "#2761E7"]}')
        return path

    def test_project(self):
        with tempfile.TemporaryDirectory() as d:
            data = reader3mf.read_3mf(self.build(d))
        self.assertEqual(data.source, "bambu")
        self.assertEqual(len(data.objects), 1)
        obj = data.objects[0]
        self.assertEqual(obj.name, "Kitty")
        self.assertEqual(obj.transform[9:], (120.0, 110.0, 0.0))
        self.assertEqual(obj.split_triangles, 2)
        self.assertEqual(data.colours, {("filament", 1): "#FFFFFF", ("filament", 2): "#000000",
                                        ("filament", 3): "#E72727", ("filament", 4): "#2761E7"})
        counts = collections.Counter(obj.face_colour)
        # cube: 12 triangles, 2 split into 4 + 2 leaves of which ...; tetra part (filament 3): 4
        self.assertEqual(counts[("filament", 3)], 4 + 1)  # the tetra part + one side leaf
        self.assertEqual(sum(counts.values()), 10 + 5 + 2 + 4)  # modifier part left out
        self.assertTrue(watertight(obj.faces[:17]))   # the cube, with split triangles
        self.assertTrue(watertight(obj.faces[17:]))   # the tetrahedron part
        tetra_z = {obj.vertices[i][2] for f in obj.faces[17:] for i in f}
        self.assertEqual(tetra_z, {5.0, 7.0})          # component transform applied


class RoundTripTest(unittest.TestCase):
    def test_own_export_keeps_exact_colours(self):
        palette = [PaletteEntry("Body", (1.0, 1.0, 1.0), 1), PaletteEntry("Ears", (1.0, 0.75, 0.8), 2)]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cube.3mf")
            writers.write_3mf(path, CUBE_V, CUBE_T, [0] * 10 + [1] * 2, palette, "Cube")
            data = reader3mf.read_3mf(path)
        obj = data.objects[0]
        self.assertEqual(collections.Counter(obj.face_colour),
                         {("rgb", "#FFFFFF"): 10, ("rgb", "#FFBFCC"): 2})
        self.assertTrue(watertight(obj.faces))


if __name__ == "__main__":
    unittest.main()
