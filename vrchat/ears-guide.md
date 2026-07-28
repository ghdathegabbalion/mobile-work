# Replacing Frennec's ears with lion cub ears

Step 4 of [`frennec-to-kaarten.md`](frennec-to-kaarten.md). The first change that makes him read as Kaarten rather than a fennec — and the lowest-risk edit on the whole model.

---

## Why this one is safe

**No face tracking shape deforms an ear.** ARKit and Unified Expressions cover eyes, brows, cheeks, jaw, lips and tongue — nothing else. So ear geometry can be deleted outright with no risk to the face rig.

**Confirm it yourself first (2 minutes):** set each shape key to `1.0` in turn and watch the ears. Nothing should move. If something does, stop and find out what before deleting anything.

Save a versioned copy before starting — `frennec_v04_ears.blend`.

---

## 1. Remove the fennec ears

The ears are almost certainly part of the head mesh rather than separate objects.

1. Edit Mode on the body mesh, **Face select**.
2. Hover over an ear and press `L` to select linked — if the ears are separate islands this grabs the whole ear cleanly.
3. If they're welded to the skull, select the ear manually up to the base, or use the ear bone's vertex group (`Select ▸ Select All by Trait`, or select the group from the Object Data panel) to get most of it and tidy by hand.
4. Delete the faces.

**Deleting vertices is safe here.** It removes them from every shape key consistently — no desync. It does change the vertex count, so if you ever want to transfer shapes from the original mesh, that's what the backup is for.

**Fill the holes.** Select the boundary loop where the ear met the skull and `F` to fill, or use Grid Fill for a cleaner result. Even though new ears will sit over the top, unfilled holes show through from odd angles and in mirrors.

---

## 2. Model the new ears

Lion cub ears are **small, round, low-set and angled slightly forward** — not scaled-down fox ears. That shape difference is most of the read.

Keep them as a **separate object**. Joining new geometry into a mesh that has shape keys is a reliable source of pain, and you'd gain nothing — d4rkAvatarOptimizer merges everything properly at the end.

A workable approach:

1. Start from a **UV sphere or cylinder**, or a subdivided plane you shape into a rounded cup.
2. Form a shallow dish: rounded outer edge, slight inward curve, thicker at the base than the rim.
3. Inner ear as a gentle indent — the detail can live in the texture rather than geometry.
4. A few short fur spikes at the base helps it sit into the head instead of looking pasted on.
5. **Mirror modifier** across X — never model both ears.

**Budget: 400–800 tris per ear.** That's generous for this shape. They sit inside the 16k head allocation alongside horns and mane.

### Placement

- **Lower and wider** on the skull than the fennec ears were — lion ears sit toward the sides, not the top.
- Angled slightly **forward and outward**.
- Rotate a few degrees off perfectly symmetrical if you want them to feel alive — but keep the mirror modifier's base placement symmetrical and do that in the pose/PhysBone layer instead.

The mane will eventually wrap the skull and cover the ear bases, so precision right at the join matters less than the silhouette above it.

---

## 3. Rig them

Frennec's ear bones already exist, positioned for tall ears. Reuse them rather than making new ones — the base is already weighted into the skeleton and Unity's Humanoid map ignores them either way.

1. Armature **Edit Mode** — reposition each ear bone chain to sit inside the new ear: head at the skull, tail toward the ear tip.
2. **Two bones per ear** is the sweet spot: a base bone and a tip bone gives a natural bend. One bone gives a rigid flick; three is more than a small ear needs.
3. Parent the ear object to the armature with **empty groups**, then assign weights — or simpler, assign the whole ear rigidly to the base bone at weight `1.0` and let the two-bone chain do the motion.

For an ear this size, rigid assignment to the base bone plus a two-bone PhysBone chain looks fine and skips weight painting entirely.

---

## 4. PhysBone tuning

Small light ears behave differently from big floppy fennec ears — reuse the fennec settings and they'll feel sluggish.

Starting points, then tune by feel:

| Setting | Start at | Why |
|---|---|---|
| Pull | ~0.4 | Returns to rest reasonably briskly |
| Spring | ~0.3 | Some bounce without wobbling |
| Stiffness | ~0.3 | Small ears resist deformation more than large ones |
| Gravity | ~0.05 | Barely any droop — they're light |
| Max Angle | limit it | Stops the ears folding back through the skull |

Add a **head collider** so they can't clip into the skull during fast head turns.

These are starting values, not answers — the only real test is moving your head sharply in-headset and seeing whether it looks like an ear or like jelly.

---

## 5. Texture

Nothing elaborate yet — you're retexturing the whole model later.

- Assign the ears to the same body material so they inherit the fur shading.
- A flat base fur colour is enough for now.
- Inner ear detail, the darker rim and any markings come during the full retexture pass.

---

## 6. Verify

- [ ] Every shape key still cycles to `1.0` and back cleanly — visemes and blinks included
- [ ] No holes in the skull where the old ears were
- [ ] Ears read as feline in silhouette from front, side and 3/4
- [ ] Nothing clips into the head when the ear bones are posed to extremes
- [ ] Tri count still inside the head budget

Then `Build & Test` and look in a mirror. This is the first moment he stops looking like a fennec.

---

## Next

Step 5 in [`frennec-to-kaarten.md`](frennec-to-kaarten.md) — body and limb proportions via Basis edit plus `Propagate to Shapes`. Much of that may already be done if you handled it during the [armature reproportion](reproportion-guide.md); this pass is for shaping the mesh itself beyond what bone scaling achieved.
