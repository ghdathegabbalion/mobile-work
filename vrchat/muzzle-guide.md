# Reshaping the muzzle — fennec to lion cub

Step 6 of [`frennec-to-kaarten.md`](frennec-to-kaarten.md). **The highest-risk edit in the conversion**, and the one that decides whether face tracking survives.

Read this fully before starting. The technique is not difficult, but the wrong approach costs you a hundred blendshapes.

---

## Why this one is different

Every other edit so far has been in territory no face shape touches. The muzzle is the opposite: it's where **most** of the ARKit / Unified Expressions set lives — jaw, lips, mouth corners, funnel, pucker, cheek puff, every viseme.

That rules out both of the easy options:

- **Editing vertices on the Basis** — other shape keys store absolute positions, so they'd snap the muzzle back to fennec shape whenever they fire.
- **`Propagate to Shapes`** — overwrites those vertices in *every* shape key, flattening all mouth movement. You'd have a lion muzzle that can't talk.

The correct approach deforms the mesh with a **modifier**, then applies that modifier across every shape key so each one gets reshaped while keeping its own deformation.

---

## Pre-flight

- Save a versioned copy: `frennec_v05_muzzle.blend`. You will come back to it.
- Install [**ApplyModifierForObjectWithShapeKeys**](https://github.com/przemir/ApplyModifierForObjectWithShapeKeys) if you haven't already.
- Note the current shape key count. Write it down — you're checking against it later.
- Confirm the face shapes currently work, so you know the baseline is good.

---

## What actually changes

| Feature | Fennec | Lion cub |
|---|---|---|
| Muzzle length | Long, tapered | **Short and blunt** |
| Muzzle width | Narrow | **Broad**, especially at the base |
| Profile | Pointed, thin bridge | **Flatter front**, deeper jaw |
| Nose pad | Small, pointed | **Wide and flat**, sitting lower |
| Cheeks | Slim | **Full whisker pads**, rounded |
| Chin | Receding | **Fuller, more defined** |

Cub specifically: even shorter and rounder than an adult lion. Push further toward blunt than reference photos of adult lions suggest.

The single biggest change is **length** — shortening the muzzle does more of the work than anything else.

---

## 1. Build the lattice

1. `Add ▸ Lattice`. Scale and position it to enclose the whole muzzle, from the nose back past the cheeks, with a little margin.
2. In the lattice's Object Data properties, set resolution to about **5 × 5 × 5**. Enough control to shape a muzzle, few enough points to keep it smooth. Higher resolutions make it easy to introduce lumps.
3. Select the **body mesh**, add a **Lattice** modifier, target the lattice.

### Mask it with a vertex group — don't skip this

Without a mask the lattice drags the entire head along with the muzzle.

1. Create a vertex group, e.g. `muzzle_mask`.
2. Assign the muzzle vertices at weight `1.0`.
3. **Feather the boundary** — weights falling from 1.0 to 0.0 over several rings back toward the cheeks and brow. A hard boundary produces a visible crease.
4. Set that group in the Lattice modifier's **Vertex Group** field.

### Modifier order

Put the **Lattice modifier above the Armature modifier** in the stack. You want the lattice deforming the rest shape, then the armature posing the result.

---

## 2. Shape it

Edit Mode on the **lattice**, moving control points. The mesh updates live.

- Turn on **proportional editing** (`O`) with smooth falloff — moving single control points creates lumps.
- Work in this order: **length first** (pull the front points back), then **width** (push the sides out), then the profile, then the nose.
- Check the front, side and 3/4 views constantly. Muzzles read very differently from each angle, and a shape that looks right from the side often reads as too narrow from the front.
- Keep it symmetrical. If your lattice is centred on X you can mirror control point edits manually, or shape one side and use the lattice's own mirror if you've set one up.

**Do not touch the eyes yet.** One region at a time — it makes verification tractable.

Iterate until the muzzle reads as a lion cub with the lattice still live. Nothing is committed yet, so this stage is free.

---

## 3. Apply across every shape key

The moment of truth.

1. Select the body mesh.
2. Run **ApplyModifierForObjectWithShapeKeys**, selecting **only the Lattice modifier** — leave the Armature modifier alone.
3. Let it run. It iterates every shape key and applies the lattice deformation to each, which is exactly what native Apply cannot do.

On a mesh with 100+ shape keys this takes a while. Let it finish.

4. Delete the now-unused lattice object.

> If you accidentally use Blender's native Apply, it refuses with *"modifier cannot be applied to a mesh with shape keys."* That refusal is protecting you. Don't look for a way around it — use the addon.

---

## 4. Verify — properly

This is where you find out. Budget real time for it.

**First, the count.** Shape key count must match what you wrote down. A different number means something went wrong; revert to the backup.

**Then the high-movement shapes**, which expose problems fastest:

- `jawOpen` — the mouth should open cleanly, no tearing at the corners
- `mouthFunnel`, `mouthPucker` — lips should form properly on the new broader muzzle
- `mouthSmileLeft` / `mouthSmileRight` — corners should pull back without collapsing
- `cheekPuff` — should inflate the new fuller whisker pads
- Visemes `aa`, `oh`, `ou` — the biggest muzzle movers

**Then sweep the rest.** Cycle every shape key to `1.0` and back. You're looking for: no movement at all, movement in the wrong place, tearing, or vertices shooting off.

**Then combinations.** Set two or three mouth shapes to `1.0` together. Individually-fine shapes can still fight each other.

---

## 5. Fixing shapes that came out wrong

Expect a handful to need correction. This is normal and cheap — budget 15–25 hrs across the whole set, against 80–120 to author from scratch.

**Correcting a single shape key is safe.** Make that shape key active in the list, enter Edit Mode, and adjust. Edits to a **non-Basis** shape key affect only that key — the trap applies to the Basis, not to the others.

Typical fixes:
- Lips not meeting on the wider muzzle → nudge the lip vertices in the affected shape
- Corners tearing at high values → soften the falloff in that shape
- A shape that now barely reads → exaggerate it, since the broader muzzle needs more travel for the same visual effect

---

## 6. The eyes — same technique, separate pass

Once the muzzle verifies clean, repeat the whole process for the eyes: **larger, rounder, set lower** on the skull for the cub read.

New lattice, new mask, new apply, new verification. Doing them separately means when something breaks you know which change caused it.

`eyeBlinkLeft` / `eyeBlinkRight` are the critical checks — blinks must close **fully**. A blink that leaves a gap is very visible and very annoying.

---

## 7. Then rebuild the nose

The fennec nose pad is the wrong shape and small enough that reshaping fights you. Easier to **delete it and model a new one** as a separate object — wide, flat, sitting lower.

No shape key interaction if it's a separate object, so this is a free-form modelling job rather than a careful one.

---

## Done when

- [ ] Shape key count unchanged
- [ ] Every shape cycles cleanly, alone and in combination
- [ ] Blinks close fully
- [ ] Muzzle reads as a lion cub from front, side and 3/4
- [ ] `Build & Test` with face tracking live, and your own mouth drives his correctly

That last one is the real test. Everything else is a proxy for it.

---

## Next

Step 7 in [`frennec-to-kaarten.md`](frennec-to-kaarten.md) — new geometry: mane, horns, tail, wings. All separate objects, no shape key interaction, and after this pass it's straightforward modelling rather than careful surgery.
