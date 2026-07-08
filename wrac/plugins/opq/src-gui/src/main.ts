/**
 * OpenPitchQuant — frontend bootstrap.
 *
 * Builds the faceplate from the Rust parameter manifest, attaches the grove
 * (live analysis display), and wires both to the bridge. In a plain browser
 * the bridge runs demo mode: local parameters + a replayed engine trace.
 */
import { createBridge } from "./bridge";
import { type ControlRegistry, makeControl } from "./controls";
import { Grove } from "./grove";
import { installConsoleLogPipe } from "./nativeLog";
import { attachTooltip } from "./tooltip";
import type { FrontendRuntimeContext } from "./wracRuntime";
import { installNativeCursorBridge, installResizeBridge } from "./wracRuntime";
import "./style.css";

const bridge = createBridge();
if (bridge.native) {
  installConsoleLogPipe();
}

// Parameter grouping — the plate's three numbered clusters.
const GROUPS: { title: string; caption: string; ids: number[] }[] = [
  {
    title: "I · MAPPING",
    caption: "the character of the remap",
    ids: [1, 2, 3, 4, 15],
  },
  {
    title: "II · DE-MIX",
    caption: "how objects are carved from the spectrum",
    ids: [5, 7, 9, 14, 16, 13],
  },
  {
    title: "III · POLICY",
    caption: "edges, transitions, the unclaimed",
    ids: [10, 17, 12, 11, 6, 8],
  },
];

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`missing #${id}`);
  return node as T;
}

const registry: ControlRegistry = new Map();
const grove = new Grove(el<HTMLCanvasElement>("grove"));

// display mode switcher (persisted per WebView)
for (const chip of document.querySelectorAll<HTMLButtonElement>(
  "#mode-switch button",
)) {
  chip.addEventListener("click", () => {
    const mode = chip.dataset.mode === "strata" ? "strata" : "cosmos";
    grove.setMode(mode);
    try {
      localStorage.setItem("opq-mode", mode);
    } catch {
      /* private webview contexts may deny storage */
    }
    for (const other of document.querySelectorAll("#mode-switch button")) {
      other.classList.toggle("is-active", other === chip);
    }
  });
}
const urlParams = new URLSearchParams(location.search);
try {
  const saved = urlParams.get("mode") ?? localStorage.getItem("opq-mode");
  if (saved === "strata") {
    document
      .querySelector<HTMLButtonElement>('#mode-switch [data-mode="strata"]')
      ?.click();
  }
} catch {
  /* default mode stands */
}

function isEditableElement(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement ||
    (target instanceof HTMLElement && target.isContentEditable)
  );
}

function restoreHostFocusIfNeeded(target?: EventTarget | null): void {
  if (!bridge.native) return;
  if (
    isEditableElement(target ?? null) ||
    isEditableElement(document.activeElement)
  ) {
    return;
  }
  window.setTimeout(() => {
    if (isEditableElement(document.activeElement)) return;
    bridge.focusHost();
  }, 0);
}

if (import.meta.env.PROD) {
  window.addEventListener(
    "contextmenu",
    (event) => {
      if (
        event.target instanceof Element &&
        event.target.closest("input, textarea, [contenteditable]")
      ) {
        return;
      }
      event.preventDefault();
    },
    { capture: true },
  );
}

void (async () => {
  const metadata = await bridge.metadata();
  document.title = metadata.pluginName;
  el("masthead-meta").textContent =
    `${metadata.companyName} · v${metadata.version} · MIDI sidechain`;

  const specs = await bridge.manifest();
  const byId = new Map(specs.map((s) => [s.id, s]));

  // --- the shrine: hand-placed composition ------------------------------
  // [x, y, w, h, rotation°] on the 1120x800 plate. Overlaps are deliberate.
  const LAYOUT: Record<number, [number, number, number, number, number]> = {
    1: [726, 64, 300, 150, -1.5],
    2: [920, 180, 190, 95, 2],
    3: [726, 200, 180, 90, 1],
    15: [884, 262, 225, 112, -2],
    4: [726, 306, 152, 76, 2.5],
    5: [742, 398, 240, 120, -1],
    7: [968, 380, 148, 74, 1.5],
    9: [726, 494, 190, 95, -2],
    14: [906, 478, 205, 102, 1],
    16: [726, 584, 220, 110, -1.5],
    13: [952, 588, 165, 82, 2],
  };
  const wardensLayer = el("wardens");
  const ritesLayer = el("rites");
  const groveCanvas = el<HTMLCanvasElement>("grove");
  const onDrag = (active: boolean, control: HTMLElement) => {
    if (!active) {
      grove.setThread(null);
      return;
    }
    const c = control.getBoundingClientRect();
    const g = groveCanvas.getBoundingClientRect();
    const k = g.width / groveCanvas.clientWidth || 1;
    grove.setThread({
      x: (c.left + c.width / 2 - g.left) / k,
      y: (c.top + c.height / 2 - g.top) / k,
    });
  };
  for (const spec of specs) {
    if (spec.id === 0) continue;
    const control = makeControl(spec, bridge, registry, "#4ff2d2", onDrag);
    if (spec.kind === "choice") {
      ritesLayer.appendChild(control);
    } else {
      const pos = LAYOUT[spec.id];
      if (pos) {
        control.style.left = `${pos[0]}px`;
        control.style.top = `${pos[1]}px`;
        control.style.width = `${pos[2]}px`;
        control.style.height = `${pos[3]}px`;
        control.style.transform = `rotate(${pos[4]}deg)`;
      }
      wardensLayer.appendChild(control);
    }
  }

  // sediment: the strongest rejected candidates, pasted under everything —
  // the obsessive never throws anything away
  const SEDIMENT: [string, number, number, number, number][] = [
    ["sed0", 745, 118, 250, 8],
    ["sed1", 56, 84, 230, -6],
    ["sed2", 934, 540, 210, 12],
    ["sed3", 296, 606, 250, -9],
    ["sed4", 812, 434, 230, 5],
  ];
  const sedimentLayer = el("sediment");
  for (const [name, x, y, w, rot] of SEDIMENT) {
    const img = document.createElement("img");
    img.src = `/shrine/${name}.png`;
    img.style.left = `${x}px`;
    img.style.top = `${y}px`;
    img.style.width = `${w}px`;
    img.style.transform = `rotate(${rot}deg)`;
    sedimentLayer.appendChild(img);
  }

  // integer scale lock: the plate is 1120x800, always; the window can only
  // magnify it whole. Resize the host window to reach x2.
  const plate = el("plate");
  const legend = el("scale-legend");
  const fit = () => {
    const k = Math.max(
      1,
      Math.floor(Math.min(window.innerWidth / 1120, window.innerHeight / 800)),
    );
    plate.style.transform = `scale(${k})`;
    plate.style.left = `${Math.max(0, (window.innerWidth - 1120 * k) / 2)}px`;
    plate.style.top = `${Math.max(0, (window.innerHeight - 800 * k) / 2)}px`;
    legend.textContent = `scale ×${k} — locked to whole numbers; enlarge the window for ×${k + 1}`;
  };
  window.addEventListener("resize", fit);
  fit();

  // --- tooltips on the fixed chrome -------------------------------------
  attachTooltip(
    el("bypass"),
    "Latency-aligned bypass — clickless and PDC-correct.",
  );
  const cosmosChip = document.querySelector<HTMLElement>(
    '#mode-switch [data-mode="cosmos"]',
  );
  const strataChip = document.querySelector<HTMLElement>(
    '#mode-switch [data-mode="strata"]',
  );
  if (cosmosChip)
    attachTooltip(
      cosmosChip,
      "The mapping as a cosmogram: pitch class is angle, octave is radius. Stars sit at their output pitch, tethered to their source ghost.",
    );
  if (strataChip)
    attachTooltip(
      strataChip,
      "The time view: an echogram scrolling leftward — ribbons are mapped pitch, dashes the source, dust the residual.",
    );

  // --- bypass ----------------------------------------------------------
  const bypass = el<HTMLButtonElement>("bypass");
  const renderBypass = (on: boolean) =>
    bypass.classList.toggle("is-engaged", on);
  bypass.addEventListener("click", () => {
    const next = bypass.classList.contains("is-engaged") ? 0 : 1;
    bridge.beginGesture(0);
    bridge.setParameter(0, next);
    bridge.endGesture(0);
    renderBypass(next === 1);
    restoreHostFocusIfNeeded();
  });
  registry.set(0, (state) => renderBypass(state.value >= 0.5));

  // --- initial values + subscriptions ----------------------------------
  // The grove hears every parameter too — the display obeys the controls.
  for (const spec of specs) {
    const state = await bridge.parameterState(spec.id);
    registry.get(spec.id)?.(state);
    grove.setParam(spec.id, state.value);
  }
  await bridge.onParameters((state) => {
    registry.get(state.parameterId)?.(state);
    grove.setParam(state.parameterId, state.value);
  });

  let lastFrameAt = performance.now();
  // ?idle keeps the feed unsubscribed — for inspecting the idle state
  if (!urlParams.has("idle")) {
    await bridge.onViz((frames) => {
      lastFrameAt = performance.now();
      grove.push(frames);
    });
  }

  const engineInfo = await bridge.engineInfo();
  grove.setEngineInfo(engineInfo);

  el("demo-badge").hidden = bridge.native;

  // --- status strip ----------------------------------------------------
  const statusLeft = el("status-left");
  const statusRight = el("status-right");
  let host = "";
  if (bridge.native) {
    installNativeCursorBridge(
      await bridge.runtimeContext().catch(() => ({}) as FrontendRuntimeContext),
    );
    const ctx = await bridge.runtimeContext().catch(() => undefined);
    host = ctx?.hostName ? ` · ${ctx.hostName}` : "";
  }

  const NOTE_NAMES = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
  ];
  const updateStatus = () => {
    const head = grove.latest();
    if (head) {
      const pcs = new Set(head.grid.map((n) => n % 12));
      const gridText = head.grid.length
        ? `${[...pcs].sort((a, b) => a - b).map((pc) => NOTE_NAMES[pc]).join(" ")}${head.repeat ? " ⟳" : ""}`
        : "—";
      const resPct = head.in > 0 ? Math.round((head.res / head.in) * 100) : 0;
      statusLeft.textContent = `OBJ ${String(head.tracks.length).padStart(2, "0")} · FLUX ${head.flux.toFixed(2)} · RES ${resPct}% · GRID ${gridText}`;
    } else {
      statusLeft.textContent = "OBJ — · FLUX — · RES — · GRID —";
    }
    const sr = engineInfo.sampleRate
      ? `${(engineInfo.sampleRate / 1000).toFixed(1)}k`
      : "—";
    statusRight.textContent = `SR ${sr} · PDC ${engineInfo.latency}${host} · opq ${metadata.version}`;
  };
  window.setInterval(updateStatus, 100);
  updateStatus();

  // --- render loop ------------------------------------------------------
  const tick = (tMs: number) => {
    if (performance.now() - lastFrameAt > 400) grove.markStalled();
    grove.render(tMs);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);

  console.info("GUI initialization completed");
})();

installResizeBridge({
  resizeGrip: el<HTMLButtonElement>("resize-grip"),
  restoreHostFocus: restoreHostFocusIfNeeded,
});

window.addEventListener("pointerup", (event) => {
  restoreHostFocusIfNeeded(event.target);
});
