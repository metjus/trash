"""Read coloured 3MF files (no bpy), so this can be tested outside Blender.

Understands:
- Bambu Studio projects: meshes in 3D/Objects/*.model referenced through
  components, per-part filaments from Metadata/model_settings.config and
  filament colours from Metadata/project_settings.config;
- per-triangle filament painting: Bambu's ``paint_color`` and PrusaSlicer's
  ``slic3rpe:mmu_segmentation`` (including triangles that the slicer split
  into smaller ones while painting);
- standard 3MF colours: ``m:colorgroup`` and ``basematerials``.

The result is a list of ImportedObject, each a polygon mesh in millimetres
with one colour key per face. Colour keys are ("filament", n) or
("rgb", "#RRGGBB"); `colours` maps every key to an sRGB hex colour.
"""

import json
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

CORE = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
PROD = "{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}"
MATERIAL = "{http://schemas.microsoft.com/3dmanufacturing/material/2015/02}"
SLIC3RPE = "{http://schemas.slic3r.org/3mf/2017/06}"

UNITS_MM = {"micron": 0.001, "millimeter": 1.0, "centimeter": 10.0, "inch": 25.4,
            "foot": 304.8, "meter": 1000.0}

# Used for filaments when the file doesn't say their colour.
DEFAULT_FILAMENT_COLOURS = ["#FFFFFF", "#000000", "#E72727", "#2761E7", "#2BA84A", "#F2C200",
                            "#8E44AD", "#F28C28", "#7A4A2B", "#808080", "#FF8FB1", "#00B3B3",
                            "#C0C0C0", "#4B0082", "#9ACD32", "#800000"]

IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)


@dataclass
class ImportedObject:
    name: str
    vertices: list = field(default_factory=list)   # (x, y, z) in mm, object space
    faces: list = field(default_factory=list)      # lists of vertex indices
    face_colour: list = field(default_factory=list)  # colour key per face
    transform: tuple = IDENTITY                     # 3MF 3x4 matrix (row vectors), mm
    split_triangles: int = 0                        # painted triangles that were subdivided


@dataclass
class Imported:
    objects: list
    colours: dict  # colour key -> "#RRGGBB"
    source: str    # "bambu", "prusa" or "3mf"


# ---------------------------------------------------------------------------
# Paint strings
# ---------------------------------------------------------------------------

def _nibbles(code):
    """Hex paint string -> nibbles in reading order (the string is stored reversed)."""
    return [int(ch, 16) for ch in reversed(code.strip())]


def decode_paint(code):
    """Decode one triangle's paint string into a tree.

    A leaf is an int (the filament state, 0 = the part's own filament); a
    split triangle is (split_sides, special_side, [children...]) with the
    children in TriangleSelector order. Mirrors TriangleSelector::deserialize
    in Bambu Studio / PrusaSlicer.
    """
    nib = _nibbles(code)
    pos = [0]

    def read():
        if pos[0] >= len(nib):
            raise ValueError("paint string ended early")
        value = nib[pos[0]]
        pos[0] += 1
        return value

    def node():
        code_ = read()
        split_sides = code_ & 0b11
        if split_sides == 0:
            if (code_ & 0b1100) == 0b1100:
                extra, runs = read(), 0
                while extra == 0b1111:
                    runs += 1
                    extra = read()
                return extra + 15 * runs + 3
            return code_ >> 2
        special = code_ >> 2
        count = split_sides + 1
        children = [None] * count
        for i in range(count - 1, -1, -1):  # children are stored last first
            children[i] = node()
        return (split_sides, special, children)

    return node()


def encode_paint(tree):
    """Inverse of decode_paint (used by tests and kept for round trips)."""
    nibbles = []

    def emit(n):
        if isinstance(n, int):
            if n < 3:
                nibbles.append(n << 2)
            else:
                nibbles.append(0b1100)
                n -= 3
                while n >= 15:
                    nibbles.append(0b1111)
                    n -= 15
                nibbles.append(n)
        else:
            split_sides, special, children = n
            nibbles.append((special << 2) | split_sides)
            for child in reversed(children):
                emit(child)

    emit(tree)
    return "".join("%X" % v for v in reversed(nibbles))


def split_leaves(tri, tree, midpoint):
    """Leaf triangles (a, b, c, state) of a painted triangle.

    `midpoint(i, j)` returns the vertex index of the middle of edge i-j
    (creating it once and sharing it with the neighbouring triangle).
    Follows TriangleSelector::perform_split.
    """
    if isinstance(tree, int):
        return [(tri[0], tri[1], tri[2], tree)]
    split_sides, special, children = tree
    v = [tri[(special + k) % 3] for k in range(3)]
    if split_sides == 1:
        m12 = midpoint(v[2], v[1])
        tris = [(v[0], v[1], m12), (m12, v[2], v[0])]
    elif split_sides == 2:
        m01 = midpoint(v[1], v[0])
        m02 = midpoint(v[0], v[2])
        tris = [(v[0], m01, m02), (m01, v[1], m02), (v[1], v[2], m02)]
    else:
        m01, m12, m20 = midpoint(v[1], v[0]), midpoint(v[2], v[1]), midpoint(v[0], v[2])
        tris = [(v[0], m01, m20), (m01, v[1], m12), (m12, v[2], m20), (m01, m12, m20)]
    leaves = []
    for child_tri, child in zip(tris, children):
        leaves.extend(split_leaves(child_tri, child, midpoint))
    return leaves


# ---------------------------------------------------------------------------
# 3MF structure
# ---------------------------------------------------------------------------

def parse_transform(text):
    if not text:
        return IDENTITY
    values = tuple(float(v) for v in text.split())
    return values if len(values) == 12 else IDENTITY


def compose(a, b):
    """Transform that applies a first, then b (3MF row-vector 3x4 matrices)."""
    def m(t):
        return [[t[0], t[1], t[2]], [t[3], t[4], t[5]], [t[6], t[7], t[8]], [t[9], t[10], t[11]]]
    ma, mb = m(a), m(b)
    out = []
    for r in range(4):
        row = [sum(ma[r][k] * mb[k][c] for k in range(3)) for c in range(3)]
        if r == 3:
            row = [row[c] + mb[3][c] for c in range(3)]
        out.extend(row)
    return tuple(out)


def apply(t, p):
    x, y, z = p
    return (x * t[0] + y * t[3] + z * t[6] + t[9],
            x * t[1] + y * t[4] + z * t[7] + t[10],
            x * t[2] + y * t[5] + z * t[8] + t[11])


@dataclass
class _Mesh:
    vertices: list
    triangles: list   # (v1, v2, v3)
    paint: list       # paint string or "" per triangle
    colour: list      # ("rgb", hex) / None per triangle


@dataclass
class _ModelFile:
    unit_mm: float = 1.0
    meshes: dict = field(default_factory=dict)       # object id -> _Mesh
    components: dict = field(default_factory=dict)   # object id -> [(path or None, id, transform)]
    names: dict = field(default_factory=dict)        # object id -> name
    build: list = field(default_factory=list)        # (path or None, object id, transform)
    application: str = ""


def _hex(colour):
    colour = colour.strip().upper()
    if not colour.startswith("#"):
        colour = "#" + colour
    return colour[:7] if len(colour) >= 7 else "#808080"


def _parse_model(data):
    model = _ModelFile()
    groups = {}  # pid -> list of hex colours (colorgroup or basematerials)
    current = None   # object id being read
    obj_default = {}  # object id -> (pid, pindex)
    group_id, group = None, None
    for event, el in ET.iterparse(data, events=("start", "end")):
        tag = el.tag
        if event == "start":
            if tag == CORE + "model":
                model.unit_mm = UNITS_MM.get(el.get("unit", "millimeter"), 1.0)
            elif tag == CORE + "object":
                current = el.get("id")
                if el.get("name"):
                    model.names[current] = el.get("name")
                if el.get("pid") is not None:
                    obj_default[current] = (el.get("pid"), int(el.get("pindex", "0")))
            elif tag == CORE + "mesh":
                model.meshes[current] = _Mesh([], [], [], [])
            elif tag in (MATERIAL + "colorgroup", CORE + "basematerials"):
                group_id, group = el.get("id"), []
            elif tag == CORE + "components":
                model.components[current] = []
            continue

        # end events
        if tag == CORE + "vertex":
            model.meshes[current].vertices.append((float(el.get("x")), float(el.get("y")), float(el.get("z"))))
        elif tag == CORE + "triangle":
            mesh = model.meshes[current]
            mesh.triangles.append((int(el.get("v1")), int(el.get("v2")), int(el.get("v3"))))
            mesh.paint.append(el.get("paint_color") or el.get(SLIC3RPE + "mmu_segmentation") or "")
            pid = el.get("pid")
            p1 = el.get("p1")
            if pid is None and current in obj_default:
                pid, index = obj_default[current]
                p1 = p1 if p1 is not None else str(index)
            mesh.colour.append((pid, int(p1)) if pid is not None and p1 is not None else None)
        elif tag == MATERIAL + "color":
            group.append(_hex(el.get("color", "#808080")))
        elif tag == CORE + "base":
            group.append(_hex(el.get("displaycolor", "#808080")))
        elif tag in (MATERIAL + "colorgroup", CORE + "basematerials"):
            groups[group_id] = group
        elif tag == CORE + "component":
            model.components[current].append(
                (el.get(PROD + "path"), el.get("objectid"), parse_transform(el.get("transform"))))
        elif tag == CORE + "item":
            model.build.append((el.get(PROD + "path"), el.get("objectid"), parse_transform(el.get("transform"))))
        elif tag == CORE + "metadata" and el.get("name") == "Application":
            model.application = (el.text or "").strip()
        elif tag == CORE + "object":
            current = None
        if tag in (CORE + "vertex", CORE + "triangle"):
            el.clear()

    # resolve (pid, index) colours now that every group is known
    for mesh in model.meshes.values():
        resolved = []
        for c in mesh.colour:
            colours = groups.get(c[0]) if c else None
            resolved.append(("rgb", colours[c[1]]) if colours and 0 <= c[1] < len(colours) else None)
        mesh.colour = resolved
    return model


def _bambu_settings(zf):
    """Per-object and per-part filament numbers and names from model_settings.config."""
    objects = {}
    try:
        root = ET.fromstring(zf.read("Metadata/model_settings.config"))
    except KeyError:
        return objects
    for obj in root.iter("object"):
        meta = {m.get("key"): m.get("value") for m in obj.findall("metadata")}
        parts = {}
        for part in obj.findall("part"):
            pmeta = {m.get("key"): m.get("value") for m in part.findall("metadata")}
            parts[part.get("id")] = {"subtype": part.get("subtype", "normal_part"),
                                     "extruder": int(pmeta.get("extruder", 0) or 0),
                                     "name": pmeta.get("name", "")}
        objects[obj.get("id")] = {"name": meta.get("name", ""),
                                  "extruder": int(meta.get("extruder", 1) or 1), "parts": parts}
    return objects


def _filament_colours(zf):
    """Filament colours from a Bambu Studio or PrusaSlicer project, if present."""
    try:
        config = json.loads(zf.read("Metadata/project_settings.config"))
        colours = config.get("filament_colour") or []
        if colours:
            return [_hex(c) for c in colours]
    except (KeyError, ValueError):
        pass
    try:
        text = zf.read("Metadata/Slic3r_PE.config").decode("utf-8", "replace")
        for key in ("extruder_colour", "filament_colour"):
            m = re.search(r"^; %s = (.*)$" % key, text, re.M)
            if m:
                colours = [c for c in m.group(1).split(";") if c.strip()]
                if any(c.strip() for c in colours):
                    return [_hex(c) for c in colours]
    except KeyError:
        pass
    return []


def _prusa_volumes(zf):
    """PrusaSlicer: object id -> (default extruder, [(first, last triangle, extruder)], name)."""
    volumes = {}
    try:
        root = ET.fromstring(zf.read("Metadata/Slic3r_PE_model.config"))
    except KeyError:
        return volumes
    for obj in root.iter("object"):
        meta = {m.get("key"): m.get("value") for m in obj.findall("metadata") if m.get("type") == "object"}
        default = int(meta.get("extruder", 1) or 1)
        ranges = []
        for vol in obj.findall("volume"):
            vmeta = {m.get("key"): m.get("value") for m in vol.findall("metadata")}
            if vmeta.get("modifier") == "1" or vmeta.get("volume_type", "ModelPart") != "ModelPart":
                ranges.append((int(vol.get("firstid")), int(vol.get("lastid")), None))
                continue
            ranges.append((int(vol.get("firstid")), int(vol.get("lastid")),
                           int(vmeta.get("extruder", 0) or 0) or default))
        volumes[obj.get("id")] = (default, ranges, meta.get("name", ""))
    return volumes


# ---------------------------------------------------------------------------
# Building objects
# ---------------------------------------------------------------------------

class _Builder:
    """Collects one output object: merges meshes, splits painted triangles."""

    def __init__(self, name):
        self.obj = ImportedObject(name)
        self._mid = {}
        self._leaves = []  # (a, b, c, colour key)

    def _midpoint(self, i, j):
        key = (i, j) if i < j else (j, i)
        if key not in self._mid:
            a, b = self.obj.vertices[i], self.obj.vertices[j]
            self.obj.vertices.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2))
            self._mid[key] = len(self.obj.vertices) - 1
        return self._mid[key]

    def add_mesh(self, mesh, transform, unit_mm, default_key, skip=None):
        """skip(i) -> True to leave triangle i out; default_key(i) -> colour key for
        unpainted triangles (state 0)."""
        base = len(self.obj.vertices)
        t = transform
        for p in mesh.vertices:
            x, y, z = apply(t, p)
            self.obj.vertices.append((x * unit_mm, y * unit_mm, z * unit_mm))
        for i, (a, b, c) in enumerate(mesh.triangles):
            if skip and skip(i):
                continue
            tri = (a + base, b + base, c + base)
            fallback = mesh.colour[i] or default_key(i)
            code = mesh.paint[i]
            if code:
                try:
                    tree = decode_paint(code)
                except ValueError:
                    tree = 0
                if isinstance(tree, int) and mesh.colour[i]:
                    # Files that store both (e.g. our own export): the exact colour wins.
                    self._leaves.append((tri[0], tri[1], tri[2], mesh.colour[i]))
                    continue
                if not isinstance(tree, int):
                    self.obj.split_triangles += 1
                for la, lb, lc, state in split_leaves(tri, tree, self._midpoint):
                    self._leaves.append((la, lb, lc, ("filament", state) if state else fallback))
            else:
                self._leaves.append((tri[0], tri[1], tri[2], fallback))

    def _chain(self, a, b):
        """Midpoints created on edge a-b, in order from a to b."""
        key = (a, b) if a < b else (b, a)
        m = self._mid.get(key)
        if m is None:
            return []
        return self._chain(a, m) + [m] + self._chain(m, b)

    def finish(self):
        # A leaf next to a split neighbour gets the neighbour's midpoints on its
        # edges, so the mesh stays watertight (an n-gon with straight sides).
        for a, b, c, key in self._leaves:
            face = [a] + self._chain(a, b) + [b] + self._chain(b, c) + [c] + self._chain(c, a)
            self.obj.faces.append(face)
            self.obj.face_colour.append(key)
        return self.obj


def read_3mf(path):
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        root_path = "3D/3dmodel.model"
        try:
            rels = ET.fromstring(zf.read("_rels/.rels"))
            for rel in rels:
                if rel.get("Type", "").endswith("/3dmodel"):
                    root_path = rel.get("Target", root_path).lstrip("/")
        except KeyError:
            pass
        files = {}

        def model_file(p):
            p = (p or root_path).lstrip("/")
            if p not in files:
                with zf.open(p) as f:
                    files[p] = _parse_model(f)
            return p, files[p]

        root_name, root = model_file(root_path)
        bambu = _bambu_settings(zf)
        prusa = _prusa_volumes(zf)
        filament_hex = _filament_colours(zf)
        source = ("bambu" if root.application.startswith("BambuStudio") or bambu
                  else "prusa" if prusa or "PrusaSlicer" in root.application else "3mf")

        objects = []
        used = {}
        for number, (item_path, object_id, item_transform) in enumerate(root.build, 1):
            item_name, item_model = model_file(item_path)
            settings = bambu.get(object_id, {}) if item_name == root_name else {}
            name = (settings.get("name") or (prusa.get(object_id, (0, 0, ""))[2] if item_name == root_name else "")
                    or item_model.names.get(object_id) or "Object %d" % number)
            builder = _Builder(name)
            builder.obj.transform = item_transform

            def walk(path, oid, transform, part_extruder):
                p, model = model_file(path)
                if oid in model.components:
                    for cpath, cid, ctransform in model.components[oid]:
                        part = settings.get("parts", {}).get(cid) if p == root_name else None
                        if part and part["subtype"] != "normal_part":
                            continue  # modifiers, negative volumes and support blockers
                        extruder = (part or {}).get("extruder") or part_extruder
                        walk(cpath or p, cid, compose(ctransform, transform), extruder)
                    return
                mesh = model.meshes.get(oid)
                if mesh is None:
                    return
                skip, default_key = None, (lambda i: ("filament", part_extruder))
                if oid in prusa and p == root_name:
                    default, ranges, _name = prusa[oid]

                    def lookup(i, ranges=ranges, default=default):
                        for first, last, extruder in ranges:
                            if first <= i <= last:
                                return extruder
                        return default
                    skip = lambda i: lookup(i) is None
                    default_key = lambda i: ("filament", lookup(i) or default)
                builder.add_mesh(mesh, transform, model.unit_mm, default_key, skip)

            walk(item_name, object_id, IDENTITY, settings.get("extruder") or 1)
            obj = builder.finish()
            if obj.faces:
                objects.append(obj)
                for key in obj.face_colour:
                    used[key] = None

    colours = {}
    for key in used:
        if key[0] == "rgb":
            colours[key] = key[1]
        else:
            n = key[1]
            colours[key] = (filament_hex[n - 1] if 0 < n <= len(filament_hex)
                            else DEFAULT_FILAMENT_COLOURS[(n - 1) % len(DEFAULT_FILAMENT_COLOURS)])
    return Imported(objects, colours, source)


def colour_name(key, hex_colour):
    return "Filament %d" % key[1] if key[0] == "filament" else hex_colour
