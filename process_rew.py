#!/usr/bin/env python3
"""
RDSL REW Processing Pipeline v4
- Auto-detects W(W) vs SPL(dB) REW format
- Per-family normalization (tele / strat / hb / p90)
- Scores mapped to 2.0–5.0 (no pickup ever hits absolute floor)
- Minimum spread check: tiny intra-family differences → midpoint score
- Attack = inverse DCR (lower output = more touch-sensitive/dynamic)
"""

import json, math, os, bisect

RAW_BASE = "raw-rew"
OUT_DIR  = "freqsets"
N_OUT    = 180
F_MIN    = 20.0
F_MAX    = 20000.0
OCTAVE_SMOOTH = 1/12

# Minimum meaningful spread per attribute (raw units).
# If family range is below this, all models score 3.5 for that attribute.
MIN_SPREAD = {
    "output":   1.2,   # kΩ
    "treble":   0.5,   # kHz
    "midrange": 1.5,   # dB
    "bass":     1.5,   # dB
    "attack":   0.003, # 1/kΩ
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
        "attack":   1.0 / dcr,   # inverse DCR: lower output = more touch-sensitive/dynamic
    }

def avg_raw(raws_list):
    attrs = ["output","treble","midrange","bass","attack"]
    return {a: sum(r[a] for r in raws_list) / len(raws_list) for a in attrs}

def normalize_family(raw_store_for_family, handles_in_family):
    """
    Normalize scores within a family to 2.0–5.0.
    If the spread for an attribute is below MIN_SPREAD, all models
    score 3.5 (differences too small to be meaningful).
    Returns: {handle: {score_key: {attr: score}}}
    """
    attrs = ["output","treble","midrange","bass","attack"]

    # Collect all raw values per attribute across all score keys in the family
    all_vals = {a: [] for a in attrs}
    for h in handles_in_family:
        for score_key, rs in raw_store_for_family.get(h, {}).items():
            for a in attrs:
                all_vals[a].append(rs[a])

    # Compute bounds and check spread
    bounds = {}
    for a in attrs:
        lo = min(all_vals[a]) if all_vals[a] else 0
        hi = max(all_vals[a]) if all_vals[a] else 1
        spread = hi - lo
        bounds[a] = (lo, hi, spread >= MIN_SPREAD[a])

    # Normalize
    result = {}
    for h in handles_in_family:
        result[h] = {}
        for score_key, rs in raw_store_for_family.get(h, {}).items():
            result[h][score_key] = {}
            for a in attrs:
                lo, hi, meaningful = bounds[a]
                if not meaningful:
                    result[h][score_key][a] = 3.5
                elif hi == lo:
                    result[h][score_key][a] = 3.5
                else:
                    raw = 2.0 + 3.0 * (rs[a] - lo) / (hi - lo)
                    result[h][score_key][a] = round(max(2.0, min(5.0, raw)), 2)
    return result

import bisect

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Pass 1 — process REW files, collect raw scores
    processed  = {}
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
            print(f"  . {pos} [{fmt}]  out={rs['output']:.2f}  treble={rs['treble']:.2f}  mid={rs['midrange']:.2f}  bass={rs['bass']:.2f}  atk={rs['attack']:.4f}")

            if sd == "toggle":
                raw_store[handle][pos] = rs
            elif sd == "solo":
                raw_store[handle]["solo"] = rs
            else:
                raw_store[handle].setdefault("_parts", []).append(rs)

        if sd == "average" and "_parts" in raw_store[handle]:
            raw_store[handle]["set"] = avg_raw(raw_store[handle].pop("_parts"))

    # Normalize per family
    families = {}
    for model in MODELS:
        families.setdefault(model["family"], []).append(model["handle"])

    all_normalized = {}
    for fam, handles in families.items():
        fam_raw = {h: raw_store[h] for h in handles if h in raw_store}
        normalized = normalize_family(fam_raw, handles)
        all_normalized.update(normalized)

        print(f"\nFamily [{fam}] — spread check:")
        attrs = ["output","treble","midrange","bass","attack"]
        all_vals = {a: [] for a in attrs}
        for h in handles:
            for sk, rs in raw_store.get(h, {}).items():
                for a in attrs:
                    all_vals[a].append(rs[a])
        for a in attrs:
            if all_vals[a]:
                spread = max(all_vals[a]) - min(all_vals[a])
                flag = "" if spread >= MIN_SPREAD[a] else " [FLAT -> 3.5]"
                print(f"  {a}: spread={spread:.4f} (min={MIN_SPREAD[a]}){flag}")

    # Pass 2 — write JSON
    for model in MODELS:
        handle = model["handle"]
        if handle not in processed or not processed[handle]: continue

        out = {
            "model":          model["model"],
            "subtitle":       model["subtitle"],
            "scores_display": model["scores_display"],
            "scores":         all_normalized.get(handle, {}),
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
