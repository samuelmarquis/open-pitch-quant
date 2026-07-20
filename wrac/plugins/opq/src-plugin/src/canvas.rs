//! The panel's painter: alpha compositing, additive phosphor, sprites with
//! tint/scale, and the two voices of text — the 5x7 machine stencil and the
//! rasterized grotesk, the latter with optional damage (SLIP scan-slips,
//! CRUNCH 1-bit thresholding).

use crate::assets::{Atlas, Sprite};
use crate::font::stencil;

pub(crate) type Ink = [u8; 3];

#[derive(Clone, Copy, PartialEq)]
pub(crate) enum Voice {
    Clean,
    Slip,
    Crunch,
}

pub(crate) struct Canvas<'a> {
    pub(crate) fb: &'a mut [u8],
    pub(crate) w: usize,
    pub(crate) h: usize,
}

impl<'a> Canvas<'a> {
    pub(crate) fn new(fb: &'a mut [u8], w: usize, h: usize) -> Self {
        Self { fb, w, h }
    }

    pub(crate) fn clear(&mut self) {
        for px in self.fb.chunks_exact_mut(4) {
            px.copy_from_slice(&[0, 0, 0, 255]);
        }
    }

    /// Source-over blend at alpha a (0..=255).
    #[inline]
    pub(crate) fn mix(&mut self, x: i32, y: i32, ink: Ink, a: u8) {
        if x < 0 || y < 0 || x >= self.w as i32 || y >= self.h as i32 || a == 0 {
            return;
        }
        let i = (y as usize * self.w + x as usize) * 4;
        let na = a as u32;
        for k in 0..3 {
            let d = self.fb[i + k] as u32;
            self.fb[i + k] = ((ink[k] as u32 * na + d * (255 - na)) / 255) as u8;
        }
    }

    pub(crate) fn fill(&mut self, x: i32, y: i32, w: i32, h: i32, ink: Ink, a: u8) {
        for yy in y..y + h {
            for xx in x..x + w {
                self.mix(xx, yy, ink, a);
            }
        }
    }

    pub(crate) fn frame(&mut self, x: i32, y: i32, w: i32, h: i32, ink: Ink, a: u8) {
        for xx in x..x + w {
            self.mix(xx, y, ink, a);
            self.mix(xx, y + h - 1, ink, a);
        }
        for yy in y..y + h {
            self.mix(x, yy, ink, a);
            self.mix(x + w - 1, yy, ink, a);
        }
    }

    pub(crate) fn hline_dotted(&mut self, x0: i32, x1: i32, y: i32, ink: Ink, a: u8, period: i32) {
        let mut x = x0;
        while x < x1 {
            self.mix(x, y, ink, a);
            x += period;
        }
    }

    pub(crate) fn line(&mut self, x0: i32, y0: i32, x1: i32, y1: i32, ink: Ink, a: u8) {
        let (mut x, mut y) = (x0, y0);
        let dx = (x1 - x0).abs();
        let dy = -(y1 - y0).abs();
        let sx = if x0 < x1 { 1 } else { -1 };
        let sy = if y0 < y1 { 1 } else { -1 };
        let mut err = dx + dy;
        loop {
            self.mix(x, y, ink, a);
            if x == x1 && y == y1 {
                break;
            }
            let e2 = 2 * err;
            if e2 >= dy {
                err += dy;
                x += sx;
            }
            if e2 <= dx {
                err += dx;
                y += sy;
            }
        }
    }

    pub(crate) fn ring(&mut self, cx: i32, cy: i32, r: i32, ink: Ink, a: u8) {
        let mut x = r;
        let mut y = 0;
        let mut err = 1 - r;
        while x >= y {
            for &(px, py) in &[
                (x, y), (y, x), (-y, x), (-x, y), (-x, -y), (-y, -x), (y, -x), (x, -y),
            ] {
                self.mix(cx + px, cy + py, ink, a);
            }
            y += 1;
            if err < 0 {
                err += 2 * y + 1;
            } else {
                x -= 1;
                err += 2 * (y - x) + 1;
            }
        }
    }

    pub(crate) fn disc(&mut self, cx: i32, cy: i32, r: i32, ink: Ink, a: u8) {
        for yy in -r..=r {
            for xx in -r..=r {
                if xx * xx + yy * yy <= r * r {
                    self.mix(cx + xx, cy + yy, ink, a);
                }
            }
        }
    }

    /// Blit a sprite frame with a tint (multiplies RGB), a global alpha
    /// multiplier, and a nearest-neighbour scale of num/den.
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn blit(
        &mut self,
        s: &Sprite,
        frame: usize,
        dx: i32,
        dy: i32,
        tint: Ink,
        alpha_mul: f32,
        num: usize,
        den: usize,
    ) {
        let frame = frame.min(s.frames.saturating_sub(1));
        let ow = s.w * num / den;
        let oh = s.h * num / den;
        for oy in 0..oh {
            let sy = oy * den / num;
            for ox in 0..ow {
                let sx = ox * den / num;
                let p = s.px(frame, sx, sy);
                let a = (p[3] as f32 * alpha_mul) as u8;
                if a == 0 {
                    continue;
                }
                let ink = [
                    ((p[0] as u16 * tint[0] as u16) / 255) as u8,
                    ((p[1] as u16 * tint[1] as u16) / 255) as u8,
                    ((p[2] as u16 * tint[2] as u16) / 255) as u8,
                ];
                self.mix(dx + ox as i32, dy + oy as i32, ink, a);
            }
        }
    }

    /// 5x7 machine stencil. Returns the advance.
    pub(crate) fn text5(&mut self, s: &str, x: i32, y: i32, ink: Ink, a: u8) -> i32 {
        let mut pen = x;
        for c in s.chars() {
            let g = stencil(c);
            for (ry, row) in g.iter().enumerate() {
                for bx in 0..5 {
                    if row & (0x10 >> bx) != 0 {
                        self.mix(pen + bx, y + ry as i32, ink, a);
                    }
                }
            }
            pen += 6;
        }
        pen - x
    }

    /// Rasterized grotesk at the baseline `(x, base_y)`. Damage per `voice`.
    /// Returns the advance.
    pub(crate) fn haas(
        &mut self,
        atlas: &Atlas,
        s: &str,
        x: i32,
        base_y: i32,
        ink: Ink,
        opacity: f32,
        voice: Voice,
    ) -> i32 {
        let mut pen = x;
        for (ci, c) in s.chars().enumerate() {
            let Some(g) = atlas.glyph(c) else {
                pen += 3;
                continue;
            };
            // fontdue: ymin is the bottom edge relative to baseline, y-up.
            let top = base_y - (g.ymin + g.h as i32);
            for gy in 0..g.h {
                // SLIP: sparse scan-slips, deterministic per row+glyph.
                let slip = if voice == Voice::Slip && (gy as i32 + top + ci as i32) % 9 == 0 {
                    1
                } else {
                    0
                };
                for gx in 0..g.w {
                    let mut a = g.alpha[gy * g.w + gx] as f32 * opacity;
                    if voice == Voice::Crunch {
                        a = if a > 96.0 { 255.0 * opacity } else { 0.0 };
                    }
                    if a >= 1.0 {
                        let yy = top + gy as i32
                            + if voice == Voice::Crunch && (pen + gx as i32) % 5 == 0 {
                                1
                            } else {
                                0
                            };
                        self.mix(pen + g.xmin + gx as i32 + slip, yy, ink, a as u8);
                    }
                }
            }
            pen += g.advance as i32;
        }
        pen - x
    }
}
