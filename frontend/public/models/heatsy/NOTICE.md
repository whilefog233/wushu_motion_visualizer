# Notice and attribution

## Heatsy Body Model

Adapted by DDDEV LTD, 2026. Licensed under the Creative Commons Attribution-ShareAlike 4.0 International licence (CC BY-SA 4.0), https://creativecommons.org/licenses/by-sa/4.0/. The full text is in `LICENSE`.

## Sources

### Z-Anatomy

- "Z-Anatomy - The libre 3D atlas of anatomy - CC-BY-SA 4.0"
- Gauthier Kervyn (design, 3D, anatomy), Marcin Zielinski (Blender add-on).
- https://github.com/Z-Anatomy/Models-of-human-anatomy (file `Startup.blend`, branch `master`).
- Licence: CC BY-SA 4.0. The Z-Anatomy licence file says: "All the code and content shared by 'Z-Anatomy' is under Creative Commons Attribution-ShareAlike 4.0 International License".
- Used: the muscle, tendon and bone meshes, the 'Tendon' material assignment and the object names. We use no Z-Anatomy parts that are under non-commercial terms. Those parts are the inner ear (CC BY-NC-SA 4.0) and the kidney (CC BY-NC 4.0). We also use no brain, nerve or white-matter models.

### BodyParts3D

Z-Anatomy's models are derived from BodyParts3D. We use BodyParts3D only through Z-Anatomy.

- Attribution in the form Z-Anatomy asks for: "BodyParts3D - The Database Center for Life Science - CC-BY-SA 2.1 Japan".
- The BodyParts3D licence page currently states: "The license for this database is specified in the Creative Commons Attribution 4.0 International". It asks for this attribution: "BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International".
- https://dbarchive.biosciencedbc.jp/en/bodyparts3d/ (licence: https://dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html, checked 2026-10-18).
- Original model: Kousaku Okubo.

## Changes made by DDDEV LTD

1. Selected the muscle, tendon and bone meshes from the Z-Anatomy atlas. Cleaned them by welding vertices, removing duplicate faces and orienting normals.
2. Trimmed overlapping surfaces, such as the rectus sheath lamina on the oblique and transversus meshes. Added sub-millimetre inward offsets where surfaces coincide.
3. Decimated each piece and joined the pieces into one superficial layer.
4. Replaced the skull, face and bare finger and toe bones with simplified mannequin head, hands and feet. These were generated from a fused surface of the same meshes. Filled hidden cavities.
5. Added a 56-bone skeleton and linear blend skinning weights.
6. Added per-vertex data: part ids (`_PART_ID`, decoded by `data/muscles.json`), muscle fibre directions (`_FIBER`) and tendon weights (`_TENDON`).
7. Quantised the positions to 0.1 mm for the app.

`data/muscles.json` (the part, muscle and group vocabulary) and `data/za_map.json` (the part to Z-Anatomy object map) were written by DDDEV LTD. They are released under CC BY-SA 4.0 with the model.

## No endorsement, no warranty

The creators and licensors of Z-Anatomy and BodyParts3D do not endorse Heatsy or DDDEV LTD. The licensed material is provided as is, without warranties of any kind, as stated in the licences.
