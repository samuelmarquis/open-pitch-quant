/**
 * The seam between the UI and its data source.
 *
 * Inside the plugin (wxp WebView) every call crosses to Rust via
 * `@novonotes/webview-bridge`. In a plain browser (design work, demos sent to
 * friends) the DemoBridge stands in: parameters echo locally and the analysis
 * feed replays a real engine trace of the phylovox test clip.
 */
import { Channel, detectEnvironment, invoke } from "@novonotes/webview-bridge";
import { demoFrames } from "./demoTrace";
import type {
  EngineInfo,
  ParamSpec,
  ParameterState,
  PluginMetadata,
  VizFrame,
} from "./types";

export type FrontendRuntimeContext = {
  os?: string;
  pluginFormat?: string;
  hostFamily?: string;
  hostName?: string;
  processName?: string;
};

export interface OpqBridge {
  readonly native: boolean;
  metadata(): Promise<PluginMetadata>;
  manifest(): Promise<ParamSpec[]>;
  engineInfo(): Promise<EngineInfo>;
  runtimeContext(): Promise<FrontendRuntimeContext>;
  focusHost(): void;
  parameterState(id: number): Promise<ParameterState>;
  setParameter(id: number, value: number): void;
  setParameterText(id: number, text: string): Promise<ParameterState>;
  resetParameter(id: number): Promise<ParameterState>;
  beginGesture(id: number): void;
  endGesture(id: number): void;
  /** Subscribe to parameter pushes. Returns an unsubscribe function. */
  onParameters(cb: (state: ParameterState) => void): Promise<() => void>;
  /** Subscribe to analysis frames. Returns an unsubscribe function. */
  onViz(cb: (frames: VizFrame[]) => void): Promise<() => void>;
}

export function createBridge(): OpqBridge {
  return detectEnvironment() === "wxp" ? new NativeBridge() : new DemoBridge();
}

// ---------------------------------------------------------------------------
// Native: thin typed wrapper over invoke()/Channel
// ---------------------------------------------------------------------------

type VizPayload = {
  type: "viz-frames";
  sampleRate: number;
  hop: number;
  frames: VizFrame[];
};

class NativeBridge implements OpqBridge {
  readonly native = true;

  metadata(): Promise<PluginMetadata> {
    return invoke<PluginMetadata>("get_plugin_metadata");
  }

  async manifest(): Promise<ParamSpec[]> {
    const res = await invoke<{ params: ParamSpec[] }>("get_parameter_manifest");
    return res.params;
  }

  engineInfo(): Promise<EngineInfo> {
    return invoke<EngineInfo>("get_engine_info");
  }

  runtimeContext(): Promise<FrontendRuntimeContext> {
    return invoke<FrontendRuntimeContext>("get_frontend_runtime_context");
  }

  focusHost(): void {
    void invoke("focus_host_window");
  }

  parameterState(id: number): Promise<ParameterState> {
    return invoke<ParameterState>("get_parameter_state", { parameterId: id });
  }

  setParameter(id: number, value: number): void {
    void invoke("set_parameter_value", { parameterId: id, value });
  }

  setParameterText(id: number, text: string): Promise<ParameterState> {
    return invoke<ParameterState>("set_parameter_text", {
      parameterId: id,
      text,
    });
  }

  resetParameter(id: number): Promise<ParameterState> {
    return invoke<ParameterState>("reset_parameter_to_default", {
      parameterId: id,
    });
  }

  beginGesture(id: number): void {
    void invoke("begin_parameter_gesture", { parameterId: id });
  }

  endGesture(id: number): void {
    void invoke("end_parameter_gesture", { parameterId: id });
  }

  async onParameters(cb: (state: ParameterState) => void): Promise<() => void> {
    const channel = new Channel<ParameterState>((message) => {
      if (message && message.type === "parameter-value") {
        cb(message);
      }
    });
    const sub = await invoke<{ subscriptionId: number }>(
      "subscribe_parameters",
      { channel },
    );
    return () => {
      void invoke("unsubscribe_gui_subscription", {
        subscriptionId: sub.subscriptionId,
      });
    };
  }

  async onViz(cb: (frames: VizFrame[]) => void): Promise<() => void> {
    const channel = new Channel<VizPayload>((message) => {
      if (message && message.type === "viz-frames" && message.frames.length) {
        cb(message.frames);
      }
    });
    const sub = await invoke<{ subscriptionId: number }>("subscribe_viz", {
      channel,
    });
    return () => {
      void invoke("unsubscribe_gui_subscription", {
        subscriptionId: sub.subscriptionId,
      });
    };
  }
}

// ---------------------------------------------------------------------------
// Demo: local parameter echo + replayed engine trace
// ---------------------------------------------------------------------------

/** Mirror of the Rust spec table — demo mode only; the plugin always uses the
 * live manifest. Keep in sync with src-plugin/src/plugin/params.rs. */
const DEMO_SPECS: ParamSpec[] = [
  { id: 0, name: "Bypass", min: 0, max: 1, default: 0, stepped: true, kind: "choice", unit: "", choices: ["Off", "On"] },
  { id: 1, name: "Mix", min: 0, max: 1, default: 1, stepped: false, kind: "percent", unit: "%", choices: null },
  { id: 2, name: "Feel", min: 0, max: 1, default: 0.35, stepped: false, kind: "percent", unit: "%", choices: null },
  { id: 3, name: "Glide", min: 0, max: 0.5, default: 0, stepped: false, kind: "seconds", unit: "ms", choices: null },
  { id: 4, name: "Grit", min: 0, max: 1, default: 0, stepped: false, kind: "percent", unit: "%", choices: null },
  { id: 5, name: "Voices", min: 1, max: 12, default: 6, stepped: true, kind: "integer", unit: "", choices: null },
  { id: 6, name: "Map Unowned", min: 0, max: 1, default: 0, stepped: true, kind: "choice", unit: "", choices: ["Off", "On"] },
  { id: 7, name: "Tonality Gate", min: 0, max: 6, default: 0, stepped: false, kind: "integer", unit: "", choices: null },
  { id: 8, name: "Gate Mode", min: 0, max: 1, default: 0, stepped: true, kind: "choice", unit: "", choices: ["Fresh", "Bypass"] },
  { id: 9, name: "Map Ceiling", min: 1000, max: 20000, default: 5000, stepped: false, kind: "hertz", unit: "Hz", choices: null },
  { id: 10, name: "Transient Bypass", min: 0, max: 1, default: 1, stepped: true, kind: "choice", unit: "", choices: ["Off", "On"] },
  { id: 11, name: "MIDI Scope", min: 0, max: 1, default: 0, stepped: true, kind: "choice", unit: "", choices: ["Repeat", "Custom"] },
  { id: 12, name: "Rounding", min: 0, max: 1, default: 0, stepped: true, kind: "choice", unit: "", choices: ["Intelligent", "Nearest"] },
  { id: 13, name: "Stereo Coherence", min: 0, max: 1, default: 1, stepped: false, kind: "percent", unit: "%", choices: null },
  { id: 14, name: "Threshold", min: 0, max: 100, default: 0, stepped: false, kind: "cents", unit: "ct", choices: null },
  { id: 15, name: "Formant Preserve", min: 0, max: 1, default: 0, stepped: false, kind: "percent", unit: "%", choices: null },
  { id: 16, name: "Residual Carry", min: 0, max: 1, default: 1, stepped: false, kind: "percent", unit: "%", choices: null },
  { id: 17, name: "Transitions", min: 0, max: 1, default: 0, stepped: true, kind: "choice", unit: "", choices: ["Map", "Dry"] },
];

export function formatValue(spec: ParamSpec, value: number): string {
  switch (spec.kind) {
    case "percent":
      return `${Math.round(value * 100)} %`;
    case "seconds":
      return `${Math.round(value * 1000)} ms`;
    case "hertz":
      return `${Math.round(value)} Hz`;
    case "cents":
      return `${Math.round(value)} ct`;
    case "integer":
      return `${Math.round(value)}`;
    case "choice": {
      const names = spec.choices ?? [];
      return names[Math.min(Math.round(value), names.length - 1)] ?? `${value}`;
    }
  }
}

class DemoBridge implements OpqBridge {
  readonly native = false;
  private values = new Map<number, number>();
  private paramSubs = new Set<(state: ParameterState) => void>();
  private vizSubs = new Set<(frames: VizFrame[]) => void>();
  private player: number | undefined;

  constructor() {
    for (const spec of DEMO_SPECS) {
      this.values.set(spec.id, spec.default);
    }
  }

  private spec(id: number): ParamSpec {
    const spec = DEMO_SPECS.find((s) => s.id === id);
    if (!spec) throw new Error(`unknown parameter ${id}`);
    return spec;
  }

  private state(id: number): ParameterState {
    const spec = this.spec(id);
    const value = this.values.get(id) ?? spec.default;
    return {
      type: "parameter-value",
      parameterId: id,
      value,
      text: formatValue(spec, value),
    };
  }

  private apply(id: number, value: number): ParameterState {
    const spec = this.spec(id);
    this.values.set(id, Math.min(spec.max, Math.max(spec.min, value)));
    const state = this.state(id);
    for (const cb of this.paramSubs) cb(state);
    return state;
  }

  metadata(): Promise<PluginMetadata> {
    return Promise.resolve({
      pluginId: "org.open-pitch-quant.opq",
      pluginName: "OpenPitchQuant",
      companyName: "open-pitch-quant",
      version: "0.1.0-demo",
    });
  }

  manifest(): Promise<ParamSpec[]> {
    return Promise.resolve(DEMO_SPECS);
  }

  engineInfo(): Promise<EngineInfo> {
    return Promise.resolve({ sampleRate: 44100, hop: 1024, latency: 4096 });
  }

  runtimeContext(): Promise<FrontendRuntimeContext> {
    return Promise.resolve({ os: "browser", hostName: "demo" });
  }

  focusHost(): void {}

  parameterState(id: number): Promise<ParameterState> {
    return Promise.resolve(this.state(id));
  }

  setParameter(id: number, value: number): void {
    this.apply(id, value);
  }

  setParameterText(id: number, text: string): Promise<ParameterState> {
    const spec = this.spec(id);
    if (spec.choices) {
      const idx = spec.choices.findIndex(
        (c) => c.toLowerCase() === text.trim().toLowerCase(),
      );
      if (idx >= 0) return Promise.resolve(this.apply(id, idx));
    }
    let v = Number.parseFloat(text);
    if (Number.isNaN(v)) return Promise.resolve(this.state(id));
    if (spec.kind === "percent") v /= 100;
    if (spec.kind === "seconds") v /= 1000;
    return Promise.resolve(this.apply(id, v));
  }

  resetParameter(id: number): Promise<ParameterState> {
    return Promise.resolve(this.apply(id, this.spec(id).default));
  }

  beginGesture(): void {}
  endGesture(): void {}

  onParameters(cb: (state: ParameterState) => void): Promise<() => void> {
    this.paramSubs.add(cb);
    return Promise.resolve(() => this.paramSubs.delete(cb));
  }

  onViz(cb: (frames: VizFrame[]) => void): Promise<() => void> {
    this.vizSubs.add(cb);
    if (this.player === undefined) this.startPlayer();
    return Promise.resolve(() => this.vizSubs.delete(cb));
  }

  /** Replays the baked trace at wall-clock pace, looping. */
  private startPlayer(): void {
    const frames = demoFrames();
    const span = frames[frames.length - 1].time;
    let cursor = 0;
    let clock = 0;
    let last = performance.now();
    this.player = window.setInterval(() => {
      const now = performance.now();
      clock += (now - last) / 1000;
      last = now;
      if (clock > span + 1.0) {
        clock = 0;
        cursor = 0;
      }
      const batch: VizFrame[] = [];
      while (cursor < frames.length && frames[cursor].time <= clock) {
        batch.push(frames[cursor]);
        cursor += 1;
      }
      if (batch.length) {
        for (const cb of this.vizSubs) cb(batch);
      }
    }, 33);
  }
}
