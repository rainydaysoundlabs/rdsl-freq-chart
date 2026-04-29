#!/usr/bin/env python3
"""
RDSL REW Processing Pipeline v2
- Auto-detects W(W) vs SPL(dB) REW format
- Computes tonal profile scores (Output, Treble, Midrange, Bass, Attack)
- Normalizes scores catalog-wide to 1.0–5.0 scale
- Bakes scores into JSON alongside frequency data

scores_display modes:
  "toggle"  — Tele sets: bridge & neck scored separately, UI toggles
  "average" — Strat/P90/HB sets: positions averaged, labeled "Calibrated set"
  "solo"    — Single-position models: no set language

Run from: rdsl-freq-chart/
  python3 process_rew.py
"""

import json, math, os, bisect

RAW_BASE = "raw-rew"
OUT_DIR  = "freqsets"
N_OUT    = 180
F_MIN    = 20.0
F_MAX    = 20000.0
OCTAVE_SMOOTH = 1/12

MODELS = [
    {"handle":"skylark","model":"Skylark\u2122","subtitle":"Telecaster Set \u00b7 Normalized Frequency Response","scores_display":"toggle","positions":{"bridge":{"file":"Telecaster/tele_skylark_bridge.txt","dcr":"6.7 k\u03a9","peak":"6.60 kHz","character":"Snappy & immediate","description":"Bell-like 1960s Tele articulation with copper baseplate snap"},"neck":{"file":"Telecaster/tele_skylark_neck.txt","dcr":"5.6 k\u03a9","peak":"8.72 kHz","character":"Glassy & open","description":"Extended high-freq response"}}},
    {"handle":"high-line","model":"High-Line\u2122","subtitle":"Telecaster Set \u00b7 Normalized Frequency Response","scores_display":"toggle","positions":{"bridge":{"file":"Telecaster/tele_high-line_bridge.txt","dcr":"7.8 k\u03a9","peak":"6.34 kHz","character":"Desert-island Tele voice","description":"Modern Alnico 5 \u2014 glassy, cutting, sits in any mix"},"neck":{"file":"Telecaster/tele_high-line_neck.txt","dcr":"6.2 k\u03a9","peak":"9.70 kHz","character":"Open & versatile","description":"Extended top-end \u2014 the modern player's Tele neck"}}},
    {"handle":"bakersfield","model":"Bakersfield\u2122","subtitle":"Telecaster Set \u00b7 Normalized Frequency Response","scores_display":"toggle","positions":{"bridge":{"file":"Telecaster/tele_bakersfield_bridge.txt","dcr":"7.2 k\u03a9","peak":"6.44 kHz","character":"Honky & mid-forward","description":"Bakersfield twang \u2014 Buck Owens, Merle Haggard territory"},"neck":{"file":"Telecaster/tele_bakersfield_neck.txt","dcr":"6.1 k\u03a9","peak":"10.20 kHz","character":"Snappy & percussive","description":"Bright vintage country attack"}}},
    {"handle":"truevintagecustom","model":"True Vintage Custom\u2122","subtitle":"Telecaster Set \u00b7 Normalized Frequency Response","scores_display":"toggle","positions":{"bridge":{"file":"Telecaster/tele_truevintagecustom_bridge.txt","dcr":"6.8 k\u03a9","peak":"6.65 kHz","character":"Warm vintage output","description":"Alnico 2 character \u2014 full but articulate"},"neck":{"file":"Telecaster/tele_truevintagecustom_neck.txt","dcr":"7.1 k\u03a9","peak":"8.20 kHz","character":"Fuller Tele voice","description":"Hot 43 AWG wind with extended high-end presence"}}},
    {"handle":"t-50","model":"T-50 Vintage","subtitle":"Telecaster Neck \u00b7 Normalized Frequency Response","scores_display":"solo","positions":{"neck":{"file":"Telecaster/tele_t-50_neck_solo.txt","dcr":"6.8 k\u03a9","peak":"6.80 kHz","character":"Blackguard warmth","description":"Open, vintage '50s neck character"}}},
    {"handle":"t-60","model":"T-60 Vintage","subtitle":"Telecaster Neck \u00b7 Normalized Frequency Response","scores_display":"solo","positions":{"neck":{"file":"Telecaster/tele_t-60_neck_solo.txt","dcr":"7.5 k\u03a9","peak":"7.50 kHz","character":"Blackguard bite","description":"Hot late-'50s wind \u2014 presence and punch"}}},
    {"handle":"redhouse","model":"Red House\u2122","subtitle":"Stratocaster Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"Stratocaster/strat_redhouse_bridge.txt","dcr":"6.65 k\u03a9","peak":"6.94 kHz","character":"Punchy & defined","description":"The RDSL Strat voice \u2014 blues, rock, studio-ready"},"middle":{"file":"Stratocaster/strat_redhouse_middle.txt","dcr":"6.25 k\u03a9","peak":"6.94 kHz","character":"Clear & balanced","description":"RWRP \u2014 positions 2 & 4 quack, noise-free"},"neck":{"file":"Stratocaster/strat_redhouse_neck.txt","dcr":"6.35 k\u03a9","peak":"6.94 kHz","character":"Warm & full","description":"Classic Alnico 5 Strat neck, present without harshness"}}},
    {"handle":"tweedvintage","model":"Tweed Vintage\u2122","subtitle":"Stratocaster Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"Stratocaster/strat_tweedvintage_bridge.txt","dcr":"5.82 k\u03a9","peak":"7.72 kHz","character":"Touch-sensitive & open","description":"Maximum dynamics \u2014 Formvar wind, Alnico 2 softness"},"middle":{"file":"Stratocaster/strat_tweedvintage_middle.txt","dcr":"5.46 k\u03a9","peak":"8.25 kHz","character":"Airy & responsive","description":"Lightest touch in the line \u2014 positions 2 & 4 shimmer"},"neck":{"file":"Stratocaster/strat_tweedvintage_neck.txt","dcr":"5.27 k\u03a9","peak":"8.16 kHz","character":"Feather-light attack","description":"Maximum feel \u2014 built for touch-responsive playing"}}},
    {"handle":"voodoo","model":"Voodoo\u2122","subtitle":"Stratocaster Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"Stratocaster/strat_voodoo_bridge.txt","dcr":"8.0 k\u03a9","peak":"6.12 kHz","character":"Authority & sustain","description":"Ferrous baseplate \u2014 added low-end weight, built to cut through"},"middle":{"file":"Stratocaster/strat_voodoo_middle.txt","dcr":"7.2 k\u03a9","peak":"6.76 kHz","character":"RWRP power","description":"More presence in positions 2 & 4 \u2014 hot and hum-free"},"neck":{"file":"Stratocaster/strat_voodoo_neck.txt","dcr":"7.15 k\u03a9","peak":"6.76 kHz","character":"Full & commanding","description":"More output, more sustain \u2014 built to be heard"}}},
    {"handle":"revival","model":"Revival\u2122 PAF","subtitle":"Humbucker Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"Humbucker/hb_revival_bridge.txt","dcr":"8.46 k\u03a9","peak":"5.62 kHz","character":"Elastic & warm","description":"Unpotted PAF \u2014 microphonic warmth at the edge of breakup"},"neck":{"file":"Humbucker/hb_revival_neck.txt","dcr":"7.94 k\u03a9","peak":"6.09 kHz","character":"Airy PAF voice","description":"Open and articulate \u2014 the pickup listens to your playing"}}},
    {"handle":"ritual","model":"Ritual\u2122","subtitle":"Humbucker Bridge \u00b7 Normalized Frequency Response","scores_display":"solo","positions":{"bridge":{"file":"Humbucker/hb_ritual_bridge_solo.txt","dcr":"17.9 k\u03a9","peak":"5.60 kHz","character":"Dense & aggressive","description":"Hard rock and old-school metal \u2014 44 AWG, built to push hard and stay mean"}}},
    {"handle":"aura-soapbar","model":"Aura\u2122 Soap Bar","subtitle":"P90 Soap Bar Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"P90/soapbar/p90_aura_bridge_soapbar.txt","dcr":"7.73 k\u03a9","peak":"4.86 kHz","character":"Growl with body","description":"Vintage P90 voice \u2014 warm, round, Alnico 2 softness"},"neck":{"file":"P90/soapbar/p90_aura_neck_soapbar.txt","dcr":"7.27 k\u03a9","peak":"4.81 kHz","character":"Round & full","description":"More body than bite \u2014 blues, jazz, indie territory"}}},
    {"handle":"aura-dogear","model":"Aura\u2122 Dog Ear","subtitle":"P90 Dog Ear Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"P90/dogear/p90_aura_bridge_dogear.txt","dcr":"7.58 k\u03a9","peak":"4.88 kHz","character":"Growl with body","description":"Vintage P90 voice \u2014 warm, round, Alnico 2 softness"},"neck":{"file":"P90/dogear/p90_aura_neck_dogear.txt","dcr":"6.95 k\u03a9","peak":"4.91 kHz","character":"Round & full","description":"More body than bite \u2014 blues, jazz, indie territory"}}},
    {"handle":"thunderbolt-soapbar","model":"Thunderbolt\u2122 Soap Bar","subtitle":"P90 Soap Bar Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"P90/soapbar/p90_thunderbolt_bridge_soapbar.txt","dcr":"8.35 k\u03a9","peak":"4.67 kHz","character":"Maximum P90 aggression","description":"Hottest in the P90 line \u2014 pushes hard, retains top-end clarity"},"neck":{"file":"P90/soapbar/p90_thunderbolt_neck_soapbar.txt","dcr":"7.66 k\u03a9","peak":"4.51 kHz","character":"Driven warmth","description":"High-output neck \u2014 rock and blues-rock authority"}}},
    {"handle":"thunderbolt-dogear","model":"Thunderbolt\u2122 Dog Ear","subtitle":"P90 Dog Ear Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"P90/dogear/p90_thunderbolt_bridge_dogear.txt","dcr":"8.45 k\u03a9","peak":"4.55 kHz","character":"Maximum P90 aggression","description":"Hottest in the P90 line \u2014 pushes hard, retains top-end clarity"},"neck":{"file":"P90/dogear/p90_thunderbolt_neck_dogear.txt","dcr":"7.54 k\u03a9","peak":"4.55 kHz","character":"Driven warmth","description":"High-output neck \u2014 rock and blues-rock authority"}}},
    {"handle":"zenith-soapbar","model":"Zenith\u2122 Soap Bar","subtitle":"P90 Soap Bar Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"P90/soapbar/p90_zenith_bridge_soapbar.txt","dcr":"7.72 k\u03a9","peak":"4.93 kHz","character":"Grind & drive","description":"Hot P90 that pushes amps hard with sustained character"},"neck":{"file":"P90/soapbar/p90_zenith_neck_soapbar.txt","dcr":"7.12 k\u03a9","peak":"4.76 kHz","character":"Commanding & clear","description":"Strong output with RDSL top-end clarity intact"}}},
    {"handle":"zenith-dogear","model":"Zenith\u2122 Dog Ear","subtitle":"P90 Dog Ear Set \u00b7 Normalized Frequency Response","scores_display":"average","positions":{"bridge":{"file":"P90/dogear/p90_zenith_bridge_dogear.txt","dcr":"7.54 k\u03a9","peak":"4.84 kHz","character":"Grind & drive","description":"Hot P90 that pushes amps hard with sustained character"},"neck":{"file":"P90/dogear/p90_zenith_neck_dogear.txt","dcr":"6.93 k\u03a9","peak":"4.75 kHz","character":"Commanding & clear","description":"Strong output with RDSL top-end clarity intact"}}},
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
                if is_spl:
                    dbs.append(val)
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
        lo_idx = bisect.bisect_left(freqs, f_out * (2 ** -half))
        hi_idx = bisect.bisect_right(freqs, f_out * (2 **  half))
        window = dbs[lo_idx:hi_idx]
        smoothed.append(sum(window) / len(window) if window else 0.0)
    peak = max(smoothed)
    norm = [round(v - peak, 2) for v in smoothed]
    return [[round(out_freqs[i], 2), norm[i]] for i in range(N_OUT)]

# ── Score helpers ─────────────────────────────────────────────────────────────

def parse_dcr(s):
    return float(s.replace("k\u03a9","").replace("k\u2126","").replace("kOhm","").strip())

def parse_peak_khz(s):
    return float(s.replace("kHz","").strip())

def band_avg(data, f_lo, f_hi):
    vals = [db for f, db in data if f_lo <= f <= f_hi]
    return sum(vals) / len(vals) if vals else -20.0

def calc_q(data):
    dbs   = [pt[1] for pt in data]
    freqs = [pt[0] for pt in data]
    pidx  = dbs.index(max(dbs))
    pf    = freqs[pidx]
    fhi   = freqs[-1]
    for i in range(pidx, len(dbs)):
        if dbs[i] <= -3.0: fhi = freqs[i]; break
    flo = freqs[0]
    for i in range(pidx, -1, -1):
        if dbs[i] <= -3.0: flo = freqs[i]; break
    bw = fhi - flo
    return pf / bw if bw > 0 else 1.0

def raw_scores(data, dcr_str, peak_str):
    return {
        "output":   parse_dcr(dcr_str),
        "treble":   parse_peak_khz(peak_str),
        "midrange": band_avg(data, 250, 2000),
        "bass":     band_avg(data, 60, 250),
        "attack":   calc_q(data),
    }

def normalize_scores(raw, bounds):
    out = {}
    for attr, val in raw.items():
        lo, hi = bounds[attr]
        if hi == lo: out[attr] = 3.0
        else: out[attr] = round(1.0 + 4.0 * (val - lo) / (hi - lo), 2)
    return out

def avg_raw(raws_list):
    attrs = ["output","treble","midrange","bass","attack"]
    return {a: sum(r[a] for r in raws_list) / len(raws_list) for a in attrs}

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Pass 1 — process all REW files, collect processed data + raw scores
    processed = {}   # handle → {pos → data_array}
    all_raws  = {}   # handle → {pos_key → raw_score_dict}

    for model in MODELS:
        handle = model["handle"]
        print(f"\nPass 1 — {model['model']} ({handle})")
        processed[handle] = {}
        all_raws[handle]  = {}
        sd = model["scores_display"]

        for pos, spec in model["positions"].items():
            path = os.path.join(RAW_BASE, spec["file"])
            if not os.path.exists(path):
                print(f"  x Missing: {path}"); continue
            freqs, dbs = parse_rew(path)
            fmt = "SPL" if dbs and dbs[0] > 1.0 else "W->dB"
            data = smooth_and_resample(freqs, dbs)
            processed[handle][pos] = data
            rs = raw_scores(data, spec["dcr"], spec["peak"])
            print(f"  . {pos} [{fmt}]  dcr={rs['output']:.2f}  peak={rs['treble']:.2f}  mid={rs['midrange']:.2f}  bass={rs['bass']:.2f}  Q={rs['attack']:.2f}")

            if sd == "toggle":
                all_raws[handle][pos] = rs       # bridge & neck separate
            elif sd == "solo":
                all_raws[handle]["solo"] = rs    # single position
            else:
                all_raws[handle].setdefault("_parts", []).append(rs)

        if sd == "average" and "_parts" in all_raws[handle]:
            all_raws[handle]["set"] = avg_raw(all_raws[handle].pop("_parts"))

    # Collect global bounds across ALL raw score entries
    attrs  = ["output","treble","midrange","bass","attack"]
    bounds = {a: [float("inf"), float("-inf")] for a in attrs}
    for handle_raws in all_raws.values():
        for key, rs in handle_raws.items():
            for a in attrs:
                if rs[a] < bounds[a][0]: bounds[a][0] = rs[a]
                if rs[a] > bounds[a][1]: bounds[a][1] = rs[a]
    print(f"\nCatalog bounds:")
    for a in attrs:
        print(f"  {a}: {bounds[a][0]:.3f} – {bounds[a][1]:.3f}")

    # Pass 2 — normalize scores and write JSON
    for model in MODELS:
        handle = model["handle"]
        if handle not in processed or not processed[handle]: continue
        print(f"\nPass 2 — {handle}")

        out = {
            "model":          model["model"],
            "subtitle":       model["subtitle"],
            "scores_display": model["scores_display"],
            "scores":         {},
        }

        # Normalize scores
        for key, rs in all_raws[handle].items():
            out["scores"][key] = normalize_scores(rs, bounds)

        # Add freq data per position
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
