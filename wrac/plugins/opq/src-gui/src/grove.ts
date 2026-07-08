/**
 * THE GROVE — the live analysis display. Two ways of seeing:
 *
 * COSMOS (flagship): a present-tense cosmogram of the mapping itself.
 * Pitch class is angle, octave is radius — the pitch continuum is a spiral
 * through the wheel. Held MIDI notes are a lit constellation (Repeat mode
 * lights whole pitch-class spokes; Custom lights single nodes). Every
 * tracked pitch object is a star sitting at its OUTPUT pitch, tethered to
 * a hollow ghost at its SOURCE pitch — the tether is the remap. Harmonic
 * combs trace spirals outward from each star. The residual layer is a
 * nebula placed by true octave-band energy; transients are shockwave
 * rings from the core.
 *
 * STRATA: the time view. An echogram scrolling leftward, output ribbons +
 * dashed source ghosts, strata for held notes, leader-line callouts.
 *
 * The star glyph (both modes) is a portrait of the object:
 *   spike count = harmonics claimed this frame
 *   size        = claimed energy
 *   spin rate   = remap tension (cents pulled)
 *   wobble      = source micro-pitch motion (what Feel re-injects)
 *   hollow+rays = newborn (transition policy window)
 *   shape       = identity (stable hash of the track id)
 */
import { IdleFlame } from "./flame";
import type { EngineInfo, VizFrame } from "./types";

export type GroveMode = "cosmos" | "strata";

const WINDOW_S = 9;
const TRAIL_S = 1.6;
const HEAD_X = 0.78;
const MIDI_TOP = 103;
const MIDI_BOT = 31;
const C_LO = 24; // C1 — cosmogram inner edge
const C_HI = 108; // C8 — cosmogram rim
const TAU = Math.PI * 2;
const PALETTE = [
  "#4ff2d2",
  "#ff3fd4",
  "#ffe23d",
  "#8aff44",
  "#ff7a1a",
  "#5b8cff",
  "#ff5470",
  "#c99bff",
];
const NOTE_NAMES = [
  "C",
  "C#",
  "D",
  "D#",
  "E",
  "F",
  "F#",
  "G",
  "G#",
  "A",
  "A#",
  "B",
];

type TrailPoint = {
  time: number;
  srcM: number;
  outM: number;
  amp: number;
  nh: number;
  nb: boolean;
};

type Trail = {
  color: string;
  points: TrailPoint[];
  lastSeen: number;
  id: number;
  /** EMA of source pitch — the reference Feel deviates from. */
  lemaM: number;
  /** Glide-smoothed displayed output pitch (client mirror of the ramp). */
  renderM: number;
};

type LiveStar = {
  trail: Trail;
  p: TrailPoint;
  x: number;
  y: number;
  size: number;
};

function hzToMidi(hz: number): number {
  return 69 + 12 * Math.log2(Math.max(hz, 1) / 440);
}

function noteName(midi: number): string {
  const m = Math.round(midi);
  return `${NOTE_NAMES[((m % 12) + 12) % 12]}${Math.floor(m / 12) - 1}`;
}

function hash01(seed: number): number {
  let x = Math.imul(seed ^ 0x9e3779b9, 0x85ebca6b);
  x ^= x >>> 13;
  x = Math.imul(x, 0xc2b2ae35);
  x ^= x >>> 16;
  return (x >>> 0) / 4294967296;
}

export class Grove {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private frames: VizFrame[] = [];
  private trails = new Map<number, Trail>();
  private now = 0;
  private ampMax = 400;
  private dpr = 1;
  private w = 0;
  private h = 0;
  private stalled = true;
  private engine: EngineInfo = { sampleRate: 0, hop: 1024, latency: 4096 };
  mode: GroveMode = "cosmos";
  private hoverX = -1;
  private hoverY = -1;
  private flame = new IdleFlame();
  /** Live parameter values — the controls ARE the model; the display obeys. */
  private params = new Map<number, number>();
  private lastRenderMs = 0;
  /** The sky remembers: every mapped note leaves a permanent faint star. */
  private memory: HTMLCanvasElement = document.createElement("canvas");
  /** Red thread: influence made physical (set while a Warden is held). */
  private thread: { x: number; y: number } | null = null;
  private pinImg = new Image();

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("no 2d context");
    this.ctx = ctx;
    const observer = new ResizeObserver(() => this.resize());
    observer.observe(canvas.parentElement ?? canvas);
    this.resize();
    canvas.addEventListener("pointermove", (event) => {
      const rect = canvas.getBoundingClientRect();
      this.hoverX = event.clientX - rect.left;
      this.hoverY = event.clientY - rect.top;
    });
    canvas.addEventListener("pointerleave", () => {
      this.hoverX = -1;
      this.hoverY = -1;
    });
  }

  setEngineInfo(info: EngineInfo): void {
    this.engine = info;
  }

  setMode(mode: GroveMode): void {
    this.mode = mode;
  }

  setParam(id: number, value: number): void {
    this.params.set(id, value);
  }

  setThread(point: { x: number; y: number } | null): void {
    this.thread = point;
    if (point && !this.pinImg.src) this.pinImg.src = "/shrine/pin.png";
  }

  private param(id: number, fallback: number): number {
    return this.params.get(id) ?? fallback;
  }

  latest(): VizFrame | undefined {
    return this.frames[this.frames.length - 1];
  }

  isStalled(): boolean {
    return this.stalled;
  }

  push(batch: VizFrame[]): void {
    for (const frame of batch) {
      const last = this.frames[this.frames.length - 1];
      if (last && frame.time < last.time - 1) {
        this.frames = [];
        this.trails.clear();
      }
      this.frames.push(frame);
      for (const track of frame.tracks) {
        let trail = this.trails.get(track.id);
        const srcM = hzToMidi(track.f0);
        const outM = hzToMidi(track.tgt);
        if (!trail) {
          trail = {
            color: PALETTE[((track.id % 8) + 8) % 8],
            points: [],
            lastSeen: frame.time,
            id: track.id,
            lemaM: srcM,
            renderM: outM,
          };
          this.trails.set(track.id, trail);
        }
        // 250ms EMA at ~43 frames/s — mirrors the engine's Feel reference
        trail.lemaM += 0.09 * (srcM - trail.lemaM);
        trail.points.push({
          time: frame.time,
          srcM,
          outM,
          amp: track.amp,
          nh: track.nh,
          nb: track.nb,
        });
        trail.lastSeen = frame.time;
        if (track.amp > this.ampMax) this.ampMax = track.amp;
      }
    }
    const head = this.frames[this.frames.length - 1];
    if (head) this.now = head.time;
    const cutoff = this.now - WINDOW_S - 0.5;
    while (this.frames.length && this.frames[0].time < cutoff) {
      this.frames.shift();
    }
    for (const [id, trail] of this.trails) {
      while (trail.points.length && trail.points[0].time < cutoff) {
        trail.points.shift();
      }
      if (!trail.points.length && trail.lastSeen < cutoff) {
        this.trails.delete(id);
      }
    }
    this.ampMax *= 0.998;
    if (this.ampMax < 50) this.ampMax = 50;
    this.stalled = false;
  }

  markStalled(): void {
    this.stalled = true;
  }

  private resize(): void {
    const parent = this.canvas.parentElement;
    if (!parent) return;
    this.dpr = window.devicePixelRatio || 1;
    this.w = parent.clientWidth;
    this.h = parent.clientHeight;
    this.canvas.width = Math.round(this.w * this.dpr);
    this.canvas.height = Math.round(this.h * this.dpr);
    this.canvas.style.width = `${this.w}px`;
    this.canvas.style.height = `${this.h}px`;
  }

  private ampN(amp: number): number {
    return Math.min(1, Math.sqrt(amp / this.ampMax));
  }

  /** Live objects at the head, loudest first, capped for legibility. */
  private liveStars(limit: number): { trail: Trail; p: TrailPoint }[] {
    let live: { trail: Trail; p: TrailPoint }[] = [];
    for (const trail of this.trails.values()) {
      const p = trail.points[trail.points.length - 1];
      if (p && this.now - p.time < 0.055) live.push({ trail, p });
    }
    live = live.sort((a, b) => b.p.amp - a.p.amp).slice(0, limit);
    return live;
  }

  // ------------------------------------------------------------- render

  render(tMs: number): void {
    const { ctx } = this;
    ctx.save();
    ctx.scale(this.dpr, this.dpr);
    ctx.clearRect(0, 0, this.w, this.h);

    const head = this.latest();
    if (!head) {
      this.flame.step(ctx, this.w, this.h, tMs);
      ctx.font = "10px ui-monospace, Menlo, monospace";
      ctx.textAlign = "center";
      ctx.fillStyle = "rgba(242,239,230,0.5)";
      ctx.fillText(
        "awaiting audio + MIDI — pitch objects will appear here",
        this.w / 2,
        this.h / 2,
      );
      ctx.fillStyle = "rgba(242,239,230,0.28)";
      ctx.fillText(
        "hold notes on the sidechain to define the grid · empty grid = silence",
        this.w / 2,
        this.h / 2 + 16,
      );
      ctx.restore();
      return;
    }

    if (this.mode === "cosmos") {
      this.renderCosmos(tMs, head);
    } else {
      this.renderStrata(tMs, head);
    }
    this.drawAlarm(head);
    this.drawCorners(head);
    ctx.restore();
  }

  // ------------------------------------------------------------- cosmos

  private cGeom() {
    const cx = this.w / 2;
    const cy = this.h / 2;
    const rOut = Math.min(this.w, this.h) / 2 - 34;
    const rIn = Math.max(26, rOut * 0.1);
    return { cx, cy, rOut, rIn };
  }

  private cAng(midi: number): number {
    return ((((midi % 12) + 12) % 12) / 12) * TAU - Math.PI / 2;
  }

  private cRad(midi: number): number {
    const { rOut, rIn } = this.cGeom();
    const m = Math.min(Math.max(midi, C_LO), C_HI);
    return rIn + ((m - C_LO) / (C_HI - C_LO)) * (rOut - rIn);
  }

  private cPos(midi: number): [number, number] {
    const { cx, cy } = this.cGeom();
    const a = this.cAng(midi);
    const r = this.cRad(midi);
    return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
  }

  private renderCosmos(tMs: number, head: VizFrame): void {
    const { ctx } = this;
    const { cx, cy, rOut, rIn } = this.cGeom();

    // the remembering sky — a session writes its own nebula
    if (this.memory.width !== this.canvas.width || this.memory.height !== this.canvas.height) {
      this.memory.width = this.canvas.width;
      this.memory.height = this.canvas.height;
    }
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 0.55;
    ctx.drawImage(this.memory, 0, 0);
    ctx.restore();

    // --- the wheel: spokes, octave rings, the pitch spiral
    ctx.lineWidth = 1;
    for (let pc = 0; pc < 12; pc++) {
      const a = this.cAng(pc);
      ctx.strokeStyle =
        pc === 0 ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.06)";
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * rIn, cy + Math.sin(a) * rIn);
      ctx.lineTo(cx + Math.cos(a) * rOut, cy + Math.sin(a) * rOut);
      ctx.stroke();
      ctx.fillStyle = "rgba(242,239,230,0.34)";
      ctx.font = "9px ui-monospace, Menlo, monospace";
      ctx.textAlign = "center";
      ctx.fillText(
        NOTE_NAMES[pc],
        cx + Math.cos(a) * (rOut + 12),
        cy + Math.sin(a) * (rOut + 12) + 3,
      );
    }
    for (let oct = C_LO; oct <= C_HI; oct += 12) {
      ctx.strokeStyle = "rgba(255,255,255,0.075)";
      ctx.beginPath();
      ctx.arc(cx, cy, this.cRad(oct), 0, TAU);
      ctx.stroke();
      // octave scale climbs the C spoke
      ctx.fillStyle = "rgba(242,239,230,0.22)";
      ctx.textAlign = "left";
      ctx.fillText(noteName(oct), cx + 3, cy - this.cRad(oct) - 2);
    }
    // the pitch continuum is a spiral — whisper it
    ctx.strokeStyle = "rgba(255,255,255,0.05)";
    ctx.beginPath();
    for (let m = C_LO; m <= C_HI; m += 0.25) {
      const [px, py] = this.cPos(m);
      if (m === C_LO) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,0.10)";
    ctx.beginPath();
    ctx.arc(cx, cy, rIn, 0, TAU);
    ctx.stroke();

    // --- transient shockwaves from the core
    for (const frame of this.frames) {
      const elapsed = this.now - frame.time;
      if (frame.transient > 0.02 && elapsed < 0.55) {
        const prog = elapsed / 0.55;
        const alpha = (1 - prog) * 0.42 * frame.transient;
        ctx.strokeStyle =
          frame.transient >= 1
            ? `rgba(255,226,61,${alpha})`
            : `rgba(255,255,255,${alpha})`;
        ctx.lineWidth = frame.transient >= 1 ? 1.6 : 1;
        ctx.beginPath();
        ctx.arc(cx, cy, rIn + prog * (rOut - rIn), 0, TAU);
        ctx.stroke();
      }
    }

    // --- residual nebula, placed by octave-band energy
    const bands = head.bands ?? [];
    const total = head.in > 0 ? head.in : 1;
    ctx.fillStyle = "rgba(165,175,195,0.5)";
    const recent = this.frames.slice(-16);
    for (const frame of recent) {
      const fb = frame.bands ?? [];
      const age = (this.now - frame.time) / (16 * 0.024);
      const fade = Math.max(0, 1 - age);
      for (let band = 0; band < 8; band++) {
        const e = fb[band] ?? 0;
        if (e <= 0) continue;
        const count = Math.min(26, Math.round((e / total) * 90));
        const mLo = 12 * band + 12;
        for (let i = 0; i < count; i++) {
          const rm = mLo + hash01(frame.t * 89 + band * 31 + i * 7) * 12;
          const am = hash01(frame.t * 53 + band * 17 + i * 13) * TAU;
          const r = this.cRad(rm);
          ctx.globalAlpha = 0.26 * fade;
          ctx.fillRect(
            cx + Math.cos(am) * r,
            cy + Math.sin(am) * r,
            1.3,
            1.3,
          );
        }
      }
      // old traces without bands: uniform fallback
      if (!fb.length && frame.res > 0 && frame.in > 0) {
        const count = Math.min(40, Math.round((frame.res / frame.in) * 46));
        for (let i = 0; i < count; i++) {
          const rr = rIn + hash01(frame.t * 131 + i * 7) * (rOut - rIn);
          const am = hash01(frame.t * 197 + i * 13) * TAU;
          ctx.globalAlpha = 0.2 * fade;
          ctx.fillRect(cx + Math.cos(am) * rr, cy + Math.sin(am) * rr, 1.3, 1.3);
        }
      }
    }
    ctx.globalAlpha = 1;
    void bands;

    // --- the grid constellation
    const occupied = new Set<number>();
    for (const track of head.tracks) {
      occupied.add(Math.round(hzToMidi(track.tgt)));
    }
    if (head.repeat) {
      // Repeat mode: the pitch CLASS is held — light the whole spoke
      const pcs = new Set(head.grid.map((n) => ((n % 12) + 12) % 12));
      for (const pc of pcs) {
        const a = this.cAng(pc);
        ctx.strokeStyle = "rgba(255,226,61,0.13)";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(a) * rIn, cy + Math.sin(a) * rIn);
        ctx.lineTo(cx + Math.cos(a) * rOut, cy + Math.sin(a) * rOut);
        ctx.stroke();
      }
    }
    ctx.lineWidth = 1;
    for (const note of head.grid) {
      if (note < C_LO || note > C_HI) continue;
      const [px, py] = this.cPos(note);
      const hot = occupied.has(note);
      const s = hot ? 4.5 : 2.8;
      ctx.strokeStyle = hot
        ? "rgba(255,226,61,0.95)"
        : "rgba(255,226,61,0.4)";
      ctx.beginPath(); // diamond node
      ctx.moveTo(px, py - s);
      ctx.lineTo(px + s, py);
      ctx.lineTo(px, py + s);
      ctx.lineTo(px - s, py);
      ctx.closePath();
      ctx.stroke();
      if (hot) {
        ctx.fillStyle = "rgba(255,226,61,0.9)";
        ctx.font = "9px ui-monospace, Menlo, monospace";
        ctx.textAlign = "left";
        ctx.fillText(noteName(note), px + 7, py - 6);
      }
    }

    // --- transition arcs (comet trails between retunes)
    for (const trail of this.trails.values()) {
      const pts = trail.points.filter((p) => this.now - p.time < TRAIL_S);
      if (pts.length < 2) continue;
      ctx.strokeStyle = trail.color;
      for (let i = 1; i < pts.length; i++) {
        const age = (this.now - pts[i].time) / TRAIL_S;
        ctx.globalAlpha = (1 - age) * 0.7;
        ctx.lineWidth = 1 + 1.6 * this.ampN(pts[i].amp) * (1 - age);
        const [x0, y0] = this.cPos(pts[i - 1].outM);
        const [x1, y1] = this.cPos(pts[i].outM);
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    // --- the stars, at their HONEST output pitch: the glide ramp toward
    // the target plus Feel's re-injected source deviation. Feel at zero
    // locks the star; Feel at one puts the full source wobble back.
    const dt = Math.min(0.1, Math.max(0.001, (tMs - this.lastRenderMs) / 1000));
    this.lastRenderMs = tMs;
    const feel = this.param(2, 0.35);
    const glide = this.param(3, 0);
    const tau = Math.max(glide, 0.03);
    const live = this.liveStars(8);
    const stars: LiveStar[] = [];
    for (const { trail, p } of live) {
      trail.renderM = p.outM + (trail.renderM - p.outM) * Math.exp(-dt / tau);
      const heardM = trail.renderM + feel * (p.srcM - trail.lemaM);
      const [x, y] = this.cPos(heardM);
      const size = 8 + 16 * this.ampN(p.amp);
      stars.push({ trail, p, x, y, size });
    }

    // harmonic combs first (under the stars): spirals through the wheel
    for (const s of stars) {
      ctx.strokeStyle = s.trail.color;
      const hMax = Math.min(s.p.nh, 12);
      for (let hh = 2; hh <= hMax; hh++) {
        const m = s.p.outM + 12 * Math.log2(hh);
        if (m > C_HI) break;
        const a = this.cAng(m);
        const r = this.cRad(m);
        ctx.globalAlpha = 0.65 / Math.pow(hh, 0.7);
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(a) * (r - 4.5), cy + Math.sin(a) * (r - 4.5));
        ctx.lineTo(cx + Math.cos(a) * (r + 4.5), cy + Math.sin(a) * (r + 4.5));
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    // tethers: source ghost -> star, with matter being DRAGGED along them.
    // Mix weights the two worlds: wet layer fades as the dry ghosts firm up.
    const mix = this.param(1, 1);
    const wetA = 0.3 + 0.7 * mix;
    const dryA = 0.45 + 0.55 * (1 - mix);
    for (const s of stars) {
      const [gx, gy] = this.cPos(s.p.srcM);
      const mx = (gx + s.x) / 2;
      const my = (gy + s.y) / 2;
      const dx = mx - cx;
      const dy = my - cy;
      const dl = Math.hypot(dx, dy) || 1;
      const cpx = mx + (dx / dl) * 10;
      const cpy = my + (dy / dl) * 10;
      ctx.strokeStyle = s.trail.color;
      ctx.globalAlpha = 0.3 * wetA;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(gx, gy);
      ctx.quadraticCurveTo(cpx, cpy, s.x, s.y);
      ctx.stroke();
      // the pull, made of small matter: particles leave the source pitch
      // and accelerate into the cluster at the target
      const pull = Math.abs(s.p.srcM - s.p.outM) * 100;
      const grains = Math.min(7, 1 + Math.floor(pull / 45));
      ctx.fillStyle = s.trail.color;
      for (let i = 0; i < grains; i++) {
        let u = (tMs * 0.00030 * (1 + i * 0.11) + i * 0.371 + s.trail.id * 0.13) % 1;
        u = Math.pow(u, 0.72); // ease: slow birth, quick arrival
        const omu = 1 - u;
        const px = omu * omu * gx + 2 * omu * u * cpx + u * u * s.x;
        const py = omu * omu * gy + 2 * omu * u * cpy + u * u * s.y;
        ctx.globalAlpha = (0.2 + 0.6 * u) * wetA;
        const r = 0.8 + 1.8 * u;
        ctx.fillRect(px - r / 2, py - r / 2, r, r);
      }
      // the source ghost — firmer as Mix leans dry
      ctx.globalAlpha = dryA;
      ctx.strokeStyle = s.trail.color;
      ctx.beginPath();
      ctx.arc(gx, gy, 2.8, 0, TAU);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    const grit = this.param(4, 0);
    const cohere = this.param(13, 1);
    for (const s of stars) {
      ctx.globalAlpha = wetA;
      if (cohere < 0.97) {
        // the Twins sunder: the two channels drift apart
        const off = (1 - cohere) * 5;
        ctx.globalAlpha = wetA * 0.6;
        this.drawGlyph(s.x - off, s.y - off * 0.6, s.size, s.trail.id, tMs, s.trail.color, s.p.nb, grit, s.p.nh);
        this.drawGlyph(s.x + off, s.y + off * 0.6, s.size, s.trail.id, tMs, s.trail.color, s.p.nb, grit, s.p.nh);
        ctx.globalAlpha = wetA;
      } else {
        this.drawGlyph(s.x, s.y, s.size, s.trail.id, tMs, s.trail.color, s.p.nb, grit, s.p.nh);
      }
      // whisper the target next to each star
      ctx.fillStyle = s.trail.color;
      ctx.globalAlpha = 0.75 * wetA;
      ctx.font = "9px ui-monospace, Menlo, monospace";
      ctx.textAlign = "left";
      ctx.fillText(noteName(s.p.outM), s.x + s.size + 4, s.y + 3);
      ctx.globalAlpha = 1;
    }

    // engrave this instant into the memory sky
    {
      const mctx = this.memory.getContext("2d");
      if (mctx) {
        mctx.save();
        mctx.scale(this.dpr, this.dpr);
        for (const s of stars) {
          mctx.fillStyle = s.trail.color;
          mctx.globalAlpha = 0.02;
          mctx.beginPath();
          mctx.arc(s.x, s.y, 1.6, 0, TAU);
          mctx.fill();
        }
        mctx.restore();
      }
    }

    // red thread: while a Warden is held, its influence runs to every star
    if (this.thread) {
      ctx.strokeStyle = "rgba(214,40,40,0.75)";
      ctx.lineWidth = 1;
      for (const s of stars) {
        const midX = (this.thread.x + s.x) / 2;
        const midY = Math.max(this.thread.y, s.y) + 26; // catenary sag
        ctx.beginPath();
        ctx.moveTo(this.thread.x, this.thread.y);
        ctx.quadraticCurveTo(midX, midY, s.x, s.y);
        ctx.stroke();
        if (this.pinImg.complete && this.pinImg.naturalWidth > 0) {
          ctx.drawImage(this.pinImg, s.x - 6, s.y - 6, 12, 12);
        }
      }
      if (this.pinImg.complete && this.pinImg.naturalWidth > 0) {
        ctx.drawImage(this.pinImg, this.thread.x - 8, this.thread.y - 8, 16, 16);
      }
    }

    this.drawHoverCard(stars);

    ctx.font = "9px ui-monospace, Menlo, monospace";
    ctx.textAlign = "left";
    ctx.fillStyle = "rgba(242,239,230,0.22)";
    ctx.fillText(
      "cosmos: angle = pitch class · radius = octave · ○→star tether = the remap · the sky remembers",
      6,
      this.h - 8,
    );
  }

  // ------------------------------------------------------------- strata

  private sx(time: number): number {
    return this.w * HEAD_X - ((this.now - time) * (this.w * HEAD_X)) / WINDOW_S;
  }

  private sy(midi: number): number {
    return ((MIDI_TOP - midi) / (MIDI_TOP - MIDI_BOT)) * this.h;
  }

  private renderStrata(tMs: number, head: VizFrame): void {
    const { ctx } = this;

    for (let m = MIDI_BOT; m <= MIDI_TOP; m++) {
      const pc = ((m % 12) + 12) % 12;
      if ([1, 3, 6, 8, 10].includes(pc)) {
        const y0 = this.sy(m + 0.5);
        const y1 = this.sy(m - 0.5);
        ctx.fillStyle = "rgba(255,255,255,0.017)";
        ctx.fillRect(0, y0, this.w, y1 - y0);
      }
      if (pc === 0) {
        const y = this.sy(m);
        ctx.strokeStyle = "rgba(255,255,255,0.08)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(this.w, y);
        ctx.stroke();
        ctx.fillStyle = "rgba(255,255,255,0.30)";
        ctx.font = "9px ui-monospace, Menlo, monospace";
        ctx.textAlign = "left";
        ctx.fillText(noteName(m), 4, y - 3);
      }
    }
    const hx = this.w * HEAD_X;
    ctx.strokeStyle = "rgba(255,255,255,0.10)";
    ctx.setLineDash([1, 3]);
    ctx.beginPath();
    ctx.moveTo(hx, 0);
    ctx.lineTo(hx, this.h);
    ctx.stroke();
    ctx.setLineDash([]);

    // strata for the grid
    if (head.grid.length) {
      const occupied = new Set<number>();
      for (const track of head.tracks) {
        occupied.add(Math.round(hzToMidi(track.tgt)));
      }
      ctx.font = "9px ui-monospace, Menlo, monospace";
      for (const note of head.grid) {
        if (note > MIDI_TOP || note < MIDI_BOT) continue;
        const y = this.sy(note);
        const hot = occupied.has(note);
        ctx.strokeStyle = hot
          ? "rgba(255,226,61,0.42)"
          : "rgba(255,226,61,0.10)";
        ctx.lineWidth = hot ? 1.3 : 1;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(this.w, y);
        ctx.stroke();
        if (hot) {
          ctx.fillStyle = "rgba(255,226,61,0.9)";
          ctx.textAlign = "right";
          ctx.fillText(noteName(note), this.w - 4, y - 3);
        }
      }
    }

    // dust
    ctx.fillStyle = "rgba(165,175,195,0.20)";
    const stepW = (this.w * HEAD_X) / (WINDOW_S / 0.0232);
    for (const frame of this.frames) {
      if (frame.in <= 0) continue;
      const ratio = Math.min(1, frame.res / (frame.in + 1e-6));
      const count = Math.round(ratio * 34);
      const fx = this.sx(frame.time);
      if (fx < -20) continue;
      for (let i = 0; i < count; i++) {
        const rx = hash01(frame.t * 131 + i * 7);
        const ry = hash01(frame.t * 197 + i * 13 + 5);
        ctx.fillRect(fx + (rx - 0.5) * stepW * 7, ry * this.h, 1.2, 1.2);
      }
    }

    // event seams
    let prevPcs = "";
    let prevHard = false;
    for (const frame of this.frames) {
      const fx = this.sx(frame.time);
      const hard = frame.transient >= 1;
      if (frame.transient > 0.02 && fx > 0) {
        if (hard && !prevHard) {
          ctx.strokeStyle = "rgba(255,226,61,0.28)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(fx, 0);
          ctx.lineTo(fx, this.h);
          ctx.stroke();
          ctx.fillStyle = "rgba(255,226,61,0.8)";
          ctx.beginPath();
          ctx.moveTo(fx - 3.5, 2);
          ctx.lineTo(fx + 3.5, 2);
          ctx.lineTo(fx, 9);
          ctx.closePath();
          ctx.fill();
        } else if (!hard) {
          ctx.strokeStyle = `rgba(255,255,255,${0.02 + 0.1 * frame.transient})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(fx, 0);
          ctx.lineTo(fx, this.h);
          ctx.stroke();
        }
      }
      prevHard = hard;
      const pcsKey = [...new Set(frame.grid.map((n) => n % 12))]
        .sort((a, b) => a - b)
        .join(",");
      if (prevPcs && pcsKey !== prevPcs && fx > 0) {
        ctx.strokeStyle = "rgba(79,242,210,0.16)";
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(fx, 0);
        ctx.lineTo(fx, this.h);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      prevPcs = pcsKey;
    }

    // trails
    for (const trail of this.trails.values()) {
      if (trail.points.length === 1) {
        const p = trail.points[0];
        ctx.fillStyle = trail.color;
        ctx.globalAlpha = 0.7;
        ctx.fillRect(this.sx(p.time) - 1, this.sy(p.outM) - 1, 2, 2);
        ctx.globalAlpha = 1;
        continue;
      }
      if (trail.points.length < 2) continue;
      ctx.strokeStyle = trail.color;
      ctx.globalAlpha = 0.26;
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 4]);
      ctx.beginPath();
      trail.points.forEach((p, i) => {
        if (i === 0) ctx.moveTo(this.sx(p.time), this.sy(p.srcM));
        else ctx.lineTo(this.sx(p.time), this.sy(p.srcM));
      });
      ctx.stroke();
      ctx.setLineDash([]);
      for (const pass of [0, 1] as const) {
        ctx.beginPath();
        trail.points.forEach((p, i) => {
          if (i === 0) ctx.moveTo(this.sx(p.time), this.sy(p.outM));
          else ctx.lineTo(this.sx(p.time), this.sy(p.outM));
        });
        if (pass === 0) {
          const headAmp = trail.points[trail.points.length - 1].amp;
          ctx.globalAlpha = 0.3;
          ctx.lineWidth = 3 + 5 * this.ampN(headAmp);
        } else {
          ctx.globalAlpha = 0.92;
          ctx.lineWidth = 1.3;
        }
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    // heads: stems, glyphs, leader labels
    const live = this.liveStars(8);
    const stars: LiveStar[] = [];
    for (const { trail, p } of live) {
      stars.push({
        trail,
        p,
        x: hx,
        y: this.sy(p.outM),
        size: 8 + 16 * this.ampN(p.amp),
      });
    }
    for (const s of stars) {
      const sy = this.sy(s.p.srcM);
      ctx.strokeStyle = s.trail.color;
      ctx.globalAlpha = 0.5;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(hx, sy);
      ctx.lineTo(hx, s.y);
      ctx.stroke();
      ctx.globalAlpha = 0.75;
      ctx.beginPath();
      ctx.arc(hx, sy, 2.6, 0, TAU);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
    const gritS = this.param(4, 0);
    for (const s of stars) {
      this.drawGlyph(s.x, s.y, s.size, s.trail.id, tMs, s.trail.color, s.p.nb, gritS, s.p.nh);
    }

    const labels = stars
      .map((s) => {
        const cents = Math.round((s.p.srcM - s.p.outM) * 100);
        const arrow = cents >= 0 ? "↓" : "↑";
        return {
          glyphY: s.y,
          y: s.y,
          text: `${noteName(s.p.outM)} ${arrow}${Math.abs(cents)}¢`,
          color: s.trail.color,
        };
      })
      .sort((a, b) => a.y - b.y);
    for (let i = 1; i < labels.length; i++) {
      if (labels[i].y - labels[i - 1].y < 13) {
        labels[i].y = labels[i - 1].y + 13;
      }
    }
    ctx.font = "10px ui-monospace, Menlo, monospace";
    ctx.textAlign = "left";
    const labelX = hx + 44;
    for (const label of labels) {
      ctx.strokeStyle = label.color;
      ctx.globalAlpha = 0.45;
      ctx.lineWidth = 0.75;
      ctx.beginPath();
      ctx.moveTo(hx + 14, label.glyphY);
      ctx.lineTo(labelX - 4, label.y);
      ctx.stroke();
      ctx.fillStyle = label.color;
      ctx.globalAlpha = 0.95;
      ctx.fillText(label.text, labelX, label.y + 3);
    }
    ctx.globalAlpha = 1;

    this.drawHoverCard(stars);

    ctx.font = "9px ui-monospace, Menlo, monospace";
    ctx.textAlign = "left";
    ctx.fillStyle = "rgba(242,239,230,0.22)";
    ctx.fillText(
      "strata: time → · pitch ↑ (log₂) · dashed = source ghost · solid = mapped · dust = residual",
      6,
      this.h - 8,
    );
  }

  // ----------------------------------------------------------- shared

  /** The star: a portrait of the pitch object (see file header). */
  private drawGlyph(
    x: number,
    y: number,
    size: number,
    id: number,
    tMs: number,
    color: string,
    newborn: boolean,
    grit: number,
    nh: number,
  ): void {
    const { ctx } = this;
    const spikes = 5 + Math.min(nh, 19);
    const rot = tMs * 0.00012 + id * 1.7;
    ctx.beginPath();
    for (let i = 0; i < spikes * 2; i++) {
      const angle = rot + (i * Math.PI) / spikes;
      const jag = 0.78 + (0.3 + grit * 0.9) * (hash01(id * 31 + i) - 0.5) * 2;
      const r = i % 2 === 0 ? size * jag : size * 0.42 * jag;
      const px = x + Math.cos(angle) * r;
      const py = y + Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    if (newborn) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.4;
      ctx.stroke();
      for (let i = 0; i < 6; i++) {
        const angle = rot * 1.3 + (i * Math.PI) / 3;
        ctx.beginPath();
        ctx.moveTo(x + Math.cos(angle) * size * 1.2, y + Math.sin(angle) * size * 1.2);
        ctx.lineTo(x + Math.cos(angle) * size * 1.75, y + Math.sin(angle) * size * 1.75);
        ctx.stroke();
      }
    } else {
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.92;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = "rgba(0,0,0,0.55)";
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }

  /** Hover a star → its full dossier. */
  private drawHoverCard(stars: LiveStar[]): void {
    if (this.hoverX < 0) return;
    let best: LiveStar | undefined;
    let bestD = 20;
    for (const s of stars) {
      const d = Math.hypot(s.x - this.hoverX, s.y - this.hoverY);
      if (d < bestD) {
        bestD = d;
        best = s;
      }
    }
    if (!best) return;
    const { ctx } = this;
    const cents = Math.round((best.p.srcM - best.p.outM) * 100);
    const srcCents = Math.round((best.p.srcM - Math.round(best.p.srcM)) * 100);
    const lines = [
      `obj·${best.trail.id}${best.p.nb ? " · newborn" : ""}`,
      `src ${noteName(best.p.srcM)}${srcCents >= 0 ? "+" : ""}${srcCents}¢ → ${noteName(best.p.outM)}`,
      `pull ${cents >= 0 ? "↓" : "↑"}${Math.abs(cents)}¢ · ${best.p.nh} harmonics`,
      `amp ${(this.ampN(best.p.amp) * 100).toFixed(0)}%`,
    ];
    ctx.font = "10px ui-monospace, Menlo, monospace";
    const cardW = 176;
    const cardH = 14 * lines.length + 10;
    let cardX = best.x + best.size + 12;
    let cardY = best.y - cardH / 2;
    if (cardX + cardW > this.w - 4) cardX = best.x - best.size - 12 - cardW;
    cardY = Math.min(Math.max(cardY, 4), this.h - cardH - 4);
    ctx.fillStyle = "rgba(5,5,5,0.88)";
    ctx.fillRect(cardX, cardY, cardW, cardH);
    ctx.strokeStyle = best.trail.color;
    ctx.lineWidth = 1;
    ctx.strokeRect(cardX, cardY, cardW, cardH);
    ctx.textAlign = "left";
    lines.forEach((line, i) => {
      ctx.fillStyle = i === 0 ? best.trail.color : "rgba(242,239,230,0.9)";
      ctx.fillText(line, cardX + 7, cardY + 16 + i * 14);
    });
  }

  private drawAlarm(head: VizFrame): void {
    const { ctx } = this;
    if (this.param(0, 0) >= 0.5) {
      ctx.font = "11px ui-monospace, Menlo, monospace";
      ctx.fillStyle = "rgba(255,84,112,0.85)";
      ctx.textAlign = "center";
      ctx.fillText("BYPASSED — DRY SIGNAL", this.w / 2, this.h - 24);
      ctx.strokeStyle = "rgba(255,84,112,0.4)";
      ctx.strokeRect(this.w / 2 - 100, this.h - 36, 200, 18);
    }
    if (!head.grid.length) {
      ctx.font = "11px ui-monospace, Menlo, monospace";
      ctx.fillStyle = "rgba(255,84,112,0.85)";
      ctx.textAlign = "center";
      ctx.fillText("NO GRID HELD — OUTPUT SILENT", this.w / 2, 24);
      ctx.strokeStyle = "rgba(255,84,112,0.4)";
      ctx.strokeRect(this.w / 2 - 118, 12, 236, 18);
    }
  }

  private drawCorners(head: VizFrame): void {
    const { ctx } = this;
    ctx.font = "9px ui-monospace, Menlo, monospace";
    ctx.fillStyle = "rgba(242,239,230,0.42)";
    ctx.textAlign = "right";
    const resPct = head.in > 0 ? Math.round((head.res / head.in) * 100) : 0;
    ctx.fillText(
      `t=${head.t}  flux=${head.flux.toFixed(2)}  obj=${head.tracks.length}  res=${resPct}%`,
      this.w - 6,
      12,
    );
    if (this.stalled) {
      ctx.fillStyle = "rgba(242,239,230,0.45)";
      ctx.textAlign = "left";
      ctx.fillText("feed idle — transport stopped?", 6, 14);
    }
  }
}
