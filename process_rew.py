#!/usr/bin/env python3
"""
RDSL REW Processing Pipeline
Reads REW .txt exports → normalized, smoothed, resampled frequency response JSON.

Run from: Claude_Workspace/RDSL_Coding/rdsl-freq-chart/
  python3 process_rew.py

Outputs one .json per model into freqsets/
"""

import json
import math
import os
import bisect

RAW_BASE = "raw-rew"
OUT_DIR  = "freqsets"
N_OUT    = 180          # output sample count
F_MIN    = 20.0         # Hz
F_MAX    = 20000.0      # Hz
OCTAVE_SMOOTH = 1/12    # smoothing window width in octaves

# ── Model definitions ─────────────────────────────────────────────────────────
# Each entry maps a URL handle → model metadata + per-position file paths & specs.
# Positions: "bridge", "middle", "neck"  (only include what exists)

MODELS = [

    # ── TELECASTER ──────────────────────────────────────────────────────────
    {
        "handle": "skylark",
        "model": "Skylark™",
        "subtitle": "Telecaster Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "Telecaster/tele_skylark_bridge.txt",
                "dcr": "6.7 kΩ", "peak": "6.60 kHz",
                "character": "Snappy & immediate",
                "description": "Bell-like 1960s Tele articulation with copper baseplate snap",
            },
            "neck": {
                "file": "Telecaster/tele_skylark_neck.txt",
                "dcr": "5.6 kΩ", "peak": "8.72 kHz",
                "character": "Glassy & open",
                "description": "Extended high-freq response",
            },
        },
    },
    {
        "handle": "high-line",
        "model": "High-Line™",
        "subtitle": "Telecaster Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "Telecaster/tele_high-line_bridge.txt",
                "dcr": "7.8 kΩ", "peak": "6.34 kHz",
                "character": "Desert-island Tele voice",
                "description": "Modern Alnico 5 — glassy, cutting, sits in any mix",
            },
            "neck": {
                "file": "Telecaster/tele_high-line_neck.txt",
                "dcr": "6.2 kΩ", "peak": "9.70 kHz",
                "character": "Open & versatile",
                "description": "Extended top-end — the modern player's Tele neck",
            },
        },
    },
    {
        "handle": "bakersfield",
        "model": "Bakersfield™",
        "subtitle": "Telecaster Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "Telecaster/tele_bakersfield_bridge.txt",
                "dcr": "7.2 kΩ", "peak": "6.44 kHz",
                "character": "Honky & mid-forward",
                "description": "Bakersfield twang — Buck Owens, Merle Haggard territory",
            },
            "neck": {
                "file": "Telecaster/tele_bakersfield_neck.txt",
                "dcr": "6.1 kΩ", "peak": "10.20 kHz",
                "character": "Snappy & percussive",
                "description": "Bright vintage country attack",
            },
        },
    },
    {
        "handle": "truevintagecustom",
        "model": "True Vintage Custom™",
        "subtitle": "Telecaster Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "Telecaster/tele_truevintagecustom_bridge.txt",
                "dcr": "6.8 kΩ", "peak": "6.65 kHz",
                "character": "Warm vintage output",
                "description": "Alnico 2 character — full but articulate",
            },
            "neck": {
                "file": "Telecaster/tele_truevintagecustom_neck.txt",
                "dcr": "7.1 kΩ", "peak": "8.20 kHz",
                "character": "Fuller Tele voice",
                "description": "Hot 43 AWG wind with extended high-end presence",
            },
        },
    },
    {
        "handle": "t-50",
        "model": "T-50 Vintage",
        "subtitle": "Telecaster Neck · Normalized Frequency Response",
        "positions": {
            "neck": {
                "file": "Telecaster/tele_t-50_neck_solo.txt",
                "dcr": "6.8 kΩ", "peak": "6.80 kHz",
                "character": "Blackguard warmth",
                "description": "Open, vintage '50s neck character",
            },
        },
    },
    {
        "handle": "t-60",
        "model": "T-60 Vintage",
        "subtitle": "Telecaster Neck · Normalized Frequency Response",
        "positions": {
            "neck": {
                "file": "Telecaster/tele_t-60_neck_solo.txt",
                "dcr": "7.5 kΩ", "peak": "7.50 kHz",
                "character": "Blackguard bite",
                "description": "Hot late-'50s wind — presence and punch",
            },
        },
    },

    # ── STRATOCASTER ─────────────────────────────────────────────────────────
    {
        "handle": "redhouse",
        "model": "Red House™",
        "subtitle": "Stratocaster Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "Stratocaster/strat_redhouse_bridge.txt",
                "dcr": "6.65 kΩ", "peak": "6.94 kHz",
                "character": "Punchy & defined",
                "description": "The RDSL Strat voice — blues, rock, studio-ready",
            },
            "middle": {
                "file": "Stratocaster/strat_redhouse_middle.txt",
                "dcr": "6.25 kΩ", "peak": "6.94 kHz",
                "character": "Clear & balanced",
                "description": "RWRP — positions 2 & 4 quack, noise-free",
            },
            "neck": {
                "file": "Stratocaster/strat_redhouse_neck.txt",
                "dcr": "6.35 kΩ", "peak": "6.94 kHz",
                "character": "Warm & full",
                "description": "Classic Alnico 5 Strat neck, present without harshness",
            },
        },
    },
    {
        "handle": "tweedvintage",
        "model": "Tweed Vintage™",
        "subtitle": "Stratocaster Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "Stratocaster/strat_tweedvintage_bridge.txt",
                "dcr": "5.82 kΩ", "peak": "7.72 kHz",
                "character": "Touch-sensitive & open",
                "description": "Maximum dynamics — Formvar wind, Alnico 2 softness",
            },
            "middle": {
                "file": "Stratocaster/strat_tweedvintage_middle.txt",
                "dcr": "5.46 kΩ", "peak": "8.25 kHz",
                "character": "Airy & responsive",
                "description": "Lightest touch in the line — positions 2 & 4 shimmer",
            },
            "neck": {
                "file": "Stratocaster/strat_tweedvintage_neck.txt",
                "dcr": "5.27 kΩ", "peak": "8.16 kHz",
                "character": "Feather-light attack",
                "description": "Maximum feel — built for touch-responsive playing",
            },
        },
    },
    {
        "handle": "voodoo",
        "model": "Voodoo™",
        "subtitle": "Stratocaster Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "Stratocaster/strat_voodoo_bridge.txt",
                "dcr": "8.0 kΩ", "peak": "6.12 kHz",
                "character": "Authority & sustain",
                "description": "Ferrous baseplate — added low-end weight, built to cut through",
            },
            "middle": {
                "file": "Stratocaster/strat_voodoo_middle.txt",
                "dcr": "7.2 kΩ", "peak": "6.76 kHz",
                "character": "RWRP power",
                "description": "More presence in positions 2 & 4 — hot and hum-free",
            },
            "neck": {
                "file": "Stratocaster/strat_voodoo_neck.txt",
                "dcr": "7.15 kΩ", "peak": "6.76 kHz",
                "character": "Full & commanding",
                "description": "More output, more sustain — built to be heard",
            },
        },
    },

    # ── HUMBUCKER ────────────────────────────────────────────────────────────
    {
        "handle": "revival",
        "model": "Revival™ PAF",
        "subtitle": "Humbucker Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "Humbucker/hb_revival_bridge.txt",
                "dcr": "8.46 kΩ", "peak": "5.62 kHz",
                "character": "Elastic & warm",
                "description": "Unpotted PAF — microphonic warmth at the edge of breakup",
            },
            "neck": {
                "file": "Humbucker/hb_revival_neck.txt",
                "dcr": "7.94 kΩ", "peak": "6.09 kHz",
                "character": "Airy PAF voice",
                "description": "Open and articulate — the pickup listens to your playing",
            },
        },
    },
    {
        "handle": "ritual",
        "model": "Ritual™",
        "subtitle": "Humbucker Bridge · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "Humbucker/hb_ritual_bridge_solo.txt",
                "dcr": "17.9 kΩ", "peak": "5.60 kHz",
                "character": "Dense & aggressive",
                "description": "Hard rock and old-school metal — 44 AWG, built to push hard and stay mean",
            },
        },
    },

    # ── P90 ──────────────────────────────────────────────────────────────────
    {
        "handle": "aura-soapbar",
        "model": "Aura™ Soap Bar",
        "subtitle": "P90 Soap Bar Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "P90/soapbar/p90_aura_bridge_soapbar.txt",
                "dcr": "7.73 kΩ", "peak": "4.86 kHz",
                "character": "Growl with body",
                "description": "Vintage P90 voice — warm, round, Alnico 2 softness",
            },
            "neck": {
                "file": "P90/soapbar/p90_aura_neck_soapbar.txt",
                "dcr": "7.27 kΩ", "peak": "4.81 kHz",
                "character": "Round & full",
                "description": "More body than bite — blues, jazz, indie territory",
            },
        },
    },
    {
        "handle": "aura-dogear",
        "model": "Aura™ Dog Ear",
        "subtitle": "P90 Dog Ear Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "P90/dogear/p90_aura_bridge_dogear.txt",
                "dcr": "7.58 kΩ", "peak": "4.88 kHz",
                "character": "Growl with body",
                "description": "Vintage P90 voice — warm, round, Alnico 2 softness",
            },
            "neck": {
                "file": "P90/dogear/p90_aura_neck_dogear.txt",
                "dcr": "6.95 kΩ", "peak": "4.91 kHz",
                "character": "Round & full",
                "description": "More body than bite — blues, jazz, indie territory",
            },
        },
    },
    {
        "handle": "thunderbolt-soapbar",
        "model": "Thunderbolt™ Soap Bar",
        "subtitle": "P90 Soap Bar Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "P90/soapbar/p90_thunderbolt_bridge_soapbar.txt",
                "dcr": "8.35 kΩ", "peak": "4.67 kHz",
                "character": "Maximum P90 aggression",
                "description": "Hottest in the P90 line — pushes hard, retains top-end clarity",
            },
            "neck": {
                "file": "P90/soapbar/p90_thunderbolt_neck_soapbar.txt",
                "dcr": "7.66 kΩ", "peak": "4.51 kHz",
                "character": "Driven warmth",
                "description": "High-output neck — rock and blues-rock authority",
            },
        },
    },
    {
        "handle": "thunderbolt-dogear",
        "model": "Thunderbolt™ Dog Ear",
        "subtitle": "P90 Dog Ear Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "P90/dogear/p90_thunderbolt_bridge_dogear.txt",
                "dcr": "8.45 kΩ", "peak": "4.55 kHz",
                "character": "Maximum P90 aggression",
                "description": "Hottest in the P90 line — pushes hard, retains top-end clarity",
            },
            "neck": {
                "file": "P90/dogear/p90_thunderbolt_neck_dogear.txt",
                "dcr": "7.54 kΩ", "peak": "4.55 kHz",
                "character": "Driven warmth",
                "description": "High-output neck — rock and blues-rock authority",
            },
        },
    },
    {
        "handle": "zenith-soapbar",
        "model": "Zenith™ Soap Bar",
        "subtitle": "P90 Soap Bar Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "P90/soapbar/p90_zenith_bridge_soapbar.txt",
                "dcr": "7.72 kΩ", "peak": "4.93 kHz",
                "character": "Grind & drive",
                "description": "Hot P90 that pushes amps hard with sustained character",
            },
            "neck": {
                "file": "P90/soapbar/p90_zenith_neck_soapbar.txt",
                "dcr": "7.12 kΩ", "peak": "4.76 kHz",
                "character": "Commanding & clear",
                "description": "Strong output with RDSL top-end clarity intact",
            },
        },
    },
    {
        "handle": "zenith-dogear",
        "model": "Zenith™ Dog Ear",
        "subtitle": "P90 Dog Ear Set · Normalized Frequency Response",
        "positions": {
            "bridge": {
                "file": "P90/dogear/p90_zenith_bridge_dogear.txt",
                "dcr": "7.54 kΩ", "peak": "4.84 kHz",
                "character": "Grind & drive",
                "description": "Hot P90 that pushes amps hard with sustained character",
            },
            "neck": {
                "file": "P90/dogear/p90_zenith_neck_dogear.txt",
                "dcr": "6.93 kΩ", "peak": "4.75 kHz",
                "character": "Commanding & clear",
                "description": "Strong output with RDSL top-end clarity intact",
            },
        },
    },
]


# ── DSP helpers ───────────────────────────────────────────────────────────────

def parse_rew(filepath):
    """Parse a REW .txt export. Returns sorted list of (freq_hz, db) tuples."""
    freqs, dbs = [], []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("*"):
                continue
            parts = line.split(";")
            if len(parts) < 2:
                continue
            try:
                freq = float(parts[0].strip())
                w    = float(parts[1].strip())
                if w > 0:
                    dbs.append(10.0 * math.log10(w))
                    freqs.append(freq)
            except ValueError:
                continue
    paired = sorted(zip(freqs, dbs), key=lambda x: x[0])
    return [p[0] for p in paired], [p[1] for p in paired]


def smooth_and_resample(freqs, dbs):
    """
    1. Apply 1/12-octave smoothing.
    2. Resample to N_OUT log-spaced points between F_MIN and F_MAX.
    3. Normalize so peak = 0 dB.
    Returns list of [freq, db] pairs (rounded to 2 decimal places).
    """
    half = OCTAVE_SMOOTH / 2.0   # ±1/24 octave

    out_freqs = [
        F_MIN * ((F_MAX / F_MIN) ** (i / (N_OUT - 1)))
        for i in range(N_OUT)
    ]

    smoothed = []
    for f_out in out_freqs:
        f_lo = f_out * (2 ** -half)
        f_hi = f_out * (2 **  half)
        lo_idx = bisect.bisect_left(freqs, f_lo)
        hi_idx = bisect.bisect_right(freqs, f_hi)
        window = dbs[lo_idx:hi_idx]
        smoothed.append(sum(window) / len(window) if window else 0.0)

    peak = max(smoothed)
    normalized = [round(v - peak, 2) for v in smoothed]
    out_freqs_r = [round(f, 2) for f in out_freqs]

    return [[out_freqs_r[i], normalized[i]] for i in range(N_OUT)]


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    for model in MODELS:
        handle = model["handle"]
        print(f"\nProcessing: {model['model']} ({handle})")

        out = {
            "model":    model["model"],
            "subtitle": model["subtitle"],
        }

        ok = True
        for pos, spec in model["positions"].items():
            raw_path = os.path.join(RAW_BASE, spec["file"])
            if not os.path.exists(raw_path):
                print(f"  ✗ Missing: {raw_path}")
                ok = False
                continue

            print(f"  · {pos}: {spec['file']}")
            freqs, dbs = parse_rew(raw_path)
            data = smooth_and_resample(freqs, dbs)

            out[pos] = {
                "dcr":         spec["dcr"],
                "peak":        spec["peak"],
                "character":   spec["character"],
                "description": spec["description"],
                "data":        data,
            }

        if not ok:
            print(f"  ⚠ Skipped (missing files)")
            continue

        out_path = os.path.join(OUT_DIR, f"{handle}.json")
        with open(out_path, "w") as f:
            json.dump(out, f, separators=(",", ":"))

        size_kb = os.path.getsize(out_path) / 1024
        print(f"  ✓ → {out_path}  ({size_kb:.1f} KB)")

    print("\nDone.")


if __name__ == "__main__":
    main()
