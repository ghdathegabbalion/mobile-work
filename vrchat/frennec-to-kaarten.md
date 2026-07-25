# Frennec → Kaarten — conversion notes

Practical guide for reshaping a fennec base into a lion cub without destroying the face tracking rig.

Companion to [`kaarten-fast-path.md`](kaarten-fast-path.md).

---

## Base: Frennec — decided

[**Frennec**](https://nattbat.gumroad.com/l/frennec) — free, full-body rig, ARKit face tracking, visemes and expressions.

He's a fennec fox and Kaarten is a lion, but the conversion is smaller than it first looks, and the cub/teen direction shrinks it further:

- **It's free.** If it doesn't work out you've lost an evening, not money.
- **Fennec bases start small and cute** — less reproportioning to reach cub/teen than an adult feline base would need.
- **The mane hides most of the argument.** Kaarten's rainbow mane wraps the whole skull and jawline, so fox-versus-lion head silhouette differences are largely covered.
- **The ears are free to replace** (below), and they're the loudest fox cue on the model.
- **The tail is new geometry regardless** — Kaarten needs a scaled, feathered dragon tail, which no feline base would have given you either.

That leaves the **muzzle** as the only genuinely fox-shaped thing you must fix, and there's a clean technique for it below.

<details>
<summary>Feline bases, if Frennec doesn't work out</summary>

| Base | Notes |
|---|---|
| [Revit's Felines](https://revit.gumroad.com/l/QHWXq) | 10 configurations including **Lion**. Blender + Substance source. |
| [Winterpaw Feline](https://juliawinterpaw.gumroad.com/l/Feline) | **Unified Expressions and ARKit**, 16 species textures. |
| [Big Cat (2025)](https://skip4d.gumroad.com/l/bigcat2025) | ARKit, 27 meshes built for fast Blender customisation. |
| [RoverCat](https://rexrover.gumroad.com/l/RoverCat) | Modular ears and tails, 12 species. |

</details>

**Before sculpting anything:** confirm Frennec ships `.blend` source (not Unity-package-only), that the ARKit shapes are actually present in the shape key list, and that the licence permits heavy modification and public upload.

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

## Cub/teen proportions — the spec

**Decision: Kaarten is a cub/teen.** This section is the build target.

I flagged FBT as a risk earlier. Having looked at what actually breaks, the constraint is much narrower than "cub proportions are risky" — and everything that makes him read as young is on the safe side of it.

### What's free, and what costs you

VRChat's IK maps your real limbs onto the avatar's. The thing that misbehaves is a **leg-length-to-height ratio** far from your own — that's what produces bad knee bends and floating hips. Nothing else about youthful proportion touches it.

| Change | FBT impact | Verdict |
|---|---|---|
| **Bigger head relative to body** | None | **Free** — and it's the single strongest youth cue |
| **Chunky, thick limbs** | None | **Free** |
| **Short overall height (138 cm)** | None | **Free** |
| **Large paws relative to limbs** | None | **Free** — already in the design sheet |
| **Round torso, soft muscle definition** | None | **Free** |
| **Short neck** | None | **Free** |
| **Shortened legs relative to torso** | **This is the one** | Keep within the rule below |

So: get the youth from **head size, limb thickness, paw size and facial features** — all free — rather than from shortening the legs. You can land a genuinely cub-like read without ever approaching the constraint.

### The one hard rule

**Leg length (floor to hip joint) ≥ 44% of total height.**

For reference: adult humans sit around 48–50%, a ten-year-old around 45%, a toddler around 36%. Below ~40% is where FBT visibly degrades.

At 138 cm that means **hip joint at 61 cm or higher**. Comfortably compatible with a cub silhouette — real children clear it easily.

### Target proportions

| Measure | Target | Note |
|---|---|---|
| Total height | **138 cm** | From the design sheet |
| Head height | **23–25 cm** | ≈ 5.5–6 heads tall. Adult is ~7.5; chibi is 2–3 |
| Hip joint height | **62–66 cm** | **45–48% — the FBT-critical number** |
| Torso, hip to shoulder | ~38–40 cm | Compact |
| Neck | Short | Strong youth cue, costs nothing |
| Shoulder width | ~1.6–1.8 head widths | Broad — keeps the sheet's "broad chest" |
| Eye line | ~45% up the skull | Lower than adult (~50%). Big youth cue |
| Muzzle | Short and blunt | Works in your favour — lion cubs have short muzzles |
| Paws | Large relative to limbs | Already specified on the sheet |

5.5–6 heads is the sweet spot: unmistakably young, still functional in VR. Below 5 heads you start fighting both FBT and world interaction heights.

### Cub/teen anatomy for the sculpt

- Larger cranium, more prominent forehead, smaller face within the skull
- Eyes larger and set **lower**; nose small; cheeks round and full
- Muzzle short and blunt rather than long and tapered
- Shorter neck, sloping into the shoulders
- Softer muscle transitions — suggest strength through bulk, not definition
- Rounder torso with minimal waist taper
- Limbs shorter and **thicker**; joints less defined
- Paws and hands oversized — one of the most effective and cheapest youth cues

### Note on the design sheet

The sheet says **"muscular"** and describes a "Noble Champion / Guardian." Cub/teen and defined musculature pull against each other. The resolution that keeps both readings: **bulk without definition** — broad chest, thick limbs, powerful stance, but soft rounded transitions instead of visible muscle separation. Reads as a sturdy, powerful young lion rather than a bodybuilder.

Worth updating the sheet's build line to match once you've settled the look.

### Test the skeleton before you sculpt

The cheapest hour in this project:

1. Reproportion the **armature only** — scale the head bone up, shorten and thicken the limb bones, set hip height.
2. Export, upload as a private test avatar.
3. Stand in it with your trackers on. Walk, crouch, sit, look in a mirror.
4. Adjust and repeat.

Proportions are the one decision that's expensive to change after sculpting and nearly free to change before. Get the skeleton feeling right in-headset first, then sculpt the mesh onto it.

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

Base and proportions are both settled — Frennec, cub/teen. Start at step 1.

1. **Verify Frennec's files** — `.blend` source present, ARKit shapes in the list, licence allows modification.
2. **Upload it unmodified** as a private test avatar. Confirm face tracking and FBT work end to end on your hardware, before any art investment.
3. **Reproportion the armature only** to the cub/teen spec above. Upload again, stand in it with trackers, adjust until it feels right. Cheapest hour in the project.
4. **Ears** — delete and remodel as a separate object. Easy win, immediate visual payoff, zero risk to the rig.
5. **Body and limb proportions** — Basis edit + `Propagate to Shapes`.
6. **Muzzle and eyes** — Lattice + apply-across-all-shape-keys. Verify every shape afterwards.
7. **New geometry** — mane, horns, tail, wings, as separate objects.
8. **Retexture** to Kaarten's palette.
9. **Armour.**

Steps 1–4 are a weekend and get you a recognisably young lion in VRChat with working face tracking. That's the milestone worth aiming at first.
