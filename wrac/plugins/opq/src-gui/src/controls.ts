/**
 * Parameter controls: SCADA data-blocks, not knobs.
 *
 * A continuous parameter is a bordered block with a big mono readout and a
 * hatched fill bar — drag anywhere (vertical or horizontal), wheel to trim,
 * double-click to reset, click the value to type. Choice parameters are
 * chunky chip rows. All ranges/labels come from the Rust manifest.
 */
import type { OpqBridge } from "./bridge";
import { formatValue } from "./bridge";
import type { ParamSpec, ParameterState } from "./types";

/** Short faceplate labels; full name stays in the tooltip. */
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

export type ControlRegistry = Map<number, (state: ParameterState) => void>;

export function makeControl(
  spec: ParamSpec,
  bridge: OpqBridge,
  registry: ControlRegistry,
): HTMLElement {
  const control =
    spec.kind === "choice"
      ? makeChoice(spec, bridge, registry)
      : makeBlock(spec, bridge, registry);
  // Mix is the hero; choice rows are single-line and take the full width.
  if (spec.id === 1 || spec.kind === "choice") {
    control.style.gridColumn = "span 2";
  }
  return control;
}

function makeBlock(
  spec: ParamSpec,
  bridge: OpqBridge,
  registry: ControlRegistry,
): HTMLElement {
  const root = document.createElement("div");
  root.className = "pblock";
  root.title = spec.name;

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

  const bar = document.createElement("div");
  bar.className = "pblock-bar";
  const fill = document.createElement("div");
  fill.className = "pblock-fill";
  bar.appendChild(fill);

  root.append(label, value, input, bar);

  let current = spec.default;
  let dragging = false;
  let gestureActive = false;
  let wheelTimer = 0;

  const range = spec.max - spec.min;
  const show = (v: number, text?: string) => {
    current = v;
    value.textContent = text ?? formatValue(spec, v);
    const norm = range > 0 ? (v - spec.min) / range : 0;
    fill.style.width = `${Math.round(norm * 1000) / 10}%`;
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
  root.title = spec.name;

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
