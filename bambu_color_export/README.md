# Bambu Color Export (Blender add-on)

Exports your Blender model with its material colours so **Bambu Studio opens it
already painted**, one filament per colour.

## Install
1. Zip the `bambu_color_export` folder (the zip must contain the folder).
2. Blender → *Edit → Preferences → Get Extensions → ⌄ → Install from Disk…* → pick the zip.
   (Or drag the zip into the Blender window.) Requires Blender 4.2+.

## Use
1. Colour parts as you already do: a material with a **Principled BSDF** whose
   *Base Color* is set directly or through a **Color (RGB)** node. Diffuse/Emission
   shaders also work; anything else falls back to the material's *Viewport Display* colour.
2. Open the **Bambu** tab in the 3D Viewport sidebar (`N`). There is one row per
   object (named as in the Outliner; objects with several materials get one row per material):
   - **Colour**: click the swatch for Blender's colour picker (wheel, RGB/HSV, **Hex**).
     It edits the material's own colour (its Color node or Base Color), so viewport,
     render and export stay in sync. Rows with a chain icon share one material, so
     changing one changes them all;
   - **Filament**: the filament/AMS slot the part gets in Bambu Studio. Parts with the
     same colour share a slot automatically. Type a number to choose it yourself, 0 to go back to automatic;
   - objects without a material show a **+** button that gives them one.
3. Click **Export 3MF** (or *File → Export → Bambu Studio 3MF*).
4. Open the 3MF in Bambu Studio. It says *"The 3mf is not from Bambu Lab, load geometry
   data and color data only"*. That is expected for any file not saved by Bambu Studio;
   click OK. Bambu then opens its colour dialog: check the colour → filament matching
   (it can add missing filaments) and confirm. The model appears painted.

### Options
- **Scale**: 1 Blender unit = 1 mm by default. Enable *Use Scene Units* if you model in
  real metres.
- **Merge Same Colours / Colour Tolerance**: combine near-identical colours into one filament.
- **Export OBJ + MTL**: fallback. Bambu Studio shows its colour-mapping dialog for coloured OBJ files.

## Paint a single model
For one whole mesh that needs several colours, use the **Bambu Paint** panel (Bambu tab):
1. Select the mesh. Click **Add Colour** for each colour you need. Colour 1 is the base
   colour (unpainted areas); click a swatch to change a colour.
2. Pick a colour (click its name), choose **Brush** or **Fill**, set **Symmetry** X / Y / Z
   if the model is symmetric, then click **Start Painting**.
3. In the viewport:
   | Input | Action |
   |---|---|
   | LMB drag | paint with the active colour |
   | Shift + LMB | paint with the base colour (erase) |
   | 1 – 9 | pick colour |
   | `[` / `]` | brush radius |
   | F | switch Brush / Fill / Smooth |
   | S | Fill: stop at sharp edges on/off |
   | X / Y / Z | toggle symmetry |
   | Ctrl+Z | undo last stroke |
   | H | show / hide the controls overlay |
   | MMB / wheel | navigate the view as usual |
   | Esc / Enter / RMB | finish |
   The controls are listed in the viewport while painting (H hides them) and in the
   panel's collapsible **Controls** section.
   **Smooth** evens out jagged colour edges: drag it along a ragged border and each face
   under the brush takes the colour that covers most of its surroundings (*Strength* =
   passes per dab). Only faces under the brush change, never the rest of the model.

   **Delete a colour** with the **X** next to it: its areas get the base colour (colour 1),
   which can't be deleted.

   **Fill options**: *Stop at Colour Change* fills only the clicked colour's area;
   *Stop at Sharp Edges* stops at creases bending more than *Sharp Angle* (default 30°)
   and at edges marked Sharp. Click a raised detail with it on to colour just that detail.
4. Export as usual. Painted areas become separate filaments.

If anything goes wrong, painting mode stops by itself and the panel shows
**An error was recorded** with a **Copy Error** button: it copies the full error (with the
add-on and Blender versions) to the clipboard, ready to paste into a bug report. While
painting, **Stop Painting** sits at the top of the panel. The add-on version is shown at
the bottom of the Bambu Paint panel.

Notes: painting colours whole faces, so edges follow the mesh. Subdivide (or remesh) low-poly
models for finer detail. Symmetry mirrors across the object's origin, so keep the origin
on the model's centre line.

## Split colours into parts (for single-colour printers, e.g. resin)
Print each colour separately and assemble: the **Bambu Split Parts** panel (Bambu tab)
turns a painted model into a **body** plus one **part** per other colour.
Each part's top is the painted surface; it goes *Depth* mm into the model and sits in a
pocket in the body that is *Tolerance* mm larger on every side.

1. Select the painted mesh.
2. Pick **Resin** (tolerance 0.05 mm, depth 1 mm) or **FDM** (0.2 mm, 1.5 mm), or type your
   own values: editing either switches to **Custom** and your values stay.
3. Check **1 Blender unit (mm)** so the model size shown matches the printed size; the
   tolerance and depth are real millimetres at that size.
4. **Body Colour** picks the colour that becomes the body (0 = Auto: colour 1, or, when
   the whole model is painted and colour 1 isn't used, the colour with the largest painted
   area). The panel shows which colour it will be.
5. Click **Split Colours into Parts**. The result goes into a new collection
   "<model> parts"; the original is only hidden.

**Flat Bottom** (on by default) gives every part a flat bottom for good bed adhesion:
the bottom is a plane square to the part's average direction, *Depth* mm below its lowest
painted point (so *Depth* is the part's thinnest spot), and the walls run straight to it, so
the part slides straight into its pocket. Each separate area of a colour (e.g. two eyes)
gets its own flat bottom. Print the part flat side down. With Flat Bottom off, the bottom
follows the surface at an even depth instead. A colour that wraps round the model too far
for one flat bottom (more than about half a sphere) gets a warning.

If the model is thinner than the part (+ tolerance) under a colour, you get a warning naming
the colour: the part could go through, so use a smaller depth. Parts of two neighbouring
colours touch each other without a gap. Export each part on its own (e.g. File → Export →
STL with *Selection Only*).

## How it works
All selected objects are merged (modifiers applied) into one mesh. Each triangle gets:
- a colour from a standard 3MF colour group (`m:colorgroup`). Bambu Studio reads this and
  shows its colour-to-filament dialog;
- Bambu's per-triangle `paint_color` filament code (the panel's Filament number), used
  if you cancel that dialog.
