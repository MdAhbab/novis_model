// NOVIS seminar deck. Run: node build_deck.js  -> ../NOVIS_Presentation.pptx
// Style follows the team's earlier HALO seminar deck: navy header band,
// gold accents, numbered figure/table captions, white content slides.
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const { applyTheme } = require("./apply_theme.js");

const OUT = "../NOVIS_Presentation.pptx";
const IMG = "img/";

// ---- palette (hex, no '#') ----
const NAVY = "213A64", NAVY_D = "182B4D", GOLD = "A27B2C", ICE = "CADCFC";
const ORANGE = "D9622B", TEAL = "17868A", VIOLET = "6B4FA0", RED = "B3261E";
const INK = "1F2937", MUTE = "6B7280", LINE = "D5DAE3", TINT = "F1F4F9", WHITE = "FFFFFF";
const FONT = "Calibri";

const THEME = {
  name: "NOVIS",
  headFontFace: FONT, bodyFontFace: FONT,
  colors: {
    dk1: "1E1E1E", lt1: "FFFFFF", dk2: NAVY, lt2: "EEF1F6",
    accent1: NAVY, accent2: GOLD, accent3: ORANGE, accent4: TEAL,
    accent5: VIOLET, accent6: RED, hlink: "2F5597", folHlink: "7F6000",
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in, same canvas as the HALO deck
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
pres.author = "NOVIS team";
pres.title = "NOVIS: Seeing a Room Without a Camera";

const W = 13.333;

// ---------------- layouts ----------------
pres.defineSlideMaster({
  title: "TITLE",
  background: { color: NAVY },
  objects: [
    { rect: { x: 0, y: 6.35, w: W, h: 1.15, fill: { color: NAVY_D } } },
    { text: { text: "CSE 4883 — Digital Image Processing", options: { x: 1.5, y: 6.5, w: 10.3, h: 0.35, align: "center", fontFace: FONT, fontSize: 14, color: "DDE3EE" } } },
    { text: { text: "Dept. of CSE  ·  United International University  ·  October 2026", options: { x: 1.5, y: 6.85, w: 10.3, h: 0.35, align: "center", fontFace: FONT, fontSize: 14, color: "DDE3EE" } } },
  ],
});

pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: WHITE },
  margin: [0.5, 0.5, 0.6, 0.5],
  objects: [
    { rect: { x: 0, y: 0, w: W, h: 0.7, fill: { color: NAVY } } },
    { placeholder: { options: { name: "section", type: "body", x: 0.5, y: 0.1, w: 11.5, h: 0.5, fontFace: FONT, fontSize: 20, bold: true, color: WHITE, valign: "middle", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.85, w: 12.3, h: 0.65, fontFace: FONT, fontSize: 26, bold: true, color: NAVY, align: "left", valign: "middle", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.45, y: 7.05, w: 0.5, h: 0.3, fontFace: FONT, fontSize: 10, color: "8A8F98", align: "right" },
});

pres.defineSlideMaster({
  title: "DARK",
  background: { color: NAVY },
  objects: [
    { placeholder: { options: { name: "section", type: "body", x: 0.5, y: 0.3, w: 11.5, h: 0.45, fontFace: FONT, fontSize: 18, bold: true, color: "E2C27A", valign: "middle", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.8, w: 12.3, h: 0.75, fontFace: FONT, fontSize: 32, bold: true, color: WHITE, align: "left", valign: "middle", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.45, y: 7.05, w: 0.5, h: 0.3, fontFace: FONT, fontSize: 10, color: "AAB4C8", align: "right" },
});

pres.defineSlideMaster({
  title: "CLOSING",
  background: { color: NAVY },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 3.0, w: 12.3, h: 1.4, fontFace: FONT, fontSize: 48, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.45, y: 7.05, w: 0.5, h: 0.3, fontFace: FONT, fontSize: 10, color: "AAB4C8", align: "right" },
});

// ---------------- helpers ----------------
let fig = 0, tab = 0;
const nextFig = (t) => `Figure ${++fig}: ${t}`;
const nextTab = (t) => `Table ${++tab}: ${t}`;

function content(section, title, sectionTitle) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle });
  s.addText(section, { placeholder: "section" });
  s.addText(title, { placeholder: "title" });
  return s;
}

function text(s, t, o) {
  s.addText(t, Object.assign({ isTextBox: true, fontFace: FONT, fontSize: 15, color: INK, margin: 0, valign: "top" }, o));
}

function caption(s, t, x, y, w) {
  text(s, t, { x, y, w, h: 0.32, fontSize: 12, color: MUTE, align: "center", valign: "middle" });
}

function bullets(s, items, o) {
  const runs = items.map((it, i) => {
    const r = typeof it === "string" ? [{ text: it }] : it;
    return r.map((run, j) => {
      const opt = Object.assign({}, run.options || {});
      if (j === 0) opt.bullet = { code: "25AA" };
      if (j === r.length - 1 && i < items.length - 1) opt.breakLine = true;
      return { text: run.text, options: opt };
    });
  }).flat();
  s.addText(runs, Object.assign({ isTextBox: true, fontFace: FONT, fontSize: 16, color: INK, margin: 0, valign: "top", paraSpaceAfter: 10 }, o));
}

function card(s, x, y, w, h, fill, name) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill || TINT }, line: { color: fill || TINT, width: 0.75 }, rectRadius: 0.08, objectName: name });
}

function circleNum(s, x, y, d, label, fill, color, size) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill } });
  text(s, label, { x, y, w: d, h: d, align: "center", valign: "middle", bold: true, fontSize: size || 14, color: color || WHITE });
}

function arrow(s, x1, y1, x2, y2, color, width) {
  s.addShape(pres.shapes.LINE, {
    x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
    flipH: x2 < x1, flipV: y2 < y1,
    line: { color: color || MUTE, width: width || 1.75, endArrowType: "triangle" },
  });
}

async function icon(Comp, color, px = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: px }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

async function iconCircle(s, Comp, x, y, d, fill, color) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill } });
  const pad = d * 0.24;
  s.addImage({ data: await icon(Comp, color || WHITE), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad });
}

const HEAD = (t, extra) => ({ text: t, options: Object.assign({ bold: true, color: WHITE, fill: { color: NAVY }, align: "center", valign: "middle" }, extra || {}) });
const CELL = (t, extra) => ({ text: String(t), options: Object.assign({ align: "center", valign: "middle" }, extra || {}) });
const tableOpts = (x, y, w, colW, extra) => Object.assign({
  x, y, w, colW, fontFace: FONT, fontSize: 14, color: INK,
  border: { type: "solid", pt: 0.75, color: LINE }, margin: [0.04, 0.08, 0.04, 0.08],
}, extra || {});
function zebra(rows) { // tint every other body row
  return rows.map((r, i) => i === 0 || i % 2 === 1 ? r : r.map(c => ({ text: c.text, options: Object.assign({}, c.options, { fill: { color: TINT } }) })));
}

const chartBase = (title) => ({
  showTitle: !!title, title, titleFontFace: "+mn-lt", titleFontSize: 14, titleColor: INK,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt",
  catAxisLabelFontSize: 12, valAxisLabelFontSize: 11, dataLabelFontSize: 11, legendFontSize: 12,
  catAxisLabelColor: "4B5563", valAxisLabelColor: "6B7280", dataLabelColor: INK,
  valGridLine: { color: "E5E7EB", size: 0.5 }, catGridLine: { style: "none" },
  catAxisLineShow: true, valAxisLineShow: false,
});

// pptxgenjs writes an <a:pPr> before every run, so a paragraph built from
// several runs (bold label + plain text) gets a second pPr after its first
// run: invalid order, and it overrides the bullet with buNone. A pPr is only
// legal as the paragraph's first child, so drop any that follow a run.
async function dropMidParagraphPPr(file) {
  const fs = require("fs");
  const JSZip = require(require.resolve("jszip", { paths: [require.resolve("pptxgenjs")] }));
  const zip = await JSZip.loadAsync(fs.readFileSync(file));
  const re = /(<\/a:r>)<a:pPr\b[^>]*?(?:\/>|>[\s\S]*?<\/a:pPr>)/g;
  for (const name of Object.keys(zip.files).filter(n => /^ppt\/slides\/slide\d+\.xml$/.test(n))) {
    const xml = await zip.file(name).async("string");
    zip.file(name, xml.replace(re, "$1"));
  }
  fs.writeFileSync(file, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
}

function notes(s, who, script) { s.addNotes(`Presenter: ${who}\n\n${script}`); }

const T1 = "Ahnaf Atique", T2 = "Md. Tanzamul Azad", T3 = "Md. Ahbab Hamid Khan", T4 = "Akib Bari", T5 = "Md. Jamiul Hasan (Shishir)";

(async () => {
  // =========== 1. Title ===========
  pres.addSection({ title: "Introduction" });
  {
    const s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Introduction" });
    text(s, "NOVIS: Seeing a Room Without a Camera", { x: 0.8, y: 0.75, w: 11.73, h: 0.9, fontSize: 40, bold: true, color: WHITE, align: "center", valign: "middle" });
    text(s, "Image reconstruction from low-resolution thermal, ultrasonic and acoustic-echo sensing", { x: 1.3, y: 1.7, w: 10.73, h: 0.5, fontSize: 18, color: ICE, align: "center", valign: "middle" });
    text(s, "Presented To", { x: 1.3, y: 2.85, w: 4.5, h: 0.45, fontSize: 20, bold: true, color: "C9A24E" });
    text(s, [{ text: "Md. Tanvir Raihan", options: { breakLine: true } }, { text: "Lecturer, Dept. of CSE, UIU" }],
      { x: 1.3, y: 3.45, w: 4.8, h: 0.9, fontSize: 17, color: WHITE, paraSpaceAfter: 6 });
    text(s, "Presented By", { x: 7.0, y: 2.85, w: 4.5, h: 0.45, fontSize: 20, bold: true, color: "C9A24E" });
    const team = [["Ahnaf Atique", "011 223 0597"], ["Md. Tanzamul Azad", "011 223 0863"], ["Md. Ahbab Hamid Khan", "011 223 0869"], ["Akib Bari", "011 223 1020"], ["Md. Jamiul Hasan", "011 223 0871"]];
    team.forEach(([n, id], i) => {
      text(s, n, { x: 7.0, y: 3.4 + i * 0.5, w: 3.4, h: 0.42, fontSize: 16, color: WHITE, valign: "middle" });
      text(s, id, { x: 10.4, y: 3.4 + i * 0.5, w: 2.0, h: 0.42, fontSize: 16, color: ICE, valign: "middle" });
    });
    notes(s, T1, "Good morning. We are presenting NOVIS, a Non-Optical Visual Inference System: it reconstructs what a room looks like, and how far away things are, without any camera. Five of us will each take one part.");
  }

  // =========== 2. Outline ===========
  {
    const s = content("OUTLINE", "What we will cover", "Introduction");
    const parts = [
      [T1, "Introduction", "Research problem · Research questions", fa.FaBullseye],
      [T2, "Novelty", "What is new · Sensor node · Dual-thermal fusion", fa.FaStar],
      [T3, "Methodology", "Pipeline · NOVISNet architecture · Missing sensors · Training", fa.FaProjectDiagram],
      [T4, "Experiments", "Training stages · Real-capture dataset · Pre-processing · Targets", fa.FaFlask],
      [T5, "Results", "Results analysis · Limitations · Future work · Conclusion", fa.FaChartBar],
    ];
    const cw = 2.3, gap = 0.2, x0 = (W - (5 * cw + 4 * gap)) / 2;
    for (let i = 0; i < 5; i++) {
      const [who, head, sub, ic] = parts[i];
      const x = x0 + i * (cw + gap);
      card(s, x, 1.85, cw, 4.1, TINT, "outline-card-" + (i + 1));
      await iconCircle(s, ic, x + cw / 2 - 0.45, 2.15, 0.9, i === 1 ? GOLD : NAVY);
      text(s, "0" + (i + 1), { x, y: 3.2, w: cw, h: 0.55, fontSize: 28, bold: true, color: GOLD, align: "center" });
      text(s, head, { x: x + 0.15, y: 3.8, w: cw - 0.3, h: 0.45, fontSize: 20, bold: true, color: NAVY, align: "center" });
      text(s, sub, { x: x + 0.2, y: 4.3, w: cw - 0.4, h: 1.2, fontSize: 14, color: INK, align: "center" });
    }
    notes(s, T1, "The talk has five parts: the problem, what is new, the method, the experiments with our own dataset, and the results.");
  }

  // =========== 3. Introduction ===========
  {
    const s = content("INTRODUCTION", "Why reconstruct a scene without a camera?", "Introduction");
    const items = [
      [fa.FaMoon, "Works without light", "Heat and sound do not need illumination — darkness, glare and smoke do not blind them."],
      [fa.FaUserShield, "Private by design", "No optical image is ever captured at run time; only temperatures, ranges and echoes."],
      [fa.FaWalking, "Assistive navigation", "Coarse layout, people and obstacle distance are what a navigation aid actually needs."],
    ];
    const cw = 3.9, gap = 0.3, x0 = (W - (3 * cw + 2 * gap)) / 2;
    for (let i = 0; i < 3; i++) {
      const x = x0 + i * (cw + gap);
      card(s, x, 1.8, cw, 3.1, TINT, "intro-card-" + (i + 1));
      await iconCircle(s, items[i][0], x + 0.3, 2.05, 0.85, NAVY);
      text(s, items[i][1], { x: x + 1.3, y: 2.1, w: cw - 1.5, h: 0.75, fontSize: 20, bold: true, color: NAVY, valign: "middle" });
      text(s, items[i][2], { x: x + 0.3, y: 3.15, w: cw - 0.6, h: 1.6, fontSize: 17 });
    }
    // NOVIS in one line: three sensors -> outputs
    const y = 5.45;
    const chips = [["Thermal 32×24", ORANGE], ["Ultrasonic range", VIOLET], ["Acoustic echo", TEAL]];
    chips.forEach(([t, c], i) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7 + i * 2.35, y, w: 2.15, h: 0.6, fill: { color: c }, line: { color: c }, rectRadius: 0.1 });
      text(s, t, { x: 0.7 + i * 2.35, y, w: 2.15, h: 0.6, fontSize: 15, bold: true, color: WHITE, align: "center", valign: "middle" });
    });
    arrow(s, 7.75, y + 0.3, 8.45, y + 0.3, NAVY, 2.25);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.6, y, w: 4.05, h: 0.6, fill: { color: NAVY }, line: { color: NAVY }, rectRadius: 0.1 });
    text(s, "Grayscale image + metric depth", { x: 8.6, y, w: 4.05, h: 0.6, fontSize: 15, bold: true, color: WHITE, align: "center", valign: "middle" });
    text(s, "NOVIS — Non-Optical Visual Inference System. Optional colour is predicted with a per-pixel confidence, never measured.",
      { x: 0.7, y: 6.3, w: 11.95, h: 0.5, fontSize: 14, color: MUTE, italic: true });
    notes(s, T1, "Cameras need light and record everything they see. Thermal and sound work in the dark, and never capture a photograph, so they are private by design. For an assistive navigation aid, the useful output is coarse: where the walls, people and obstacles are and how far away. NOVIS takes three cheap sensors and outputs a grayscale image plus metric depth.");
  }

  // =========== 4. Research problem ===========
  {
    const s = content("RESEARCH PROBLEM", "768 thermal pixels must become a 49,152-pixel picture", "Introduction");
    bullets(s, [
      [{ text: "Tiny thermal input: ", options: { bold: true } }, { text: "a low-cost thermopile array sees 32×24 pixels — and sees heat, not furniture" }],
      [{ text: "Sparse range: ", options: { bold: true } }, { text: "two ultrasonic sensors give two distances, not a depth image" }],
      [{ text: "Ambiguous echo: ", options: { bold: true } }, { text: "many rooms produce similar echo signatures" }],
      [{ text: "Unreliable sensors: ", options: { bold: true } }, { text: "any one modality can be missing or noisy at run time" }],
    ], { x: 0.6, y: 1.85, w: 5.6, h: 3.7, fontSize: 17, paraSpaceAfter: 14 });
    // what the sensor sees vs what we must produce
    const iy = 1.95, iw = 2.9, ih = 2.175;
    s.addImage({ path: IMG + "can01_thermal_baa.png", x: 6.6, y: iy, w: iw, h: ih });
    s.addImage({ path: IMG + "can01_photo.jpg", x: 9.95, y: iy, w: iw, h: ih });
    arrow(s, 9.55, iy + ih / 2, 9.9, iy + ih / 2, NAVY, 2.5);
    text(s, "Sensor input (32×24)", { x: 6.6, y: iy + ih + 0.08, w: iw, h: 0.3, fontSize: 13, color: MUTE, align: "center" });
    text(s, "Target (192×256)", { x: 9.95, y: iy + ih + 0.08, w: iw, h: 0.3, fontSize: 13, color: MUTE, align: "center" });
    // stat callouts
    const stats = [["768", "input pixels"], ["49,152", "output pixels"], ["64×", "expansion"]];
    stats.forEach(([n, l], i) => {
      const x = 6.6 + i * 2.13;
      text(s, n, { x, y: 5.05, w: 2.0, h: 0.75, fontSize: 36, bold: true, color: i === 2 ? GOLD : NAVY, align: "center", valign: "middle" });
      text(s, l, { x, y: 5.8, w: 2.0, h: 0.35, fontSize: 14, color: MUTE, align: "center" });
    });
    card(s, 0.6, 5.65, 5.6, 1.1, "FBF6EA", "prob-take");
    text(s, "Everything finer than the sensor grid must come from learned priors — so the model has to combine every weak cue it has.",
      { x: 0.8, y: 5.7, w: 5.2, h: 1.0, fontSize: 15, italic: true, color: NAVY, valign: "middle" });
    caption(s, nextFig("Real canteen capture: thermal input vs. photo target."), 6.6, 4.5, 6.25);
    notes(s, T1, "This is the core difficulty. The thermal sensor gives 768 numbers; the picture we want has about 49 thousand pixels — a 64-times expansion. On the left is a real frame from our node, on the right the photo of the same view. Sonar gives two distances and echoes are ambiguous, so no single sensor is enough.");
  }

  // =========== 5. Research questions ===========
  {
    const s = content("RESEARCH QUESTIONS", "Reconstruction + Fusion + Robustness + Real-world transfer", "Introduction");
    const qs = [
      ["01", "Reconstruct?", "Can a 32×24 thermal array with sonar and echo give a recognisable scene and usable depth?", "Image & depth fidelity", fa.FaImage],
      ["02", "Fuse?", "Does combining the three sensors beat each sensor on its own?", "Fusion gain", fa.FaLayerGroup],
      ["03", "Missing sensor?", "Does the model degrade gracefully when a sensor drops out?", "Robustness", fa.FaUnlink],
      ["04", "Real world?", "Does a model trained on public datasets transfer to our own hardware?", "Domain gap", fa.FaGlobeAsia],
    ];
    const cw = 2.85, gap = 0.25, x0 = (W - (4 * cw + 3 * gap)) / 2;
    for (let i = 0; i < 4; i++) {
      const [n, h, d, tag, ic] = qs[i];
      const x = x0 + i * (cw + gap);
      await iconCircle(s, ic, x + cw / 2 - 0.5, 2.0, 1.0, NAVY);
      text(s, n, { x, y: 3.15, w: cw, h: 0.7, fontSize: 36, bold: true, color: GOLD, align: "center", valign: "middle" });
      text(s, h, { x, y: 3.9, w: cw, h: 0.5, fontSize: 21, bold: true, color: NAVY, align: "center" });
      text(s, d, { x: x + 0.1, y: 4.5, w: cw - 0.2, h: 1.4, fontSize: 16, align: "center" });
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.35, y: 6.1, w: cw - 0.7, h: 0.45, fill: { color: TINT }, line: { color: TINT }, rectRadius: 0.1 });
      text(s, tag, { x: x + 0.35, y: 6.1, w: cw - 0.7, h: 0.45, fontSize: 14, color: MUTE, align: "center", valign: "middle" });
    }
    notes(s, T1, "We ask four questions. One: can these weak sensors reconstruct a recognisable scene and usable depth? Two: does fusing them beat each alone? Three: does the model survive a missing sensor? Four: does what we learn on public data transfer to our own hardware? Now Tanzamul will explain what is new.");
  }

  // =========== 6. Novelty (highlight) ===========
  pres.addSection({ title: "Novelty" });
  {
    const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Novelty" });
    s.addText("NOVELTY  ★  THE CORE CONTRIBUTIONS", { placeholder: "section" });
    s.addText("What is new in NOVIS", { placeholder: "title" });
    const nov = [
      ["1", "Tri-modal, camera-free reconstruction", "Thermal + ultrasonic range + active chirp echo → grayscale image, metric depth and confidence-gated colour, from one model.", fa.FaEyeSlash],
      ["2", "One model for any subset of sensors", "Learned mask tokens and 30% modality dropout: the network is trained to run with thermal, echo or sonar missing.", fa.FaPuzzlePiece],
      ["3", "Dual-thermal \"foveated\" vision", "A wide (110°) and a narrow (55°) MLX90640 registered like two eyes: the narrow sensor adds 2× detail at the centre.", fa.FaEye],
      ["4", "A real, paired, leakage-safe dataset", "Our own ESP32 node: 31 scenes, 925 samples, each with a photo target; split by location so no room is in both train and validation.", fa.FaDatabase],
    ];
    const cw = 5.95, ch = 2.15, gx = 0.3, gy = 0.3, x0 = (W - (2 * cw + gx)) / 2, y0 = 1.85;
    for (let i = 0; i < 4; i++) {
      const x = x0 + (i % 2) * (cw + gx), y = y0 + Math.floor(i / 2) * (ch + gy);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: ch, fill: { color: "2C4A7C" }, line: { color: "3E5F94", width: 1 }, rectRadius: 0.08 });
      await iconCircle(s, nov[i][3], x + 0.3, y + 0.3, 0.85, GOLD);
      text(s, nov[i][1], { x: x + 1.35, y: y + 0.28, w: cw - 1.6, h: 0.85, fontSize: 20, bold: true, color: WHITE, valign: "middle" });
      text(s, nov[i][2], { x: x + 0.3, y: y + 1.2, w: cw - 0.6, h: 0.9, fontSize: 15, color: "DCE4F2" });
    }
    text(s, "Plus: results are judged against targets derived from sensor physics (floor → ceiling), not against camera-based leaderboards.",
      { x: x0, y: 6.75, w: 12.2, h: 0.4, fontSize: 14, italic: true, color: "E2C27A" });
    notes(s, T2, "These are our four contributions. First, one model turns thermal, sonar and an active echo into an image and depth, with no camera. Second, the same model runs when any sensor is missing, thanks to learned mask tokens. Third, we pair a wide and a narrow thermal sensor like two eyes, so the centre of the view gets twice the detail. Fourth, we built our own node and a real paired dataset that is split by location, so there is no leakage between training and validation.");
  }

  // =========== 7. Novelty cont: comparison ===========
  {
    const s = content("NOVELTY (CONT'D)", "How NOVIS differs from the closest prior set-ups", "Novelty");
    const Y = "✓", N = "—";
    const rows = zebra([
      [HEAD("Set-up"), HEAD("Thermal"), HEAD("Ultrasonic range"), HEAD("Active echo"), HEAD("Depth output"), HEAD("Missing-sensor handling"), HEAD("Low-cost node")],
      [CELL("Thermal → visible translation (LLVIP benchmark [1])", { align: "left" }), CELL("High-res camera"), CELL(N), CELL(N), CELL(N), CELL(N), CELL(N)],
      [CELL("Sound → depth (BatVision [6])", { align: "left" }), CELL(N), CELL(N), CELL(Y), CELL(Y), CELL(N), CELL(N)],
      [CELL("NOVIS (ours)", { align: "left", bold: true, color: NAVY }), CELL("32×24 ×2", { bold: true, color: ORANGE }), CELL(Y, { bold: true, color: ORANGE }), CELL(Y, { bold: true, color: ORANGE }), CELL(Y, { bold: true, color: ORANGE }), CELL(Y, { bold: true, color: ORANGE }), CELL(Y, { bold: true, color: ORANGE })],
    ]);
    caption(s, nextTab("Qualitative comparison of sensing set-ups."), 0.6, 1.75, 12.1);
    s.addTable(rows, tableOpts(0.6, 2.15, 12.1, [3.7, 1.55, 1.45, 1.3, 1.3, 1.6, 1.2], { rowH: [0.6, 0.62, 0.62, 0.62], fontSize: 15 }));
    const pts = [
      [fa.FaCompressArrowsAlt, "Far less input", "32×24 thermopile instead of a megapixel thermal camera."],
      [fa.FaLayerGroup, "More modalities", "Heat, range and echo fused in one token sequence."],
      [fa.FaShieldAlt, "Built to degrade", "A sensor can drop out without retraining."],
    ];
    const cw = 3.85, gap = 0.27;
    for (let i = 0; i < 3; i++) {
      const x = 0.6 + i * (cw + gap);
      card(s, x, 5.0, cw, 1.55, TINT, "diff-" + i);
      await iconCircle(s, pts[i][0], x + 0.25, 5.25, 0.7, NAVY);
      text(s, pts[i][1], { x: x + 1.1, y: 5.22, w: cw - 1.25, h: 0.4, fontSize: 17, bold: true, color: NAVY });
      text(s, pts[i][2], { x: x + 1.1, y: 5.65, w: cw - 1.25, h: 0.8, fontSize: 14 });
    }
    notes(s, T2, "The closest prior work either translates a high-resolution thermal camera into a visible image, like the LLVIP benchmark, or predicts depth from sound alone, like BatVision. NOVIS uses a far smaller thermal array, adds ultrasonic range, outputs depth as well as an image, and is designed to keep working when a sensor is missing — on a low-cost node we built ourselves.");
  }

  // =========== 8. Sensor node ===========
  {
    const s = content("METHODOLOGY", "The NOVIS sensor node", "Novelty");
    s.addImage({ path: IMG + "node_layout.png", x: 0.7, y: 1.65, w: 3.4, h: 5.1 });
    caption(s, nextFig("Node layout, top view (≈12 × 20 cm)."), 0.3, 6.8, 4.2);
    const rows = zebra([
      [HEAD("Sensor"), HEAD("Part"), HEAD("What it gives the model")],
      [CELL("Thermal — wide", { align: "left", bold: true }), CELL("MLX90640 BAA, 110°×75°", { align: "left" }), CELL("32×24 temperature frame of the whole view", { align: "left" })],
      [CELL("Thermal — narrow", { align: "left", bold: true }), CELL("MLX90640 BAB, 55°×35°", { align: "left" }), CELL("32×24 of the centre at ≈2× detail", { align: "left" })],
      [CELL("Sonar ×2", { align: "left", bold: true }), CELL("HC-SR04, left + right", { align: "left" }), CELL("Two ranges in mm, up to 4 m", { align: "left" })],
      [CELL("Echo", { align: "left", bold: true }), CELL("INMP441 mic + PAM8302 speaker", { align: "left" }), CELL("60 ms at 16 kHz after a 5 ms 1→8 kHz chirp", { align: "left" })],
      [CELL("Controller", { align: "left", bold: true }), CELL("ESP32-WROOM-32", { align: "left" }), CELL("Wi-Fi capture dashboard, JSON export", { align: "left" })],
    ]);
    caption(s, nextTab("Sensors on the node."), 4.6, 1.7, 8.2);
    s.addTable(rows, tableOpts(4.6, 2.05, 8.2, [2.15, 2.85, 3.2], { rowH: 0.56, fontSize: 14 }));
    card(s, 4.6, 5.65, 8.2, 1.0, TINT, "node-note");
    await iconCircle(s, fa.FaCamera, 4.8, 5.8, 0.7, GOLD);
    text(s, "A phone photo of the same view is taken once per scene — it is only the training target, never an input.",
      { x: 5.7, y: 5.75, w: 6.9, h: 0.8, fontSize: 15, valign: "middle" });
    notes(s, T2, "This is the node we built on an ESP32. Two thermal sensors — wide and narrow — two ultrasonic sensors left and right, and a microphone with a small speaker that plays a chirp and records the echo. A phone photo of the same view is the training target only; at run time there is no camera.");
  }

  // =========== 9. Dual-thermal fusion ===========
  {
    const s = content("METHODOLOGY (CONT'D)", "Dual-thermal fusion: two sensors, one sharper view", "Novelty");
    const ims = [["can01_photo.jpg", "Photo (target)"], ["can01_thermal_baa.png", "BAA — wide, 110°"], ["can01_thermal_bab.png", "BAB — narrow, 55°"], ["can01_thermal_merged.png", "Merged (BAA + BAB)"]];
    const iw = 2.85, ih = 2.1375, gap = 0.2, x0 = (W - (4 * iw + 3 * gap)) / 2;
    ims.forEach(([f, l], i) => {
      const x = x0 + i * (iw + gap);
      s.addImage({ path: IMG + f, x, y: 1.75, w: iw, h: ih });
      text(s, l, { x, y: 1.75 + ih + 0.06, w: iw, h: 0.3, fontSize: 14, bold: true, color: i === 3 ? ORANGE : NAVY, align: "center" });
    });
    caption(s, nextFig("Real canteen scene: the narrow sensor fills the centre of the wide view (box) — a sharp fovea, like an eye."), 0.6, 4.3, 12.1);
    const steps = [
      ["Register", "Grid search for BAB's scale and centre that maximise normalised cross-correlation with BAA"],
      ["Resample", "Both frames bicubically interpolated onto one 96 × 128 grid"],
      ["Level-match", "BAB shifted by the median temperature gap (≈2 °C) over the overlap"],
      ["Feather-blend", "Weight α ramps 0 → 1 over 1.5 pixels, so the seam does not show"],
    ];
    const sw = 2.85;
    for (let i = 0; i < 4; i++) {
      const x = x0 + i * (sw + gap);
      card(s, x, 4.8, sw, 2.0, TINT, "fuse-step-" + i);
      circleNum(s, x + 0.2, 5.0, 0.5, String(i + 1), NAVY);
      text(s, steps[i][0], { x: x + 0.82, y: 5.0, w: sw - 0.95, h: 0.5, fontSize: 16, bold: true, color: NAVY, valign: "middle" });
      text(s, steps[i][1], { x: x + 0.2, y: 5.55, w: sw - 0.4, h: 1.2, fontSize: 14 });
      if (i < 3) arrow(s, x + sw + 0.01, 5.725, x + sw + gap - 0.01, 5.725, MUTE, 1.5);
    }
    notes(s, T2, "Here is a real scene from our node. The wide sensor sees the whole view, the narrow one sees the centre at twice the detail. We find where the narrow view sits inside the wide one by searching for the scale and centre with the highest cross-correlation, resample both onto one grid with bicubic interpolation, match their temperature levels, and blend the edge smoothly — a sharp centre inside a wide view, like the fovea of an eye. Ahbab will now explain the model.");
  }

  // =========== 10. Pipeline ===========
  pres.addSection({ title: "Methodology" });
  {
    const s = content("METHODOLOGY", "NOVIS end-to-end pipeline", "Methodology");
    const blocks = [
      ["Sensor node", "thermal ×2, sonar ×2, chirp echo", NAVY],
      ["Pre-process", "un-mirror, de-chess, pixel repair, echo onset", NAVY],
      ["Modality stems", "each sensor → tokens", NAVY],
      ["Fusion backbone", "220 tokens · mask tokens for missing sensors", ORANGE],
      ["Decoder", "12×16 → 192×256, thermal skip", NAVY],
      ["Outputs", "grayscale · depth · colour + confidence", GOLD],
    ];
    const bw = 1.85, gap = 0.27, x0 = (W - (6 * bw + 5 * gap)) / 2, y = 2.75, bh = 2.3;
    for (let i = 0; i < 6; i++) {
      const x = x0 + i * (bw + gap), c = blocks[i][2];
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: bw, h: bh, fill: { color: i === 3 ? "FBEDE4" : WHITE }, line: { color: c, width: 1.75 }, rectRadius: 0.1 });
      circleNum(s, x + bw / 2 - 0.27, y - 0.27, 0.54, String(i + 1), c);
      text(s, blocks[i][0], { x: x + 0.1, y: y + 0.4, w: bw - 0.2, h: 0.7, fontSize: 16, bold: true, color: i === 3 ? ORANGE : NAVY, align: "center", valign: "middle" });
      text(s, blocks[i][1], { x: x + 0.12, y: y + 1.15, w: bw - 0.24, h: 1.05, fontSize: 14, align: "center" });
      if (i < 5) arrow(s, x + bw + 0.02, y + bh / 2, x + bw + gap - 0.02, y + bh / 2, NAVY, 2);
    }
    // training-stage bracket
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x0, y: 1.75, w: 6 * bw + 5 * gap, h: 0.55, fill: { color: "FBF6EA" }, line: { color: GOLD, width: 1, dashType: "dash" }, rectRadius: 0.08 });
    text(s, "Staged training:  A thermal  →  B echo  →  C fusion  →  D real capture (our node)", { x: x0, y: 1.75, w: 6 * bw + 5 * gap, h: 0.55, fontSize: 15, bold: true, color: GOLD, align: "center", valign: "middle" });
    // modality legend
    const leg = [["Thermal", ORANGE], ["Echo", TEAL], ["Sonar", VIOLET]];
    leg.forEach(([t, c], i) => {
      s.addShape(pres.shapes.OVAL, { x: x0 + i * 1.6, y: 5.55, w: 0.22, h: 0.22, fill: { color: c }, line: { color: c } });
      text(s, t, { x: x0 + i * 1.6 + 0.3, y: 5.48, w: 1.2, h: 0.36, fontSize: 14, color: INK, valign: "middle" });
    });
    text(s, "No camera at inference: the photo appears only as the training target.", { x: x0 + 5.0, y: 5.48, w: 7.0, h: 0.36, fontSize: 14, italic: true, color: MUTE, valign: "middle" });
    caption(s, nextFig("NOVIS pipeline from raw sensor readings to reconstructed image and depth."), 0.6, 6.3, 12.1);
    notes(s, T3, "This is the whole pipeline. The node captures thermal, sonar and echo. We clean the signals, turn each sensor into tokens, fuse them in a transformer backbone that has a learned stand-in for any missing sensor, and decode back up to a 192 by 256 image, depth map, and optional colour with confidence. Training happens in four stages, from public thermal data to our own captures.");
  }

  // =========== 11. Architecture ===========
  {
    const s = content("METHODOLOGY (CONT'D)", "NOVISNet: token-fusion architecture", "Methodology");
    const rowY = [2.15, 3.35, 4.55], rh = 0.95;
    const ins = [["Thermal", "1 × 24 × 32", ORANGE], ["Echo spectrogram", "2 × 64 × 64", TEAL], ["Sonar features", "10 values", VIOLET]];
    const stems = [["Thermal stem", "192 grid tokens (12×16)"], ["Echo stem", "24 tokens"], ["Sonar stem", "4 tokens"]];
    for (let i = 0; i < 3; i++) {
      const c = ins[i][2], y = rowY[i];
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y, w: 2.1, h: rh, fill: { color: c }, line: { color: c }, rectRadius: 0.08 });
      text(s, [{ text: ins[i][0], options: { bold: true, breakLine: true } }, { text: ins[i][1] }], { x: 0.55, y, w: 2.0, h: rh, fontSize: 14, color: WHITE, align: "center", valign: "middle" });
      arrow(s, 2.62, y + rh / 2, 3.0, y + rh / 2, MUTE, 1.5);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 3.02, y, w: 2.35, h: rh, fill: { color: WHITE }, line: { color: c, width: 1.5 }, rectRadius: 0.08 });
      text(s, [{ text: stems[i][0], options: { bold: true, color: c, breakLine: true } }, { text: stems[i][1] }], { x: 3.07, y, w: 2.25, h: rh, fontSize: 14, align: "center", valign: "middle" });
      arrow(s, 5.39, y + rh / 2, 5.95, 3.82, MUTE, 1.5);
    }
    // backbone
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.97, y: 2.15, w: 2.75, h: 3.35, fill: { color: "FBEDE4" }, line: { color: ORANGE, width: 1.75 }, rectRadius: 0.1 });
    text(s, "Fusion backbone", { x: 6.02, y: 2.22, w: 2.65, h: 0.45, fontSize: 17, bold: true, color: ORANGE, align: "center" });
    text(s, "220 tokens × 320", { x: 6.02, y: 2.65, w: 2.65, h: 0.35, fontSize: 14, align: "center" });
    ["Depthwise local mixing", "8-head self-attention", "Gated feed-forward"].forEach((t, i) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.2, y: 3.1 + i * 0.58, w: 2.3, h: 0.48, fill: { color: WHITE }, line: { color: "E8B89A" }, rectRadius: 0.06 });
      text(s, t, { x: 6.2, y: 3.1 + i * 0.58, w: 2.3, h: 0.48, fontSize: 13, align: "center", valign: "middle" });
    });
    text(s, "× 14 sandwich blocks", { x: 6.02, y: 4.92, w: 2.65, h: 0.4, fontSize: 14, bold: true, color: ORANGE, align: "center" });
    arrow(s, 8.74, 3.82, 9.1, 3.82, MUTE, 1.75);
    // decoder
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 9.12, y: 2.8, w: 1.85, h: 2.05, fill: { color: WHITE }, line: { color: NAVY, width: 1.5 }, rectRadius: 0.08 });
    text(s, [{ text: "Decoder", options: { bold: true, color: NAVY, breakLine: true } }, { text: "4 PixelShuffle + SE stages", options: { breakLine: true } }, { text: "12×16 → 192×256" }],
      { x: 9.17, y: 2.8, w: 1.75, h: 2.05, fontSize: 13, align: "center", valign: "middle" });
    arrow(s, 10.99, 3.82, 11.2, 3.82, MUTE, 1.5);
    // skip
    s.addShape(pres.shapes.LINE, { x: 4.2, y: 1.95, w: 5.85, h: 0, line: { color: ORANGE, width: 1.25, dashType: "dash" } });
    s.addShape(pres.shapes.LINE, { x: 4.2, y: 1.95, w: 0, h: 0.2, line: { color: ORANGE, width: 1.25, dashType: "dash" } });
    arrow(s, 10.05, 1.95, 10.05, 2.78, ORANGE, 1.25);
    text(s, "thermal skip map 24×32", { x: 6.0, y: 1.63, w: 2.7, h: 0.3, fontSize: 12, color: ORANGE, align: "center" });
    // heads
    const heads = [["Grayscale", NAVY], ["Inverse depth", NAVY], ["Colour + confidence", GOLD]];
    heads.forEach(([t, c], i) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 11.22, y: 2.8 + i * 0.72, w: 1.65, h: 0.6, fill: { color: c }, line: { color: c }, rectRadius: 0.08 });
      text(s, t, { x: 11.22, y: 2.8 + i * 0.72, w: 1.65, h: 0.6, fontSize: 13, bold: true, color: WHITE, align: "center", valign: "middle" });
    });
    // stats row
    const st = [["≈27 M", "parameters"], ["220", "fused tokens"], ["14", "transformer blocks"], ["192×256", "output resolution"]];
    st.forEach(([n, l], i) => {
      const x = 0.9 + i * 3.0;
      text(s, n, { x, y: 5.68, w: 2.6, h: 0.55, fontSize: 26, bold: true, color: i === 0 ? GOLD : NAVY, align: "center", valign: "middle" });
      text(s, l, { x, y: 6.2, w: 2.6, h: 0.3, fontSize: 13, color: MUTE, align: "center" });
    });
    caption(s, nextFig("NOVISNet: per-sensor stems, a shared token backbone, and a convolutional decoder."), 0.6, 6.62, 12.1);
    notes(s, T3, "Each sensor has its own stem. Thermal becomes a 12 by 16 grid of 192 tokens plus a skip map; the echo spectrogram becomes 24 tokens; sonar becomes 4. All 220 tokens go through 14 blocks that mix locally, attend globally with 8 heads, and apply a gated feed-forward layer. A four-stage decoder upsamples to 192 by 256 and re-injects the thermal detail. Three heads predict grayscale, depth, and colour with a confidence. About 27 million parameters.");
  }

  // =========== 12. Missing sensors ===========
  {
    const s = content("METHODOLOGY (CONT'D)", "Missing sensors: learned mask tokens", "Methodology");
    card(s, 0.6, 1.8, 5.7, 1.45, "FBF6EA", "formula");
    text(s, "z = m · t + (1 − m) · τ", { x: 0.6, y: 1.9, w: 5.7, h: 0.75, fontSize: 30, bold: true, color: NAVY, align: "center", valign: "middle" });
    text(s, "t = sensor tokens,  m ∈ {0, 1} = sensor present,  τ = learned mask token", { x: 0.7, y: 2.7, w: 5.5, h: 0.4, fontSize: 13, color: MUTE, align: "center" });
    bullets(s, [
      [{ text: "One learned token per modality ", options: { bold: true } }, { text: "replaces an absent sensor's tokens" }],
      [{ text: "Modality dropout 0.3 ", options: { bold: true } }, { text: "in training: sensors are randomly hidden, so the model never relies on one" }],
      [{ text: "Thermal skip map is zeroed ", options: { bold: true } }, { text: "when thermal is absent — no stale detail leaks to the decoder" }],
      [{ text: "Same at run time: ", options: { bold: true } }, { text: "a sensor that fails on the device is simply masked — no retraining" }],
    ], { x: 0.6, y: 3.5, w: 5.7, h: 3.2, fontSize: 15, paraSpaceAfter: 10 });
    // token strip visual
    const groups = [["Thermal", 8, ORANGE], ["Echo", 4, TEAL], ["Sonar", 2, VIOLET]];
    const sq = 0.3, sg = 0.05;
    const drawRow = (y, maskEcho, label) => {
      text(s, label, { x: 6.9, y: y - 0.45, w: 5.9, h: 0.35, fontSize: 15, bold: true, color: NAVY });
      let x = 6.9;
      groups.forEach(([g, n, c]) => {
        for (let k = 0; k < n; k++) {
          const masked = maskEcho && g === "Echo";
          s.addShape(pres.shapes.RECTANGLE, { x, y, w: sq, h: sq, fill: { color: masked ? "C7CCD4" : c }, line: { color: WHITE, width: 0.5 } });
          if (masked) text(s, "τ", { x, y, w: sq, h: sq, fontSize: 13, bold: true, color: INK, align: "center", valign: "middle" });
          x += sq + sg;
        }
        x += 0.22;
      });
    };
    drawRow(2.3, false, "All sensors present");
    drawRow(3.75, true, "Echo missing → echo tokens replaced by τ");
    let lx = 6.9;
    groups.forEach(([g, n, c]) => {
      const w = n * (sq + sg) - sg;
      text(s, g, { x: lx, y: 4.17, w: Math.max(w, 0.9), h: 0.3, fontSize: 12, color: c, bold: true });
      lx += w + sg + 0.22;
    });
    card(s, 6.9, 4.85, 5.85, 1.6, TINT, "robust-note");
    await iconCircle(s, fa.FaShieldAlt, 7.1, 5.1, 0.75, NAVY);
    text(s, "One trained model serves every combination of {thermal, echo, sonar} — the property RQ3 tests.", { x: 8.05, y: 5.0, w: 4.55, h: 1.3, fontSize: 15, valign: "middle" });
    caption(s, nextFig("Token sequence with and without the echo sensor (token counts not to scale)."), 6.6, 6.55, 6.4);
    notes(s, T3, "Real sensors fail, so the model must cope. Every sensor has one learned mask token. If a sensor is absent, its tokens are replaced by that learned token. During training we hide each sensor 30 percent of the time, so the model learns not to depend on any one. This is already useful on our real data: when the node did not hear its own chirp, we mark the echo as missing instead of feeding noise.");
  }

  // =========== 13. Losses + training ===========
  {
    const s = content("METHODOLOGY (CONT'D)", "Losses and staged training", "Methodology");
    const rows = zebra([
      [HEAD("Output"), HEAD("Loss"), HEAD("Weight")],
      [CELL("Grayscale", { align: "left", bold: true }), CELL("L1 + SSIM + VGG16 perceptual", { align: "left" }), CELL("1 · 1 · 0.1")],
      [CELL("Inverse depth", { align: "left", bold: true }), CELL("Masked L1 + smoothness", { align: "left" }), CELL("λd = 1.0")],
      [CELL("Colour (ab)", { align: "left", bold: true }), CELL("Heteroscedastic L1 — learns its own confidence", { align: "left" }), CELL("λc = 0.5")],
      [CELL("Realism", { align: "left", bold: true }), CELL("PatchGAN hinge (fusion stage only)", { align: "left" }), CELL("λadv")],
    ]);
    caption(s, nextTab("Training objective per output head."), 0.6, 1.7, 6.6);
    s.addTable(rows, tableOpts(0.6, 2.05, 6.6, [1.7, 3.75, 1.15], { rowH: 0.6, fontSize: 14 }));
    const opt = "AdamW · lr 2×10⁻⁴ · weight decay 0.05 · batch 32 · bfloat16 · EMA 0.999 · one RTX 5070 Ti";
    card(s, 0.6, 5.25, 6.6, 1.2, TINT, "optim");
    text(s, [{ text: "Optimisation", options: { bold: true, color: NAVY, breakLine: true } }, { text: opt }], { x: 0.8, y: 5.35, w: 6.2, h: 1.0, fontSize: 14, valign: "middle" });
    // stages
    const st = [["A", "Thermal", "thermal → image", ORANGE], ["B", "Echo", "echo → depth", TEAL], ["C", "Fusion", "all sensors, dropout 0.3", NAVY], ["D", "Real capture", "fine-tune on our node", GOLD]];
    text(s, "Four training stages", { x: 7.7, y: 1.7, w: 5.0, h: 0.4, fontSize: 17, bold: true, color: NAVY });
    st.forEach(([k, n, d, c], i) => {
      const y = 2.2 + i * 1.08;
      circleNum(s, 7.7, y + 0.06, 0.75, k, c, WHITE, 22);
      text(s, n, { x: 8.65, y, w: 4.0, h: 0.42, fontSize: 17, bold: true, color: c });
      text(s, d, { x: 8.65, y: y + 0.42, w: 4.0, h: 0.42, fontSize: 14 });
      if (i < 3) s.addShape(pres.shapes.LINE, { x: 8.075, y: y + 0.83, w: 0, h: 0.3, line: { color: LINE, width: 2 } });
    });
    text(s, "Each stage starts from the previous stage's weights.", { x: 7.7, y: 6.6, w: 5.0, h: 0.35, fontSize: 13, italic: true, color: MUTE });
    notes(s, T3, "Each output has its own loss. Grayscale uses L1, SSIM and a perceptual loss; depth a masked L1 with smoothness; colour a loss that also learns how confident it is. The fusion stage can add an adversarial term. Training runs in four stages — thermal, echo, fusion, then our real captures — each starting from the previous weights. Akib will now present the experiments.");
  }

  // =========== 14. Experiments: stages ===========
  pres.addSection({ title: "Experiments" });
  {
    const s = content("EXPERIMENTS", "Four training stages, each answering one research question", "Experiments");
    const rows = zebra([
      [HEAD("Stage"), HEAD("Data"), HEAD("Supervises"), HEAD("Why it matters for NOVIS"), HEAD("RQ")],
      [CELL("A  Thermal", { bold: true, color: ORANGE, align: "left" }), CELL("LLVIP, KAIST, M3FD, RoadScene, TNO", { align: "left" }), CELL("grayscale, colour"), CELL("Learns heat → appearance from paired thermal/visible images", { align: "left" }), CELL("1")],
      [CELL("B  Echo", { bold: true, color: TEAL, align: "left" }), CELL("BatVision V2 — 7 locations, 3,120 triplets", { align: "left" }), CELL("depth, grayscale"), CELL("The only data in the project with depth ground truth", { align: "left" }), CELL("1")],
      [CELL("C  Fusion", { bold: true, color: NAVY, align: "left" }), CELL("Merged corpus, modality dropout 0.3", { align: "left" }), CELL("all heads"), CELL("Tests fusion gain and graceful degradation", { align: "left" }), CELL("2, 3")],
      [CELL("D  Prototype", { bold: true, color: GOLD, align: "left" }), CELL("NOVIS real capture — 31 scenes", { align: "left" }), CELL("grayscale"), CELL("Measures the domain gap to our own hardware", { align: "left" }), CELL("4")],
    ]);
    caption(s, nextTab("Experimental stages, data and purpose."), 0.6, 1.7, 12.1);
    s.addTable(rows, tableOpts(0.6, 2.05, 12.1, [1.7, 3.6, 1.75, 4.25, 0.8], { rowH: [0.55, 0.7, 0.7, 0.7, 0.7], fontSize: 14 }));
    const st = [["69,139", "public training samples"], ["2,808", "with depth ground truth"], ["≈4%", "depth-supervised share"]];
    st.forEach(([n, l], i) => {
      const x = 0.9 + i * 4.0;
      text(s, n, { x, y: 5.75, w: 3.5, h: 0.6, fontSize: 32, bold: true, color: i === 2 ? GOLD : NAVY, align: "center", valign: "middle" });
      text(s, l, { x, y: 6.35, w: 3.5, h: 0.32, fontSize: 14, color: MUTE, align: "center" });
    });
    notes(s, T4, "We train in four stages, each tied to a research question. Stage A learns thermal to image from five public paired datasets. Stage B uses BatVision, the only data with depth ground truth. Stage C fuses everything with sensor dropout to test fusion and robustness. Stage D uses our own captures to measure the real-hardware gap. Note that depth supervision is scarce: only about 4 percent of training samples have it.");
  }

  // =========== 15. Real-capture dataset (images) ===========
  {
    const s = content("EXPERIMENTS (CONT'D)", "Our real-capture dataset: 31 scenes, five locations", "Experiments");
    const lab = ["CLA-02 · Classroom", "GAR-06 · Garage", "GAM-01 · Game room", "OUT-01 · Outdoor", "CAN-03 · Canteen", "OUT-04 · Dark corner"];
    const pw = 1.9, ph = 1.425, pg = 0.06, colGap = 0.4, pairW = 2 * pw + pg;
    const x0 = (W - (3 * pairW + 2 * colGap)) / 2;
    for (let i = 0; i < 6; i++) {
      const c = i % 3, r = Math.floor(i / 3);
      const x = x0 + c * (pairW + colGap), y = 1.75 + r * 2.0;
      s.addImage({ path: IMG + `ph${i + 1}.jpg`, x, y, w: pw, h: ph });
      s.addImage({ path: IMG + `th${i + 1}.png`, x: x + pw + pg, y, w: pw, h: ph });
      text(s, lab[i], { x, y: y + ph + 0.05, w: pairW, h: 0.3, fontSize: 13, bold: true, color: NAVY, align: "center" });
    }
    caption(s, nextFig("Six of the 31 scenes: phone photo (target) beside what the wide thermal sensor saw."), 0.6, 5.72, 12.1);
    const st = [["31", "scenes"], ["925", "real samples"], ["5", "locations"], ["0 – 7", "people in view"], ["1 – 5 m", "distance"]];
    st.forEach(([n, l], i) => {
      const x = 0.75 + i * 2.4;
      text(s, n, { x, y: 6.05, w: 2.2, h: 0.5, fontSize: 26, bold: true, color: i === 0 ? GOLD : NAVY, align: "center", valign: "middle" });
      text(s, l, { x, y: 6.55, w: 2.2, h: 0.3, fontSize: 13, color: MUTE, align: "center" });
    });
    notes(s, T4, "This is the dataset we captured with our node on two days: 31 scenes in classrooms, a garage, a game room, outdoors and the canteen, 925 sensor samples, each scene with a phone photo. Notice that thermal shows people and warm objects clearly, but walls and chairs barely appear — thermal sees heat, not furniture.");
  }

  // =========== 16. Dataset composition charts ===========
  {
    const s = content("EXPERIMENTS (CONT'D)", "Dataset composition and leakage-safe split", "Experiments");
    s.addChart(pres.charts.BAR, [{ name: "Scenes", labels: ["Classroom", "Game room", "Garage", "Outdoor", "Canteen"], values: [9, 6, 6, 6, 4] }],
      Object.assign(chartBase("Scenes per location"), { x: 0.5, y: 1.7, w: 4.2, h: 4.2, barDir: "bar", chartColors: [NAVY], showValue: true, dataLabelPosition: "outEnd", showLegend: false, valAxisHidden: true, valGridLine: { style: "none" }, catAxisOrientation: "maxMin" }));
    s.addChart(pres.charts.DOUGHNUT, [{ name: "Samples", labels: ["Train", "Val (Canteen)", "Stress (> 4 m)"], values: [700, 125, 100] }],
      Object.assign(chartBase("Samples per split"), { x: 4.75, y: 1.7, w: 4.0, h: 4.2, chartColors: [NAVY, GOLD, ORANGE], holeSize: 55, showPercent: false, showValue: true, dataLabelColor: WHITE, showLegend: true, legendPos: "b" }));
    s.addChart(pres.charts.DOUGHNUT, [{ name: "Echo", labels: ["Echo usable", "Echo masked"], values: [516, 409] }],
      Object.assign(chartBase("Echo availability"), { x: 8.8, y: 1.7, w: 4.0, h: 4.2, chartColors: [TEAL, "C7CCD4"], holeSize: 55, showPercent: false, showValue: true, dataLabelColor: INK, showLegend: true, legendPos: "b" }));
    caption(s, nextFig("Composition of the real-capture set (31 scenes, 925 samples)."), 0.6, 5.95, 12.1);
    const pts = [
      [fa.FaLock, "Validation = a whole unseen location (Canteen, 4 scenes) — no room appears on both sides."],
      [fa.FaCopy, "Augmented copies (2,100 train samples, 62 images) are kept separate and never counted as data."],
    ];
    for (let i = 0; i < 2; i++) {
      const x = 0.6 + i * 6.15;
      await iconCircle(s, pts[i][0], x, 6.35, 0.5, i ? GOLD : NAVY);
      text(s, pts[i][1], { x: x + 0.62, y: 6.3, w: 5.4, h: 0.6, fontSize: 14, valign: "middle" });
    }
    notes(s, T4, "Classrooms are the largest group. We split by location, not by sample: the whole canteen is held out for validation, so the model is scored on a place it has never seen. Scenes beyond 4 metres, past the sonar's limit, form a separate stress split. The echo was usable on 516 of 925 samples; the rest are marked missing. Augmented copies are stored separately and never counted as real data.");
  }

  // =========== 17. Data quality ===========
  {
    const s = content("EXPERIMENTS (CONT'D)", "Image pre-processing and restoration", "Experiments");
    const st = [
      [fa.FaExchangeAlt, "Un-mirror", "Both thermal sensors deliver frames flipped left–right; a horizontal flip restores the true view."],
      [fa.FaChessBoard, "De-chess", "The MLX90640 reads two interleaved sub-pages; their offset is removed per frame (pattern-noise removal)."],
      [fa.FaTools, "Repair pixels", "Dead pixel (3,12) on BAB interpolated from its neighbours; biased pixels offset-corrected."],
      [fa.FaCompressArrowsAlt, "Normalise & resize", "Thermal scaled to [0, 1]; photo converted to CIELAB (L* and ab) at 192 × 256."],
      [fa.FaWaveSquare, "Echo → image", "Echo aligned to the chirp onset and turned into a 2 × 64 × 64 spectrogram."],
    ];
    const cw = 2.3, gap = 0.2, x0 = (W - (5 * cw + 4 * gap)) / 2;
    for (let i = 0; i < 5; i++) {
      const x = x0 + i * (cw + gap);
      card(s, x, 1.8, cw, 3.55, TINT, "dq-" + i);
      await iconCircle(s, st[i][0], x + cw / 2 - 0.42, 2.05, 0.84, NAVY);
      text(s, `${i + 1}. ${st[i][1]}`, { x: x + 0.1, y: 3.0, w: cw - 0.2, h: 0.45, fontSize: 17, bold: true, color: NAVY, align: "center" });
      text(s, st[i][2], { x: x + 0.18, y: 3.5, w: cw - 0.36, h: 1.75, fontSize: 14, align: "center" });
      if (i < 4) arrow(s, x + cw + 0.01, 3.55, x + cw + gap - 0.01, 3.55, MUTE, 1.5);
    }
    card(s, x0, 5.65, 5 * cw + 4 * gap, 0.95, "FBF6EA", "dq-check");
    await iconCircle(s, fa.FaCheck, x0 + 0.2, 5.8, 0.65, GOLD);
    text(s, "An automatic check then confirms image sizes, value ranges and no dead channels — and that no scene appears in both training and validation.",
      { x: x0 + 1.05, y: 5.7, w: 5 * cw + 4 * gap - 1.25, h: 0.85, fontSize: 15, valign: "middle" });
    notes(s, T4, "Before training, every image goes through a restoration chain: flip the mirrored thermal frames back, remove the sensor's chessboard pattern noise, interpolate the dead pixel from its neighbours, normalise the values, and convert the photo to CIELAB. The echo is aligned to the chirp and turned into a spectrogram image. An automatic check confirms the result and that no scene leaks between training and validation.");
  }

  // =========== 18. Targets ===========
  {
    const s = content("EXPERIMENTS (CONT'D)", "How we judge a score: targets from sensor physics", "Experiments");
    s.addChart(pres.charts.BAR, [{ name: "Average error", labels: ["10", "12.5", "15", "18", "20", "25", "30"], values: [81, 60, 45, 32, 26, 14, 8] }],
      Object.assign(chartBase("PSNR (dB) → average pixel error (of 255 levels)"), { x: 0.5, y: 1.7, w: 5.6, h: 4.3, barDir: "col", chartColors: [NAVY], showValue: true, dataLabelPosition: "outEnd", showLegend: false, valAxisMaxVal: 90, valAxisMinVal: 0, catAxisTitle: "PSNR (dB)", showCatAxisTitle: true, catAxisTitleFontSize: 12, catAxisTitleColor: "4B5563" }));
    caption(s, nextFig("PSNR is a log scale: 12.5 dB means each pixel is off by ≈60 of 255 levels."), 0.5, 6.05, 5.6);
    const rows = zebra([
      [HEAD("Metric"), HEAD("Floor"), HEAD("Working"), HEAD("Strong (goal)"), HEAD("Ceiling")],
      [CELL("PSNR (dB) ↑", { align: "left", bold: true }), CELL("12"), CELL("16"), CELL("19 – 21", { bold: true, color: NAVY }), CELL("≈25")],
      [CELL("SSIM ↑", { align: "left", bold: true }), CELL("0.30"), CELL("0.45"), CELL("0.62 – 0.72", { bold: true, color: NAVY }), CELL("≈0.80")],
      [CELL("Depth RMSE (m) ↓", { align: "left", bold: true }), CELL("1.5"), CELL("1.0"), CELL("0.55 – 0.75", { bold: true, color: NAVY }), CELL("≈0.35")],
      [CELL("δ1 (within 25%) ↑", { align: "left", bold: true }), CELL("0.45"), CELL("0.65"), CELL("0.80 – 0.87", { bold: true, color: NAVY }), CELL("≈0.92")],
    ]);
    caption(s, nextTab("Target tiers for the fusion stage (C)."), 6.6, 1.7, 6.2);
    s.addTable(rows, tableOpts(6.6, 2.05, 6.2, [2.0, 0.9, 1.0, 1.4, 0.9], { rowH: 0.55, fontSize: 14 }));
    bullets(s, [
      [{ text: "Ceiling: ", options: { bold: true } }, { text: "PSNR above ≈25 dB would mean memorising, not sensing — the 64× gap caps it" }],
      [{ text: "Not NYUv2: ", options: { bold: true } }, { text: "echo → depth is ambiguous, so camera depth leaderboards (δ1 > 0.85) are the wrong yardstick" }],
    ], { x: 6.6, y: 5.0, w: 6.2, h: 1.6, fontSize: 14, paraSpaceAfter: 8 });
    notes(s, T4, "To judge results honestly we set four tiers for each metric: floor, working, strong and ceiling. PSNR is logarithmic — at 12.5 dB each pixel is off by about 60 of 255 levels. Because of the 64-times gap, scores above about 25 dB would mean the model memorised rather than sensed. Shishir will now show where our runs stand.");
  }

  // =========== 19. Results ===========
  pres.addSection({ title: "Results" });
  {
    const s = content("RESULTS", "Where the trained runs stand", "Results");
    const rows = zebra([
      [HEAD("Model"), HEAD("Stage"), HEAD("Best epoch"), HEAD("PSNR"), HEAD("SSIM"), HEAD("RMSE (m)"), HEAD("δ1")],
      [CELL("Thermal · LLVIP", { align: "left" }), CELL("A"), CELL("3 / 60"), CELL("15.25"), CELL("0.446"), CELL("—"), CELL("—")],
      [CELL("Thermal · 5 datasets", { align: "left" }), CELL("A"), CELL("5 / 12"), CELL("12.43"), CELL("0.380"), CELL("—"), CELL("—")],
      [CELL("Echo · BatVision", { align: "left" }), CELL("B"), CELL("39 / 40"), CELL("12.39"), CELL("0.090"), CELL("1.203", { bold: true, color: TEAL }), CELL("0.632", { bold: true, color: TEAL })],
      [CELL("Fusion · all sensors", { align: "left" }), CELL("C"), CELL("6 / 12"), CELL("12.46"), CELL("0.401"), CELL("n/a*"), CELL("n/a*")],
    ]);
    caption(s, nextTab("Best epoch by validation loss for each run."), 0.6, 1.7, 6.3);
    s.addTable(rows, tableOpts(0.6, 2.05, 6.3, [1.85, 0.6, 0.95, 0.7, 0.7, 0.8, 0.7], { rowH: 0.55, fontSize: 13 }));
    text(s, "Validation sets differ (LLVIP 3,463 · merged 6,484 · BatVision 312), so rows are not directly comparable.  * fusion-stage depth not yet evaluated.",
      { x: 0.6, y: 4.95, w: 6.3, h: 0.7, fontSize: 12, color: MUTE });
    s.addChart(pres.charts.BAR, [
      { name: "Achieved", labels: ["Thermal · LLVIP", "Thermal · 5 sets", "Echo", "Fusion"], values: [15.25, 12.43, 12.39, 12.46] },
      { name: "Working target", labels: ["Thermal · LLVIP", "Thermal · 5 sets", "Echo", "Fusion"], values: [15, 15, 12, 16] },
      { name: "Strong target (low end)", labels: ["Thermal · LLVIP", "Thermal · 5 sets", "Echo", "Fusion"], values: [18, 18, 14, 19] },
    ], Object.assign(chartBase("PSNR (dB): achieved vs. targets"), { x: 7.2, y: 1.7, w: 5.6, h: 4.15, barDir: "col", barGrouping: "clustered", chartColors: [ORANGE, "9AA5B8", NAVY], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", dataLabelFontSize: 9, showLegend: true, legendPos: "b", valAxisMinVal: 0, valAxisMaxVal: 22 }));
    caption(s, nextFig("Each run's PSNR beside its stage's Working and Strong targets."), 7.2, 5.9, 5.6);
    card(s, 0.6, 5.85, 6.3, 0.95, "FBEDE4", "res-take");
    text(s, [{ text: "Takeaway: ", options: { bold: true, color: ORANGE } }, { text: "no run reaches Strong yet. Stage A is 3–5 dB and ≈0.2 SSIM short; Stage B depth is at Working." }],
      { x: 0.8, y: 5.9, w: 5.95, h: 0.85, fontSize: 14, valign: "middle" });
    notes(s, T5, "Here are our best checkpoints. The thermal runs reach 12 to 15 dB PSNR and around 0.4 SSIM — between the floor and working tiers, three to five dB short of our goal. The echo run is at the working tier for depth. The fusion run's image scores are similar to thermal, and its depth has not been evaluated yet. Honestly: nothing reaches the strong tier yet.");
  }

  // =========== 20. Depth ===========
  {
    const s = content("RESULTS (CONT'D)", "Echo → depth (Stage B) is the healthiest run", "Results");
    const tiers = ["Floor", "Working", "NOVIS", "Strong", "Ceiling"];
    const rm = Object.assign(chartBase("Depth RMSE (m) — lower is better"), { x: 0.5, y: 1.7, w: 6.0, h: 3.9, barDir: "col", chartColors: ["9AA5B8", "9AA5B8", ORANGE, NAVY, "4B5D80"], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00#", showLegend: false, valAxisMinVal: 0, valAxisMaxVal: 2.4 });
    s.addChart(pres.charts.BAR, [{ name: "RMSE", labels: tiers, values: [2.0, 1.2, 1.203, 0.7, 0.4] }], rm);
    const d1 = Object.assign(chartBase("δ1 (within 25% of truth) — higher is better"), { x: 6.85, y: 1.7, w: 6.0, h: 3.9, barDir: "col", chartColors: ["9AA5B8", "9AA5B8", ORANGE, NAVY, "4B5D80"], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00#", showLegend: false, valAxisMinVal: 0, valAxisMaxVal: 1 });
    s.addChart(pres.charts.BAR, [{ name: "delta1", labels: tiers, values: [0.35, 0.60, 0.632, 0.815, 0.90] }], d1);
    caption(s, nextFig("Stage B (BatVision validation, 312 samples) against the Stage B target tiers; Strong shown at mid-range."), 0.5, 5.62, 12.35);
    const pts = [
      [fa.FaChartLine, "Still improving", "Best at epoch 39 of 40 — monotonic, no instability."],
      [fa.FaRulerHorizontal, "What 1.2 m means", "At 4 m, a 'correct' δ1 pixel can still be 0.8 m out."],
      [fa.FaForward, "Cheapest gain", "Simply train Stage B for more epochs."],
    ];
    const cw = 3.95, gap = 0.25;
    for (let i = 0; i < 3; i++) {
      const x = 0.5 + i * (cw + gap);
      await iconCircle(s, pts[i][0], x, 6.05, 0.62, i === 0 ? TEAL : NAVY);
      text(s, [{ text: pts[i][1], options: { bold: true, color: NAVY, breakLine: true } }, { text: pts[i][2] }], { x: x + 0.75, y: 5.98, w: cw - 0.8, h: 0.85, fontSize: 14, valign: "middle" });
    }
    notes(s, T5, "Depth from sound is our strongest result. RMSE is 1.20 metres and delta-one is 0.63, right at the working tier. The run improved every epoch and was still improving when it stopped at 40 epochs, so the cheapest gain in the whole project is to train it longer.");
  }

  // =========== 21. Limitations ===========
  {
    const s = content("LIMITATIONS", "What limits the results today", "Results");
    const lim = [
      [fa.FaCompressArrowsAlt, "64× resolution gap", "Detail finer than 32×24 is learned prior, not measurement."],
      [fa.FaThermometerHalf, "Heat, not furniture", "A room at rest is one temperature: walls and chairs are nearly invisible."],
      [fa.FaVolumeMute, "Echo is fragile", "Ambiguous by nature, and unheard on 44% of real captures (409 / 925)."],
      [fa.FaRulerHorizontal, "Sonar reach", "Two narrow cones, 4 m maximum — the 5 m scenes go blind."],
      [fa.FaDatabase, "Small real set", "31 scenes over two days; 4 validation scenes give noisy metrics."],
      [fa.FaClipboardList, "Evaluation still open", "Fusion-stage depth and perceptual (LPIPS) scores not yet reported; thermal runs peak early."],
    ];
    const cw = 3.9, ch = 2.15, gx = 0.3, gy = 0.3, x0 = (W - (3 * cw + 2 * gx)) / 2;
    for (let i = 0; i < 6; i++) {
      const x = x0 + (i % 3) * (cw + gx), y = 1.8 + Math.floor(i / 3) * (ch + gy);
      card(s, x, y, cw, ch, TINT, "lim-" + i);
      await iconCircle(s, lim[i][0], x + 0.25, y + 0.25, 0.75, i < 3 ? RED : NAVY);
      text(s, lim[i][1], { x: x + 1.15, y: y + 0.25, w: cw - 1.3, h: 0.75, fontSize: 18, bold: true, color: NAVY, valign: "middle" });
      text(s, lim[i][2], { x: x + 0.25, y: y + 1.15, w: cw - 0.5, h: 0.9, fontSize: 15 });
    }
    text(s, "Red: limits of the sensors themselves.  Navy: limits of our data and evaluation, which we can fix.", { x: x0, y: 6.75, w: 12.3, h: 0.35, fontSize: 13, italic: true, color: MUTE });
    notes(s, T5, "The top row are limits of the sensors themselves: the 64-times resolution gap, thermal seeing heat rather than furniture, and an echo that is ambiguous and was not heard in 44 percent of our captures. The bottom row we can fix: sonar reach defines our stress split, the real dataset is still small, and fusion-stage depth and the perceptual score are still to be reported.");
  }

  // =========== 22. Future ===========
  {
    const s = content("FUTURE EXTENSIONS", "Planned next steps", "Results");
    const cols = [
      ["Next", NAVY, ["Evaluate fusion-stage depth", "Report perceptual quality (LPIPS)", "Train the echo stage longer", "Fill the modality ablation table"]],
      ["Then", TEAL, ["Stage D: fine-tune on our 925 real samples", "Stronger regularisation against early over-fitting", "Rendered depth (SoundSpaces) to grow depth data", "More capture sessions, more people and lighting"]],
      ["Later", GOLD, ["System metrics: obstacle recall > 95%, stairs > 98%", "End-to-end latency < 200 ms", "Compact edge model, int8, on a phone", "User study as a navigation aid"]],
    ];
    const cw = 3.95, gap = 0.25, x0 = (W - (3 * cw + 2 * gap)) / 2;
    cols.forEach(([h, c, items], i) => {
      const x = x0 + i * (cw + gap);
      s.addShape(pres.shapes.CHEVRON, { x, y: 1.8, w: cw, h: 0.75, fill: { color: c }, line: { color: c } });
      text(s, h, { x: x + 0.3, y: 1.8, w: cw - 0.6, h: 0.75, fontSize: 20, bold: true, color: WHITE, align: "center", valign: "middle" });
      card(s, x, 2.75, cw, 3.55, TINT, "fut-" + i);
      bullets(s, items, { x: x + 0.25, y: 2.95, w: cw - 0.45, h: 3.2, fontSize: 15, paraSpaceAfter: 12 });
    });
    text(s, "The ablation table (all sensors vs. each alone vs. pairs) is the single most important missing result — it is what RQ2 asks.",
      { x: x0, y: 6.5, w: 12.35, h: 0.45, fontSize: 14, italic: true, color: NAVY });
    notes(s, T5, "Next, we evaluate fusion-stage depth, report perceptual quality, train the echo stage longer, and fill in the ablation table — all sensors versus each alone — which is the evidence fusion needs. Then we fine-tune on our real captures and collect more scenes. Later we measure what a navigation aid needs, such as obstacle recall and latency, and move to a phone-sized model.");
  }

  // =========== 23. Conclusion ===========
  {
    const s = content("CONCLUSION", "Key takeaways", "Results");
    const pts = [
      ["01", "Camera-free sensing", "three low-cost sensors reconstruct coarse layout, warm bodies and depth"],
      ["02", "Robust by design", "mask tokens let one model run with any sensor missing"],
      ["03", "Real, honest data", "31 scenes / 925 samples, held-out location, augmentation kept separate"],
      ["04", "Where we stand", "echo depth at Working (RMSE 1.20 m, δ1 0.63); image metrics below Strong"],
      ["05", "What decides it next", "the ablation table and fine-tuning on our own hardware"],
    ];
    pts.forEach(([n, h, d], i) => {
      const y = 1.85 + i * 0.98;
      card(s, 0.6, y - 0.09, 12.1, 0.78, i === 3 ? "FBEDE4" : TINT, "concl-" + i);
      text(s, n, { x: 0.8, y, w: 0.9, h: 0.6, fontSize: 30, bold: true, color: GOLD, valign: "middle" });
      text(s, [{ text: h, options: { bold: true, color: NAVY } }, { text: "  —  " + d }], { x: 1.8, y, w: 10.8, h: 0.6, fontSize: 19, valign: "middle" });
    });
    notes(s, T5, "To conclude: three cheap sensors can recover coarse scene layout and depth without a camera; one model handles missing sensors; our real dataset is split honestly; depth from echo already reaches the working tier while image quality still has a gap; and the ablation study plus real-data fine-tuning are what come next. Thank you.");
  }

  // =========== 24. References ===========
  {
    const s = content("REFERENCES", "Works cited", "Results");
    const refs = [
      "[1] X. Jia et al., \"LLVIP: A Visible-infrared Paired Dataset for Low-light Vision,\" ICCV Workshops, 2021.",
      "[2] S. Hwang et al., \"Multispectral Pedestrian Detection: Benchmark Dataset and Baseline,\" CVPR, 2015.",
      "[3] J. Liu et al., \"Target-aware Dual Adversarial Learning and a Multi-scenario Multi-Modality Benchmark to Fuse Infrared and Visible for Object Detection,\" CVPR, 2022.",
      "[4] H. Xu et al., \"FusionDN: A Unified Densely Connected Network for Image Fusion,\" AAAI, 2020.",
      "[5] A. Toet, \"The TNO Multiband Image Data Collection,\" Data in Brief, 2017.",
      "[6] A. Brunetto, S. Hornauer, S. X. Yu, F. Moutarde, \"The Audio-Visual BatVision Dataset for Research on Sight and Sound,\" IROS, 2023.",
      "[7] C. Chen et al., \"SoundSpaces: Audio-Visual Navigation in 3D Environments,\" ECCV, 2020.",
      "[8] P. Isola et al., \"Image-to-Image Translation with Conditional Adversarial Networks,\" CVPR, 2017.",
      "[9] J. Johnson, A. Alahi, L. Fei-Fei, \"Perceptual Losses for Real-Time Style Transfer and Super-Resolution,\" ECCV, 2016.",
      "[10] A. Kendall, Y. Gal, \"What Uncertainties Do We Need in Bayesian Deep Learning for Computer Vision?\" NeurIPS, 2017.",
      "[11] Z. Wang et al., \"Image Quality Assessment: From Error Visibility to Structural Similarity,\" IEEE TIP, 2004.",
      "[12] R. Zhang et al., \"The Unreasonable Effectiveness of Deep Features as a Perceptual Metric,\" CVPR, 2018.",
    ];
    text(s, refs.map((r, i) => ({ text: r, options: { breakLine: i < refs.length - 1 } })), { x: 0.6, y: 1.75, w: 12.1, h: 5.1, fontSize: 14, paraSpaceAfter: 6 });
  }

  // =========== 25-26. Closing ===========
  {
    const s = pres.addSlide({ masterName: "CLOSING", sectionTitle: "Results" });
    s.addText("Thank You", { placeholder: "title" });
    const s2 = pres.addSlide({ masterName: "CLOSING", sectionTitle: "Results" });
    s2.addText("Any Questions?", { placeholder: "title" });
  }

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  await dropMidParagraphPPr(OUT);
  console.log("wrote", OUT);
})();
