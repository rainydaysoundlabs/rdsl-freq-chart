#!/usr/bin/env python3
"""
RDSL REW Processing Pipeline v5
- Auto-detects W(W) vs SPL(dB) REW format
- Fixed physical anchor ranges per family for Output, Treble, Dynamics
  (prevents small-family distortion — e.g. 2-model HB family)
- Padded catalog range for Midrange and Bass (curve-derived, family-relative)
- Scores 2.0–5.0 (floor prevents any pickup anchoring at absolute minimum)
- Dynamics = inverse DCR (lower output = more touch-sensitive)
"""

import json, math, os, bisect

RAW_BASE = "raw-rew"
OUT_DIR  = "freqsets"
N_OUT    = 180
F_MIN    = 20.0
F_MAX    = 20000.0
OCTAVE_SMOOTH = 1/12

# Fixed physical anchor ranges per family
# output = DCR kΩ, treble = resonant peak kHz, dynamics = 1/DCR
ANCHORS = {
    "tele":  {"output": (4.5, 10.5), "treble": (5.0, 12.0), "dynamics": (1/10.5, 1/4.5)},
    "strat": {"output": (4.5, 10.5), "treble": (5.0, 11.0), "dynamics": (1/10.5, 1/4.5)},
    "p90":   {"output": (5.5, 13.0), "treble": (3.5,  7.0), "dynamics": (1/13.0, 1/5.5)},
    "hb":    {"output": (6.0, 20.0), "treble": (3.5,  7.5), "dynamics": (1/20.0, 1/6.0)},
}

MODELS = [
    # TELECASTER
    {"handle":"skylark","family":"tele","model":"Skylark\u2122","subtitle":"Telecaster Set \u00b7 Normalized Frequency Response","scores_display":"toggle","positions":{"bridge":{"file":"Telecaster/tele_skylark_bridge.txt","dcr":"6.7 k\u03a9","peak":"6.60 kHz","character":"Snappy & immediate","description":"Bell-like 1960s Tele articulation with copper baseplate snap"},"neck":{"file":"Telecaster/tele_skylark_neck.txt","dcr":"5.6 k\u03a9","peak":"8.72 kHz","character":"Glassy & open","description":"Extended high-freq response"}}},
    {"handle":"high-line","family":"tele","model":"High-Line\u2122","subtitle":"Telecaster Set \u00b7 Normalized Frequency Response","scores_display":"toggle","positions":{"bridge":{"file":"Telecaster/tele_high-line_bridge.txt","dcr":"7.8 k\u03a9","peak":"6.34 kHz","character":"Desert-island Tele voice","description":"Modern Alnico 5 \u2014 glassy, cutting, sits in any mix"},"neck":{"file":"Telecaster/tele_high-line_neck.txt","dcr":"6.2 k\u03a9","peak":"9.70 kHz","character":"Open & versatile","description":"Extended top-end \u2014 the modern player's Tele neck"}}},
    {"handle":"bakersfield","family":"tele","model":"Bakersfield\u2122","subtitle":"Telecaster Set \u00b7 Normalized Frequency Response","scores_display":"toggle","positions":{"bridge":{"file":"Telecaster/tele_bakersfield_bridge.txt","dcr":"7.2 k\u03a9","peak":"6.44 kHz","character":"Honky & mid-forward","description":"Bakersfield twang \u2014 Buck Owens, Merle Haggard territory"},"neck":{"file":"Telecaster/tele_bakersfield_neck.txt","dcr":"6.1 k\u03a9","peak":"10.20 kHz","character":"Snappy & percussive","description":"Bright vintage country attack"}}},
    {"handle":"truevintagecustom","family":"tele","model":"True Vintage Custom\u2122","subtitle":"Telecaster Set \u00b7 Normalized Frequency Response","scores_display":"toggle","positions":{"bridge":{"file":"Telecaster/tele_truevintagecustom_bridge.txt","dcr":"6.8 k\u03a9","peak":"6.65 kHz","character":"Warm vintage output","description":"Alnico 2 character \u2014 full but articulate"},"neck":{"file":"Telecaster/tele_truevintagecustom_neck.txt","dcr":"7.1 k\u03a9","peak":"8.20 kHz","character":"Fuller Tele voice","description":"Hot 43 AWG wind with extended high-end presence"}}},
    {"handle":"t-50","family":"tele","model":"T-50 Vintage","subtitle":"Telecaster Neck \u00b7 Normalized Frequency Response","scores_display":"solo","positions":{"neck":{"file":"Telecaster/tele_t-50_neck_solo.txt","dcr":"6.8 k\u03a9","peak":"6.80 kHz","character":"Blackguard warmth","description":"Open, vintage '50s neck character"}}},
    {"handle":"t-60","family":"tele","model":"T-60 Vintage","subtitle":"Telecaster Neck \u00b7 Normalized Frequency Response","scores_display":"solo","positions":{"neck":{"file":"Telecaster/tele_t-60_neck_solo.txt","dcr":"7.5 k\u03a9","peak":"7.50 kHz","character":"Blackguard bite","description":"Hot late-'50s wind \u2014 presence and punch"}}},
    # STRATOCASTER
    {"handle":"redhouse","family":"strat","model":"Red House\u2122","subtitle":"Stratocaster Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"Stratocaster/strat_redhouse_bridge.txt","dcr":"6.65 k\u03a9","peak":"6.94 kHz","character":"Punchy & defined","description":"The RDSL Strat voice \u2014 blues, rock, studio-ready"},"middle":{"file":"Stratocaster/strat_redhouse_middle.txt","dcr":"6.25 k\u03a9","peak":"6.94 kHz","character":"Clear & balanced","description":"RWRP \u2014 positions 2 & 4 quack, noise-free"},"neck":{"file":"Stratocaster/strat_redhouse_neck.txt","dcr":"6.35 k\u03a9","peak":"6.94 kHz","character":"Warm & full","description":"Classic Alnico 5 Strat neck, present without harshness"}}},
    {"handle":"tweedvintage","family":"strat","model":"Tweed Vintage\u2122","subtitle":"Stratocaster Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"Stratocaster/strat_tweedvintage_bridge.txt","dcr":"5.82 k\u03a9","peak":"7.72 kHz","character":"Touch-sensitive & open","description":"Maximum dynamics \u2014 Formvar wind, Alnico 2 softness"},"middle":{"file":"Stratocaster/strat_tweedvintage_middle.txt","dcr":"5.46 k\u03a9","peak":"8.25 kHz","character":"Airy & responsive","description":"Lightest touch in the line \u2014 positions 2 & 4 shimmer"},"neck":{"file":"Stratocaster/strat_tweedvintage_neck.txt","dcr":"5.27 k\u03a9","peak":"8.16 kHz","character":"Feather-light attack","description":"Maximum feel \u2014 built for touch-responsive playing"}}},
    {"handle":"voodoo","family":"strat","model":"Voodoo\u2122","subtitle":"Stratocaster Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"Stratocaster/strat_voodoo_bridge.txt","dcr":"8.0 k\u03a9","peak":"6.12 kHz","character":"Authority & sustain","description":"Ferrous baseplate \u2014 added low-end weight, built to cut through"},"middle":{"file":"Stratocaster/strat_voodoo_middle.txt","dcr":"7.2 k\u03a9","peak":"6.76 kHz","character":"RWRP power","description":"More presence in positions 2 & 4 \u2014 hot and hum-free"},"neck":{"file":"Stratocaster/strat_voodoo_neck.txt","dcr":"7.15 k\u03a9","peak":"6.76 kHz","character":"Full & commanding","description":"More output, more sustain \u2014 built to be heard"}}},
    # HUMBUCKER
    {"handle":"revival","family":"hb","model":"Revival\u2122 PAF","subtitle":"Humbucker Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"Humbucker/hb_revival_bridge.txt","dcr":"8.46 k\u03a9","peak":"5.62 kHz","character":"Elastic & warm","description":"Unpotted PAF \u2014 microphonic warmth at the edge of breakup"},"neck":{"file":"Humbucker/hb_revival_neck.txt","dcr":"7.94 k\u03a9","peak":"6.09 kHz","character":"Airy PAF voice","description":"Open and articulate \u2014 the pickup listens to your playing"}}},
    {"handle":"ritual","family":"hb","model":"Ritual\u2122","subtitle":"Humbucker Bridge \u00b7 Normalized Frequency Response","scores_display":"solo","positions":{"bridge":{"file":"Humbucker/hb_ritual_bridge_solo.txt","dcr":"17.9 k\u03a9","peak":"5.60 kHz","character":"Dense & aggressive","description":"Hard rock and old-school metal \u2014 44 AWG, built to push hard and stay mean"}}},
    # P90
    {"handle":"aura-soapbar","family":"p90","model":"Aura\u2122 Soap Bar","subtitle":"P90 Soap Bar Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"P90/soapbar/p90_aura_bridge_soapbar.txt","dcr":"7.73 k\u03a9","peak":"4.86 kHz","character":"Growl with body","description":"Vintage P90 voice \u2014 warm, round, Alnico 2 softness"},"neck":{"file":"P90/soapbar/p90_aura_neck_soapbar.txt","dcr":"7.27 k\u03a9","peak":"4.81 kHz","character":"Round & full","description":"More body than bite \u2014 blues, jazz, indie territory"}}},
    {"handle":"aura-dogear","family":"p90","model":"Aura\u2122 Dog Ear","subtitle":"P90 Dog Ear Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"P90/dogear/p90_aura_bridge_dogear.txt","dcr":"7.58 k\u03a9","peak":"4.88 kHz","character":"Growl with body","description":"Vintage P90 voice \u2014 warm, round, Alnico 2 softness"},"neck":{"file":"P90/dogear/p90_aura_neck_dogear.txt","dcr":"6.95 k\u03a9","peak":"4.91 kHz","character":"Round & full","description":"More body than bite \u2014 blues, jazz, indie territory"}}},
    {"handle":"thunderbolt-soapbar","family":"p90","model":"Thunderbolt\u2122 Soap Bar","subtitle":"P90 Soap Bar Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"P90/soapbar/p90_thunderbolt_bridge_soapbar.txt","dcr":"8.35 k\u03a9","peak":"4.67 kHz","character":"Maximum P90 aggression","description":"Hottest in the P90 line \u2014 pushes hard, retains top-end clarity"},"neck":{"file":"P90/soapbar/p90_thunderbolt_neck_soapbar.txt","dcr":"7.66 k\u03a9","peak":"4.51 kHz","character":"Driven warmth","description":"High-output neck \u2014 rock and blues-rock authority"}}},
    {"handle":"thunderbolt-dogear","family":"p90","model":"Thunderbolt\u2122 Dog Ear","subtitle":"P90 Dog Ear Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"P90/dogear/p90_thunderbolt_bridge_dogear.txt","dcr":"8.45 k\u03a9","peak":"4.55 kHz","character":"Maximum P90 aggression","description":"Hottest in the P90 line \u2014 pushes hard, retains top-end clarity"},"neck":{"file":"P90/dogear/p90_thunderbolt_neck_dogear.txt","dcr":"7.54 k\u03a9","peak":"4.55 kHz","character":"Driven warmth","description":"High-output neck \u2014 rock and blues-rock authority"}}},
    {"handle":"zenith-soapbar","family":"p90","model":"Zenith\u2122 Soap Bar","subtitle":"P90 Soap Bar Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"P90/soapbar/p90_zenith_bridge_soapbar.txt","dcr":"7.72 k\u03a9","peak":"4.93 kHz","character":"Grind & drive","description":"Hot P90 that pushes amps hard with sustained character"},"neck":{"file":"P90/soapbar/p90_zenith_neck_soapbar.txt","dcr":"7.12 k\u03a9","peak":"4.76 kHz","character":"Commanding & clear","description":"Strong output with RDSL top-end clarity intact"}}},
    {"handle":"zenith-dogear","family":"p90","model":"Zenith\u2122 Dog Ear","subtitle":"P90 Dog Ear Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"P90/dogear/p90_zenith_bridge_dogear.txt","dcr":"7.54 k\u03a9","peak":"4.84 kHz","character":"Grind & drive","description":"Hot P90 that pushes amps hard with sustained character"},"neck":{"file":"P90/dogear/p90_zenith_neck_dogear.txt","dcr":"6.93 k\u03a9","peak":"4.75 kHz","character":"Commanding & clear","description":"Strong output with RDSL top-end clarity intact"}}},
]

# ── REW parsing ───────────────────────────────────────────────────────────────

def parse_rew(filepath):
    freqs, dbs = [], []
    is_spl = False
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            if line.startswith("*"):
                if "SPL(dB)" in line: is_spl = True
                elif "W(W)" in line:  is_spl = False
                continue
            parts = line.split(";")
            if len(parts) < 2: continue
            try:
                freq = float(parts[0].strip())
                val  = float(parts[1].strip())
                if is_spl: dbs.append(val)
                else:
                    if val > 0: dbs.append(10.0 * math.log10(val))
                freqs.append(freq)
            except ValueError:
                continue
    paired = sorted(zip(freqs, dbs), key=lambda x: x[0])
    return [p[0] for p in paired], [p[1] for p in paired]

def smooth_and_resample(freqs, dbs):
    half = OCTAVE_SMOOTH / 2.0
    out_freqs = [F_MIN * ((F_MAX / F_MIN) ** (i / (N_OUT - 1))) for i in range(N_OUT)]
    smoothed = []
    for f_out in out_freqs:
        lo = bisect.bisect_left(freqs,  f_out * (2 ** -half))
        hi = bisect.bisect_right(freqs, f_out * (2 **  half))
        window = dbs[lo:hi]
        smoothed.append(sum(window) / len(window) if window else 0.0)
    peak = max(smoothed)
    norm = [round(v - peak, 2) for v in smoothed]
    return [[round(out_freqs[i], 2), norm[i]] for i in range(N_OUT)]

# ── Score helpers ─────────────────────────────────────────────────────────────

def parse_dcr(s):
    return float(s.replace("k\u03a9","").replace("k\u2126","").strip())

def parse_peak_khz(s):
    return float(s.replace("kHz","").strip())

def band_avg(data, f_lo, f_hi):
    vals = [db for f, db in data if f_lo <= f <= f_hi]
    return sum(vals) / len(vals) if vals else -20.0

def raw_scores(data, dcr_str, peak_str):
    dcr = parse_dcr(dcr_str)
    return {
        "output":   dcr,
        "treble":   parse_peak_khz(peak_str),
        "midrange": band_avg(data, 250, 2000),
        "bass":     band_avg(data, 60, 250),
        "dynamics": 1.0 / dcr,
    }

def avg_raw(raws_list):
    attrs = ["output","treble","midrange","bass","dynamics"]
    return {a: sum(r[a] for r in raws_list) / len(raws_list) for a in attrs}

def scale(val, lo, hi):
    """Map val from [lo,hi] to [2.0,5.0], clamped."""
    if hi == lo: return 3.5
    return round(max(2.0, min(5.0, 2.0 + 3.0 * (val - lo) / (hi - lo))), 2)

def padded_bounds(values, pad=0.5):
    """Expand catalog min/max by pad fraction to avoid extremes."""
    lo, hi = min(values), max(values)
    spread = (hi - lo) if hi != lo else 1.0
    return lo - spread * pad, hi + spread * pad

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Pass 1 — process all REW files, collect raw scores
    processed = {}
    raw_store  = {}

    for model in MODELS:
        handle = model["handle"]
        sd     = model["scores_display"]
        print(f"\nPass 1 — {model['model']} ({handle})")
        processed[handle] = {}
        raw_store[handle] = {}

        for pos, spec in model["positions"].items():
            path = os.path.join(RAW_BASE, spec["file"])
            if not os.path.exists(path):
                print(f"  x Missing: {path}"); continue
            freqs, dbs = parse_rew(path)
            fmt  = "SPL" if dbs and dbs[0] > 1.0 else "W->dB"
            data = smooth_and_resample(freqs, dbs)
            processed[handle][pos] = data
            rs   = raw_scores(data, spec["dcr"], spec["peak"])
            print(f"  . {pos} [{fmt}]  out={rs['output']:.2f}  treble={rs['treble']:.2f}  mid={rs['midrange']:.2f}  bass={rs['bass']:.2f}  dyn={rs['dynamics']:.4f}")

            if sd == "toggle":
                raw_store[handle][pos] = rs
            elif sd == "solo":
                raw_store[handle]["solo"] = rs
            else:
                raw_store[handle].setdefault("_parts", []).append(rs)

        if sd == "average" and "_parts" in raw_store[handle]:
            raw_store[handle]["set"] = avg_raw(raw_store[handle].pop("_parts"))

    # Collect midrange + bass values per family for padded bounds
    family_curve_vals = {}
    for model in MODELS:
        fam = model["family"]
        family_curve_vals.setdefault(fam, {"midrange": [], "bass": []})
        for sk, rs in raw_store.get(model["handle"], {}).items():
            family_curve_vals[fam]["midrange"].append(rs["midrange"])
            family_curve_vals[fam]["bass"].append(rs["bass"])

    # Pass 2 — normalize and write JSON
    for model in MODELS:
        handle = model["handle"]
        fam    = model["family"]
        if handle not in processed or not processed[handle]: continue

        anch = ANCHORS[fam]
        mid_lo, mid_hi = padded_bounds(family_curve_vals[fam]["midrange"])
        bas_lo, bas_hi = padded_bounds(family_curve_vals[fam]["bass"])

        scores_out = {}
        for sk, rs in raw_store[handle].items():
            scores_out[sk] = {
                "output":   scale(rs["output"],   *anch["output"]),
                "treble":   scale(rs["treble"],   *anch["treble"]),
                "midrange": scale(rs["midrange"], mid_lo, mid_hi),
                "bass":     scale(rs["bass"],     bas_lo, bas_hi),
                "dynamics": scale(rs["dynamics"], *anch["dynamics"]),
            }
            print(f"  {handle}/{sk}: out={scores_out[sk]['output']}  treble={scores_out[sk]['treble']}  mid={scores_out[sk]['midrange']}  bass={scores_out[sk]['bass']}  dyn={scores_out[sk]['dynamics']}")

        out = {
            "model":          model["model"],
            "subtitle":       model["subtitle"],
            "scores_display": model["scores_display"],
            "scores":         scores_out,
        }
        for pos, spec in model["positions"].items():
            if pos not in processed[handle]: continue
            out[pos] = {
                "dcr":         spec["dcr"],
                "peak":        spec["peak"],
                "character":   spec["character"],
                "description": spec["description"],
                "data":        processed[handle][pos],
            }

        out_path = os.path.join(OUT_DIR, f"{handle}.json")
        with open(out_path, "w") as f:
            json.dump(out, f, separators=(",",":"))
        print(f"  -> {out_path}  ({os.path.getsize(out_path)/1024:.1f} KB)")

    print("\nDone.")

if __name__ == "__main__":
    main()
