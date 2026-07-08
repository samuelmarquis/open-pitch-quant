/**
 * Parameter controls: reliquary blocks. Each continuous parameter is kept
 * by a Warden from the Meltdown Bestiary — a specimen painted in two
 * aspects (Flux-generated, unmulted onto the void), crossfaded by the
 * value. Three heroes wake into WAN-generated motion while dragged.
 * Drag anywhere (shift = fine), wheel to trim, double-click to reset,
 * click the value to type. Hover for the Warden's name and its mechanism.
 */
import type { OpqBridge } from "./bridge";
import { formatValue } from "./bridge";
import { attachTooltip } from "./tooltip";
import type { ParamSpec, ParameterState } from "./types";

/** The Meltdown Bestiary: each continuous parameter is kept by a Warden,
 * painted in two aspects. The block face crossfades between them; three
 * heroes wake into motion while dragged. */
const WARDENS: Record<number, { slug: string; name: string; video?: boolean }> = {
  1: { slug: "mix", name: "the Vessel", video: true },
  2: { slug: "feel", name: "the Tremble", video: true },
  3: { slug: "glide", name: "the Stair" },
  4: { slug: "grit", name: "the Burr", video: true },
  5: { slug: "voices", name: "the Choir" },
  7: { slug: "gate", name: "the Door" },
  9: { slug: "ceiling", name: "the Sky" },
  13: { slug: "cohere", name: "the Twins" },
  14: { slug: "thresh", name: "the Mercy" },
  15: { slug: "formant", name: "the Mask" },
  16: { slug: "carry", name: "the Burden" },
};

/** Short faceplate labels; the mechanism lives in the tooltip. */
const SHORT_LABELS: Record<number, string> = {
  0: "BYPASS",
  1: "MIX",
  2: "FEEL",
  3: "GLIDE",
  4: "GRIT",
  5: "VOICES",
  6: "MAP UNOWNED",
  7: "GATE",
  8: "GATE MODE",
  9: "CEILING",
  10: "TRANSIENT",
  11: "SCOPE",
  12: "ROUNDING",
  13: "COHERE",
  14: "THRESH",
  15: "FORMANT",
  16: "CARRY",
  17: "TRANSITIONS",
};

const TIPS: Record<number, string> = {
  0: "Latency-aligned bypass — the dry path runs through the same delay, so switching never clicks or phases.",
  1: "THE VESSEL · Wet/dry balance. The dry path is delay-matched, so any blend stays phase-coherent.",
  2: "THE TREMBLE · Re-injects the source's own micro-pitch motion (vibrato, scoops) on top of the mapped note. 0% = robotic lock, 100% = the full human wobble, transposed.",
  3: "THE STAIR · Portamento of the remap when a target changes. Even at 0 ms a ~30 ms micro-ramp keeps retunes from tearing.",
  4: "THE BURR · Crossfades each object's clean resynthesis toward a raw spectral translation — the 'wrong' algorithm, kept as a character knob.",
  5: "THE CHOIR · How many pitch objects the de-mixer may carve per frame. Same-pitch sources fuse into one object; leftovers become residual.",
  6: "What happens to spectral regions no object claimed: Off = they pass dry, On = they get snapped to the grid as raw regions.",
  7: "THE DOOR · Tonality test for unowned regions before mapping (peak vs. surroundings). Higher = only clearly tonal content is eligible.",
  8: "Fate of regions that fail the tonality gate: Fresh = pass dry, Bypass = excluded from mapping entirely.",
  9: "THE SKY · Unowned mapping stops above this frequency — leaves air and sibilance untouched.",
  10: "Spectral-flux onset detector: attacks blend toward dry (hard hits reset synthesis). Off = drums get mapped too — worth hearing once.",
  11: "Repeat: held pitch CLASSES apply in every octave (spokes light up in COSMOS). Custom: exactly the notes you hold.",
  12: "Intelligent adds 40¢ of hysteresis toward the current target, so vibrato stops flapping between neighbors. Nearest is memoryless.",
  13: "THE TWINS · 100% preserves the stereo image (level AND timing) through retuning. Lower decorrelates partial phases per channel — width wash.",
  14: "THE MERCY · Objects already within this many cents of their own chromatic pitch pass unmapped — in-tune content stays untouched.",
  15: "THE MASK · Holds the source's spectral envelope (the vowel) in place while the partials move underneath it.",
  16: "THE BURDEN · Keeps each region's between-partial bins (breath, noise, attack) at their source position. At 0 only pure retuned partials remain.",
  17: "Policy for a note's ambiguous first frames: Map quantizes immediately (slides step), Dry lets transitions pass at source pitch.",
};

export type ControlRegistry = Map<number, (state: ParameterState) => void>;

export function makeControl(
  spec: ParamSpec,
  bridge: OpqBridge,
  registry: ControlRegistry,
  accent: string,
): HTMLElement {
  const control =
    spec.kind === "choice"
      ? makeChoice(spec, bridge, registry)
      : makeBlock(spec, bridge, registry, accent);
  // Mix is the hero; choice rows are single-line and take the full width.
  if (spec.id === 1 || spec.kind === "choice") {
    control.style.gridColumn = "span 2";
  }
  const tip = TIPS[spec.id];
  if (tip) attachTooltip(control, tip);
  return control;
}

function makeBlock(
  spec: ParamSpec,
  bridge: OpqBridge,
  registry: ControlRegistry,
  accent: string,
): HTMLElement {
  const root = document.createElement("div");
  root.className = "pblock";

  const label = document.createElement("div");
  label.className = "pblock-label";
  label.textContent = SHORT_LABELS[spec.id] ?? spec.name.toUpperCase();

  const value = document.createElement("button");
  value.className = "pblock-value";
  value.type = "button";

  const input = document.createElement("input");
  input.className = "pblock-input";
  input.type = "text";
  input.hidden = true;

  const warden = WARDENS[spec.id];
  const face = document.createElement("canvas");
  face.className = "pblock-face";
  const loImg = new Image();
  const hiImg = new Image();
  if (warden) {
    loImg.src = `/specimens/${warden.slug}_lo.png`;
    hiImg.src = `/specimens/${warden.slug}_hi.png`;
  }
  let video: HTMLVideoElement | undefined;
  if (warden?.video) {
    video = document.createElement("video");
    video.className = "pblock-video";
    video.src = `/specimens/${warden.slug}_drag.mp4`;
    video.loop = true;
    video.muted = true;
    video.playsInline = true;
    video.hidden = true;
    video.addEventListener("error", () => video?.remove());
  }
  const wardenTag = document.createElement("span");
  wardenTag.className = "pblock-warden";
  wardenTag.textContent = warden?.name ?? "";

  root.append(face);
  if (video) root.append(video);
  root.append(label, value, input, wardenTag);

  let current = spec.default;
  let dragging = false;
  let gestureActive = false;
  let wheelTimer = 0;

  const range = spec.max - spec.min;
  const faceCtx = face.getContext("2d");

  const coverDraw = (img: HTMLImageElement, cw: number, ch: number) => {
    if (!faceCtx || !img.complete || img.naturalWidth === 0) return;
    const scale = Math.max(cw / img.naturalWidth, ch / img.naturalHeight);
    const dw = img.naturalWidth * scale;
    const dh = img.naturalHeight * scale;
    faceCtx.drawImage(img, (cw - dw) / 2, (ch - dh) / 2, dw, dh);
  };

  const drawFace = () => {
    if (!faceCtx || !warden) return;
    const dpr = window.devicePixelRatio || 1;
    const cw = face.clientWidth;
    const ch = face.clientHeight;
    if (cw === 0) return;
    if (face.width !== cw * dpr || face.height !== ch * dpr) {
      face.width = cw * dpr;
      face.height = ch * dpr;
    }
    const v = range > 0 ? (current - spec.min) / range : 0;
    faceCtx.save();
    faceCtx.scale(dpr, dpr);
    faceCtx.clearRect(0, 0, cw, ch);
    faceCtx.globalAlpha = 1 - v;
    coverDraw(loImg, cw, ch);
    faceCtx.globalAlpha = v;
    coverDraw(hiImg, cw, ch);
    // scrim so the readout stays legible over the specimen
    faceCtx.globalAlpha = 1;
    const scrim = faceCtx.createLinearGradient(0, 0, 0, ch);
    scrim.addColorStop(0, "rgba(0,0,0,0.55)");
    scrim.addColorStop(0.55, "rgba(0,0,0,0.10)");
    scrim.addColorStop(1, "rgba(0,0,0,0.30)");
    faceCtx.fillStyle = scrim;
    faceCtx.fillRect(0, 0, cw, ch);
    faceCtx.restore();
  };
  loImg.addEventListener("load", drawFace);
  hiImg.addEventListener("load", drawFace);

  const show = (v: number, text?: string) => {
    current = v;
    value.textContent = text ?? formatValue(spec, v);
    drawFace();
  };
  show(spec.default);

  registry.set(spec.id, (state) => {
    if (dragging || !input.hidden) return; // don't fight the hand
    show(state.value, state.text);
  });

  const clamp = (v: number) =>
    Math.min(spec.max, Math.max(spec.min, spec.stepped ? Math.round(v) : v));

  const apply = (v: number) => {
    const next = clamp(v);
    show(next);
    bridge.setParameter(spec.id, next);
  };

  const beginGesture = () => {
    if (gestureActive) return;
    gestureActive = true;
    bridge.beginGesture(spec.id);
  };
  const endGesture = () => {
    if (!gestureActive) return;
    gestureActive = false;
    bridge.endGesture(spec.id);
  };

  let startX = 0;
  let startY = 0;
  let startValue = 0;

  root.addEventListener("pointerdown", (event) => {
    if (event.target === value || event.target === input) return;
    dragging = true;
    startX = event.clientX;
    startY = event.clientY;
    startValue = current;
    root.setPointerCapture(event.pointerId);
    root.classList.add("is-dragging");
    if (video?.isConnected) {
      video.hidden = false;
      void video.play().catch(() => undefined);
    }
    beginGesture();
  });

  root.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    const scale = event.shiftKey ? 0.1 : 1;
    const px = event.clientX - startX + (startY - event.clientY);
    apply(startValue + (px / 220) * range * scale);
  });

  const finish = (event: PointerEvent) => {
    if (!dragging) return;
    dragging = false;
    root.releasePointerCapture(event.pointerId);
    root.classList.remove("is-dragging");
    if (video) {
      video.hidden = true;
      video.pause();
    }
    endGesture();
  };
  root.addEventListener("pointerup", finish);
  root.addEventListener("pointercancel", finish);

  root.addEventListener("dblclick", (event) => {
    event.preventDefault();
    void bridge.resetParameter(spec.id).then((state) => {
      show(state.value, state.text);
    });
  });

  root.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      beginGesture();
      const scale = event.shiftKey ? 0.1 : 1;
      apply(current - (event.deltaY / 600) * range * scale);
      window.clearTimeout(wheelTimer);
      wheelTimer = window.setTimeout(endGesture, 160);
    },
    { passive: false },
  );

  const enterText = () => {
    input.hidden = false;
    value.hidden = true;
    input.value = (value.textContent ?? "").trim();
    input.focus();
    input.select();
  };
  const leaveText = () => {
    input.hidden = true;
    value.hidden = false;
  };
  value.addEventListener("click", enterText);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      const text = input.value;
      leaveText();
      void bridge
        .setParameterText(spec.id, text)
        .then((state) => show(state.value, state.text))
        .catch(() => undefined);
    }
    if (event.key === "Escape") {
      event.preventDefault();
      leaveText();
    }
  });
  input.addEventListener("blur", leaveText);

  return root;
}

function makeChoice(
  spec: ParamSpec,
  bridge: OpqBridge,
  registry: ControlRegistry,
): HTMLElement {
  const root = document.createElement("div");
  root.className = "pblock pblock-choice";

  const label = document.createElement("div");
  label.className = "pblock-label";
  label.textContent = SHORT_LABELS[spec.id] ?? spec.name.toUpperCase();

  const chips = document.createElement("div");
  chips.className = "chip-row";

  const buttons: HTMLButtonElement[] = [];
  (spec.choices ?? []).forEach((choice, index) => {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.type = "button";
    chip.textContent = choice.toUpperCase();
    chip.addEventListener("click", () => {
      bridge.beginGesture(spec.id);
      bridge.setParameter(spec.id, index);
      bridge.endGesture(spec.id);
      select(index);
    });
    buttons.push(chip);
    chips.appendChild(chip);
  });

  const select = (index: number) => {
    buttons.forEach((b, i) => b.classList.toggle("is-active", i === index));
  };
  select(Math.round(spec.default));

  registry.set(spec.id, (state) => {
    select(Math.round(state.value));
  });

  root.append(label, chips);
  return root;
}
