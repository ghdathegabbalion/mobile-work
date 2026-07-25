# Uploading Frennec as a test avatar

First-upload walkthrough. Goal: Frennec in VRChat, **unmodified**, with face tracking and FBT confirmed working — before you invest any art time.

Allow 1–2 hours the first time, most of it installers.

---

## Before you start

- **VRChat account at "New User" trust rank or above.** Brand-new accounts can't upload. If you've played a bit you're fine — check on your profile.
- **A Unity account** (free Personal licence).
- Frennec downloaded from [Gumroad](https://nattbat.gumroad.com/l/frennec) and unzipped.

---

## 1. Install the Creator Companion

Download **VCC** from [vrchat.com/home/download](https://vrchat.com/home/download).

VCC manages Unity versions, the SDK, and packages. **Let it install the Unity version it wants** — don't pick one yourself. Mismatched Unity versions are the single most common cause of upload failures.

It'll pull in Unity Hub and the correct Unity editor. This is the slow part.

---

## 2. Create the project

In VCC: **New Project ▸ Avatar Project**. Name it something like `kaarten`.

Then in the project's package list, add:

- **VRChat SDK - Avatars** (added by default)
- **VRCFury** — you'll want it shortly, and adding it now saves a round trip

Open the project. First launch takes a few minutes while Unity compiles.

---

## 3. Import Frennec

Order matters here.

1. **Shaders first.** Frennec will ship with lilToon or Poiyomi. Import that `.unitypackage` *before* the avatar. If you do it the other way round, every material comes in bright magenta.
2. **Then the avatar** — drag Frennec's `.unitypackage` into the Unity Assets window, or `Assets ▸ Import Package ▸ Custom Package`. Accept all.
3. Find the avatar **prefab** in the imported folder and drag it into the scene hierarchy.

Magenta materials at this point = missing shader. Import the shader package and they'll fix themselves.

---

## 4. Check the descriptor

Select the avatar in the hierarchy. In the Inspector you should see a **VRC Avatar Descriptor** component. A face-tracking-ready base will have this filled in already — you're just confirming, not configuring:

- **View Position** — the small sphere should sit between the eyes
- **LipSync** — set to Viseme Blend Shape, with the 15 visemes mapped
- **Eye Look** — eye bones and blink shapes assigned

If any of that is blank, the base isn't as complete as advertised — worth knowing now.

---

## 5. Sign in to the SDK

`VRChat SDK ▸ Show Control Panel`

- **Authentication** tab — sign in with your VRChat account
- **Builder** tab — it validates the avatar and lists any errors

Auto-fix anything it offers to fix. Warnings are usually fine; errors block the upload.

---

## 6. Build & Test — do this one first

In the Builder tab: **Build & Test**.

This puts the avatar **locally** on your machine only. It doesn't publish anything, doesn't use an upload slot, and doesn't touch VRChat's servers. It's the right tool for iteration — you'll use it constantly.

VRChat launches. In the avatar menu, your test avatar appears under the local/test section. Select it.

**Build & Test is your iteration loop.** Change something in Unity, hit it again, and the avatar updates. Only use Build & Publish when you want it on your account properly.

---

## 7. Build & Publish (when you're ready)

Same panel, **Build & Publish**. Fill in a name and description.

Avatars are **private by default** — nobody else can use it unless you explicitly make it public. Nothing to worry about here.

---

## 8. Turn on face tracking

1. Install **[VRCFaceTracking](https://docs.vrcft.io/docs/intro/getting-started)** and the module for your hardware (Project Babble for mouth, EyeTrackVR for eyes).
2. Start VRCFaceTracking **before** VRChat.
3. In VRChat: **Action Menu ▸ Options ▸ OSC ▸ Enable**.
4. Load the avatar. VRCFT should show it detected the avatar's parameters.

⚠️ **The OSC caching gotcha.** VRChat caches each avatar's OSC parameter config. When you change an avatar's parameters and re-upload, the stale config sticks around and face tracking silently stops working.

Fix: **Action Menu ▸ Options ▸ OSC ▸ Reset Config**. Do this any time you change parameters — it will save you hours of confused debugging.

---

## 9. Turn on full-body tracking

1. Trackers on, powered, visible to base stations.
2. SteamVR should show all of them tracking before you launch VRChat.
3. In VRChat, with trackers detected, a **calibration** option appears in the menu.
4. Calibrate: stand in a T-pose, match the on-screen prompt.

Frennec is adult-proportioned right now, so calibration should feel normal. That's deliberate — you're establishing a baseline before you reproportion him to cub/teen, so when something feels off later you know it's your change and not the setup.

---

## What "working" looks like

Before you touch a single vertex, confirm all of:

- [ ] Avatar loads with correct materials — no magenta
- [ ] Mouth moves when you talk (visemes)
- [ ] Eyes blink and track around
- [ ] VRCFT reports parameters detected
- [ ] Your real mouth movement drives the avatar's mouth
- [ ] Eye tracking follows your gaze (once EyeTrackVR is calibrated)
- [ ] FBT calibrates and limbs follow you
- [ ] Look in a mirror — everything moves as expected

Once all of that is ticked, **every problem you hit afterwards is a problem you created.** That's worth a lot when you're debugging at hour 60.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Magenta materials | Shader not imported. Import lilToon/Poiyomi, then reassign if needed |
| SDK panel shows errors | Read them — usually a missing descriptor field or wrong rig type |
| "You are not allowed to upload" | Trust rank below New User |
| Upload fails silently | Unity version mismatch — let VCC reinstall the pinned version |
| Face tracking does nothing | OSC not enabled, VRCFT started after VRChat, or stale OSC config — reset it |
| Avatar T-poses in game | Rig not set to Humanoid in the model import settings |
| Eyes don't move | Eye Look not configured in the descriptor |
| Trackers not detected | Fix in SteamVR first — VRChat only sees what SteamVR sees |

---

## Then what

Once the baseline is confirmed, go to [`frennec-to-kaarten.md`](frennec-to-kaarten.md) step 3 — reproportion the armature to the cub/teen spec and upload again with Build & Test.
