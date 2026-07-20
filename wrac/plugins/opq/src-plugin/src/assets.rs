//! Baked collage assets, embedded whole. Formats are authored by
//! tools/bake-assets (see its header); parsing is zero-copy slices into the
//! embedded bins. Sources and licenses: docs/design/assets-sources.md.

use std::sync::OnceLock;

pub(crate) struct Sprite {
    pub(crate) w: usize,
    pub(crate) h: usize,
    pub(crate) frames: usize,
    data: &'static [u8],
}

impl Sprite {
    fn parse(bin: &'static [u8]) -> Self {
        assert_eq!(&bin[0..4], b"OPQR");
        let rd = |i: usize| u16::from_le_bytes([bin[i], bin[i + 1]]) as usize;
        let (w, h, frames) = (rd(4), rd(6), rd(8));
        let data = &bin[12..];
        assert_eq!(data.len(), w * h * frames * 4);
        Self { w, h, frames, data }
    }

    /// RGBA at (x, y) of `frame` (straight alpha).
    #[inline]
    pub(crate) fn px(&self, frame: usize, x: usize, y: usize) -> [u8; 4] {
        let i = ((frame * self.h + y) * self.w + x) * 4;
        [self.data[i], self.data[i + 1], self.data[i + 2], self.data[i + 3]]
    }
}

pub(crate) struct Glyph {
    pub(crate) w: usize,
    pub(crate) h: usize,
    pub(crate) xmin: i32,
    pub(crate) ymin: i32,
    pub(crate) advance: u32,
    pub(crate) alpha: &'static [u8],
}

/// A rasterized grotesk atlas (see bake-assets: fontdue metrics — `ymin` is
/// the glyph's bottom edge relative to the baseline, y-up).
pub(crate) struct Atlas {
    #[allow(dead_code)] // .font header field; no reader yet
    pub(crate) ascent: i32,
    glyphs: Vec<Option<Glyph>>,
}

impl Atlas {
    fn parse(bin: &'static [u8]) -> Self {
        assert_eq!(&bin[0..4], b"OPQF");
        let n = u16::from_le_bytes([bin[4], bin[5]]) as usize;
        let ascent = i16::from_le_bytes([bin[8], bin[9]]) as i32;
        let mut glyphs: Vec<Option<Glyph>> = (0..128).map(|_| None).collect();
        let mut o = 12usize;
        for _ in 0..n {
            let code = bin[o] as usize;
            let (w, h) = (bin[o + 1] as usize, bin[o + 2] as usize);
            let xmin = bin[o + 3] as i8 as i32;
            let ymin = bin[o + 4] as i8 as i32;
            let advance = bin[o + 5] as u32;
            o += 6;
            let alpha = &bin[o..o + w * h];
            o += w * h;
            if code < 128 {
                glyphs[code] = Some(Glyph { w, h, xmin, ymin, advance, alpha });
            }
        }
        Self { ascent, glyphs }
    }

    #[inline]
    pub(crate) fn glyph(&self, c: char) -> Option<&Glyph> {
        self.glyphs.get(c as usize)?.as_ref()
    }

    pub(crate) fn measure(&self, s: &str) -> u32 {
        s.chars()
            .map(|c| self.glyph(c).map(|g| g.advance).unwrap_or(3))
            .sum()
    }
}

macro_rules! sprite {
    ($fn_name:ident, $file:literal) => {
        pub(crate) fn $fn_name() -> &'static Sprite {
            static S: OnceLock<Sprite> = OnceLock::new();
            S.get_or_init(|| Sprite::parse(include_bytes!(concat!("../assets/", $file))))
        }
    };
}
macro_rules! atlas {
    ($fn_name:ident, $file:literal) => {
        pub(crate) fn $fn_name() -> &'static Atlas {
            static A: OnceLock<Atlas> = OnceLock::new();
            A.get_or_init(|| Atlas::parse(include_bytes!(concat!("../assets/", $file))))
        }
    };
}

sprite!(chladni, "chladni.rgba");
sprite!(trefoil, "trefoil.rgba");
sprite!(gray907, "gray907.rgba");
sprite!(phonautograph, "phonautograph.rgba");
sprite!(blake_ear, "blake_ear.rgba");
sprite!(redon_ghost, "redon_ghost.rgba");
atlas!(haas10, "haas10.font");
atlas!(haas14, "haas14.font");
atlas!(haas30, "haas30.font");
