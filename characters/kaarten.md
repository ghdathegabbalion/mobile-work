# Kaarten — design sheet

Reference sheet: `ref/kaarten-ref.png`. To render on the PC, see `RUN-ON-PC.md`.

Anthropomorphic feline-dragon cub wizard. Storybook-fantasy anime illustration, ornate and jewel-toned.

## Design traits (keep these locked)

- **Species/build:** young cat cub with dragon traits, small and round, full-body poses read best.
- **Fur:** soft tan, faint darker spots on the limbs; freckled muzzle, tufted cheek fur.
- **Eyes:** big round emerald green. Gentle closed-mouth smile.
- **Hair:** wild shaggy rainbow gradient — red/orange at the crown → green → teal → blue at the tips.
- **Wings:** small red membranous bat-dragon wings, gold-plated bones, shoulder-mounted.
- **Tail:** long serpentine dragon tail, iridescent rainbow scales, plumed red-and-gold fan at the tip.
- **Hat:** enormous wide-brimmed golden wizard hat, quilted, embroidered with gold stars and constellation lines, jewelled band, red/green/gold feathers and purple crystals in the brim, tall crown flopping to one side.
- **Robe:** heavy royal-blue robe lined in cream, gold filigree stars and constellation stitching, long train sweeping the floor.
- **Chest:** bare, with a large faceted **emerald heart gem** on layered gold chains set with amethyst and ruby.
- **Rest:** cream ruffled cuffs, gold pauldrons, jewelled gold belt, **green-and-white striped puffed pantaloons** trimmed in gold, clawed paw-feet in gold sandal-greaves.
- **Staff:** tall gold staff topped with a purple orb ringed in gold.
- **Setting:** crystal library at night — deep indigo, vast glowing gold arcane circle behind him, tomes, floating crystals, hanging pendant gems, candles, mirror-polished reflective floor.

## Render notes (Comfy Cloud, 2026-07-25)

- Model: `bfl/flux-2-pro` via `partner_generate`, seed `77420`.
- The top-level `aspect_ratio` arg is ignored — output came back 4:3 landscape. Putting `aspect_ratio` / `width` / `height` in `params` **plus** opening the prompt with "tall vertical portrait-orientation composition" gets portrait, but the prose reorder also drifts the design (loses the striped pantaloons and orb staff, brightens the scene to daylight).
- Best fidelity so far: the landscape run — arcane circle, pantaloons, orb staff and dark indigo palette all held.
- On the PC over SSH, prefer a proper img2img/LoRA pass off the reference sheet instead of pure text-to-image; text-only can't hold the costume detail reliably.

## Prompt (working version)

> Highly detailed anime-style fantasy illustration, full body, front-facing, of a young anthropomorphic feline-dragon cub wizard standing in an enchanted crystal library. Soft tan fur with faint spots, big round emerald-green eyes, freckled muzzle, gentle closed-mouth smile, tufted cheek fur. Wild shaggy rainbow-gradient hair — red and orange at the crown fading through green and teal to blue at the tips. Small red membranous bat-dragon wings with gold-plated bones sprouting from the shoulders. Long serpentine dragon tail covered in iridescent rainbow scales ending in a plumed red-and-gold fan.
>
> Wearing an enormous wide-brimmed golden wizard hat, quilted and embroidered with tiny gold stars and constellation lines, jewels set along the band, a spray of red-green-gold feathers and purple crystals tucked into the brim, the tall crown flopping to one side. Over the shoulders a heavy royal-blue robe lined in cream, covered in gold filigree stars and geometric constellation stitching, sweeping wide across the floor. Bare chest with a huge faceted emerald heart-shaped gem hanging at the collarbone on layered gold chains set with amethyst and ruby. Wide cream ruffled cuffs at the wrists, gold pauldrons, an ornate gold-plated belt studded with green and violet gems, and green-and-white vertical-striped puffed pantaloons trimmed in gold. Large clawed paw-feet in gold jewelled sandal-greaves. One hand open and raised, palm up, cradling a tiny glowing arcane sigil; the other hand resting on a tall gold staff topped with a purple orb ringed in gold.
>
> Behind him a vast glowing arcane circle of gold star-lines fills the deep indigo night-sky background. Bookshelves of ancient tomes, floating faceted crystals in amber, violet, and rainbow, hanging pendant gems on gold chains, lit candles, an open spellbook, a glass orb. Warm candlelight and cool magical glow, glittering bokeh sparkles, mirror-polished floor with reflections. Rich jewel-tone palette of gold, sapphire blue, emerald, and amethyst. Ornate, opulent, symmetrical, storybook fantasy, crisp linework, painterly shading, extremely intricate detail.
