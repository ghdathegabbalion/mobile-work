# Kaarten — fast path

**Companion to [`kaarten-build-plan.md`](kaarten-build-plan.md).** That document is the reference — full detail, every constraint. This one is the plan you actually work to.

**Target: ~150 hrs instead of 350–500, with Kaarten in VRChat and usable at ~30.**

Nothing here compromises the end result. It removes work that doesn't show up in the final avatar.

---

## The correction that matters most

Earlier I offered you "kitbash a bought base" versus "full custom sculpt," and you picked custom. Fair — but I set up a false choice, and it cost about 150 hours on the estimate.

**Starting from a base mesh is not kitbashing.** They're different things:

| | What it is | Result |
|---|---|---|
| **Kitbash** | Take someone's finished avatar, retexture it, swap parts | Someone else's character wearing your colours |
| **Base mesh** | Take clean topology as a *starting armature*, sculpt your own character onto it | **Your character** — you shaped every form |

The second is how professional character artists work. Nobody derives human topology from scratch every time; it's solved geometry. You sculpt Kaarten's muzzle, his stout build, his paws, his silhouette — you just don't re-invent where the edge loops go around an elbow.

The result is fully Kaarten. What you skip is Phase 3 — retopology — which is the single largest time sink and the number one place first avatars die.

---

## Lever 1 — Start from a face-tracking-ready anthro base

**Saves ~100–150 hrs.** By far the biggest lever, because a good base arrives with all of this already done:

- Clean quad topology with deformation loops
- UVs laid out
- Humanoid rig, FBT-ready
- 15 visemes
- **ARKit / Unified Expressions face shapes**
- Often a modelled mouth interior with teeth and tongue

That last group is Phase 6 — the phase face tracking tripled. Inheriting it is the difference between authoring 100+ blendshapes from zero and correcting a set that already works.

### The technique that makes it work

**If you don't change topology, shape keys survive.**

Sculpt Kaarten's form by *moving the existing vertices* — no adding, deleting, or re-flowing loops — and every blendshape, weight, and UV comes along. You can take a generic anthro base to 138 cm, stout, broad-chested, lion-muzzled, and the whole face rig still works.

Practical rules:
- Use sculpt brushes in **Elastic Deform / Grab / Snake Hook** mode. Avoid Dyntopo and Remesh on the head — both destroy topology.
- Add geometry only where it's genuinely new (horns, mane, wings, tail, armour) as **separate objects**.
- Expect to *correct* the face shapes after reshaping the muzzle, not re-author them. Budget ~15–25 hrs for that, versus ~80–120 authoring from scratch.

### Choosing a base

Requirements, in priority order:

1. **Ships Blender source (`.blend` or FBX), not a Unity package only.** Non-negotiable — you can't sculpt on a Unity prefab.
2. **Ships ARKit or Unified Expressions shapes.** This is the whole point.
3. **Anthro, plantigrade, quad topology.**
4. **Licence permits heavy modification.** You're not redistributing — you're uploading your own avatar — but check that editing and public upload are allowed.

[**Frennec**](https://nattbat.gumroad.com/l/frennec) is a free furry base with a full-body rig, ARKit face tracking, visemes and expressions — worth evaluating first precisely because it costs nothing to try. If its proportions fight the short stout build, a paid base in the £20–50 range is still trivially worth it against 100+ hours.

Evaluate two or three before committing. An afternoon spent choosing well saves weeks.

---

## Lever 2 — Box-model the armour, don't sculpt it

**Saves ~20–30 hrs.**

Sculpt-then-retopo is the right workflow for organic form. It's wasted on hard surface. Kaarten's armour, bracers, boots, horns and chest gem setting should be **modelled directly to final topology** — box modelling, bevels, mirror modifier.

Sculpting a gold pauldron and then retopologising it produces exactly the same mesh you'd have box-modelled in a third of the time.

---

## Lever 3 — Texture it, don't model it

**Saves ~30–50 hrs, and rescues the triangle budget.**

The design sheet is dense with detail that must *read* but doesn't need geometry:

| Detail | Do this | Not this |
|---|---|---|
| Gold filigree | Normal map + MatCap | Modelled scrollwork |
| Checker panels | Texture on flat UVs | Modelled inlay |
| Small accent gems | Texture + MatCap highlight | Individual cut gems |
| Tail scales | Tiling texture on a smooth tail | Modelled overlapping scales |
| Embroidery on cape | Texture | Geometry |
| Fur texture | Texture, with fringe geometry only at the silhouette | Modelled fur |

**Trim sheets** are the multiplier here: author one gold-filigree strip texture, reuse it across every armour piece, bracer and boot. One texture, one UV strategy, a dozen pieces.

Only the **chest gem** earns real geometry — it's the character's focal point.

---

## Lever 4 — Let tooling build the Unity side

**Saves ~25–40 hrs.**

Do not hand-build animator layers or hand-encode parameters.

- [**VRCFury**](https://vrcfury.com) — non-destructive prefab-based setup. Toggles, PhysBones, menus without touching an animator state machine.
- [**Adjerry91's VRCFaceTracking Templates**](https://github.com/Adjerry91/VRCFaceTracking-Templates) — VRCFury/Modular Avatar prefabs that wire VRCFT's OSC straight to your blendshapes, **including the binary parameter encoding** that solves the 256-bit ceiling. Reported setup time is around **2 hours** against several days by hand.
- [**Haï~ FaceTra Shape Creator**](https://docs.hai-vr.dev/docs/changelogs/facetra-shape-creator) — helps generate and fix face tracking shapes.
- [**d4rkAvatarOptimizer**](https://github.com/d4rkc0d3r/d4rkAvatarOptimizer) — automatic mesh/material merging at the end.

The 256-bit parameter problem I flagged? Jerry's templates solve it. Don't solve it yourself.

---

## Lever 5 — Ship in milestones

**Saves nothing directly. Saves the project.**

The failure mode for a 350-hour build is 200 hours in, nothing usable, motivation gone. Milestones also surface rig and proportion problems *before* you've built forty hours of armour on a broken foundation.

| Milestone | What exists | Hrs | Cumulative |
|---|---|---:|---:|
| **v0.1 — In game** | Base reproportioned to 138 cm stout, Kaarten's colours, uploaded, FT + FBT working | 30 | 30 |
| **v1 — Recognisably Kaarten** | Muzzle sculpted, mane, horns, tail, paws, eyes, face textured | 40 | 70 |
| **v2 — Dressed** | Armour, bracers, boots, belt, chest gem | 35 | 105 |
| **v3 — Complete** | Cape, wings, ornaments, polish pass | 30 | 135 |
| **v4 — Quest** | Automated optimisation pass, stripped variant | 15 | 150 |

**You're in VRChat as a recognisable Kaarten at ~70 hrs**, with everything after that an upgrade to an avatar you're already wearing.

Build the cape last deliberately — it's the highest-risk item and the easiest to descope if you're tired of the project by then.

---

## What NOT to cut

Cutting these creates more work than it saves.

- **The mouth interior.** Jaw tracking opens the mouth. Skipping teeth and tongue means visible holes and a re-sculpt.
- **Eye bones and eye shapes.** With EyeTrackVR they're fully driven. Retrofitting is a Phase 6 redo.
- **Deformation weights at elbows, knees, shoulders, hips.** Thick limbs deform badly and FBT exposes it constantly.
- **FBT proportion sanity.** Leg-to-torso ratio has to stay plausible. Discovered late, this is a re-rig.
- **Testing in-headset each milestone.** The single cheapest bug-catching habit available.

---

## Revised estimate

| | Original | Fast path |
|---|---:|---:|
| Sculpt + retopo + UV + rig | 150 | 35 |
| Blendshapes / face tracking | 90 | 25 |
| Armour, props, texturing | 90 | 55 |
| Unity, FT wiring, PhysBones | 50 | 20 |
| Quest variant | 30 | 15 |
| **Total** | **~410** | **~150** |

Roughly a **third of the original**, for the same finished avatar.

---

## Start here

1. Download [Frennec](https://nattbat.gumroad.com/l/frennec) and two other candidate bases. Open each in Blender. Confirm: `.blend` source, ARKit/Unified shapes present, clean quads, licence allows modification.
2. Pick one. Import to Unity with VRCFury + Jerry's FT templates, upload it **unmodified** as a private test avatar.
3. Confirm face tracking and FBT work end to end on your hardware, on a model you haven't invested in yet.
4. Only then start sculpting Kaarten onto it.

Step 3 is the important one. Proving the tracking pipeline before the art means every problem you hit afterwards is an art problem, not a mystery.
