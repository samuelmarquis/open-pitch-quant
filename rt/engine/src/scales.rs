//! The Key Transform (Sam, 2026-10-11): a source key and scale, a
//! destination key and scale, and the note-to-note map between them.
//!
//! PITCHMAP's scale presets assume the input is in C major; this names the
//! source instead. The destination is the Keys source's target set (the
//! ruler): choosing a destination scale writes it there, and a hand-edited
//! ruler reads back as a known scale or as none. The source side is
//! [`KeyTransform`]; with the targets it gives the engine a [`Remap`].
//!
//! The rule, one and the same everywhere:
//! - A key of [`ANY_KEY`] ("*") adopts the other side's; both "*" is C.
//! - The key change is the shortest way round (a tritone goes down).
//! - Scales of the same size map degree to degree (C major to C minor: E
//!   to E flat). Scales of different sizes map each source degree, after
//!   the key change, to the nearest destination degree, a tie going down.
//! - A source note off the source scale is first pulled to its nearest
//!   source degree, a tie going down.
//! - A chromatic source in the destination's key is no remap at all: the
//!   engine pulls each pitch to its nearest target, as it always has.

/// A scale: its name and its pitch classes above the root (bit i is i
/// semitones up; bit 0, the root, is always set).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Scale {
    pub name: &'static str,
    pub classes: u16,
}

const fn scale<const N: usize>(name: &'static str, steps: [u8; N]) -> Scale {
    let mut classes = 0u16;
    let mut i = 0;
    while i < N {
        classes |= 1 << steps[i];
        i += 1;
    }
    Scale { name, classes }
}

pub const CHROMATIC: usize = 0;

/// The scales on offer, in the lists' order. No two share a set of pitch
/// classes, so a set read back from the ruler names one scale at most.
pub const SCALES: [Scale; 31] = [
    scale("CHROMATIC", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]),
    scale("MAJOR", [0, 2, 4, 5, 7, 9, 11]),
    scale("MINOR", [0, 2, 3, 5, 7, 8, 10]),
    scale("DORIAN", [0, 2, 3, 5, 7, 9, 10]),
    scale("PHRYGIAN", [0, 1, 3, 5, 7, 8, 10]),
    scale("LYDIAN", [0, 2, 4, 6, 7, 9, 11]),
    scale("MIXOLYDIAN", [0, 2, 4, 5, 7, 9, 10]),
    scale("LOCRIAN", [0, 1, 3, 5, 6, 8, 10]),
    scale("HARMONIC MINOR", [0, 2, 3, 5, 7, 8, 11]),
    scale("MELODIC MINOR", [0, 2, 3, 5, 7, 9, 11]),
    scale("HARMONIC MAJOR", [0, 2, 4, 5, 7, 8, 11]),
    scale("PHRYGIAN DOMINANT", [0, 1, 4, 5, 7, 8, 10]),
    scale("LYDIAN DOMINANT", [0, 2, 4, 6, 7, 9, 10]),
    scale("ALTERED", [0, 1, 3, 4, 6, 8, 10]),
    scale("DOUBLE HARMONIC", [0, 1, 4, 5, 7, 8, 11]),
    scale("HUNGARIAN MINOR", [0, 2, 3, 6, 7, 8, 11]),
    scale("NEAPOLITAN MINOR", [0, 1, 3, 5, 7, 8, 11]),
    scale("NEAPOLITAN MAJOR", [0, 1, 3, 5, 7, 9, 11]),
    scale("ENIGMATIC", [0, 1, 4, 6, 8, 10, 11]),
    scale("PERSIAN", [0, 1, 4, 5, 6, 8, 11]),
    scale("MAJOR PENTATONIC", [0, 2, 4, 7, 9]),
    scale("MINOR PENTATONIC", [0, 3, 5, 7, 10]),
    scale("BLUES", [0, 3, 5, 6, 7, 10]),
    scale("WHOLE TONE", [0, 2, 4, 6, 8, 10]),
    scale("DIMINISHED W-H", [0, 2, 3, 5, 6, 8, 9, 11]),
    scale("DIMINISHED H-W", [0, 1, 3, 4, 6, 7, 9, 10]),
    scale("AUGMENTED", [0, 3, 4, 7, 8, 11]),
    scale("HIRAJOSHI", [0, 2, 3, 7, 8]),
    scale("IN SEN", [0, 1, 5, 7, 10]),
    scale("IWATO", [0, 1, 5, 6, 10]),
    scale("PROMETHEUS", [0, 2, 4, 6, 9, 10]),
];

/// The key names, C first; [`ANY_KEY`] reads "*".
pub const KEY_NAMES: [&str; 13] = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B", "*"];

/// "*": this side's key is the other side's.
pub const ANY_KEY: u8 = 12;

/// Pitch classes above a root, as absolute pitch classes (bit 0 is C).
pub fn absolute(classes: u16, root: u8) -> u16 {
    let root = (root % 12) as u32;
    ((classes << root) | (classes >> (12 - root))) & 0xfff
}

/// Absolute pitch classes, as classes above `root`.
pub fn relative(classes: u16, root: u8) -> u16 {
    absolute(classes, (12 - root % 12) % 12)
}

/// The scale whose pitch classes above `root` are exactly these absolute
/// ones, if any.
pub fn recognise(classes: u16, root: u8) -> Option<usize> {
    let above = relative(classes, root);
    SCALES.iter().position(|scale| scale.classes == above)
}

/// The source side of the transform, and the destination's key. The
/// destination's scale is the Keys target set itself.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct KeyTransform {
    /// 0..=11 (C..B), or [`ANY_KEY`].
    pub src_key: u8,
    /// An index into [`SCALES`].
    pub src_scale: u8,
    pub dst_key: u8,
}

impl Default for KeyTransform {
    /// "* CHROMATIC to *": no remap.
    fn default() -> Self {
        Self { src_key: ANY_KEY, src_scale: CHROMATIC as u8, dst_key: ANY_KEY }
    }
}

impl KeyTransform {
    /// As loaded: anything out of range falls back to its default.
    pub fn sanitised(self) -> Self {
        let key = |k: u8| if k <= ANY_KEY { k } else { ANY_KEY };
        Self {
            src_key: key(self.src_key),
            src_scale: if (self.src_scale as usize) < SCALES.len() { self.src_scale } else { CHROMATIC as u8 },
            dst_key: key(self.dst_key),
        }
    }

    /// The source's root: its own key, else the destination's, else C.
    pub fn src_root(&self) -> u8 {
        [self.src_key, self.dst_key].into_iter().find(|&k| k < ANY_KEY).unwrap_or(0)
    }

    /// The destination's root: its own key, else the source's, else C.
    pub fn dst_root(&self) -> u8 {
        [self.dst_key, self.src_key].into_iter().find(|&k| k < ANY_KEY).unwrap_or(0)
    }

    /// The map onto a destination of these absolute pitch classes (the
    /// Keys targets, every octave alike), or `None` where the engine's
    /// own nearest-target pull is the whole of it: a chromatic source in
    /// the destination's key, or no destination.
    pub fn remap(&self, dst_classes: u16) -> Option<Remap> {
        let (src_root, dst_root) = (self.src_root(), self.dst_root());
        // The key change, the shortest way round: -6..=5 semitones.
        let change = (dst_root as i32 - src_root as i32 + 18).rem_euclid(12) - 6;
        if dst_classes & 0xfff == 0 || (self.src_scale as usize == CHROMATIC && change == 0) {
            return None;
        }
        let degrees = |classes: u16| -> ([i32; 12], usize) {
            let mut out = [0; 12];
            let mut n = 0;
            for step in 0..12 {
                if classes >> step & 1 == 1 {
                    out[n] = step;
                    n += 1;
                }
            }
            (out, n)
        };
        let (src, src_n) = degrees(SCALES[self.src_scale as usize].classes);
        let (dst, dst_n) = degrees(relative(dst_classes, dst_root));
        let mut offset = [0i8; 12];
        for k in 0..src_n {
            let to = if src_n == dst_n {
                dst[k]
            } else {
                // The nearest destination degree, the octave's neighbours
                // included; ascending, so a tie keeps the lower.
                let mut best = dst[0] - 12;
                for wrap in [-12, 0, 12] {
                    for &degree in &dst[..dst_n] {
                        if (degree + wrap - src[k]).abs() < (best - src[k]).abs() {
                            best = degree + wrap;
                        }
                    }
                }
                best
            };
            offset[(src_root as usize + src[k] as usize) % 12] = (change + to - src[k]) as i8;
        }
        Some(Remap { src: absolute(SCALES[self.src_scale as usize].classes, src_root), offset })
    }
}

/// The engine's note-to-note map: the absolute pitch classes the source is
/// taken to be in, and for each of them how many semitones it moves.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Remap {
    pub src: u16,
    pub offset: [i8; 12],
}

impl Remap {
    /// The source note (MIDI, in the source scale) nearest a pitch given as
    /// a fractional MIDI note; a tie goes down.
    pub fn source_note(&self, note: f64) -> i32 {
        let floor = note.floor() as i32;
        let mut best = floor;
        let mut distance = f64::INFINITY;
        for n in floor - 12..=floor + 13 {
            if self.src >> n.rem_euclid(12) & 1 == 1 && (n as f64 - note).abs() < distance {
                distance = (n as f64 - note).abs();
                best = n;
            }
        }
        best
    }

    /// Where a source note is sung (MIDI).
    pub fn sung(&self, source_note: i32) -> i32 {
        source_note + self.offset[source_note.rem_euclid(12) as usize] as i32
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn index(name: &str) -> u8 {
        SCALES.iter().position(|s| s.name == name).unwrap() as u8
    }

    fn classes(name: &str, root: u8) -> u16 {
        absolute(SCALES[index(name) as usize].classes, root)
    }

    #[test]
    fn every_scale_is_rooted_and_no_two_are_the_same_set() {
        for (i, a) in SCALES.iter().enumerate() {
            assert_eq!(a.classes & 1, 1, "{}", a.name);
            for b in &SCALES[i + 1..] {
                assert_ne!(a.classes, b.classes, "{} and {}", a.name, b.name);
            }
            for root in 0..12 {
                assert_eq!(recognise(absolute(a.classes, root), root), Some(i), "{}", a.name);
            }
        }
        // F major read from C is C mixolydian; a stray set is no scale.
        assert_eq!(recognise(classes("MAJOR", 5), 0), Some(index("MIXOLYDIAN") as usize));
        assert_eq!(recognise(0b0000_0000_0111, 0), None);
    }

    #[test]
    fn a_chromatic_source_in_the_destinations_key_is_no_remap() {
        let any = KeyTransform::default();
        assert_eq!(any.remap(classes("MAJOR", 5)), None);
        // "* CHROMATIC to F": the source adopts F.
        let f = KeyTransform { dst_key: 5, ..any };
        assert_eq!((f.src_root(), f.dst_root()), (5, 5));
        assert_eq!(f.remap(classes("MAJOR", 5)), None);
        // No targets: nothing to map onto.
        let minor = KeyTransform { src_scale: index("MINOR"), ..any };
        assert_eq!(minor.remap(0), None);
    }

    #[test]
    fn same_sized_scales_map_degree_to_degree() {
        // C major to C minor: the third, sixth and seventh drop a semitone.
        let t = KeyTransform { src_key: 0, src_scale: index("MAJOR"), dst_key: ANY_KEY };
        let r = t.remap(classes("MINOR", 0)).unwrap();
        let sung: Vec<i32> = [60, 62, 64, 65, 67, 69, 71].iter().map(|&n| r.sung(n)).collect();
        assert_eq!(sung, [60, 62, 63, 65, 67, 68, 70]);
        // C major to F major: up a fourth (the shortest way), every degree.
        let t = KeyTransform { src_key: 0, src_scale: index("MAJOR"), dst_key: 5 };
        let r = t.remap(classes("MAJOR", 5)).unwrap();
        assert!((0..7).all(|k| r.sung([60, 62, 64, 65, 67, 69, 71][k]) == [65, 67, 69, 70, 72, 74, 76][k]));
        // C to G is down a fourth, and a tritone goes down.
        let g = KeyTransform { src_key: 0, src_scale: index("MAJOR"), dst_key: 7 }.remap(classes("MAJOR", 7)).unwrap();
        assert_eq!(g.sung(60), 55);
        let tritone = KeyTransform { src_key: 0, src_scale: CHROMATIC as u8, dst_key: 6 };
        assert_eq!(tritone.remap(0xfff).unwrap().sung(60), 54);
    }

    #[test]
    fn different_sizes_take_the_nearest_degree_and_ties_go_down() {
        // C major onto C major pentatonic (C D E G A): F is a semitone
        // from E and two from G; B is a semitone from C above.
        let t = KeyTransform { src_key: 0, src_scale: index("MAJOR"), dst_key: 0 };
        let r = t.remap(classes("MAJOR PENTATONIC", 0)).unwrap();
        let sung: Vec<i32> = [60, 62, 64, 65, 67, 69, 71].iter().map(|&n| r.sung(n)).collect();
        assert_eq!(sung, [60, 62, 64, 64, 67, 69, 72]);
        // C chromatic onto F major (a named source key moves it): C sharp
        // lands a fourth up on F sharp, between F and G, and goes down.
        let t = KeyTransform { src_key: 0, src_scale: CHROMATIC as u8, dst_key: 5 };
        let r = t.remap(classes("MAJOR", 5)).unwrap();
        assert_eq!((r.sung(60), r.sung(61)), (65, 65));
    }

    #[test]
    fn a_pitch_is_pulled_to_its_nearest_source_degree() {
        let t = KeyTransform { src_key: 0, src_scale: index("MAJOR"), dst_key: ANY_KEY };
        let r = t.remap(classes("MINOR", 0)).unwrap();
        assert_eq!(r.source_note(63.9), 64);
        assert_eq!(r.source_note(61.4), 62);
        // C sharp sits between C and D: down.
        assert_eq!(r.source_note(61.0), 60);
        assert_eq!(r.source_note(-0.4), 0);
    }

    #[test]
    fn a_loaded_transform_out_of_range_falls_back() {
        let t = KeyTransform { src_key: 40, src_scale: 200, dst_key: 12 }.sanitised();
        assert_eq!(t, KeyTransform::default());
    }
}
