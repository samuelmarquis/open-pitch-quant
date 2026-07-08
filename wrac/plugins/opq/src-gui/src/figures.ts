/**
 * Control figures: every continuous parameter is a tiny software-rendered
 * diagram OF ITS OWN MECHANISM — the plugin illustrating its own organs.
 * Each renderer gets the normalized value, a slow clock, and the group's
 * accent color, and draws into the block's little canvas.
 */

export type Fig = {
  ctx: CanvasRenderingContext2D;
  w: number;
  h: number;
  /** normalized value 0..1 */
  v: number;
  /** seconds, slow ambient clock */
  t: number;
  color: string;
};

function h01(seed: number): number {
  let x = Math.imul(seed ^ 0x9e3779b9, 0x85ebca6b);
  x ^= x >>> 13;
  x = Math.imul(x, 0xc2b2ae35);
  x ^= x >>> 16;
  return (x >>> 0) / 4294967296;
}

/** A Hann-ish spectral lobe centered at cx with half-width hw. */
function lobe(f: Fig, cx: number, hw: number, amp: number, jag = 0, seed = 0) {
  const { ctx, h } = f;
  ctx.beginPath();
  const y0 = h - 2;
  ctx.moveTo(cx - hw, y0);
  for (let i = 0; i <= 20; i++) {
    const u = i / 20;
    const x = cx - hw + u * 2 * hw;
    let y = amp * 0.5 * (1 - Math.cos(u * Math.PI * 2));
    if (jag > 0) y += jag * amp * (h01(seed + i * 17) - 0.5) * 0.9;
    ctx.lineTo(x, y0 - Math.max(0, y));
  }
  ctx.stroke();
}

const dim = "rgba(141,137,124,0.55)";

export const FIGURES: Record<number, (f: Fig) => void> = {
  // MIX — dry comb and wet comb crossfading
  1: (f) => {
    const { ctx, w, h, v } = f;
    const y0 = h - 2;
    for (let i = 0; i < 7; i++) {
      const x = 6 + (i * (w - 12)) / 6;
      const tall = (h - 6) * (0.5 + 0.5 * h01(i * 3));
      ctx.strokeStyle = dim;
      ctx.globalAlpha = Math.max(0.08, 1 - v);
      ctx.beginPath();
      ctx.moveTo(x, y0);
      ctx.lineTo(x, y0 - tall);
      ctx.stroke();
      ctx.strokeStyle = f.color;
      ctx.globalAlpha = Math.max(0.08, v);
      ctx.beginPath();
      ctx.moveTo(x + 3, y0);
      ctx.lineTo(x + 3, y0 - tall * 0.9);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  },
  // FEEL — micro-pitch wiggle re-injected around the locked target
  2: (f) => {
    const { ctx, w, h, v, t } = f;
    const mid = h / 2;
    ctx.strokeStyle = dim;
    ctx.beginPath();
    ctx.moveTo(2, mid);
    ctx.lineTo(w - 2, mid);
    ctx.stroke();
    ctx.strokeStyle = f.color;
    ctx.beginPath();
    for (let x = 2; x <= w - 2; x++) {
      const u = x / w;
      const wig =
        Math.sin(u * 19 + t * 2.1) * 0.6 + Math.sin(u * 47 + t * 3.7) * 0.4;
      const y = mid - wig * v * (h / 2 - 3);
      if (x === 2) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  },
  // GLIDE — the retune ramp stretching in time
  3: (f) => {
    const { ctx, w, h, v } = f;
    ctx.strokeStyle = dim;
    ctx.setLineDash([2, 3]);
    ctx.beginPath();
    ctx.moveTo(2, 4);
    ctx.lineTo(w - 2, 4);
    ctx.stroke();
    ctx.setLineDash([]);
    const ramp = 4 + v * (w - 14);
    ctx.strokeStyle = f.color;
    ctx.beginPath();
    ctx.moveTo(2, h - 4);
    ctx.lineTo(8, h - 4);
    ctx.lineTo(8 + ramp, 4);
    ctx.lineTo(w - 2, 4);
    ctx.stroke();
  },
  // GRIT — the clean lobe roughening
  4: (f) => {
    const { ctx, w, h, v, t } = f;
    ctx.strokeStyle = f.color;
    lobe(f, w / 2, w / 3, h - 7, v, Math.floor(t * 2) * 31);
  },
  // VOICES — the de-mixer's seats, filled per value
  5: (f) => {
    const { ctx, w, h, v } = f;
    const n = 12;
    const filled = Math.round(1 + v * 11);
    for (let i = 0; i < n; i++) {
      const x = 7 + (i * (w - 14)) / (n - 1);
      const y = h / 2;
      const r = 3.2;
      ctx.beginPath();
      for (let k = 0; k < 10; k++) {
        const a = (k * Math.PI) / 5 + i;
        const rr = k % 2 === 0 ? r : r * 0.45;
        const px = x + Math.cos(a) * rr;
        const py = y + Math.sin(a) * rr;
        if (k === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      if (i < filled) {
        ctx.fillStyle = f.color;
        ctx.fill();
      } else {
        ctx.strokeStyle = dim;
        ctx.stroke();
      }
    }
  },
  // GATE — a peak proving itself above the rising peakiness floor
  7: (f) => {
    const { ctx, w, h, v } = f;
    const y0 = h - 2;
    ctx.strokeStyle = dim;
    ctx.beginPath();
    for (let x = 2; x <= w - 2; x += 2) {
      const y = y0 - 3 - 2.5 * h01(x * 7);
      if (x === 2) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    const gateY = y0 - 4 - v * (h - 10);
    ctx.strokeStyle = f.color;
    ctx.setLineDash([3, 2]);
    ctx.beginPath();
    ctx.moveTo(2, gateY);
    ctx.lineTo(w - 2, gateY);
    ctx.stroke();
    ctx.setLineDash([]);
    const peakH = h - 7;
    ctx.strokeStyle = y0 - peakH < gateY ? f.color : dim;
    lobe(f, w * 0.55, 6, peakH);
  },
  // CEILING — mapping stops above the line; the air stays air
  9: (f) => {
    const { ctx, w, h, v } = f;
    const cut = 8 + v * (w - 14);
    const y0 = h - 2;
    for (let i = 0; i < 9; i++) {
      const x = 5 + (i * (w - 10)) / 8;
      const tall = (h - 6) * (1 - i / 11);
      ctx.strokeStyle = x <= cut ? f.color : dim;
      ctx.globalAlpha = x <= cut ? 1 : 0.45;
      ctx.beginPath();
      ctx.moveTo(x, y0);
      ctx.lineTo(x, y0 - tall);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.strokeStyle = f.color;
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(cut, 2);
    ctx.lineTo(cut, h - 2);
    ctx.stroke();
    ctx.setLineDash([]);
  },
  // COHERE — two channel phasors: locked image vs decorrelated wash
  13: (f) => {
    const { ctx, w, h, v, t } = f;
    const cx = w / 2;
    const cy = h / 2 + 1;
    const r = h / 2 - 3;
    ctx.strokeStyle = dim;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
    const base = t * 0.9;
    const spread = (1 - v) * 2.2;
    for (const [sign, alpha] of [
      [-1, 0.95],
      [1, 0.6],
    ] as const) {
      const a = base + (sign * spread) / 2;
      ctx.strokeStyle = f.color;
      ctx.globalAlpha = alpha;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  },
  // THRESH — the in-tune amnesty band around the chromatic line
  14: (f) => {
    const { ctx, w, h, v, t } = f;
    const mid = h / 2;
    const band = v * (h / 2 - 3);
    ctx.fillStyle = f.color;
    ctx.globalAlpha = 0.16;
    ctx.fillRect(2, mid - band, w - 4, band * 2);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = dim;
    ctx.beginPath();
    ctx.moveTo(2, mid);
    ctx.lineTo(w - 2, mid);
    ctx.stroke();
    // a wandering source dot: inside the band = spared (hollow)
    const wander = Math.sin(t * 1.3) * (h / 2 - 4);
    const inside = Math.abs(wander) < band;
    const dx = w * 0.62;
    ctx.beginPath();
    ctx.arc(dx, mid - wander, 2.6, 0, Math.PI * 2);
    if (inside) {
      ctx.strokeStyle = f.color;
      ctx.stroke();
    } else {
      ctx.fillStyle = f.color;
      ctx.fill();
    }
  },
  // FORMANT — the envelope holds while the comb slides under it
  15: (f) => {
    const { ctx, w, h, v, t } = f;
    const y0 = h - 2;
    const env = (x: number) => {
      const u = x / w;
      return (
        (h - 8) *
        (0.55 * Math.exp(-(((u - 0.3) * 4.2) ** 2)) +
          0.85 * Math.exp(-(((u - 0.62) * 5.5) ** 2)))
      );
    };
    ctx.strokeStyle = dim;
    ctx.beginPath();
    for (let x = 2; x <= w - 2; x += 2) {
      const y = y0 - env(x) - 2;
      if (x === 2) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    const drift = (t * 6) % 12;
    ctx.strokeStyle = f.color;
    for (let x = 4 + drift; x < w - 2; x += 12) {
      const flat = (h - 8) * 0.6;
      const tall = flat + v * (env(x) - flat);
      ctx.beginPath();
      ctx.moveTo(x, y0);
      ctx.lineTo(x, y0 - Math.max(2, tall));
      ctx.stroke();
    }
  },
  // CARRY — the mainlobe keeps its skirt (the breath between partials)
  16: (f) => {
    const { ctx, w, h, v } = f;
    ctx.strokeStyle = f.color;
    lobe(f, w / 2, 7, h - 7);
    ctx.fillStyle = f.color;
    for (let i = 0; i < 14; i++) {
      const side = i % 2 === 0 ? -1 : 1;
      const x = w / 2 + side * (10 + h01(i * 13) * (w / 2 - 14));
      const y = h - 4 - h01(i * 29) * (h * 0.35);
      ctx.globalAlpha = 0.15 + 0.75 * v;
      ctx.fillRect(x, y, 1.5, 1.5);
    }
    ctx.globalAlpha = 1;
  },
};
