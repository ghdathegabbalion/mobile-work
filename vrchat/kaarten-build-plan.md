# Kaarten — VRChat avatar build plan

**Route:** full custom sculpt in Blender · **Body:** anthro, plantigrade
**Target:** match the quality bar of the kemono-samurai reference (toon-shaded anthro, modelled fur fringe, layered armour, PhysBone-driven accessories).

> Status: pipeline locked, character sheet not yet filled in. Fill §1 before starting Phase 1.

---

## 1. Character sheet — FILL THIS IN FIRST

Everything downstream keys off this. Nail it down before a single vertex moves; changing species or silhouette after retopo costs weeks.

| Field | Value |
|---|---|
| Species | _TBD_ |
| Build / height | _TBD_ (plantigrade — human leg structure, digit/paw feet) |
| Fur base colour | _TBD_ |
| Markings | _TBD_ |
| Eye colour | _TBD_ |
| Distinguishing features | _TBD_ (horns, scars, ear shape, tail type) |
| Outfit | _TBD_ |
| Expression / vibe | _TBD_ |

Existing references to pull from the PC: `C:\Users\GH-DA\ComfyUI-Shared\training\` — check for a Kaarten sheet alongside the Aster one.

---

## 2. What the reference quality actually consists of

Decomposed, so you know what you're chasing. None of it is one big secret — it's five separate things done competently.

- **Toon shading, not PBR.** lilToon with a soft two-step shadow ramp and a faint rim light. Attempting realistic PBR is what makes home-made avatars read as cheap.
- **Fur is geometry, not a shader.** Cheek fluff, chest ruff, wrist tufts, tail — modelled fringe: spiky edge loops on the silhouette plus a few alpha-tested cards where depth is needed. Fur shaders are a Quest-killer and look worse.
- **The face is painted, not modelled.** Eyeliner, blush, nose shading, freckles all live in the texture. The head mesh underneath is simple.
- **Layered hard-surface accessories** over a soft body — the read comes from the contrast. Armour is separate meshes with their own materials, not part of the body mesh.
- **Everything secondary moves.** Ears, tail, hair spikes, chest fluff, every hanging strap and bead on PhysBones. Motion is ~40% of the perceived quality.

---

## 3. Pipeline

### Phase 0 — Reference & design lock
- Assemble an orthographic-ish reference sheet: front, side, back, 3/4, face close-up, marking layout, outfit details.
- Generate variations through ComfyUI on the PC to explore before committing (SSH session only — no GPU in the cloud sandbox).
- Lock a front + side view at matched scale; these become Blender background images.
- **Exit criteria:** you can describe Kaarten's silhouette without looking at anything.

### Phase 1 — Block-out
- Human-proportion base (plantigrade means you can use standard humanoid proportions with a beast head, hands, feet, tail).
- Grey primitives only. Get proportion and silhouette right at this stage — it is essentially free to fix here and brutally expensive later.
- Check in first-person: an avatar is viewed from its own eyeline most of the time. Arm length and chest bulk read very differently in-headset.
- **Exit criteria:** silhouette reads as Kaarten from 20m at thumbnail size.

### Phase 2 — Sculpt
- Multires or Dyntopo, whichever you're comfortable with. Sculpt form, not detail — toon shading discards fine pores and wrinkles entirely.
- Sculpt the head separately from the body; it takes the most iteration.
- Fur fringe: sculpt the major clumps, treat as silhouette shapes rather than strands.
- **Exit criteria:** high-poly reads correctly with flat shading and no textures.

### Phase 3 — Retopo + UV
The phase that separates finished avatars from abandoned ones. Budget real time here.

- Target **~30–50k tris** for the body+head, leaving headroom for outfit and accessories under the 70k Good-rank ceiling.
- Quad topology. Edge loops around eyes, mouth, and every joint — blendshapes and deformation both depend on this.
- Denser where it deforms (face, shoulders, hips), sparse on flat armour plates.
- UV: separate islands per material zone. Give the face a generously large UV area — it carries the most painted detail. Keep texel density consistent everywhere else.
- Plan material slots now: **body / face / hair+fur / outfit / accessories** ≈ 5 slots. Atlas later if needed.
- **Exit criteria:** clean quads, no n-gons on deforming areas, UVs unwrapped with no visible stretching on a checker map.

### Phase 4 — Texture
- Substance Painter, or Blender texture-paint if you'd rather stay in one app.
- **2K per material** is plenty for toon. 4K only for the face if you want crisp eye detail.
- Bake AO from the high-poly, then paint over it — do not rely on AO alone for shading; the toon ramp handles that.
- Paint markings, face makeup, and fur direction hints into the albedo. Toon avatars live and die on albedo quality.
- Emission mask for any glowing parts (eyes, runes, trim).
- **Exit criteria:** looks correct under flat lighting in Blender, not just in a nice HDRI.

### Phase 5 — Rig
- Unity **Humanoid** rig — mandatory for VRChat. Rigify or a manual armature, but the final bone hierarchy must map to Humanoid: hips → spine → chest → neck → head, plus shoulders/arms and legs.
- **Eye bones** if you want eye tracking. **Jaw bone** optional (blendshape visemes are generally better).
- Tail, ears, hair, and accessory chains are *extra* bones outside the Humanoid map — they get PhysBones in Unity.
- Weight paint: joints, armpits, hips, and the neck seam are where it goes wrong. Test with extreme poses before you call it done.
- Keep the bone count reasonable (~150 total for Good rank).
- **Exit criteria:** no candy-wrapper twisting on a full arm rotation or a deep squat.

### Phase 6 — Blendshapes
- **15 visemes** (sil, PP, FF, TH, DD, kk, CH, SS, nn, RR, aa, E, ih, oh, ou) — non-negotiable for lip sync.
- Expression set: happy, angry, sad, surprised, smug, blink, wink, plus blush and fang toggles.
- **Face tracking (optional but it's a big part of that reference's expressiveness):** the ARKit set is ~52 shapes and roughly triples this phase's work. Decide now — retrofitting is painful. VRCFaceTracking handles the runtime side.
- Name shapes conventionally (`vrc.v_aa` style or the standard ARKit names) so tooling picks them up automatically.
- **Exit criteria:** every shape works in isolation *and* in combination without mesh tearing.

### Phase 7 — Unity + VRChat SDK
- **VRChat Creator Companion** manages the project and pins the Unity version (currently 2022.3.x — let VCC decide, don't pick manually).
- Import FBX → set rig to Humanoid → check the bone auto-map, fix anything red.
- **lilToon** on everything. Set up the shadow ramp once, then reuse the material as a template.
- **PhysBones** on ears, tail, hair, chest fluff, every strap and hanging accessory. Starting points: stiffness ~0.2, spring ~0.3, gravity light. Add colliders on chest and head so hair and tail don't clip through.
- Expression menu + parameters for toggles (outfit pieces, blush, accessories).
- Build & Test locally before uploading. Then upload as private, check it in-game, iterate.
- **Exit criteria:** it works in a real world, in a mirror, with someone else looking at it.

### Phase 8 — Optimise + Quest variant
- PC target: **Good** rank — roughly ≤70k tris, ≤8 material slots, ≤150 bones. The SDK build panel shows exact live numbers; trust that over any written list including this one.
- **d4rkAvatarOptimizer** for automatic mesh/material merging — often a whole rank for free.
- Quest/Android variant: a separate, stripped build — ~10k tris, **1 material**, `VRChat/Mobile/Toon` shader, most PhysBones removed. Plan for it from the start; retrofitting a Quest version is genuinely miserable.

---

## 4. Time & cost

| | |
|---|---|
| Realistic time, first custom avatar | 150–300 hrs |
| Where the time actually goes | retopo, weight painting, blendshapes — not sculpting |
| Software cost | £0 (Blender + Unity + VCC + lilToon all free) |
| Optional | Substance Painter subscription |

If that number is unwelcome: the kitbash route reaches ~85% of this quality in a couple of weeks. Worth reconsidering if the goal is "Kaarten in VRChat soon" rather than "I built Kaarten myself."

---

## 5. Gotchas that kill first avatars

1. **Sculpting detail that toon shading throws away.** Form only.
2. **Retopo with no deformation loops.** Discovered at weight-painting, fixed by redoing retopo.
3. **Skipping the Quest variant until the end.** Plan the low-poly pass from Phase 3.
4. **Scale.** Build to real-world scale in Blender (~1.6–1.8m). Wrong scale breaks IK, PhysBones, and every world's interactions.
5. **Not testing in first-person early.** Proportions that look right in the viewport can feel wrong in-headset.
6. **Face tracking decided late.** It's a Phase 6 fork, not a Phase 8 addition.
7. **One giant material.** Separate slots keep shading controllable; atlas at the *end*, with a tool.

---

## 6. Next actions

- [ ] Fill in §1 from the PC design references
- [ ] Decide: face tracking yes/no (forks Phase 6)
- [ ] Generate/collect the reference sheet — ComfyUI, SSH session
- [ ] Lock front + side orthos as Blender background images
- [ ] Start Phase 1 block-out
