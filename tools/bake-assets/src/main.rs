//! Offline bakery for the panel's collage layer. Emits raw asset bins the
//! plugin embeds via include_bytes! — the plugin never decodes PNG/JPEG or
//! touches font machinery at runtime.
//!
//! Formats (little-endian):
//!   .rgba sprite/strip:  "OPQR" u16 w, u16 h, u16 frames, u16 _pad,
//!                        then frames*w*h*4 bytes RGBA (straight alpha).
//!   .font glyph atlas:   "OPQF" u16 n, u16 px, i16 ascent, u16 _pad, then n
//!                        records: u8 code, u8 w, u8 h, i8 xmin, i8 ymin,
//!                        u8 advance, then w*h alpha bytes. (fontdue metrics:
//!                        ymin is the glyph bottom relative to baseline, y-up.)
//!
//! Run from tools/bake-assets:  cargo run --release
//! Inputs: scratchpad plunder dir (Commons downloads) + design-refs.
//! Outputs: wrac/plugins/opq/src-plugin/assets/ + PNG previews in scratchpad.

use image::GenericImageView;
use std::f64::consts::PI;
use std::path::Path;

const OUT: &str = "../../wrac/plugins/opq/src-plugin/assets";
const PLUNDER: &str = "/private/tmp/claude-501/-Users-sam-Developer-open-pitch-quant/3ff53855-9ed2-4bdf-bfb0-36e3f350bb55/scratchpad/plunder";
const PREVIEW: &str = "/private/tmp/claude-501/-Users-sam-Developer-open-pitch-quant/3ff53855-9ed2-4bdf-bfb0-36e3f350bb55/scratchpad/previews";

fn main() {
    std::fs::create_dir_all(OUT).unwrap();
    std::fs::create_dir_all(PREVIEW).unwrap();

    engraving("gray907.png", "gray907", 300, 0.9, true);
    engraving("phonautograph1859.jpg", "phonautograph", 460, 0.85, true);
    engraving("blake_ear.jpg", "blake_ear", 420, 0.9, true);
    redon_ghost();
    chladni();
    trefoil();
    font_atlas(10.0, "haas10");
    font_atlas(14.0, "haas14");
    font_atlas(30.0, "haas30");
    println!("bakery done");
}

fn write_rgba(name: &str, w: usize, h: usize, frames: usize, data: &[u8]) {
    assert_eq!(data.len(), w * h * frames * 4);
    let mut out = Vec::with_capacity(12 + data.len());
    out.extend_from_slice(b"OPQR");
    out.extend_from_slice(&(w as u16).to_le_bytes());
    out.extend_from_slice(&(h as u16).to_le_bytes());
    out.extend_from_slice(&(frames as u16).to_le_bytes());
    out.extend_from_slice(&0u16.to_le_bytes());
    out.extend_from_slice(data);
    std::fs::write(format!("{OUT}/{name}.rgba"), &out).unwrap();
    // Preview: frames tiled horizontally on black.
    let mut img = image::RgbaImage::new((w * frames) as u32, h as u32);
    for f in 0..frames {
        for y in 0..h {
            for x in 0..w {
                let i = ((f * h + y) * w + x) * 4;
                let a = data[i + 3] as u32;
                let px = [
                    ((data[i] as u32 * a) / 255) as u8,
                    ((data[i + 1] as u32 * a) / 255) as u8,
                    ((data[i + 2] as u32 * a) / 255) as u8,
                    255,
                ];
                img.put_pixel((f * w + x) as u32, y as u32, image::Rgba(px));
            }
        }
    }
    img.save(format!("{PREVIEW}/{name}.png")).unwrap();
    println!("baked {name}: {w}x{h} x{frames}");
}

/// Ink-on-white engraving -> white ink on transparency (tint at composite).
fn engraving(input: &str, name: &str, target_w: usize, gamma: f64, _unused: bool) {
    let img = image::open(Path::new(PLUNDER).join(input)).unwrap();
    let (iw, ih) = img.dimensions();
    let th = (target_w as f64 * ih as f64 / iw as f64).round() as usize;
    let img = img
        .resize_exact(target_w as u32, th as u32, image::imageops::FilterType::Triangle)
        .to_luma8();
    // Percentile stretch so paper ~0 ink, dark ink ~1.
    let mut hist = [0u32; 256];
    for p in img.pixels() {
        hist[p.0[0] as usize] += 1;
    }
    let total: u32 = hist.iter().sum();
    let pct = |q: f64| -> u8 {
        let mut acc = 0u32;
        for (v, &c) in hist.iter().enumerate() {
            acc += c;
            if acc as f64 >= q * total as f64 {
                return v as u8;
            }
        }
        255
    };
    let (lo, hi) = (pct(0.02) as f64, pct(0.85) as f64);
    let mut data = vec![0u8; target_w * th * 4];
    for (i, p) in img.pixels().enumerate() {
        let v = p.0[0] as f64;
        let ink = 1.0 - ((v - lo) / (hi - lo).max(1.0)).clamp(0.0, 1.0);
        let a = (ink.powf(gamma) * 255.0) as u8;
        data[i * 4..i * 4 + 4].copy_from_slice(&[255, 255, 255, a]);
    }
    write_rgba(name, target_w, th, 1, &data);
}

/// The one-eyed watcher, as a barely-there continuous-tone ghost.
fn redon_ghost() {
    let img = image::open("../../design-refs/ugliness.jpg").unwrap();
    let w = 300usize;
    let (iw, ih) = img.dimensions();
    let h = (w as f64 * ih as f64 / iw as f64).round() as usize;
    let img = img
        .resize_exact(w as u32, h as u32, image::imageops::FilterType::Triangle)
        .to_luma8();
    let mut data = vec![0u8; w * h * 4];
    for (i, p) in img.pixels().enumerate() {
        let v = p.0[0] as f64 / 255.0;
        let g = (v.powf(1.4) * 235.0) as u8;
        // Vignette so the ghost dissolves at its edges.
        let (x, y) = (i % w, i / w);
        let dx = (x as f64 / w as f64 - 0.5) * 2.0;
        let dy = (y as f64 / h as f64 - 0.5) * 2.0;
        let vin = (1.0 - (dx * dx + dy * dy).sqrt()).clamp(0.0, 1.0);
        let a = (v.powf(1.8) * vin.powf(1.5) * 110.0) as u8;
        data[i * 4..i * 4 + 4].copy_from_slice(&[g, g, g, a]);
    }
    write_rgba("redon_ghost", w, h, 1, &data);
}

fn hash01(a: u64, b: u64) -> f64 {
    let mut h = a.wrapping_mul(0x9E3779B97F4A7C15) ^ b.wrapping_mul(0xD1B54A32D192ED03);
    h ^= h >> 32;
    h = h.wrapping_mul(0xD6E8FEB86659FD93);
    h ^= h >> 32;
    (h & 0xFFFFFF) as f64 / 16_777_216.0
}

/// Seven sand figures for a square plate: frame k = k tones held (0 = dust).
fn chladni() {
    const S: usize = 128;
    let modes: [(f64, f64, f64); 7] = [
        (0.0, 0.0, 0.0), // dust
        (1.0, 2.0, 1.0),
        (2.0, 3.0, 1.0),
        (3.0, 4.0, -1.0),
        (3.0, 5.0, 1.0),
        (4.0, 6.0, -1.0),
        (5.0, 7.0, 1.0),
    ];
    let mut data = vec![0u8; S * S * 7 * 4];
    for (f, &(n, m, s)) in modes.iter().enumerate() {
        for y in 0..S {
            for x in 0..S {
                let u = x as f64 / (S - 1) as f64 * 2.0 - 1.0;
                let v = y as f64 / (S - 1) as f64 * 2.0 - 1.0;
                let a = if f == 0 {
                    0.05 * hash01(x as u64, y as u64 + 7777)
                } else {
                    let chi = (n * PI * u / 2.0).cos() * (m * PI * v / 2.0).cos()
                        + s * (m * PI * u / 2.0).cos() * (n * PI * v / 2.0).cos();
                    let sand = (-(chi.abs() * 6.5).powf(1.35)).exp();
                    sand * (0.5 + 0.5 * hash01(x as u64 + f as u64 * 131, y as u64))
                };
                let i = ((f * S + y) * S + x) * 4;
                let ab = (a * 255.0).clamp(0.0, 255.0) as u8;
                data[i..i + 4].copy_from_slice(&[236, 232, 220, ab]);
            }
        }
    }
    write_rgba("chladni", S, S, 7, &data);
}

/// Glass trefoil knot turntable: 24 frames, rim-lit fake refraction on black.
fn trefoil() {
    const W: usize = 128;
    const H: usize = 144;
    const FRAMES: usize = 24;

    fn curve(t: f64) -> [f64; 3] {
        let s = 0.42;
        [
            s * ((t).sin() + 2.0 * (2.0 * t).sin()),
            s * ((t).cos() - 2.0 * (2.0 * t).cos()),
            s * -(3.0 * t).sin(),
        ]
    }
    fn rot(p: [f64; 3], ay: f64, ax: f64) -> [f64; 3] {
        let (sy, cy) = ay.sin_cos();
        let p = [p[0] * cy + p[2] * sy, p[1], -p[0] * sy + p[2] * cy];
        let (sx, cx) = ax.sin_cos();
        [p[0], p[1] * cx - p[2] * sx, p[1] * sx + p[2] * cx]
    }
    fn dist(p: [f64; 3]) -> f64 {
        // Coarse bracket then local refinement around the best sample.
        let mut best = f64::INFINITY;
        let mut bt = 0.0;
        for i in 0..36 {
            let t = i as f64 / 36.0 * 2.0 * PI;
            let c = curve(t);
            let d = ((p[0] - c[0]).powi(2) + (p[1] - c[1]).powi(2) + (p[2] - c[2]).powi(2)).sqrt();
            if d < best {
                best = d;
                bt = t;
            }
        }
        let mut span = 2.0 * PI / 36.0;
        for _ in 0..5 {
            for &t in &[bt - span * 0.5, bt + span * 0.5] {
                let c = curve(t);
                let d =
                    ((p[0] - c[0]).powi(2) + (p[1] - c[1]).powi(2) + (p[2] - c[2]).powi(2)).sqrt();
                if d < best {
                    best = d;
                    bt = t;
                }
            }
            span *= 0.5;
        }
        best - 0.30
    }

    let mut data = vec![0u8; W * H * FRAMES * 4];
    for f in 0..FRAMES {
        let ay = f as f64 / FRAMES as f64 * 2.0 * PI;
        let ax = 0.45 + 0.18 * (ay * 2.0).sin();
        for py in 0..H {
            for px in 0..W {
                let u = (px as f64 + 0.5) / W as f64 * 2.0 - 1.0;
                let v = ((py as f64 + 0.5) / H as f64 * 2.0 - 1.0) * (H as f64 / W as f64);
                let rd = {
                    let d = [u * 0.62, -v * 0.62, 1.0];
                    let l = (d[0] * d[0] + d[1] * d[1] + d[2] * d[2]).sqrt();
                    [d[0] / l, d[1] / l, d[2] / l]
                };
                let ro = [0.0, 0.0, -3.1];
                let mut t = 0.0;
                let mut hit = None;
                for _ in 0..110 {
                    let p = [ro[0] + rd[0] * t, ro[1] + rd[1] * t, ro[2] + rd[2] * t];
                    let q = rot(p, ay, ax);
                    let d = dist(q);
                    if d < 0.005 {
                        hit = Some(q);
                        break;
                    }
                    t += d * 0.8;
                    if t > 6.0 {
                        break;
                    }
                }
                let i = ((f * H + py) * W + px) * 4;
                if let Some(q) = hit {
                    let e = 0.012;
                    let n = {
                        let dx = dist([q[0] + e, q[1], q[2]]) - dist([q[0] - e, q[1], q[2]]);
                        let dy = dist([q[0], q[1] + e, q[2]]) - dist([q[0], q[1] - e, q[2]]);
                        let dz = dist([q[0], q[1], q[2] + e]) - dist([q[0], q[1], q[2] - e]);
                        let l = (dx * dx + dy * dy + dz * dz).sqrt().max(1e-9);
                        [dx / l, dy / l, dz / l]
                    };
                    // View is ~+z in object space after rotation; keep it cheap.
                    let ndv = (-n[2]).clamp(-1.0, 1.0);
                    let fresnel = (1.0 - ndv.abs()).powf(2.4);
                    let lgt = [0.42, 0.78, -0.46];
                    let ndl = (n[0] * lgt[0] + n[1] * lgt[1] + n[2] * lgt[2]).max(0.0);
                    let r = [
                        rd[0] - 2.0 * ndv * n[0],
                        rd[1] - 2.0 * ndv * n[1],
                        rd[2] - 2.0 * ndv * n[2],
                    ];
                    let spec = (r[0] * lgt[0] + r[1] * lgt[1] + r[2] * lgt[2])
                        .max(0.0)
                        .powf(26.0);
                    let interior = 0.5 + 0.5 * (q[1] * 9.0 + q[0] * 5.0).sin();
                    let lum = 0.24 + 0.26 * interior + 0.95 * fresnel + 0.38 * ndl.powi(2)
                        + 1.2 * spec;
                    let a = (0.34 + 0.60 * fresnel + 0.5 * spec).clamp(0.0, 1.0);
                    let c = (lum * 255.0).clamp(0.0, 255.0) as u8;
                    data[i..i + 4].copy_from_slice(&[c, c, c, (a * 255.0) as u8]);
                }
            }
        }
        println!("trefoil frame {f}");
    }
    write_rgba("trefoil", W, H, FRAMES, &data);
}

/// Rasterize the house grotesk (Helvetica Neue — Neue Haas Grotesk's direct
/// descendant) into a fixed alpha atlas. Provenance in assets-sources.md.
fn font_atlas(px: f32, name: &str) {
    let bytes = std::fs::read("/System/Library/Fonts/HelveticaNeue.ttc").unwrap();
    let font = fontdue::Font::from_bytes(
        bytes.as_slice(),
        fontdue::FontSettings {
            collection_index: 0,
            ..Default::default()
        },
    )
    .unwrap();
    let ascent = font
        .horizontal_line_metrics(px)
        .map(|m| m.ascent)
        .unwrap_or(px * 0.8);
    let mut out = Vec::new();
    out.extend_from_slice(b"OPQF");
    let chars: Vec<char> = (32u8..127).map(|c| c as char).collect();
    out.extend_from_slice(&(chars.len() as u16).to_le_bytes());
    out.extend_from_slice(&(px as u16).to_le_bytes());
    out.extend_from_slice(&(ascent.round() as i16).to_le_bytes());
    out.extend_from_slice(&0u16.to_le_bytes());
    for &ch in &chars {
        let (m, bitmap) = font.rasterize(ch, px);
        assert!(m.width < 256 && m.height < 256, "glyph too large");
        out.push(ch as u8);
        out.push(m.width as u8);
        out.push(m.height as u8);
        out.push(m.xmin.clamp(-128, 127) as i8 as u8);
        out.push(m.ymin.clamp(-128, 127) as i8 as u8);
        out.push(m.advance_width.round().clamp(0.0, 255.0) as u8);
        out.extend_from_slice(&bitmap);
    }
    std::fs::write(format!("{OUT}/{name}.font"), &out).unwrap();
    println!("baked {name}: {} glyphs at {px}px", chars.len());
}
