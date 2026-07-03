"""Audio + MIDI loading utilities for the offline prototype."""

import mido
import numpy as np
import scipy.signal
import soundfile as sf

SR = 48000

_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def load_audio(path, sr=SR):
    """Load any audio file → mono float64 at `sr`."""
    x, fs = sf.read(str(path), always_2d=True)
    x = x.mean(axis=1)
    if fs != sr:
        g = np.gcd(int(fs), sr)
        x = scipy.signal.resample_poly(x, sr // g, int(fs) // g)
    return x


def save_audio(path, x, sr=SR):
    peak = np.max(np.abs(x))
    if peak > 0.99:  # clip guard only; otherwise preserve gain
        x = x * (0.99 / peak)
    sf.write(str(path), x, sr, subtype="PCM_24")


def parse_note(name):
    """'C4' / 'F#3' / 'Bb2' → MIDI note number (C4 = 60)."""
    name = name.strip()
    pc = _PC[name[0].upper()]
    i = 1
    while i < len(name) and name[i] in "#b":
        pc += 1 if name[i] == "#" else -1
        i += 1
    return pc + 12 * (int(name[i:]) + 1)


def midi_breakpoints(path):
    """MIDI file → [(t_seconds, frozenset(held_notes)), ...], t ascending.

    This is the sidechain model: the held-note set as a function of time.
    """
    out = [(0.0, frozenset())]
    held = set()
    t = 0.0
    for msg in mido.MidiFile(str(path)):  # yields delta times in seconds
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            held.add(msg.note)
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            held.discard(msg.note)
        else:
            continue
        out.append((t, frozenset(held)))
    return out


def held_fn_from_breakpoints(bps):
    """→ f(t_seconds) = frozenset of held notes at time t."""

    times = [t for t, _ in bps]

    def f(t):
        i = np.searchsorted(times, t, side="right") - 1
        return bps[max(0, i)][1]

    return f


def held_fn_static(notes):
    s = frozenset(notes)
    return lambda t: s
