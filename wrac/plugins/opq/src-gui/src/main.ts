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

  // --- rail: grouped parameter clusters -------------------------------
  const rail = el("rail");
  const ACCENTS = ["#4ff2d2", "#ff3fd4", "#ffe23d"];
  GROUPS.forEach((group, gi) => {
    const box = document.createElement("section");
    box.className = "pgroup";
    const head = document.createElement("header");
    const title = document.createElement("span");
    title.className = "pgroup-title";
    title.textContent = group.title;
    const caption = document.createElement("span");
    caption.className = "pgroup-caption";
    caption.textContent = group.caption;
    head.append(title, caption);
    box.appendChild(head);
    const body = document.createElement("div");
    body.className = "pgroup-body";
    for (const id of group.ids) {
      const spec = byId.get(id);
      if (spec) body.appendChild(makeControl(spec, bridge, registry, ACCENTS[gi]));
    }
    box.appendChild(body);
    rail.appendChild(box);
  });

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
  for (const spec of specs) {
    const state = await bridge.parameterState(spec.id);
    registry.get(spec.id)?.(state);
  }
  await bridge.onParameters((state) => {
    registry.get(state.parameterId)?.(state);
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
