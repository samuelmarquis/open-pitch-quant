"""The spectral pitch-mapping engine — FROZEN PROTOTYPE LAB.

As of 2026-07-03 the Rust engine (rt/engine) is the sole canonical
implementation; this module is kept as the algorithm-exploration lab and
historical record. New features land in Rust first; anything prototyped
here must be ported before it counts. Known drift vs Rust: mono only, no
stereo coherence, no full-comb ownership, no Threshold, no formant.

STFT analysis, per-bin instantaneous frequency via phase differences
(Bernsee), spectral-peak detection with regions of influence
(Laroche & Dolson), then one of two ASSIGNMENT strategies:

  assign="peak"  (M0) — every peak independently snaps to the nearest
      allowed target. No objects: noise tonalizes, harmonics snap
      separately. Maximum kaleidoscope.
  assign="group" (M1) — greedy multi-F0 grouping (Klapuri-style harmonic
      summation with cancellation): up to `voices` harmonic objects per
      frame; each object's members move together by their FUNDAMENTAL's
      snap ratio (harmonic coherence). Unowned peaks follow the `unowned`
      policy: "map" = M0 treatment, "dry" = residual layer (verbatim).

Mapping modes (octave scope of the held-note set, after PITCHMAP's Edit Mode):
  repeat — held notes define allowed PITCH CLASSES in all octaves
  custom — held notes are the only allowed targets, exact octaves
Empty held set → SILENCE (PITCHMAP behavior, user-confirmed 2026-07-03).
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


def _hann_kernel(x, n_fft):
    """Zero-phase Hann window spectrum at fractional bin offsets x,
    normalized to W(0) = 1. Mainlobe support |x| < 2; small sidelobes
    beyond (we stamp out to |x| <= 4)."""
    def diric(u):
        num = np.sin(np.pi * u)
        den = n_fft * np.sin(np.pi * u / n_fft)
        small = np.abs(den) < 1e-12
        return np.where(small, 1.0, num / np.where(small, 1.0, den))

    return diric(x) + 0.5 * (diric(x - 1) + diric(x + 1))


def _wmedian(v, w):
    """Weighted median."""
    o = np.argsort(v)
    cw = np.cumsum(w[o])
    return float(v[o][min(np.searchsorted(cw, 0.5 * cw[-1]), len(v) - 1)])


def _harmonic_objects(peaks, mag, f_true, voices=6, n_harm=20,
                      fmin_f0=55.0, fmax_f0=1046.5, tol_cents=45.0):
    """Greedy iterative multi-F0 grouping over detected peaks.

    Klapuri-flavored: harmonic-summation salience on a semitone candidate
    grid, pick the best candidate, claim its peaks (cancellation), repeat
    up to `voices` times or until salience collapses (<5% of the first
    object's). Requires >=3 harmonic hits per object (ghost suppression).
    f0 refined robustly: weighted median over LOW harmonics (cross-object
    comb collisions live in the high harmonics — e.g. C's h16 is 0.4 cents
    from E's h13), then re-claim all peaks against the refined comb at
    tight tolerance and take the weighted median of the inliers.

    Returns (f0s, owner): refined fundamental per object, and for each
    peak an object index or -1 (unowned).
    """
    pk_f = f_true[peaks].astype(float)
    pk_m = mag[peaks].astype(float)
    n_pk = len(peaks)
    owner = np.full(n_pk, -1, dtype=int)
    if n_pk == 0:
        return [], owner

    lo = int(np.ceil(69 + 12 * np.log2(fmin_f0 / 440.0)))
    hi = int(np.floor(69 + 12 * np.log2(fmax_f0 / 440.0)))
    cand = 440.0 * 2.0 ** ((np.arange(lo, hi + 1) - 69) / 12.0)
    harm = np.arange(1, n_harm + 1)
    log_fh = np.log(np.outer(cand, harm))  # (C, H)
    w_h = 1.0 / harm ** 0.9
    tol = tol_cents / 1200.0 * np.log(2.0)
    log_pk = np.log(np.maximum(pk_f, 1e-9))

    avail = pk_m.copy()
    f0s = []
    first_sal = None
    for _ in range(voices):
        lp = np.where(avail > 0, log_pk, np.inf)
        d = np.abs(log_fh[:, :, None] - lp[None, None, :])  # (C, H, P)
        j = np.argmin(d, axis=2)  # nearest available peak per (cand, harm)
        dmin = np.take_along_axis(d, j[:, :, None], axis=2)[:, :, 0]
        hit = dmin < tol
        sal = (np.where(hit, avail[j], 0.0) * w_h[None, :]).sum(axis=1)
        sal = np.where(hit.sum(axis=1) >= 3, sal, 0.0)  # ghost suppression
        c = int(np.argmax(sal))
        if sal[c] <= 0:
            break
        if first_sal is None:
            first_sal = sal[c]
        elif sal[c] < 0.05 * first_sal:
            break
        # claimed peaks (dedupe: one peak may match several harmonic slots)
        jj0 = np.array(sorted({int(j[c, hidx]) for hidx in np.flatnonzero(hit[c])}))
        hh0 = np.maximum(np.round(pk_f[jj0] / cand[c]), 1.0)
        # initial f0: weighted median over LOW harmonics only
        low = hh0 <= 6
        sel = jj0[low] if low.sum() >= 2 else jj0
        hsel = hh0[low] if low.sum() >= 2 else hh0
        f0e = _wmedian(pk_f[sel] / hsel, avail[sel])
        # re-claim ALL available peaks against the refined comb, tight tol
        hh = np.round(pk_f / f0e)
        dev = np.abs(np.log(np.maximum(pk_f, 1e-9)
                            / (np.maximum(hh, 1.0) * f0e)))
        inl = (hh >= 1) & (hh <= n_harm) & (avail > 0) \
            & (dev < 30.0 / 1200.0 * np.log(2.0))
        if inl.sum() < 3:
            avail[jj0] = 0.0  # burn the evidence, try next candidate
            continue
        f0r = _wmedian(pk_f[inl] / hh[inl], avail[inl])
        for idx in np.flatnonzero(inl):
            if owner[idx] == -1:
                owner[idx] = len(f0s)
        # burn ONLY confirmed inliers — coarse claims the refined comb
        # rejected stay available for other objects (they're often another
        # object's harmonics: C's slot h5 sits 26 cents from E's h4)
        avail[inl] = 0.0
        f0s.append(f0r)
    return f0s, owner


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
    assign="peak",
    voices=6,
    unowned="map",
    synth="translate",
    feel=0.0,
    glide=0.0,
    grit=0.0,
    rounding="nearest",
    hyst_cents=40.0,
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
      assign           — "peak" (M0, independent snapping) or "group"
                         (M1, harmonic objects; see module docstring)
      voices           — max simultaneous objects for assign="group"
                         (PITCHMAP's Electrify is this knob, inverted)
      unowned          — assign="group" only: peaks no object claims are
                         "map"ped M0-style or left "dry" (residual layer)
      synth            — how tonal mapped partials are rendered:
                         "translate" = shift analysis bins by an integer
                             offset (legacy; scallops + dbin-toggles under
                             vibrato → the batch-006 washiness)
                         "stamp" = synthesize each partial by writing the
                             analytic window kernel at its EXACT fractional
                             output frequency with de-scalloped amplitude
                             and accumulator phase (no integer quantization
                             anywhere — frequency-domain oscillator bank)

    M3 options (object TRACKS across frames; assign="group" only):
      feel   — 0..1: re-introduce the track's micro-pitch deviation
               (vibrato, drift vs a ~250 ms moving reference) on top of the
               mapped target. 0 = fully quantized, 1 = all intonation
               detail preserved while still mapped. (PITCHMAP's FEEL.)
      glide  — seconds: on track birth, pitch ramps from the SOURCE pitch
               to the target; on target change (chord change under a
               sustained track), ramps from wherever it currently is.
               Tracks die on transients, so glide re-triggers after hits
               (matches the manual's note). 0 = off. (PITCHMAP's GLIDE.)
      grit   — 0..1 (synth="stamp" only): per-partial blend between pure
               oscillator stamping (0) and fresh-phase spectral translation
               (1) — the batch-006 crunch as a character control.
      rounding — "nearest" (always snap to closest target) or
               "intelligent" (PITCHMAP's Xclude rounding: a track KEEPS its
               current target unless a competitor is closer by more than
               hyst_cents — hysteresis kills target ping-pong on wobbly
               sources near snap boundaries)
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
    # M3 object-track state (assign="group"): tracks matched frame-to-frame
    # by f0 proximity; each carries a pitch reference (EMA) for Feel, glide
    # state, and per-harmonic phase accumulators for stamping
    tracks = []
    glide_frames = glide * sr / hop
    ema_a = 1.0 - np.exp(-(hop / sr) / 0.25)  # ~250 ms reference
    hyst = hyst_cents / 1200.0 * np.log(2.0)

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

        if grid is None:
            # no held notes → silence (PITCHMAP semantics, user-confirmed);
            # reset synthesis state so re-entry re-anchors cleanly
            phi_syn = phi.copy()
            note_seen.fill(-2)
            tracks.clear()
            Y = np.zeros(n_bins, dtype=complex)
        elif is_transient:
            # pass the frame through untouched; re-anchor synthesis phases
            phi_syn = phi.copy()
            note_seen.fill(-2)  # note accumulators re-anchor on next use
            tracks.clear()  # glide re-triggers after transients (manual)
            Y = X
        else:
            # per-region mapping decisions (shared by both synthesis paths)
            regions = []
            peaks = _find_peaks(mag, rel_floor_db)
            bounds = _region_bounds(mag, peaks, n_bins)
            log_grid = np.log(grid)

            owner = None
            obj_mult, obj_trk = [], []
            if assign == "group" and len(peaks):
                f0s, owner = _harmonic_objects(peaks, mag, f_true, voices)
                # ---- M3: match objects to tracks by f0 proximity ----
                for f0 in f0s:
                    best, bestd = None, np.log(2) * 100.0 / 1200.0
                    for trk in tracks:
                        if trk["seen"] == t:
                            continue
                        dd = abs(np.log(f0 / trk["f0"]))
                        if dd < bestd:
                            best, bestd = trk, dd
                    tgt = grid[np.argmin(np.abs(log_grid - np.log(f0)))]
                    if (rounding == "intelligent" and best is not None
                            and np.min(np.abs(log_grid - np.log(best["tgt"]))) < 1e-9):
                        # sticky target: keep the old one (if still allowed)
                        # unless the new is closer by more than the hysteresis
                        if (abs(np.log(f0 / best["tgt"]))
                                < abs(np.log(f0 / tgt)) + hyst):
                            tgt = best["tgt"]
                    if best is None:  # birth: glide starts at SOURCE pitch
                        trk = {"f0": f0, "lema": np.log(f0), "tgt": tgt,
                               "r_from": 0.0, "g0": t, "phases": {},
                               "seen": t}
                        tracks.append(trk)
                    else:
                        trk = best
                        # effective ratio now (pre-update): target changes
                        # glide FROM wherever the pitch currently sits
                        r_old = np.log(trk["tgt"] / trk["f0"])
                        if glide_frames > 0:
                            prog = min(1.0, (t - trk["g0"]) / glide_frames)
                            r_now = trk["r_from"] + (r_old - trk["r_from"]) * prog
                        else:
                            r_now = r_old
                        if abs(np.log(tgt / trk["tgt"])) > 1e-6:
                            trk["r_from"] = r_now
                            trk["g0"] = t
                            trk["tgt"] = tgt
                        trk["f0"] = f0
                        trk["lema"] += ema_a * (np.log(f0) - trk["lema"])
                        trk["seen"] = t
                    r_to = np.log(trk["tgt"] / trk["f0"])
                    if glide_frames > 0:
                        prog = min(1.0, (t - trk["g0"]) / glide_frames)
                        r_eff = trk["r_from"] + (r_to - trk["r_from"]) * prog
                    else:
                        r_eff = r_to
                    dev = np.log(trk["f0"]) - trk["lema"]  # micro-pitch
                    obj_mult.append(float(np.exp(r_eff + feel * dev)))
                    obj_trk.append(trk)
                tracks[:] = [trk for trk in tracks if trk["seen"] == t]

            for i, (p, (lo, hi)) in enumerate(zip(peaks, bounds)):
                fp = f_true[p]
                if owner is not None and owner[i] >= 0:
                    # harmonic member: move with its object's fundamental
                    oi = owner[i]
                    trk = obj_trk[oi]
                    df = fp * (obj_mult[oi] - 1.0)
                    h = max(int(round(fp / trk["f0"])), 1)
                    regions.append((p, lo, hi, fp, df, False, trk, h))
                    continue
                if owner is not None and unowned == "dry":
                    regions.append((p, lo, hi, fp, 0.0, False, None, 0))
                    continue
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
                regions.append((p, lo, hi, fp, df, noisy, None, 0))

            if phase_lock:
                # rigid phase locking with per-TARGET-NOTE accumulators:
                # each mapped region's phase advances at exactly its target
                # frequency, keyed by target note number (stable under
                # vibrato); intra-region analysis phase offsets preserved.
                # Unmapped regions pass through VERBATIM (fully transparent).
                Y = np.zeros(n_bins, dtype=complex)
                for p, lo, hi, fp, df, noisy, trk, h in regions:
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
                    if synth == "stamp":
                        # frequency-domain oscillator: exact fractional
                        # output freq, de-scalloped amplitude, accum phase
                        ft = fp + df
                        dsrc = fp / bin_hz - p
                        amp = mag[p] / max(
                            float(_hann_kernel(np.array([dsrc]), n_fft)[0]), 0.1
                        )
                        anchor = phi[p] - np.pi * dsrc
                        if trk is not None:
                            # phase lives on the TRACK, per harmonic number
                            entry = trk["phases"].get(h)
                            if entry is not None and entry[1] == t:
                                phv = entry[0]  # duplicate h this frame
                            elif entry is not None and entry[1] == t - 1:
                                phv = entry[0] + TWO_PI * ft * hop / sr
                            else:
                                phv = anchor
                            trk["phases"][h] = (phv, t)
                        else:
                            ni = min(max(int(round(69 + 12 * np.log2(ft / 440.0))), 0), 127)
                            if note_seen[ni] == t:
                                pass
                            elif note_seen[ni] == t - 1:
                                note_phase[ni] += TWO_PI * ft * hop / sr
                            else:
                                note_phase[ni] = anchor
                            note_seen[ni] = t
                            phv = note_phase[ni]
                        if grit > 0.0:
                            # character blend: fresh-phase translation crunch
                            Y[dst] += grit * mag[src] * np.exp(
                                1j * (phi[src] + TWO_PI * df * (t * hop) / sr
                                      + np.pi * dbin)
                            )
                        b = ft / bin_hz
                        kk = np.arange(max(int(np.ceil(b - 4)), 1),
                                       min(int(np.floor(b + 4)), n_bins - 2) + 1)
                        if len(kk):
                            xoff = kk - b
                            Y[kk] += (1.0 - grit) * amp * _hann_kernel(
                                xoff, n_fft
                            ) * np.exp(1j * (phv - np.pi * xoff))
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
                for p, lo, hi, fp, df, noisy, trk, h in regions:
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
