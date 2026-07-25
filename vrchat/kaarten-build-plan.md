# Kaarten — VRChat avatar build plan

**Route:** full custom sculpt in Blender · **Body:** anthro, plantigrade
**Reference:** [`reference/kaarten-design-sheet.png`](reference/kaarten-design-sheet.png)
**Quality target:** the kemono-samurai reference video — toon-shaded anthro, modelled fur fringe, layered armour, PhysBone-driven accessories.

---

## 1. Character spec

From the design sheet.

| Field | Value |
|---|---|
| Species | Lion (feline) / Dragonborn |
| Role | Noble Champion / Guardian |
| Height | **138 cm (4'6")** — short, against a 180 cm human reference |
| Build | Short, stout, muscular — broad chest, thick limbs, large hands/feet |
| Personality | Bold, loyal, charismatic |
| Fur | Tan base, cream accent. Short on body, longer at trim |
| Mane | Full rainbow — red, orange, yellow, green, blue, purple, magenta, cyan — with flower and gem ornaments |
| Eyes | Green, freckled muzzle |
| Horns | Two, dark, curving back |
| Wings | Small, structured, red membrane; attach at upper back **under** the shoulder armour |
| Tail | Long and heavy — dragon scales at the base transitioning to layered rainbow feathers, slightly translucent |
| Chest gem | Large green heart-cut gem in a gold setting, emits a soft green glow |
| Armour | Gold filigree, black/white checker panels, purple/blue/red accent gems |
| Cape | Woven panels with gold embroidery, red velvet lining, white fur trim |
| Boots/paws | Large lion paws, gold-and-gem bracers, leather straps |

**Symmetry:** gem placement is symmetrical unless the sheet says otherwise.
**Metals:** all gold with filigree, edges slightly worn.

The sheet's front/side/back panels work as Blender background images — but they're illustrated, not true orthographic. There's mild perspective in them. Use them for proportion and placement, not as a vertex-snapping ground truth.

---

## 2. Scope reality check — read this before Phase 0

**Kaarten is a significantly harder build than the reference video.** That wolf is a body, a head, some fur fringe, and hard-surface armour plates. Kaarten adds five things that are each independently among the hardest parts of avatar work:

1. **A full cape** — cloth sim doesn't exist in VRChat. Capes are a PhysBone bone-grid, and they are notorious for folding inside out, clipping through legs, and eating your entire physics budget.
2. **A long feathered tail** — heavy, layered, translucent. Layered transparency is the single worst thing for VRChat performance and has real sorting artefacts.
3. **Wings** — extra bones outside the Humanoid map, and they have to attach cleanly *under* the shoulder armour without clipping during arm movement.
4. **A rainbow mane with ornaments** — lots of silhouette geometry, plus gems and flowers that all want to move.
5. **Heavy gem-and-filigree armour** — many small hard-surface details, and gems/metal need MatCap treatment to read correctly under toon shading.

Every one of those is a "this is where people quit" item, and Kaarten has all five. Realistic first-avatar estimate for **this** design: **250–400 hours**, not the 150–300 from the generic plan.

None of that is a reason not to do it. It *is* a reason to build in the order below and to hold the performance budget from Phase 3 onward rather than discovering it at upload.

---

## 3. What the reference quality actually consists of

Decomposed, so you know what you're chasing. Five separate things done competently — no single secret.

- **Toon shading, not PBR.** lilToon with a soft two-step shadow ramp and faint rim light. Attempting realistic PBR is what makes home-made avatars read as cheap.
- **Fur is geometry, not a shader.** Modelled fringe: spiky edge loops on the silhouette plus alpha cards where depth is needed. Fur shaders are a Quest-killer and look worse.
- **The face is painted, not modelled.** Eye lining, blush, nose shading, freckles all live in the texture. The mesh underneath is simple.
- **Layered hard-surface over soft body** — the read comes from the contrast.
- **Everything secondary moves.** Motion is ~40% of perceived quality.

---

## 4. Budgets — hold these from Phase 3

Targeting **Good** rank on PC (~70k tris, ~8 material slots, ~150 bones). The SDK build panel gives exact live numbers — trust it over this table.

### Triangles

| Component | Budget |
|---|---:|
| Head + horns + mane | 16k |
| Body + paws | 14k |
| Armour, bracers, belt, boots | 16k |
| Tail (scales + feathers) | 10k |
| Cape | 8k |
| Wings | 5k |
| **Total** | **~69k** |

That's tight. The mane and the tail feathers are the two that will try to run away from you.

### Material slots (8)

1. Body fur + face (atlas together)
2. Mane + tail feathers (cutout alpha)
3. Wing membrane
4. Gold metal + gems (MatCap, shared emission mask)
5. Cloth — cape panels + velvet lining
6. Leather — belts, pouches, straps
7. Tail scales
8. Eyes

Slot 7 can fold into 1 if the UV layout allows. Atlas at the *end*, with a tool — not by hand while modelling.

---

## 5. Kaarten-specific solutions

The design decisions that aren't in a generic tutorial.

### The cape
The biggest single risk in this build.
- Bone grid, roughly **5 columns × 3–4 rows**. More rows = smoother motion and more cost.
- **One PhysBone component on the cape root**, not one per column. Components and transforms are budgeted separately — a single component covering all child chains is dramatically cheaper than five.
- Colliders on hips and both upper legs, or it will pass straight through them.
- Set rotation limits. Without them the cape folds inside out the first time you crouch.
- The fur trim rides the cape's bones — don't give it its own chains.

### The tail
- Heavy and long: low stiffness, higher inertia, a bit of gravity. It should feel weighty, not whip-like.
- **Feathers ride the tail bones rigidly.** Only the last few tip feathers get their own short chains. Individually simulating layered feathers will end the physics budget on its own.
- Scale-to-feather transition happens in the texture and in the geometry silhouette, not in the material — keep it one material.

### Transparency (feathers + wing membrane)
- The sheet says "slightly translucent." Use **cutout / alpha-to-coverage** in lilToon, not alpha-blend, for the feathers. Blend mode causes visible sorting artefacts when layered feathers overlap — which is constantly, on a feathered tail.
- Reserve true alpha-blend for the wing membrane only, where the layering is shallow.

### Gold, gems, and glow
- Gold filigree = **MatCap** in lilToon plus a normal map. Not PBR metallic — metallic workflows read as muddy grey under a toon ramp.
- Gems = MatCap with a hard highlight and slight emission. "Cut, high clarity, saturated" is a MatCap job.
- Chest gem glow = emission mask. **Bake a soft glow into the albedo too** — VRChat worlds control post-processing, so bloom isn't guaranteed and the gem will look flat in worlds without it.
- Worn metal edges: paint into the albedo, cheap and effective.

### The checker pattern
Put the checker panels on **straight, axis-aligned UV islands** with generous texel density. Warped UVs make the checks wobble, which is instantly visible and reads as amateur.

### The wings
- Small and structured — 2–3 bones per wing is plenty.
- They attach under the shoulder armour: model the attachment point *after* the pauldrons exist, and test a full arm raise for clipping before committing weights.
- Consider driving them from an animation toggle rather than PhysBones — more control, less budget.

### The mane
- One texture carries the whole rainbow gradient. **Do not** use eight materials for eight colours.
- Ornaments (flowers, gems) are part of the mane mesh, riding mane bones. Not separate objects.
- Silhouette clumps only — resist modelling strands.

### Short, stout proportions
- **Build at true 138 cm scale in Blender.** Wrong scale breaks IK, PhysBones, and world interactions.
- Set **View Position** to actual eye height (~128 cm), not the default.
- Short avatars have real reach limitations in worlds, and full-body tracking calibration is fussier. Worth testing early with whatever tracking setup you use.
- Thick limbs deform worse than thin ones — elbows, knees, and shoulders need extra weight-painting attention on this build specifically.

---

## 6. Pipeline

### Phase 0 — Reference prep
- Design sheet is done and 3D-ready. Extract the front/side panels as separate images, scale-matched, for Blender backgrounds.
- Generate any additional angles you want through ComfyUI on the PC (SSH session only — no GPU in the cloud sandbox).
- **Exit:** front + side loaded in Blender at correct 138 cm scale.

### Phase 1 — Block-out
- Grey primitives. Short stout proportions, broad chest, thick limbs, large paws.
- Block the cape, wings, and tail as crude shapes too — silhouette is most of this character.
- Check in first-person early; proportions lie in the viewport, especially at 138 cm.
- **Exit:** silhouette reads as Kaarten at thumbnail size.

### Phase 2 — Sculpt
- Form only. Toon shading discards pores and fine wrinkles entirely.
- Head separately from body — it takes the most iteration.
- Mane and tail: sculpt major clumps as silhouette shapes.
- **Exit:** high-poly reads correctly flat-shaded, untextured.

### Phase 3 — Retopo + UV
The make-or-break phase. Budget real time.
- Hold the §4 tri budgets. Quads. Edge loops around eyes, mouth, and every joint.
- Denser where it deforms, sparse on flat armour plates.
- Generous UV area for the face; axis-aligned islands for the checker panels; consistent texel density elsewhere.
- **Plan the Quest decimation now** — know which parts collapse and how.
- **Exit:** clean quads, no n-gons on deforming areas, no stretching on a checker map.

### Phase 4 — Texture
- 2K per material. 4K for the face only if you want crisp eye detail.
- Bake AO from the high-poly, paint over it. The toon ramp does the shading, not the AO.
- Paint markings, freckles, face detail, worn metal edges, and the baked gem glow into albedo.
- Emission mask for the chest gem and any glowing accents.
- **Exit:** correct under flat lighting, not just a flattering HDRI.

### Phase 5 — Rig
- Unity **Humanoid** — mandatory. Hips → spine → chest → neck → head, plus shoulders/arms/legs.
- Eye bones for eye tracking. Jaw bone optional (blendshape visemes are better).
- Extra chains outside the Humanoid map: mane, horns (static), wings, tail, cape grid, ear.
- Watch total bone count against ~150 for Good rank — the cape grid alone is 15–20.
- **Exit:** no candy-wrapper twisting on full arm rotation or a deep squat, with thick limbs.

### Phase 6 — Blendshapes
- **15 visemes** (sil, PP, FF, TH, DD, kk, CH, SS, nn, RR, aa, E, ih, oh, ou) — non-negotiable.
- Expressions: happy, angry, sad, surprised, smug, blink, wink, plus blush and fang toggles.
- **Face tracking decision goes here.** ARKit is ~52 shapes and roughly triples this phase. Decide before starting — retrofitting is genuinely miserable.
- **Exit:** every shape works alone *and* in combination without tearing.

### Phase 7 — Unity + VRChat SDK
- **VRChat Creator Companion** manages the project and pins Unity (currently 2022.3.x — let VCC decide).
- FBX → Humanoid → verify the bone auto-map.
- lilToon everywhere. Build the shadow ramp once, reuse as a template. MatCap setup for metal and gems.
- PhysBones per §5. Colliders on hips, legs, chest.
- Expression menu for toggles — cape on/off, wings on/off, ornaments.
- Set View Position to eye height. Build & Test locally, then upload private and iterate in-game.
- **Exit:** works in a real world, in a mirror, with someone else looking at it.

### Phase 8 — Optimise + Quest
- **d4rkAvatarOptimizer** for mesh/material merging — often a free rank.
- Quest/Android: a separate stripped build — ~10k tris, **1 material**, `VRChat/Mobile/Toon`, most PhysBones gone.

**Be realistic about the Quest version.** At 10k tris and one material, Kaarten becomes: cape as a simple 3–4 bone skirt, wings as flat baked cards, tail feathers as a handful of cards, mane as solid geometry, all gems and filigree painted flat into a single atlas. It will read as a simplified version of the character, not the same model. That's normal and unavoidable — every complex avatar on Quest looks like this. Plan it as its own deliverable rather than a downgrade you do grudgingly at the end.

---

## 7. Time & cost

| | |
|---|---|
| Realistic time, this design, first custom avatar | **250–400 hrs** |
| Where the time goes | retopo, weight painting, the cape, blendshapes |
| Software cost | £0 — Blender, Unity, VCC, lilToon all free |
| Optional | Substance Painter subscription |

---

## 8. Gotchas that kill first avatars

1. **Sculpting detail that toon shading discards.** Form only.
2. **Retopo with no deformation loops.** Found at weight-painting, fixed by redoing retopo.
3. **The cape without colliders or rotation limits.** It will fold through his legs.
4. **Per-column PhysBone components on the cape.** One component on the root instead.
5. **Alpha-blend on layered feathers.** Sorting artefacts. Use cutout.
6. **PBR metallic for the gold.** Muddy grey under toon. MatCap.
7. **Wrong scale.** Build at 138 cm; set View Position to eye height.
8. **Skipping the Quest plan until the end.** Decide the decimation at Phase 3.
9. **Face tracking decided late.** Phase 6 fork, not a Phase 8 addition.
10. **Warped UVs under the checker pattern.** Instantly visible.

---

## 9. Next actions

- [ ] Decide: face tracking yes/no — forks Phase 6
- [ ] Extract front/side ortho panels from the design sheet as Blender backgrounds
- [ ] Start Phase 1 block-out at true 138 cm scale
- [ ] Test short-stature proportions in-headset before leaving block-out
