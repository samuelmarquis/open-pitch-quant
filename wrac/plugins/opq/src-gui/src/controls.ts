/**
 * Parameter controls: SCADA data-blocks whose faces are FIGURES — each
 * continuous parameter renders a tiny animated diagram of its own DSP
 * mechanism (see figures.ts). Drag anywhere on a block (shift = fine),
 * wheel to trim, double-click to reset, click the value to type. Choice
 * parameters are chip rows. Ranges/labels come from the Rust manifest;
 * hover any control for what it actually does.
 */
import type { OpqBridge } from "./bridge";
import { formatValue } from "./bridge";
import { FIGURES } from "./figures";
import { attachTooltip } from "./tooltip";
import type { ParamSpec, ParameterState } from "./types";

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
  1: "Wet/dry balance. The dry path is delay-matched, so any blend stays phase-coherent.",
  2: "Re-injects the source's own micro-pitch motion (vibrato, scoops) on top of the mapped note. 0% = robotic lock, 100% = the full human wobble, transposed.",
  3: "Portamento of the remap when a target changes. Even at 0 ms a ~30 ms micro-ramp keeps retunes from tearing.",
  4: "Crossfades each object's clean resynthesis toward a raw spectral translation — the 'wrong' algorithm, kept as a character knob.",
  5: "How many pitch objects the de-mixer may carve per frame. Same-pitch sources fuse into one object; leftovers become residual.",
  6: "What happens to spectral regions no object claimed: Off = they pass dry, On = they get snapped to the grid as raw regions.",
  7: "Tonality test for unowned regions before mapping (peak vs. surroundings). Higher = only clearly tonal content is eligible.",
  8: "Fate of regions that fail the tonality gate: Fresh = pass dry, Bypass = excluded from mapping entirely.",
  9: "Unowned mapping stops above this frequency — leaves air and sibilance untouched.",
  10: "Spectral-flux onset detector: attacks blend toward dry (hard hits reset synthesis). Off = drums get mapped too — worth hearing once.",
  11: "Repeat: held pitch CLASSES apply in every octave (spokes light up in COSMOS). Custom: exactly the notes you hold.",
  12: "Intelligent adds 40¢ of hysteresis toward the current target, so vibrato stops flapping between neighbors. Nearest is memoryless.",
  13: "100% preserves the stereo image (level AND timing) through retuning. Lower decorrelates partial phases per channel — width wash.",
  14: "Objects already within this many cents of their own chromatic pitch pass unmapped — in-tune content stays untouched.",
  15: "Holds the source's spectral envelope (the vowel) in place while the partials move underneath it.",
  16: "Keeps each region's between-partial bins (breath, noise, attack) at their source position. At 0 only pure retuned partials remain.",
  17: "Policy for a note's ambiguous first frames: Map quantizes immediately (slides step), Dry lets transitions pass at source pitch.",
};

export type ControlRegistry = Map<number, (state: ParameterState) => void>;

// One shared ambient clock repaints every figure (~12 fps; canvases are tiny).
const FIGURE_REDRAWS: (() => void)[] = [];
window.setInterval(() => {
  for (const redraw of FIGURE_REDRAWS) redraw();
}, 85);

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

  const fig = document.createElement("canvas");
  fig.className = "pblock-fig";

  root.append(label, value, input, fig);

  let current = spec.default;
  let dragging = false;
  let gestureActive = false;
  let wheelTimer = 0;

  const range = spec.max - spec.min;
  const figCtx = fig.getContext("2d");
  const renderer = FIGURES[spec.id];
  const born = performance.now();

  const drawFigure = () => {
    if (!figCtx || !renderer) return;
    const dpr = window.devicePixelRatio || 1;
    const cw = fig.clientWidth;
    const ch = fig.clientHeight;
    if (cw === 0) return;
    if (fig.width !== cw * dpr || fig.height !== ch * dpr) {
      fig.width = cw * dpr;
      fig.height = ch * dpr;
    }
    figCtx.save();
    figCtx.scale(dpr, dpr);
    figCtx.clearRect(0, 0, cw, ch);
    figCtx.lineWidth = 1;
    renderer({
      ctx: figCtx,
      w: cw,
      h: ch,
      v: range > 0 ? (current - spec.min) / range : 0,
      t: (performance.now() - born) / 1000,
      color: accent,
    });
    figCtx.restore();
  };
  FIGURE_REDRAWS.push(drawFigure);

  const show = (v: number, text?: string) => {
    current = v;
    value.textContent = text ?? formatValue(spec, v);
    drawFigure();
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
