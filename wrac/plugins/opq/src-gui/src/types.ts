/** One tracked pitch object in an analysis frame (mirrors Rust VizTrack). */
export type VizTrack = {
  /** Stable identity across frames. */
  id: number;
  /** Source fundamental, Hz. */
  f0: number;
  /** Mapping target, Hz. */
  tgt: number;
  /** Summed claimed-region magnitude this frame. */
  amp: number;
  /** Harmonic regions claimed. */
  nh: number;
  /** Newborn (transition policy window). */
  nb: boolean;
};

/** One engine analysis frame (mirrors Rust VizFrame / CLI --viz-dump). */
export type VizFrame = {
  t: number;
  time: number;
  flux: number;
  /** 0 = fully mapped … 1 = fully dry (transient handling). */
  transient: number;
  /** Total mid-spectrum magnitude. */
  in: number;
  /** Residual (unclaimed) magnitude. */
  res: number;
  repeat: boolean;
  /** MIDI notes on the active target grid. */
  grid: number[];
  /** Residual magnitude by octave band (C0..C8); absent in old traces. */
  bands?: number[];
  tracks: VizTrack[];
};

/** Parameter spec from the Rust manifest (single source of truth). */
export type ParamSpec = {
  id: number;
  name: string;
  min: number;
  max: number;
  default: number;
  stepped: boolean;
  kind: "percent" | "seconds" | "hertz" | "cents" | "integer" | "choice";
  unit: string;
  choices: string[] | null;
};

export type ParameterState = {
  type: "parameter-value";
  parameterId: number;
  value: number;
  text: string;
};

export type PluginMetadata = {
  pluginId: string;
  pluginName: string;
  companyName: string;
  version: string;
};

export type EngineInfo = {
  sampleRate: number;
  hop: number;
  latency: number;
};
