# Heatsy Body Model

The open 3D body model used in **Heatsy**, an iOS workout app that shows which muscles an exercise works as heat on an animated anatomical body.

The model is adapted from **Z-Anatomy**, which is itself derived from **BodyParts3D**. It is released under the **Creative Commons Attribution-ShareAlike 4.0 International** licence (CC BY-SA 4.0). See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

Only the body model is covered by this licence. The Heatsy app, its code, animations, equipment models and other assets are not part of this repository and are not licensed here.

## Contents

| Path | What it is |
|---|---|
| `model/body_superficial.app5m.glb` | The body mesh used by the app: one skinned mesh (79,658 vertices, 149,030 triangles) on a 56-bone skeleton. Muscle, tendon and bone surfaces from Z-Anatomy, with simplified mannequin head, hands and feet. Quantised positions. |
| `data/muscles.json` | Vocabulary that decodes the `_PART_ID` vertex attribute: part, muscle and group ids, English and Latin names, layer. |
| `data/za_map.json` | Which Z-Anatomy objects form each part in `muscles.json`. |
| `LICENSE` | Full text of CC BY-SA 4.0. |
| `NOTICE.md` | Attribution and a list of changes. |
| `MANIFEST.md`, `manifest.json` | Every file with its size, SHA-256, origin and licence. |

## The glb file

- glTF 2.0 binary. Positions are `SHORT` values. Multiply by `extras.app_model.position_unit_m` (0.0001) to get metres.
- Standard attributes: `POSITION`, `NORMAL`, `JOINTS_0`, `WEIGHTS_0` (linear blend skinning, 56 joints, `skins[0]`).
- Custom attributes:
  - `_PART_ID` (uint8): 0 = none (mannequin parts, tendon-only and filler surface). Otherwise `1 + 2 * part_index + side`, where `part_index` is the position in `muscles.json` → `parts` and `side` is 0 for left and 1 for right.
  - `_FIBER` (int8 ×3, normalised): muscle fibre direction for each vertex.
  - `_TENDON` (uint8, normalised): how much of the surface is tendon, from 0 (muscle) to 1 (tendon).
- One material (`muscle_grey`). No textures.

## Relation to the app

Heatsy 1.0 (build 1) ships three body files: `body.hbody` (male), `body_f.hbody` and `body_f_home.hbody` (female). All three are baked from `model/body_superficial.app5m.glb` (the headers of the female files name `app5f.glb` as the source; it is a byte-identical copy). The male and female versions use the same body and differ only in the head. The baker copies the glb's geometry, skinning, fibre directions, tendon flags and part ids. It also adds a per-vertex contour field and a depth value, both computed from this geometry.

The heads in the app come from a third-party commercial asset. They are not under CC BY-SA, so they are not in this repository and no file here contains them. In the app the head replaces the mannequin head in this mesh. The app's `.hbody` files combine the body with that head, so they are not published as they are.

The repository will be tagged for each app release that changes the body model.

## Credits

Z-Anatomy by Gauthier Kervyn (design, 3D, anatomy) and Marcin Zielinski (Blender add-on), CC BY-SA 4.0. Its models are derived from BodyParts3D, © The Database Center for Life Science. Full attribution: [NOTICE.md](NOTICE.md).

The creators of Z-Anatomy and BodyParts3D do not endorse Heatsy or DDDEV LTD.

## Licence

Copyright © 2026 DDDEV LTD for the adaptations, licensed under CC BY-SA 4.0. The underlying material is copyright of its creators, as listed in NOTICE.md.

You may share and adapt this model, including for commercial use. You must give appropriate credit, indicate any changes, and release your adaptations under CC BY-SA 4.0 or a compatible licence. The material is provided as is, without warranty.
