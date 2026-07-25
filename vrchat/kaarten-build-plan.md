# Kaarten — VRChat avatar build plan

**Route:** full custom sculpt in Blender · **Body:** anthro, plantigrade
**Reference:** [`reference/kaarten-design-sheet.png`](reference/kaarten-design-sheet.png)
**Quality target:** the kemono-samurai reference video — toon-shaded anthro, modelled fur fringe, layered armour, PhysBone-driven accessories.
**Platform:** PC (primary) + Quest/Android variant
**Tracking:** Valve Index — full-body tracking, plus face tracking via add-on

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

**Kaarten is a significantly harder build than the reference video**, and the tracking requirements push him further again.

The video's wolf is a body, a head, fur fringe, and armour plates. Kaarten adds five things that are each independently among the hardest parts of avatar work:

1. **A full cape** — cloth sim doesn't exist in VRChat. Capes are a PhysBone bone-grid, and they are notorious for folding inside out, clipping through legs, and eating the entire physics budget.
2. **A long feathered tail** — heavy, layered, translucent. Layered transparency is the worst case for both performance and sorting artefacts.
3. **Wings** — extra bones outside the Humanoid map, attaching cleanly *under* the shoulder armour without clipping on arm raise.
4. **A rainbow mane with ornaments** — heavy silhouette geometry, plus gems and flowers that all want to move.
5. **Gem-and-filigree armour** — dozens of small hard-surface details, needing MatCap to read under toon shading.

On top of that:

6. **Face tracking** — a full expression shape set, a modelled mouth interior, and a parameter-budget problem (§6).
7. **Full-body tracking on a 138 cm stout body** — the proportions that make Kaarten characterful are the ones that make FBT IK misbehave (§7).
8. **A Quest variant** — a second, heavily stripped build.

Realistic estimate for **this** design with **these** requirements, as a first custom avatar: **350–500 hours**. That is a genuinely large project — several months of evenings.

None of that is a reason not to do it. It *is* a reason to build in the order below, decide the face-tracking shape set before Phase 3, and hold the performance budget from Phase 3 onward rather than discovering it at upload.

---

## 3. What the reference quality actually consists of

- **Toon shading, not PBR.** lilToon with a soft two-step shadow ramp and faint rim light. Attempting realistic PBR is what makes home-made avatars read as cheap.
- **Fur is geometry, not a shader.** Modelled fringe: spiky edge loops on the silhouette plus alpha cards where depth is needed.
- **The face is painted, not modelled.** Eye lining, blush, nose shading, freckles all live in the texture.
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

Tight. The mane and tail feathers will try to run away from you. Note the head budget now also has to cover a **modelled mouth interior** (§6) — teeth, tongue, inner cheeks.

### Material slots (8)

1. Body fur + face (atlas together)
2. Mane + tail feathers (cutout alpha)
3. Wing membrane
4. Gold metal + gems (MatCap, shared emission mask)
5. Cloth — cape panels + velvet lining
6. Leather — belts, pouches, straps
7. Tail scales
8. Eyes

Slot 7 can fold into 1 if the UV layout allows. Atlas at the *end*, with a tool.

---

## 5. Kaarten-specific solutions

### The cape
The biggest single risk in this build — and FBT makes it worse, because your legs actually move.
- Bone grid, roughly **5 columns × 3–4 rows**.
- **One PhysBone component on the cape root**, not one per column. Components and transforms are budgeted separately; a single component covering all child chains is dramatically cheaper.
- Colliders on hips and both upper legs — mandatory with FBT.
- Rotation limits, or it folds inside out the first time you crouch.
- Fur trim rides the cape bones — no separate chains.

### The tail
- Heavy and long: low stiffness, higher inertia, some gravity. Weighty, not whip-like.
- **Feathers ride the tail bones rigidly.** Only the last few tip feathers get their own short chains.
- The scale-to-feather transition lives in the texture and silhouette, not in a second material.

### Transparency (feathers + wing membrane)
- Use **cutout / alpha-to-coverage** in lilToon for the feathers, not alpha-blend. Blend mode causes visible sorting artefacts wherever layered feathers overlap — constantly, on this tail.
- Reserve true alpha-blend for the wing membrane, where layering is shallow.

### Gold, gems, and glow
- Gold filigree = **MatCap** plus a normal map. Not PBR metallic — metallic reads muddy grey under a toon ramp.
- Gems = MatCap with a hard highlight and slight emission.
- Chest gem = emission mask, **and bake a soft glow into the albedo** — worlds control post-processing, so bloom isn't guaranteed.
- Worn metal edges: paint into albedo.

### The checker pattern
Axis-aligned UV islands, generous texel density. Warped UVs make the checks wobble — instantly visible.

### The wings
- 2–3 bones per wing is plenty.
- Model the attachment point *after* the pauldrons exist; test a full arm raise for clipping before committing weights.
- Consider driving them from an animation toggle rather than PhysBones — more control, less budget.

### The mane
- **One texture carries the whole rainbow.** Not eight materials for eight colours.
- Ornaments are part of the mane mesh, riding mane bones.
- Silhouette clumps only — don't model strands.

---

## 6. Face tracking & the expression rig

You asked for moving eyes, eyelids, mouth, and ears. Here's what each actually needs, and the hardware reality.

### Hardware reality on Index — read this first

| Feature | On your Index | Notes |
|---|---|---|
| **Mouth / jaw / tongue tracking** | ✅ with **Vive Facial Tracker** | USB add-on that clips to the front of the Index. This is the one that gives you real mouth tracking. |
| **Eye tracking** | ❌ not available | The Index has no native eye tracking, and the aftermarket add-on (Droolon Pi1) is discontinued and was never reliable. |
| **Eye movement anyway** | ✅ built-in | VRChat's **Eye Look** moves eyes and blinks procedurally with no hardware at all. |
| **Full-body tracking** | ✅ | Vive or Tundra trackers + base stations. |

So: **your eyes will move, and your eyelids will blink, but they won't follow your real gaze.** Everything else — jaw, lips, tongue, cheeks — tracks for real with the Facial Tracker.

**Build the eye bones and the full eye shape set regardless.** If you later move to a Bigscreen Beyond 2e or Quest Pro, real eye tracking then works with zero rework. Skipping them now means redoing Phase 6 later.

### What to author

Author the **Unified Expressions** set (the VRCFaceTracking standard, ~60+ shapes). VRCFaceTracking maps whatever hardware you own onto it, so one shape set serves the Facial Tracker now and better hardware later. If that's too much, **ARKit's 52** is the acceptable floor and Unified maps down from it.

Layers, in build order:

1. **Visemes — 15 shapes** (sil, PP, FF, TH, DD, kk, CH, SS, nn, RR, aa, E, ih, oh, ou). Mic-driven lip sync. Required, works on every platform including Quest. Build these first — they're the fallback when tracking is off.
2. **Eye Look** — eye bones (left/right) plus blink shapes. Procedural look-at and blinking. Configured on the avatar descriptor, not the animator.
3. **Expressions** — happy, angry, sad, surprised, smug, wink, blush, fangs. Hand-gesture driven.
4. **Unified Expressions / ARKit** — the real face tracking layer. Brows, cheeks, individual lip shapes, jaw, tongue.

### The mouth interior — don't skip this

Real jaw tracking opens the mouth properly, which means **the inside of the mouth is now visible**. You need modelled teeth, tongue, and inner cheeks. Most first-time face-tracking avatars forget this and end up with a hole in the head on camera. Budget geometry for it in Phase 3.

The Vive Facial Tracker also tracks **tongue** — so the tongue needs to be a real, riggable object, not a flat card.

### The parameter budget — the non-obvious constraint

VRChat caps expression parameters at **256 bits per avatar**. A naive face-tracking setup blows straight through this before you've added a single outfit toggle.

The fix is **binary parameter encoding** — packing float parameters into bit sets. Don't hand-roll it: use a face-tracking template (VRCFury or one of the community FT setup packages) that handles the encoding. Verify the total in the SDK panel, not by counting manually.

This matters for Kaarten specifically because he also wants toggles for the cape, wings, and ornaments. Face tracking plus outfit toggles is exactly the combination that hits the ceiling.

### Blendshape mesh constraint — affects Phase 3

The avatar descriptor picks **one skinned mesh** for visemes and eyelids. Keep every face shape — visemes, blinks, expressions, and the FT set — on **one mesh**. If you split the head into its own object from the body, all the face shapes must live on whichever mesh the descriptor points at.

Decide the mesh split in Phase 3, before retopo, not after. Fixing it later means re-authoring shapes.

### Ears

Two options, and you can have both:
- **PhysBones** — passive wobble as you move. Cheap, always-on, good default.
- **Expression-driven** — blendshapes or bone animations for deliberate ear positions (perked, flattened, angry). Genuinely expressive on a feline character and worth the small extra cost.

Recommend physics as the base with 2–3 expression poses layered on top.

---

## 7. Full-body tracking on a 138 cm stout body

FBT and Kaarten's proportions are in direct tension. Worth understanding before Phase 1, because it constrains the block-out.

- **VRChat's IK maps your real proportions onto the avatar.** You're presumably not 138 cm with a 4'6" stout build, so every offset is large. Short avatars with tall users produce odd knee bends and floating-hip artefacts.
- **Don't over-stylise the leg-to-torso ratio.** Stout and thick-limbed is fine. Very short legs relative to torso is where FBT IK visibly breaks. Keep leg length within a plausible fraction of total height even while the limbs are chunky.
- **Hip bone placement is critical** — more so than for desktop or 3-point. Get it anatomically sensible, centred, at true hip height.
- **Clean T-pose and correct bone rolls.** FBT amplifies every rigging sloppiness.
- **Thick limbs deform worse than thin ones.** Elbows, knees, shoulders and hips need extra weight-painting attention, and possibly corrective blendshapes driven by joint angle.
- **Test with your trackers during Phase 5**, not at upload. Rig problems found in FBT are cheap to fix before weights are final and expensive after.
- VRChat's avatar scaling lets users rescale at runtime, but the authored default height is what calibration works from — build at true 138 cm.

---

## 8. Pipeline

### Phase 0 — Reference prep
- Design sheet is done and 3D-ready. Extract front/side panels, scale-matched, for Blender backgrounds.
- Generate extra angles through ComfyUI on the PC (SSH session only — no GPU in the cloud sandbox).
- **Exit:** front + side in Blender at true 138 cm scale.

### Phase 1 — Block-out
- Grey primitives. Short stout proportions, broad chest, thick limbs, large paws — within the FBT constraints in §7.
- Block cape, wings, and tail as crude shapes; silhouette is most of this character.
- Check in first-person early. Proportions lie in the viewport, especially at 138 cm.
- **Exit:** silhouette reads as Kaarten at thumbnail size; leg ratio sane for FBT.

### Phase 2 — Sculpt
- Form only. Toon shading discards pores and fine wrinkles.
- Head separately — it takes the most iteration, and it now carries the face rig.
- **Exit:** high-poly reads correctly flat-shaded, untextured.

### Phase 3 — Retopo + UV
The make-or-break phase, and now it carries the face-tracking constraints too.
- Hold §4 tri budgets. Quads. Edge loops around eyes, mouth, and every joint.
- **Dense, deliberate topology around the mouth and eyes** — face tracking demands far more than visemes alone. Concentric loops around the lips, loops around each eye.
- **Model the mouth interior**: teeth, riggable tongue, inner cheeks.
- **Fix the mesh split now** so all face shapes land on one skinned mesh (§6).
- Generous UV for the face; axis-aligned islands for checker panels; consistent texel density.
- **Plan the Quest decimation now** — know what collapses and how.
- **Exit:** clean quads, mouth interior exists, face loops support FT, no stretching on a checker map.

### Phase 4 — Texture
- 2K per material; 4K for the face if you want crisp eyes.
- Bake AO from high-poly, paint over it. The toon ramp does the shading.
- Paint markings, freckles, worn metal edges, baked gem glow into albedo.
- Emission mask for the chest gem and glowing accents.
- **Exit:** correct under flat lighting, not just a flattering HDRI.

### Phase 5 — Rig
- Unity **Humanoid** — mandatory. Hips → spine → chest → neck → head, plus shoulders/arms/legs.
- **Eye bones — build them** even though the Index can't drive them yet (§6).
- Jaw bone optional; blendshape visemes are better, and the FT set supersedes it.
- Extra chains: mane, horns (static), wings, tail, cape grid, ears.
- Watch bone count against ~150 for Good rank — the cape grid alone is 15–20.
- **Test in FBT with your trackers before finalising weights** (§7).
- **Exit:** no candy-wrapper twisting on full arm rotation or a deep squat; clean deformation in FBT.

### Phase 6 — Blendshapes
The phase your tracking requirements have tripled. Build in the layer order from §6.
- 15 visemes first — the always-works fallback.
- Blinks and eye shapes second.
- Gesture expressions third.
- Unified Expressions / ARKit set last.
- Name shapes **exactly** to the standard so tooling auto-maps them.
- Every shape must work alone *and* in combination — corrective shapes for bad combos.
- **Exit:** full set drives cleanly from VRCFaceTracking with no tearing on combined shapes.

### Phase 7 — Unity + VRChat SDK
- **VRChat Creator Companion** manages the project and pins Unity (currently 2022.3.x — let VCC decide).
- FBX → Humanoid → verify the bone auto-map.
- lilToon everywhere; shadow ramp once, reused. MatCap for metal and gems.
- PhysBones per §5. Colliders on hips, legs, chest.
- **VRCFaceTracking + a template that handles binary parameter encoding** (§6). Check the parameter total in the SDK panel.
- Expression menu: cape, wings, ornaments, ear poses.
- Set View Position to eye height (~128 cm).
- Build & Test locally, then upload private and iterate in-game with trackers on.
- **Exit:** works in a real world, in a mirror, in FBT, with someone else looking at it.

### Phase 8 — Optimise + Quest
- **d4rkAvatarOptimizer** for mesh/material merging — often a free rank. Watch blendshape handling when merging.
- Quest/Android: separate stripped build — ~10k tris, **1 material**, `VRChat/Mobile/Toon`, most PhysBones gone.
- **Face tracking is PC-only.** The Quest build keeps visemes and Eye Look; the FT layer simply isn't there. That's expected, not a bug.

**Be realistic about the Quest version.** At 10k tris and one material, Kaarten becomes: cape as a simple 3–4 bone skirt, wings as flat baked cards, tail feathers as a handful of cards, mane as solid geometry, gems and filigree painted flat into one atlas. It reads as a simplified version of the character, not the same model. Every complex avatar on Quest looks like this. Treat it as its own deliverable.

---

## 9. Time & cost

| | |
|---|---|
| Realistic time, this design + face tracking + FBT + Quest | **350–500 hrs** |
| Where the time goes | retopo, weight painting, the cape, the FT blendshape set |
| Software cost | £0 — Blender, Unity, VCC, lilToon, VRCFaceTracking all free |
| Hardware needed | **Vive Facial Tracker** for mouth tracking; trackers + base stations for FBT |
| Optional | Substance Painter subscription |

---

## 10. Gotchas that kill first avatars

1. **Sculpting detail that toon shading discards.** Form only.
2. **Retopo with no deformation loops** — and, for FT, no mouth/eye loops.
3. **Forgetting the mouth interior.** Jaw tracking opens the mouth; there needs to be something inside it.
4. **Splitting the head mesh after authoring shapes.** Decide the mesh split in Phase 3.
5. **Blowing the 256-bit parameter budget.** Use binary encoding via a template.
6. **The cape without colliders or rotation limits.** It will fold through his legs — worse in FBT.
7. **Per-column PhysBone components on the cape.** One component on the root.
8. **Alpha-blend on layered feathers.** Sorting artefacts. Use cutout.
9. **PBR metallic for the gold.** Muddy grey under toon. MatCap.
10. **Over-stylised leg-to-torso ratio.** FBT IK breaks visibly.
11. **Wrong scale.** Build at 138 cm; View Position at eye height.
12. **Skipping eye bones** because the Index can't drive them. Build them for the upgrade path.
13. **Warped UVs under the checker pattern.** Instantly visible.

---

## 11. Next actions

- [ ] Confirm whether you have the **Vive Facial Tracker** — without it, mouth tracking isn't possible on Index
- [ ] Choose the shape set: **Unified Expressions** (recommended) or ARKit 52
- [ ] Extract front/side ortho panels from the design sheet as Blender backgrounds
- [ ] Start Phase 1 block-out at true 138 cm scale, checking the FBT leg-ratio constraint
- [ ] Test short-stature proportions in-headset, in FBT, before leaving block-out
