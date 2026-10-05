# ChatGPT prompts for the NOVIS slide diagrams

Each prompt makes one figure to replace the native diagram on that slide.
Ask for a 16:9 PNG on a white background. When pasting it in, keep the
figure caption under it as it is.

Style line used in every prompt, so the figures match the deck:

> Clean flat academic diagram, white background, navy #213A64 as the main
> colour, gold #A27B2C for highlights, thermal = orange #D9622B, echo = teal
> #17868A, sonar = violet #6B4FA0. Rounded boxes, thin arrows, Calibri-like
> sans-serif labels, no 3D, no shadows, no gradients, no decorative
> background, every label spelled exactly as given.

---

## 1. Slide 10: end-to-end pipeline (Figure 4)

```
Create a horizontal, left-to-right pipeline diagram for a research paper, 16:9, white background.
Title at top: "NOVIS end-to-end pipeline".
Eight numbered stages in rounded boxes, each with a small icon and a 1–2 line label, connected by arrows:
1 "Sensor node" – icon of a small circuit board with two thermal sensors, two ultrasonic sensors, a microphone and a speaker. Label: "thermal ×2 · sonar ×2 · chirp echo"
2 "Pre-processing" – label: "un-mirror · remove chess pattern · repair dead pixel · align echo to chirp"
3 "Thermal stem" (orange), "Echo stem" (teal), "Sonar stem" (violet) – three small stacked boxes producing "192 tokens", "24 tokens", "4 tokens"
4 "Fusion backbone" – highlighted in orange outline: "220 tokens · 14 transformer blocks · learned mask tokens for missing sensors"
5 "Decoder" – "12×16 → 192×256 · thermal skip"
6 "Outputs" – three small image tiles: a grayscale room image, a depth map (dark-near, light-far), a colour image with a small "confidence" bar
Above stages 3–6, a dashed gold bracket labelled "Staged training: A thermal → B echo → C fusion → D real capture".
Below stage 1, a small phone icon with a dashed arrow to stage 6 labelled "photo = training target only, never an input".
Style: clean flat academic diagram, navy #213A64 main colour, gold #A27B2C highlights, thermal orange #D9622B, echo teal #17868A, sonar violet #6B4FA0, rounded boxes, thin arrows, sans-serif labels, no 3D, no shadows, no gradients. Spell every label exactly as given.
```

## 2. Slide 11: NOVISNet architecture (Figure 5)

```
Create a neural-network architecture diagram, 16:9, white background, flowing left to right.
Left column, three input blocks drawn as small tensors:
- orange "Thermal 1×24×32" (a small heat-map grid)
- teal "Echo spectrogram 2×64×64" (a small spectrogram image)
- violet "Sonar 10 values" (a short bar of 10 cells)
Each goes into its own stem box: "Thermal stem → 192 grid tokens (12×16)", "Echo stem → 24 tokens", "Sonar stem → 4 tokens".
The token sets are drawn as rows of small coloured squares (orange, teal, violet) and concatenate into one long row labelled "220 tokens × 320".
This row enters a large rounded block "Fusion backbone × 14" that contains three stacked layers: "Depthwise local mixing", "8-head self-attention", "Gated feed-forward", with a residual arrow around each.
Next, a decoder drawn as four widening trapezoids labelled "PixelShuffle + SE" with sizes "12×16 → 24×32 → 48×64 → 96×128 → 192×256".
A dashed orange skip arrow runs from the thermal stem to the decoder at 24×32, labelled "thermal skip".
Three output heads on the right: navy "Grayscale", navy "Inverse depth", gold "Colour (ab) + confidence".
A small note at the bottom: "≈27 M parameters".
Style: clean flat academic diagram, navy #213A64, gold #A27B2C, orange #D9622B, teal #17868A, violet #6B4FA0, thin arrows, sans-serif labels, no 3D, no shadows. Spell every label exactly as given.
```

## 3. Slide 12: missing sensors / mask tokens (Figure 6)

```
Create a two-row explanatory diagram, 16:9, white background.
Row 1, titled "All sensors present": a row of small squares — 8 orange (thermal), 4 teal (echo), 2 violet (sonar) — entering a box "Fusion backbone".
Row 2, titled "Echo missing": the same row, but the 4 teal squares are replaced by 4 light-grey squares each marked with the Greek letter τ, with a small callout "learned mask token τ_echo". A crossed-out microphone icon sits above the grey squares.
Between the rows, the formula, large and centred: "z = m · t + (1 − m) · τ", with a small legend: "t = sensor tokens, m = 1 if present / 0 if missing, τ = learned mask token".
At the bottom right, a small shield icon with the text "Modality dropout 0.3 during training → one model for any subset of sensors".
Style: clean flat academic diagram, navy #213A64, gold #A27B2C, orange #D9622B, teal #17868A, violet #6B4FA0, sans-serif labels, no 3D, no shadows. Spell every label exactly as given.
```

## 4. (Optional) Slide 8: sensor node, with both thermal sensors

The existing node figure shows only one MLX90640. If you want one with both:

```
Redraw this top-down circuit layout (12 × 20 cm perfboard) as a clean technical illustration, white background:
top centre: two MLX90640 thermal sensors side by side, labelled "BAA wide 110°" and "BAB narrow 55°", with their field-of-view wedges drawn in dashed lines (110° and 55°);
top left and top right: "HC-SR04 left" and "HC-SR04 right" ultrasonic sensors with 20° wedges;
middle: "INMP441 microphone" and "speaker";
centre: "ESP32-WROOM-32";
below: "PAM8302 amplifier", then "LiPo battery".
An arrow at the top reads "forward / sensing direction".
Style: technical line illustration, navy #213A64 labels, orange #D9622B for the thermal wedges, no 3D, no shadows.
```
