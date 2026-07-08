/**
 * Idle-state attractor — a small fractal-flame-style IFS (chaos game over
 * drifting affine + sinusoidal/swirl variations, log-ish accumulation via
 * low-alpha plotting onto a persistent buffer). Runs only when the engine
 * feed is empty: the plugin dreaming until you give it sound.
 */

type Affine = { a: number; b: number; c: number; d: number; e: number; f: number };

export class IdleFlame {
  private buffer: HTMLCanvasElement;
  private bctx: CanvasRenderingContext2D;
  private x = 0.1;
  private y = 0.1;

  constructor() {
    this.buffer = document.createElement("canvas");
    const ctx = this.buffer.getContext("2d");
    if (!ctx) throw new Error("no 2d context");
    this.bctx = ctx;
  }

  /** Advance the chaos game and composite onto `ctx`, centered. */
  step(ctx: CanvasRenderingContext2D, w: number, h: number, tMs: number): void {
    const bw = Math.max(160, Math.floor(w / 2));
    const bh = Math.max(160, Math.floor(h / 2));
    if (this.buffer.width !== bw || this.buffer.height !== bh) {
      this.buffer.width = bw;
      this.buffer.height = bh;
    }
    const b = this.bctx;
    // slow fade — the accumulation buffer breathes rather than smears
    b.fillStyle = "rgba(0,0,0,0.03)";
    b.fillRect(0, 0, bw, bh);

    const t = tMs * 0.00005;
    const maps: Affine[] = [
      { a: 0.62 * Math.cos(t), b: -0.6 * Math.sin(t * 0.7), c: 0.6 * Math.sin(t * 0.7), d: 0.62 * Math.cos(t), e: 0.18 * Math.sin(t * 1.3), f: 0.0 },
      { a: -0.45, b: 0.5 + 0.1 * Math.sin(t * 0.9), c: -0.5, d: -0.45, e: 0.35, f: 0.12 * Math.cos(t * 1.1) },
      { a: 0.3, b: 0.0, c: 0.0, d: 0.3, e: -0.4 * Math.cos(t * 0.6), f: 0.4 * Math.sin(t * 0.8) },
    ];
    const scale = Math.min(bw, bh) * 0.42;
    const cx = bw / 2;
    const cy = bh / 2;
    const hueMix = 0.5 + 0.5 * Math.sin(t * 2.1);
    const r = Math.round(79 + (255 - 79) * hueMix);
    const g = Math.round(242 + (63 - 242) * hueMix);
    const bl = Math.round(210 + (212 - 210) * hueMix);
    b.fillStyle = `rgba(${r},${g},${bl},0.07)`;

    let { x, y } = this;
    for (let i = 0; i < 9000; i++) {
      const m = maps[(Math.random() * maps.length) | 0];
      let nx = m.a * x + m.b * y + m.e;
      let ny = m.c * x + m.d * y + m.f;
      // sinusoidal + swirl variations, blended
      const r2 = nx * nx + ny * ny;
      const sx = Math.sin(nx);
      const sy = Math.sin(ny);
      const swx = nx * Math.sin(r2) - ny * Math.cos(r2);
      const swy = nx * Math.cos(r2) + ny * Math.sin(r2);
      nx = 0.65 * sx + 0.35 * swx;
      ny = 0.65 * sy + 0.35 * swy;
      x = nx;
      y = ny;
      if (i > 16) {
        b.fillRect(cx + x * scale, cy + y * scale, 1, 1);
      }
    }
    this.x = x;
    this.y = y;

    ctx.save();
    ctx.globalAlpha = 0.75;
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(this.buffer, 0, 0, bw, bh, 0, 0, w, h);
    ctx.restore();
  }
}
