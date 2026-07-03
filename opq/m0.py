"""M0 — "everything is a nail."

The simplest thing that makes the sound: STFT analysis, per-bin instantaneous
frequency via phase differences (Bernsee), spectral-peak detection with
regions of influence (Laroche & Dolson), and EVERY peak independently
translated to the nearest allowed target pitch. No grouping, no objects, no
residual layer: noise gets tonalized, harmonics snap separately. This is the
lower bound on quality and the upper bound on kaleidoscope.

Mapping modes (octave scope of the held-note set, after PITCHMAP's Edit Mode):
  repeat — held notes define allowed PITCH CLASSES in all octaves
  custom — held notes are the only allowed targets, exact octaves
Empty held set → identity (v0 choice; PITCHMAP's behavior undocumented).
"""

import numpy as np
from numpy.fft import irfft, rfft

TWO_PI = 2.0 * np.pi


def target_grid(held, mode="repeat"):
    """Held MIDI notes → ascending array of allowed target freqs in Hz.

    Returns None for 'no mapping' (empty set → identity).
    """
    if not held:
        return None
    if mode == "repeat":
        pcs = sorted({n % 12 for n in held})
        notes = [pc + 12 * o for o in range(11) for pc in pcs]
        notes = [n for n in notes if 0 <= n <= 127]
    elif mode == "custom":
        notes = sorted(held)
    else:
        raise ValueError(f"unknown mode {mode!r}")
    return 440.0 * 2.0 ** ((np.asarray(notes, dtype=float) - 69.0) / 12.0)


def _find_peaks(mag, rel_floor_db=-60.0, abs_floor=1e-7):
    """Indices of local maxima above floors (never DC/Nyquist edges)."""
    floor = max(mag.max() * 10.0 ** (rel_floor_db / 20.0), abs_floor)
    m = mag[2:-2]
    is_pk = (
        (m > mag[1:-3]) & (m >= mag[3:-1])
        & (m > mag[:-4]) & (m >= mag[4:])
        & (m > floor)
    )
    return np.flatnonzero(is_pk) + 2


def _region_bounds(mag, peaks, n_bins):
    """Laroche-Dolson regions of influence: split at the magnitude valley
    between adjacent peaks. Returns [(lo, hi)] half-open bin ranges."""
    bounds = []
    for i, p in enumerate(peaks):
        lo = 1 if i == 0 else bounds[i - 1][1]
        if i == len(peaks) - 1:
            hi = n_bins - 1
        else:
            q = peaks[i + 1]
            hi = p + 1 + int(np.argmin(mag[p + 1 : q + 1])) if q > p + 1 else q
        bounds.append((lo, hi))
    return bounds


def process(
    x,
    sr,
    held_fn,
    mode="repeat",
    n_fft=4096,
    hop=1024,
    rel_floor_db=-60.0,
    fmin=30.0,
    fmax_map=None,
    transient_bypass=False,
    flux_thresh=0.6,  # calibrated on amen/resoguitar/audio178, 2026-07-03
    tonality_gate=None,
    tonality_mode="fresh",
    phase_lock=True,
):
    """Run the M0 remap over mono signal x. Returns y, same length.

    M0.5 options (M2-lite, added after listening batch 001):
      fmax_map         — peaks above this freq (Hz) pass through unshifted
                         (proto-residual: HF noise stops being tonalized)
      transient_bypass — spectral-flux onset frames pass through DRY and
                         re-anchor synthesis phases (transient preservation
                         + periodic phase reset against wateriness)
      flux_thresh      — relative positive magnitude growth per hop that
                         counts as a transient
      tonality_gate    — if set, regions whose peak/mean magnitude ratio is
                         below this count as NOISE (proto-Purify; off by
                         default). Calibrated 2026-07-03: tonal regions
                         median ~4.8, noise ~1.55 → gate 2.5 splits cleanly.
      tonality_mode    — what to do with noise regions when gated:
                         "fresh"  = still mapped, but with per-frame analysis
                                    phases (tonalized without accumulator
                                    warble; keeps the drums-into-chords
                                    character)
                         "bypass" = pass unshifted (transparent noise;
                                    un-PITCHMAP but clean)
      phase_lock       — rigid phase locking with one accumulator per
                         TARGET NOTE (stable identity under vibrato);
                         mapped regions advance at exactly their target
                         frequency, intra-region analysis phase offsets
                         preserved, unmapped regions pass through verbatim.
                         Fixes the hollowed-out-fundamental artifact from
                         batch 002. Fully quantized (Feel=0 character);
                         micro-pitch re-injection is M3. False = legacy
                         per-bin free-running accumulators (watery/shimmery;
                         kept for A/B — the shimmer may be a feature).
    """
    win = np.hanning(n_fft)
    n_bins = n_fft // 2 + 1
    bin_hz = sr / n_fft
    bin_centers = np.arange(n_bins) * bin_hz
    expected_dphi = TWO_PI * hop * np.arange(n_bins) / n_fft

    xp = np.concatenate([x, np.zeros(n_fft)])
    n_frames = 1 + (len(xp) - n_fft) // hop
    y = np.zeros(len(xp) + n_fft)

    phi_prev = None
    phi_syn = None
    mag_prev = None
    # phase-lock state: one accumulator per TARGET note (stable identity —
    # destinations are quantized, unlike source bins under vibrato)
    note_phase = np.zeros(128)
    note_seen = np.full(128, -2, dtype=int)

    for t in range(n_frames):
        seg = xp[t * hop : t * hop + n_fft]
        X = rfft(seg * win)
        mag = np.abs(X)
        phi = np.angle(X)

        # instantaneous frequency per bin (phase-difference method)
        if phi_prev is None:
            f_true = bin_centers.copy()
            phi_syn = phi.copy()
        else:
            d = phi - phi_prev - expected_dphi
            d = np.mod(d + np.pi, TWO_PI) - np.pi
            f_true = bin_centers + d / (TWO_PI * hop / n_fft) * bin_hz
        phi_prev = phi

        grid = target_grid(held_fn((t * hop + n_fft / 2) / sr), mode)

        # spectral flux (relative positive magnitude growth) → onset detector
        if mag_prev is None:
            flux = np.inf  # first frame anchors phases / passes dry
        else:
            flux = np.maximum(mag - mag_prev, 0).sum() / (mag_prev.sum() + 1e-12)
        mag_prev = mag
        is_transient = transient_bypass and flux > flux_thresh

        if grid is None or is_transient:
            # pass the frame through untouched; re-anchor synthesis phases
            phi_syn = phi.copy()
            note_seen.fill(-2)  # note accumulators re-anchor on next use
            Y = X
        else:
            # per-region mapping decisions (shared by both synthesis paths)
            regions = []
            peaks = _find_peaks(mag, rel_floor_db)
            log_grid = np.log(grid)
            for p, (lo, hi) in zip(peaks, _region_bounds(mag, peaks, n_bins)):
                fp = f_true[p]
                mappable = fmin < fp < sr / 2 * 0.95
                if fmax_map is not None:
                    mappable = mappable and fp <= fmax_map
                noisy = False
                if mappable and tonality_gate is not None:
                    peakiness = mag[p] / (mag[lo:hi].mean() + 1e-12)
                    noisy = peakiness < tonality_gate
                    if noisy and tonality_mode == "bypass":
                        mappable = False
                if mappable:
                    ft = grid[np.argmin(np.abs(log_grid - np.log(fp)))]
                    df = ft - fp
                else:
                    df = 0.0
                regions.append((p, lo, hi, fp, df, noisy))

            if phase_lock:
                # rigid phase locking with per-TARGET-NOTE accumulators:
                # each mapped region's phase advances at exactly its target
                # frequency, keyed by target note number (stable under
                # vibrato); intra-region analysis phase offsets preserved.
                # Unmapped regions pass through VERBATIM (fully transparent).
                Y = np.zeros(n_bins, dtype=complex)
                for p, lo, hi, fp, df, noisy in regions:
                    dbin = int(round(df / bin_hz))
                    clo, chi = max(lo + dbin, 1), min(hi + dbin, n_bins - 1)
                    if chi <= clo:
                        continue
                    src = slice(clo - dbin, chi - dbin)
                    dst = slice(clo, chi)
                    if df == 0.0:
                        Y[dst] += X[dst]  # unmapped: dry spectrum, dry phase
                        continue
                    if noisy:
                        # mapped noise: fresh per-frame phases, deterministic
                        # shift ramp — tonalized without accumulator warble
                        Y[dst] += mag[src] * np.exp(
                            1j * (phi[src] + TWO_PI * df * (t * hop) / sr
                                  + np.pi * dbin)
                        )
                        continue
                    ft = fp + df
                    ni = min(max(int(round(69 + 12 * np.log2(ft / 440.0))), 0), 127)
                    if note_seen[ni] == t:
                        pass  # another region already advanced it this frame
                    elif note_seen[ni] == t - 1:
                        note_phase[ni] += TWO_PI * ft * hop / sr
                    else:
                        note_phase[ni] = phi[p]  # (re)anchor from source
                    note_seen[ni] = t
                    # π·dbin corrects the Hann-lobe sign parity under
                    # integer-bin translation (centered-window convention)
                    Y[dst] += mag[src] * np.exp(
                        1j * (note_phase[ni] + phi[src] - phi[p] + np.pi * dbin)
                    )
            else:
                # legacy path: per-bin free-running accumulators (watery)
                out_mag = np.zeros(n_bins)
                out_freq = bin_centers.copy()
                best = np.zeros(n_bins)
                for p, lo, hi, fp, df, noisy in regions:
                    dbin = int(round(df / bin_hz))
                    clo, chi = max(lo + dbin, 1), min(hi + dbin, n_bins - 1)
                    if chi <= clo:
                        continue
                    src = slice(clo - dbin, chi - dbin)
                    dst = slice(clo, chi)
                    out_mag[dst] += mag[src]
                    take = mag[src] > best[dst]
                    out_freq[dst][...] = np.where(take, f_true[src] + df, out_freq[dst])
                    best[dst] = np.maximum(best[dst], mag[src])
                phi_syn = phi_syn + TWO_PI * out_freq * hop / sr
                Y = out_mag * np.exp(1j * phi_syn)

        y[t * hop : t * hop + n_fft] += irfft(Y, n=n_fft) * win

    return y[: len(x)] / 1.5  # hann^2 COLA at 75% overlap sums to 1.5
