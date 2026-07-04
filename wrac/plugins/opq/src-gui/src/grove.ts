/**
 * THE GROVE — the live analysis display.
 *
 * An echogram of the engine's mind: time scrolls leftward, pitch runs
 * vertically (log). Every tracked pitch object is a jagged glyph whose shape
 * is hashed from its identity, trailing a ribbon of its OUTPUT pitch, with a
 * dashed ghost of its SOURCE pitch — the vertical stem between them at the
 * head is the remap, drawn live. Held MIDI notes are strata lines; the
 * residual layer is dust; transients flash the field dry.
 */
import type { EngineInfo, VizFrame } from "./types";

const WINDOW_S = 9;
const HEAD_X = 0.78; // "now" position as a fraction of width
const MIDI_TOP = 103;
const MIDI_BOT = 31;
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
  nb: boolean;
};

type Trail = {
  color: string;
  points: TrailPoint[];
  lastSeen: number;
  id: number;
};

function hzToMidi(hz: number): number {
  return 69 + 12 * Math.log2(hz / 440);
}

function noteName(midi: number): string {
  const m = Math.round(midi);
  return `${NOTE_NAMES[((m % 12) + 12) % 12]}${Math.floor(m / 12) - 1}`;
}

/** Deterministic 0..1 hash — stable dust fields and glyph shapes. */
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

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("no 2d context");
    this.ctx = ctx;
    const observer = new ResizeObserver(() => this.resize());
    observer.observe(canvas.parentElement ?? canvas);
    this.resize();
  }

  setEngineInfo(info: EngineInfo): void {
    this.engine = info;
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
        // engine reset / demo loop restart — start the field over
        this.frames = [];
        this.trails.clear();
      }
      this.frames.push(frame);
      for (const track of frame.tracks) {
        let trail = this.trails.get(track.id);
        if (!trail) {
          trail = {
            color: PALETTE[((track.id % 8) + 8) % 8],
            points: [],
            lastSeen: frame.time,
            id: track.id,
          };
          this.trails.set(track.id, trail);
        }
        trail.points.push({
          time: frame.time,
          srcM: hzToMidi(track.f0),
          outM: hzToMidi(track.tgt),
          amp: track.amp,
          nb: track.nb,
        });
        trail.lastSeen = frame.time;
        if (track.amp > this.ampMax) this.ampMax = track.amp;
      }
    }
    const head = this.frames[this.frames.length - 1];
    if (head) this.now = head.time;
    // prune the window
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

  private x(time: number): number {
    return this.w * HEAD_X - (this.now - time) * (this.w * HEAD_X) / WINDOW_S;
  }

  private y(midi: number): number {
    return ((MIDI_TOP - midi) / (MIDI_TOP - MIDI_BOT)) * this.h;
  }

  private ampN(amp: number): number {
    return Math.min(1, Math.sqrt(amp / this.ampMax));
  }

  render(tMs: number): void {
    const { ctx } = this;
    ctx.save();
    ctx.scale(this.dpr, this.dpr);
    ctx.clearRect(0, 0, this.w, this.h);

    this.drawPitchField();
    const head = this.latest();
    if (head) {
      this.drawStrata(head);
      this.drawDust();
      this.drawEventMarkers();
      this.drawTrails();
      this.drawHeads(tMs, head);
      this.drawCorners(head);
    } else {
      // fresh instance, nothing analyzed yet — say what will happen here
      ctx.font = "10px ui-monospace, Menlo, monospace";
      ctx.textAlign = "center";
      ctx.fillStyle = "rgba(242,239,230,0.35)";
      ctx.fillText(
        "awaiting audio + MIDI — pitch objects will appear here",
        this.w / 2,
        this.h / 2,
      );
      ctx.fillStyle = "rgba(242,239,230,0.18)";
      ctx.fillText(
        "hold notes on the sidechain to define the grid · empty grid = silence",
        this.w / 2,
        this.h / 2 + 16,
      );
    }
    ctx.restore();
  }

  private drawPitchField(): void {
    const { ctx } = this;
    // black-key rows, barely there — the piano is in the paper grain
    for (let m = MIDI_BOT; m <= MIDI_TOP; m++) {
      const pc = ((m % 12) + 12) % 12;
      if ([1, 3, 6, 8, 10].includes(pc)) {
        const y0 = this.y(m + 0.5);
        const y1 = this.y(m - 0.5);
        ctx.fillStyle = "rgba(255,255,255,0.017)";
        ctx.fillRect(0, y0, this.w, y1 - y0);
      }
      if (pc === 0) {
        const y = this.y(m);
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
    // head line — the present moment
    const hx = this.w * HEAD_X;
    ctx.strokeStyle = "rgba(255,255,255,0.10)";
    ctx.setLineDash([1, 3]);
    ctx.beginPath();
    ctx.moveTo(hx, 0);
    ctx.lineTo(hx, this.h);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  private drawStrata(head: VizFrame): void {
    const { ctx } = this;
    if (!head.grid.length) return;
    // which grid notes have a mapped object on them right now?
    const occupied = new Set<number>();
    for (const track of head.tracks) {
      occupied.add(Math.round(hzToMidi(track.tgt)));
    }
    ctx.font = "9px ui-monospace, Menlo, monospace";
    for (const note of head.grid) {
      if (note > MIDI_TOP || note < MIDI_BOT) continue;
      const y = this.y(note);
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

  private drawDust(): void {
    const { ctx } = this;
    ctx.fillStyle = "rgba(165,175,195,0.20)";
    const stepW = (this.w * HEAD_X) / (WINDOW_S / 0.0232);
    for (const frame of this.frames) {
      if (frame.in <= 0) continue;
      const ratio = Math.min(1, frame.res / (frame.in + 1e-6));
      const count = Math.round(ratio * 34);
      const fx = this.x(frame.time);
      if (fx < -20) continue;
      for (let i = 0; i < count; i++) {
        const rx = hash01(frame.t * 131 + i * 7);
        const ry = hash01(frame.t * 197 + i * 13 + 5);
        ctx.fillRect(
          fx + (rx - 0.5) * stepW * 7,
          ry * this.h,
          1.2,
          1.2,
        );
      }
    }
  }

  private drawEventMarkers(): void {
    const { ctx } = this;
    let prevPcs = "";
    let prevHard = false;
    for (const frame of this.frames) {
      const fx = this.x(frame.time);
      // transient handling: soft blends are a faint breath of white; a hard
      // reset draws one seam at the START of its run, marked with a burst
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
          ctx.strokeStyle = `rgba(255,255,255,${0.02 + 0.10 * frame.transient})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(fx, 0);
          ctx.lineTo(fx, this.h);
          ctx.stroke();
        }
      }
      prevHard = hard;
      // chord-change seams (pitch-class set changes only)
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
  }

  private drawTrails(): void {
    const { ctx } = this;
    for (const trail of this.trails.values()) {
      if (trail.points.length === 1) {
        // one-frame object: a mote, not a ribbon
        const p = trail.points[0];
        ctx.fillStyle = trail.color;
        ctx.globalAlpha = 0.7;
        ctx.fillRect(this.x(p.time) - 1, this.y(p.outM) - 1, 2, 2);
        ctx.globalAlpha = 1;
        continue;
      }
      if (trail.points.length < 2) continue;
      // source ghost — the dry pitch that was, dashed and faint
      ctx.strokeStyle = trail.color;
      ctx.globalAlpha = 0.26;
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 4]);
      ctx.beginPath();
      trail.points.forEach((p, i) => {
        const px = this.x(p.time);
        const py = this.y(p.srcM);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      ctx.stroke();
      ctx.setLineDash([]);

      // mapped ribbon — glow pass then core
      for (const pass of [0, 1] as const) {
        ctx.beginPath();
        trail.points.forEach((p, i) => {
          const px = this.x(p.time);
          const py = this.y(p.outM);
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        if (pass === 0) {
          const headAmp = trail.points[trail.points.length - 1].amp;
          ctx.globalAlpha = 0.30;
          ctx.lineWidth = 3 + 5 * this.ampN(headAmp);
        } else {
          ctx.globalAlpha = 0.92;
          ctx.lineWidth = 1.3;
        }
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }
  }

  private drawHeads(tMs: number, head: VizFrame): void {
    const { ctx } = this;
    const hx = this.w * HEAD_X;
    let live: { trail: Trail; p: TrailPoint }[] = [];
    for (const trail of this.trails.values()) {
      const p = trail.points[trail.points.length - 1];
      if (p && this.now - p.time < 0.055) live.push({ trail, p });
    }
    // during dense polyphony keep the plate legible: loudest eight only
    live = live.sort((a, b) => b.p.amp - a.p.amp).slice(0, 8);

    // stems: source → target, the remap made visible
    for (const { trail, p } of live) {
      const sy = this.y(p.srcM);
      const oy = this.y(p.outM);
      ctx.strokeStyle = trail.color;
      ctx.globalAlpha = 0.5;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(hx, sy);
      ctx.lineTo(hx, oy);
      ctx.stroke();
      // hollow marker at the source pitch
      ctx.globalAlpha = 0.75;
      ctx.beginPath();
      ctx.arc(hx, sy, 2.6, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // jagged glyphs at the output pitch
    for (const { trail, p } of live) {
      const oy = this.y(p.outM);
      const size = 5.5 + 13 * this.ampN(p.amp);
      this.drawGlyph(hx, oy, size, trail.id, tMs, trail.color, p.nb);
    }

    // right-margin label column with hairline leaders to each glyph — the
    // callout language of the plate. The cents figure is the remap distance:
    // how far the source was pulled to reach its target.
    const labels = live
      .map(({ trail, p }) => {
        const cents = Math.round((p.srcM - p.outM) * 100);
        const arrow = cents >= 0 ? "↓" : "↑";
        return {
          glyphY: this.y(p.outM),
          y: this.y(p.outM),
          text: `${noteName(p.outM)} ${arrow}${Math.abs(cents)}¢`,
          color: trail.color,
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

    // empty grid — the PITCHMAP contract, stated plainly
    if (!head.grid.length) {
      ctx.font = "11px ui-monospace, Menlo, monospace";
      ctx.fillStyle = "rgba(255,84,112,0.85)";
      ctx.textAlign = "center";
      ctx.fillText("NO GRID HELD — OUTPUT SILENT", this.w / 2, 24);
      ctx.strokeStyle = "rgba(255,84,112,0.4)";
      ctx.strokeRect(this.w / 2 - 118, 12, 236, 18);
    }
  }

  private drawGlyph(
    x: number,
    y: number,
    size: number,
    id: number,
    tMs: number,
    color: string,
    newborn: boolean,
  ): void {
    const { ctx } = this;
    const spikes = 7 + (((id % 5) + 5) % 5);
    const rot = tMs * 0.0004 + id * 1.7;
    ctx.beginPath();
    for (let i = 0; i < spikes * 2; i++) {
      const angle = rot + (i * Math.PI) / spikes;
      const jag = 0.72 + 0.5 * hash01(id * 31 + i);
      const r = i % 2 === 0 ? size * jag : size * 0.42 * jag;
      const px = x + Math.cos(angle) * r;
      const py = y + Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    if (newborn) {
      // tensorfield "source": hollow burst with rays
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
    // figure legend, lower left — the plate explains itself
    ctx.textAlign = "left";
    ctx.fillStyle = "rgba(242,239,230,0.22)";
    ctx.fillText(
      "pitch axis: log₂ · window 9 s · dashed = source ghost · solid = mapped · dust = residual",
      6,
      this.h - 8,
    );
    if (this.stalled) {
      ctx.fillStyle = "rgba(242,239,230,0.45)";
      ctx.fillText("feed idle — transport stopped?", 6, this.h - 20);
    }
  }
}
