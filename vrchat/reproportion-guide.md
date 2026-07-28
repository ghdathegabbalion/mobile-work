# Reproportioning Frennec to cub/teen

Step 3 of [`frennec-to-kaarten.md`](frennec-to-kaarten.md). Do this **before** any sculpting — proportions are nearly free to change now and expensive to change later.

Target spec is in [the proportion section](frennec-to-kaarten.md#cubteen-proportions--the-spec). Working numbers:

| Measure | Target |
|---|---|
| Total height | **1.38 m** |
| Head height | **0.23–0.25 m** (≈ 5.5–6 heads) |
| Hip joint height | **0.62–0.66 m** — **must be ≥ 0.61 m** |

---

## Before you start

- **Save a versioned copy.** `frennec_v01_base.blend`, then work in `frennec_v02_proportions.blend`. You will want to go back.
- Install [**ApplyModifierForObjectWithShapeKeys**](https://github.com/przemir/ApplyModifierForObjectWithShapeKeys) — you need it here and again for the muzzle later.
- Confirm the shape key list is populated before you touch anything, so you can tell if you break it.

---

## 1. Measure what you've got

Open the N-panel (`N`) ▸ **Item** tab to read coordinates.

- **Total height** — select the topmost skull vertex (not ears), read `Z`.
- **Head height** — topmost skull `Z` minus chin `Z`.
- **Hip height** — select the `Hips` bone in Edit Mode, read its head `Z`.

Then compute:

```
heads_tall  = total_height / head_height
leg_ratio   = hip_height / total_height     ← must end ≥ 0.44
```

Write the starting numbers down. Frennec will come in somewhere around 6.5–7 heads with a leg ratio near 0.47 — normal adult-ish proportions.

---

## 2. Set overall height first

Scale the whole rig (armature + mesh together, object mode) so total height is **1.38 m**.

Do this before proportion changes — every later number is relative to it, and getting it right now means you're checking against absolutes rather than percentages.

Apply the scale (`Ctrl+A ▸ Scale`) on both objects afterwards.

---

## 3. Reproportion in Pose Mode — not Edit Mode

**This is the part people get wrong.** Moving bones in the armature's *Edit Mode* changes the rest pose but leaves the mesh behind — weights then map to the wrong places and the model tears.

The correct sequence:

1. **Pose Mode** on the armature. Pose the bones to the new proportions (recipe below). The mesh follows live through the Armature modifier, so you can see exactly what you're getting.
2. Happy with it? Select the **mesh**, and apply the Armature modifier using **ApplyModifierForObjectWithShapeKeys**. This bakes the deformation into the mesh *and every shape key* — which the native Apply cannot do.
3. Re-add an **Armature modifier** to the mesh, targeting the armature.
4. Back in Pose Mode: **`Pose ▸ Apply ▸ Apply Pose as Rest Pose`**.

Now the new proportions are the rest pose, the mesh matches, and the face rig is intact.

> If you skip step 2's special tool and use Blender's normal Apply, it will refuse — "modifier cannot be applied to a mesh with shape keys." That error is the guardrail telling you you're about to lose the face tracking.

---

## 4. The posing recipe

In Pose Mode, roughly in this order. Scale uniformly unless noted — non-uniform bone scaling can confuse Unity's Humanoid retargeting.

**Head — the biggest youth cue, and free**
- Scale the `Head` bone up until head height reaches **0.23–0.25 m**.
- Typically `S` around `1.25–1.4` depending on where Frennec starts.
- Check the neck join doesn't pinch; nudge `Neck` scale slightly if it does.

**Neck — shorten**
- Scale `Neck` down to ~`0.8`. Short necks read young and cost nothing.

**Legs — careful, this is the constrained one**
- Shorten `UpperLeg` and `LowerLeg` only as far as the ratio allows.
- **Re-measure hip height after every change.** Stop at **0.62 m**; do not go below **0.61 m**.
- If he still looks too leggy at the limit, take the remaining youth from head size and limb thickness instead.

**Limbs — thicken**
- Scale arm and leg bones on their **cross-section axes only** (typically X and Y, not the bone's length axis) to `1.15–1.3`.
- Thickness has zero IK impact. Use it freely — it's doing a lot of the cub read.

**Torso — compact and broad**
- Slightly shorten `Spine` and `Chest`; widen `Chest` on X.
- Aim for hip-to-shoulder around **0.38–0.40 m**.

**Paws and hands — oversize them**
- Scale hand and foot bones to `1.15–1.25`.
- Already called for on the design sheet, and one of the cheapest youth cues available.

---

## 5. Verify the numbers

Re-measure and check:

```
total_height ≈ 1.38          ✓
head_height  = 0.23 – 0.25   ✓
heads_tall   = 5.5 – 6.0     ✓
hip_height   ≥ 0.61          ✓ ← the FBT-critical one
```

If `hip_height` came in under 0.61, lengthen the legs back and compensate with head scale. **That check is not negotiable** — it's the one measurement that degrades full-body tracking.

---

## 6. Verify the rig still works

Before exporting:

1. Cycle every shape key to `1.0` and back. Nothing should snap, tear, or sit inert.
2. Check visemes specifically — `aa`, `oh`, `ou` move the muzzle most.
3. Check blinks close fully.
4. In Pose Mode, rotate shoulders, elbows, knees and hips through their range. Look for candy-wrapper twisting, especially at the now-thicker joints.

Thicker limbs deform worse than thin ones. If a joint pinches, fix the weights now rather than after sculpting.

---

## 7. Export to Unity

FBX export, mostly defaults. The ones that matter:

- **Include:** Selected Objects — mesh + armature
- **Forward:** `-Z Forward`, **Up:** `Y Up`
- **Apply Scalings:** `FBX All`
- **Armature ▸ Add Leaf Bones:** **off** — leaf bones confuse the Humanoid mapping
- **Bake Animation:** off
- Shape keys export by default — confirm they arrived on the Unity side

In Unity: reimport, confirm **Rig ▸ Animation Type = Humanoid**, and check the avatar bone mapping has no red entries. A changed skeleton sometimes needs `Configure` opened once to re-verify.

---

## 8. Test in-headset

`Build & Test` — local only, no upload slot consumed.

Stand in it with trackers on and pay attention to:

- **Knee bends** while crouching. Odd angles here mean the leg ratio is too low.
- **Hip position** — floating or sunk hips is the same symptom.
- **Reach.** Can you touch the floor, and reach things at normal world heights?
- **Eye height.** Does the world scale feel right, or oppressive?
- **Mirror check.** Does he read as young, or just small? These are different, and the difference is head size.

Iterate here. Pose changes are cheap right now.

---

## When it feels right

Save as `frennec_v03_proportioned.blend` and move to step 4 in [`frennec-to-kaarten.md`](frennec-to-kaarten.md) — the ears, which are zero-risk and the first change that'll make him look like Kaarten rather than a fennec.
