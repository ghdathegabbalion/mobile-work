# Frennec → Kaarten — conversion notes

Practical guide for reshaping a fennec base into a lion cub without destroying the face tracking rig.

Companion to [`kaarten-fast-path.md`](kaarten-fast-path.md).

---

## First — consider a feline base instead

Frennec is a **fennec fox**. Converting him to a lion means changing the ears, the muzzle, the paws, the tail and the head proportions — which is most of the head and a fair chunk of the body.

There are feline bases that ship with face tracking and Blender source, and at least one that ships a **lion** configuration outright:

| Base | Notes |
|---|---|
| [**Revit's Felines**](https://revit.gumroad.com/l/QHWXq) | 10 configurations including **Lion**, plus lynx, sabertooth, cheetah, snow leopard. Blender + Substance source. |
| [**Winterpaw Feline**](https://juliawinterpaw.gumroad.com/l/Feline) | Supports **both Unified Expressions and ARKit**, 16 species textures, organised Substance/Photoshop files. |
| [**Big Cat (2025)**](https://skip4d.gumroad.com/l/bigcat2025) | ARKit, 27 meshes built for fast Blender customisation. |
| [**RoverCat**](https://rexrover.gumroad.com/l/RoverCat) | **Modular ears and tails**, 12 cat species. Modularity is a real advantage here. |

Starting from a lion means the muzzle, ears, paws and fur direction are already right, and you spend your time on *Kaarten* — the mane, horns, wings, tail, armour — rather than on undoing fox anatomy.

**The cuteness you like in Frennec is mostly proportion and face texture**, both of which you're redoing anyway. Worth an hour comparing before committing. If you still prefer Frennec's base afterwards, everything below applies.

---

## The ears are the easy part

Counter-intuitively, the ears are the *least* risky change on the model.

**Face tracking shapes don't touch the ears.** ARKit and Unified Expressions cover eyes, brows, cheeks, jaw, lips and tongue. Nothing in either standard deforms an ear. So ear geometry can be deleted and rebuilt with zero risk to the face rig.

### Verify first (2 minutes)

In Blender, open the shape key list and set each key to `1.0` in turn, watching the ears. If nothing moves — and it won't — they're free to replace.

### Replace, don't scale

Scaling a fennec ear down gives you a *small pointed fennec ear*. Lion cub ears are **small, round, and set low on the sides of the skull** — different shape, not just different size.

1. Select the ear geometry (`L` with the cursor over it selects linked, if they're separate islands).
2. Delete it.
3. Model new ears as a **separate object** — rounded, low-set, slightly forward.
4. Keep them as a separate object for now (see below).
5. Weight them to the existing ear bones.
6. Retune the ear PhysBones — smaller, lighter ears want higher stiffness and less droop than fennec ears did.

### Keep new geometry as separate objects

Joining a new mesh into an object that already has shape keys is a reliable source of pain. Instead, keep every addition — ears, horns, mane, wings, tail, armour — as **separate objects** through development, and merge them at the very end with **d4rkAvatarOptimizer**, which handles the merge correctly.

Costs you nothing, avoids a whole category of problem.

---

## The shape key trap — read before touching the head

This is the one that silently ruins work.

**In Blender, editing the Basis shape key does not update the other shape keys.** Other keys store absolute vertex positions. So you reshape the muzzle on Basis, everything looks right — then face tracking activates and the muzzle *snaps back* to fennec shape.

There are three correct approaches, depending on where you're editing.

### Region A — no shape keys touch it (ears, tail, limbs, torso, paws)

Edit the Basis freely, then select the affected vertices and use:

**`Mesh ▸ Propagate to Shapes`** *(native Blender — no addon needed)*

This writes the current positions into every other shape key. Safe here precisely because nothing in the face set deforms these vertices.

⚠️ **Do not use it on the face.** It overwrites those vertices in *all* shape keys — meaning every mouth and eye movement in that region gets flattened out. It's a hammer, and the face needs a scalpel.

⚠️ **Never undo mid-edit on the Basis.** A known Blender issue: undoing during a Basis editing session makes that session's changes untransferable to existing shape keys. Save incrementally instead.

### Region B — the muzzle, eyes, cheeks, jaw (shape keys live here)

Don't edit vertices directly. **Deform with a modifier, then apply it across every shape key.**

1. Add a **Lattice** around the muzzle (or use Surface Deform against a sculpted target).
2. Shape the lattice: fennec's narrow pointed muzzle → a lion cub's broad, short, flat muzzle.
3. Apply the modifier across all keys with [**ApplyModifierForObjectWithShapeKeys**](https://github.com/przemir/ApplyModifierForObjectWithShapeKeys) — it iterates every shape key and applies the deformation to each.

Result: the muzzle becomes a lion's, **and every face tracking shape is reshaped with it**. The rig keeps working.

This is the single most valuable technique in this document. Without it, the muzzle is a re-author of 100+ blendshapes; with it, it's an afternoon.

### Region C — genuinely new geometry

Mane, horns, wings, dragon tail, armour. No shape key interaction at all — model freely as separate objects.

---

## Cub proportions vs. full-body tracking

A real tension, worth deciding deliberately.

"Lion cub" implies **bigger head relative to body, shorter limbs, rounder features**. That is *exactly* the direction that makes FBT IK misbehave — short legs relative to torso is the specific thing that produces bad knee bends and floating hips.

Also worth flagging: the design sheet describes Kaarten as **"short, stout, muscular"** and a **"Noble Champion / Guardian"** — an adult-proportioned character who happens to be 138 cm, not a cub. Those are different silhouettes.

Options:

- **Cub face, adult-ish proportions** — round muzzle, big eyes, soft features on a stout compact body. Reads young and cute, keeps FBT sane. **Recommended**, and closest to the sheet.
- **Full cub proportions** — commit to the chunky-limbed, big-headed look and accept that FBT will need careful calibration and may still look off in some poses.
- **Cub v1, adult v2** — proportions are just vertex positions. With shape keys handled properly you can revisit this later.

Worth deciding before Phase 1 block-out, since it sets the skeleton.

---

## Full fennec → lion conversion checklist

| Part | Fennec | Lion cub | Method | Risk |
|---|---|---|---|---|
| **Ears** | Huge, pointed, upright | Small, round, low-set | Delete + remodel | None |
| **Muzzle** | Narrow, pointed, long | Broad, short, flat | Lattice + apply-across-keys | **High** |
| **Eyes** | Fox-set | Rounder, forward, larger | Lattice, same method | **High** |
| **Head size** | Standard | Larger relative to body | Basis + Propagate | Low |
| **Paws** | Slim, small | Chunky, broad toe pads | Basis + Propagate | Low |
| **Body** | Slim | Stout, broad chest | Basis + Propagate | Low |
| **Limbs** | Long | Shorter, thicker | Basis + Propagate — watch FBT ratio | Medium |
| **Tail** | Bushy fox tail | Scaled → feathered dragon tail | Delete + new object | None |
| **Fur texture** | Fennec cream/tan | Kaarten tan + cream accent | Retexture | None |
| **Mane, horns, wings** | — | New | New objects | None |

---

## Verification after every head edit

Cheap, catches everything:

1. Cycle every shape key to `1.0` and back. Watch for snapping, tearing, or a shape doing nothing.
2. Check the visemes specifically — `aa`, `oh`, `ou` move the muzzle most.
3. Check blinks still close fully.
4. Save incrementally, with versioned filenames. Shape key corruption is often noticed late.

---

## Order of work

1. Decide base — Frennec or a feline base. **Do this before anything else.**
2. Decide cub-vs-stout proportions.
3. Upload the unmodified base as a private test avatar; confirm FT and FBT work end to end.
4. Ears — delete and remodel. Easy win, immediate visual payoff, zero risk.
5. Body and limb proportions — Basis + Propagate to Shapes.
6. Muzzle and eyes — Lattice + apply-across-keys. Verify shapes.
7. New geometry — mane, horns, tail, wings.
8. Retexture.
9. Armour.
