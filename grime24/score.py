"""Score Wi-Fi channels 1–13 from HackRF sweep bins.

Receive-side only. Each channel uses a nominal 20 MHz mask
(center ± 10 MHz) clipped to 2400–2484 MHz.

floor_db
    Median of bins inside the band and outside every channel mask.
    If that set is empty, median of the quietest 20% of bins.

occupancy
    Fraction of in-mask bins more than 8 dB above floor_db.

parasite
    A contiguous in-mask run narrower than 3 MHz, each bin more
    than 12 dB above the in-band median. Not a full-width blob.

barrage
    Occupancy >= 0.50 and in-band median more than 10 dB above
    floor_db. Wide energy across most of the mask.

label
    barrage, else busy if a hot run is at least 3 MHz wide,
    else parasite, else busy if occupancy >= 0.25, else quiet.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

BAND_LO_MHZ = 2400.0
BAND_HI_MHZ = 2484.0
CHANNEL_LO = 1
CHANNEL_HI = 13
MASK_HALF_MHZ = 10.0
OCC_ABOVE_FLOOR_DB = 8.0
PARASITE_ABOVE_MEDIAN_DB = 12.0
PARASITE_NARROWER_THAN_MHZ = 3.0
BARRAGE_ABOVE_FLOOR_DB = 10.0
BARRAGE_OCCUPANCY_MIN = 0.50
BUSY_OCCUPANCY_MIN = 0.25
QUIETEST_FRACTION = 0.20
LABELS = ("quiet", "busy", "parasite", "barrage")

ROOT = Path(__file__).resolve().parent.parent


def q2(value: float) -> float:
    return float(f"{value:.2f}")


def channel_center_mhz(channel: int) -> float:
    return 2412.0 + (channel - 1) * 5.0


def mask_mhz(center: float) -> tuple[float, float]:
    lo = max(BAND_LO_MHZ, center - MASK_HALF_MHZ)
    hi = min(BAND_HI_MHZ, center + MASK_HALF_MHZ)
    return lo, hi


def channel_masks() -> list[dict]:
    rows = []
    for channel in range(CHANNEL_LO, CHANNEL_HI + 1):
        center = channel_center_mhz(channel)
        lo, hi = mask_mhz(center)
        rows.append({"ch": channel, "center_mhz": center, "lo": lo, "hi": hi})
    return rows


def load_sweeps(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    sweeps = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"{path}:{line_no}: expected an object")
        raw_bins = obj.get("bins")
        if not isinstance(raw_bins, list) or not raw_bins:
            raise ValueError(f"{path}:{line_no}: missing bins")
        bins = []
        for item in raw_bins:
            if not isinstance(item, dict) or "mhz" not in item or "db" not in item:
                raise ValueError(f"{path}:{line_no}: bin missing mhz/db")
            bins.append({"mhz": float(item["mhz"]), "db": float(item["db"])})
        config = obj.get("config")
        sweeps.append(
            {
                "ts": str(obj.get("ts") or ""),
                "config": config if isinstance(config, dict) else {},
                "duration_ms": obj.get("duration_ms"),
                "bins": bins,
            }
        )
    if not sweeps:
        raise ValueError(f"{path}: no sweeps")
    return sweeps


def collapse_bins(bins: list[dict]) -> list[dict]:
    """One level per MHz inside 2400–2484. Duplicate MHz keeps the louder bin."""
    acc: dict[float, float] = {}
    for bin_row in bins:
        mhz = round(float(bin_row["mhz"]), 6)
        if mhz < BAND_LO_MHZ or mhz > BAND_HI_MHZ:
            continue
        db = q2(float(bin_row["db"]))
        prev = acc.get(mhz)
        if prev is None or db > prev:
            acc[mhz] = db
    return [{"mhz": mhz, "db": acc[mhz]} for mhz in sorted(acc)]


def bin_step_mhz(bins: list[dict]) -> float:
    mhzs = [row["mhz"] for row in bins]
    deltas = [round(b - a, 6) for a, b in zip(mhzs, mhzs[1:]) if b > a]
    if not deltas:
        return 1.0
    return float(statistics.median(deltas))


def quietest_median(bins: list[dict], fraction: float = QUIETEST_FRACTION) -> float:
    levels = sorted(row["db"] for row in bins)
    count = max(1, int(len(levels) * fraction))
    return q2(statistics.median(levels[:count]))


def outside_mask_bins(bins: list[dict], masks: list[dict]) -> list[dict]:
    outside = []
    for row in bins:
        mhz = row["mhz"]
        if any(mask["lo"] <= mhz <= mask["hi"] for mask in masks):
            continue
        outside.append(row)
    return outside


def floor_db(bins: list[dict], masks: list[dict]) -> tuple[float, str, list[dict], float]:
    outside = outside_mask_bins(bins, masks)
    quiet = quietest_median(bins)
    if outside:
        level = q2(statistics.median(row["db"] for row in outside))
        return level, "outside_masks", outside, quiet
    return quiet, "quietest_20pct", [], quiet


def hot_runs(inband: list[dict], inband_median: float, step: float) -> list[dict]:
    """Contiguous bins more than 12 dB above the in-band median."""
    threshold = inband_median + PARASITE_ABOVE_MEDIAN_DB
    runs: list[list[dict]] = []
    current: list[dict] = []
    gap = step * 1.5
    for row in inband:
        if row["db"] <= threshold:
            if current:
                runs.append(current)
                current = []
            continue
        if current and row["mhz"] - current[-1]["mhz"] > gap:
            runs.append(current)
            current = [row]
        else:
            current.append(row)
    if current:
        runs.append(current)

    packed = []
    for run in runs:
        peak = max(run, key=lambda row: (row["db"], -row["mhz"]))
        width = round((run[-1]["mhz"] - run[0]["mhz"]) + step, 4)
        packed.append(
            {
                "mhz": peak["mhz"],
                "db": peak["db"],
                "width_mhz": width,
                "excess_db": q2(peak["db"] - inband_median),
                "bins_mhz": [row["mhz"] for row in run],
            }
        )
    return packed


def classify(occupancy: float, inband_median: float, floor_level: float, runs: list[dict]) -> tuple[str, bool, bool]:
    """Barrage wins. A wide hot run is busy. A narrow run alone is parasite."""
    narrow = [run for run in runs if run["width_mhz"] < PARASITE_NARROWER_THAN_MHZ]
    wide = [run for run in runs if run["width_mhz"] >= PARASITE_NARROWER_THAN_MHZ]
    barrage = (
        occupancy >= BARRAGE_OCCUPANCY_MIN
        and (inband_median - floor_level) > BARRAGE_ABOVE_FLOOR_DB
    )
    if barrage:
        label = "barrage"
    elif wide:
        label = "busy"
    elif narrow:
        label = "parasite"
    elif occupancy >= BUSY_OCCUPANCY_MIN:
        label = "busy"
    else:
        label = "quiet"
    return label, bool(narrow), barrage


def score_spectrum(bins: list[dict], masks: list[dict] | None = None) -> dict:
    masks = masks if masks is not None else channel_masks()
    bins = collapse_bins(bins)
    if not bins:
        raise ValueError("no bins inside 2400–2484 MHz")
    step = bin_step_mhz(bins)
    level, method, outside, quiet = floor_db(bins, masks)
    channels = []
    for mask in masks:
        inband = [row for row in bins if mask["lo"] <= row["mhz"] <= mask["hi"]]
        if not inband:
            channels.append(
                {
                    "ch": mask["ch"],
                    "center_mhz": mask["center_mhz"],
                    "mask_mhz": [mask["lo"], mask["hi"]],
                    "n_bins": 0,
                    "floor_db": level,
                    "inband_median_db": None,
                    "inband_peak_db": None,
                    "inband_peak_mhz": None,
                    "occupancy": None,
                    "parasite": False,
                    "parasites": [],
                    "hot_runs": [],
                    "barrage": False,
                    "label": "quiet",
                }
            )
            continue
        levels = [row["db"] for row in inband]
        inband_median = q2(statistics.median(levels))
        peak = max(inband, key=lambda row: (row["db"], -row["mhz"]))
        occupied = sum(1 for row in inband if row["db"] > level + OCC_ABOVE_FLOOR_DB)
        occupancy = occupied / len(inband)
        runs = hot_runs(inband, inband_median, step)
        label, parasite, barrage = classify(occupancy, inband_median, level, runs)
        narrow = [run for run in runs if run["width_mhz"] < PARASITE_NARROWER_THAN_MHZ]
        channels.append(
            {
                "ch": mask["ch"],
                "center_mhz": mask["center_mhz"],
                "mask_mhz": [mask["lo"], mask["hi"]],
                "n_bins": len(inband),
                "floor_db": level,
                "inband_median_db": inband_median,
                "inband_peak_db": peak["db"],
                "inband_peak_mhz": peak["mhz"],
                "occupancy": round(occupancy, 4),
                "parasite": parasite,
                "parasites": narrow,
                "hot_runs": runs,
                "barrage": barrage,
                "label": label,
            }
        )
    return {
        "floor_db": level,
        "floor_method": method,
        "quietest_20_db": quiet,
        "n_outside": len(outside),
        "outside_bins": [{"mhz": row["mhz"], "db": row["db"]} for row in outside],
        "bin_step_mhz": step,
        "n_bins": len(bins),
        "channels": channels,
    }


def median_spectrum(collapsed: list[list[dict]]) -> list[dict]:
    acc: dict[float, list[float]] = {}
    for bins in collapsed:
        for row in bins:
            acc.setdefault(row["mhz"], []).append(row["db"])
    return [{"mhz": mhz, "db": q2(statistics.median(levels))} for mhz, levels in sorted(acc.items())]


def stamp_from(sweeps: list[dict]) -> str:
    dates = []
    for sweep in sweeps:
        ts = sweep["ts"]
        if len(ts) >= 8 and ts[:8].isdigit():
            dates.append(ts[:8])
    return dates[0] if dates else "undated"


def score_sweeps(sweeps: list[dict], source: str) -> dict:
    masks = channel_masks()
    scored_sweeps = []
    collapsed = []
    for index, sweep in enumerate(sweeps):
        bins = collapse_bins(sweep["bins"])
        collapsed.append(bins)
        spectrum = score_spectrum(bins, masks)
        scored_sweeps.append(
            {
                "index": index,
                "ts": sweep["ts"],
                "config": sweep["config"],
                "duration_ms": sweep["duration_ms"],
                **spectrum,
            }
        )
    median = score_spectrum(median_spectrum(collapsed), masks)
    counts = []
    for channel in range(CHANNEL_LO, CHANNEL_HI + 1):
        labels = [sweep["channels"][channel - 1]["label"] for sweep in scored_sweeps]
        occupancies = [sweep["channels"][channel - 1]["occupancy"] for sweep in scored_sweeps]
        medians = [sweep["channels"][channel - 1]["inband_median_db"] for sweep in scored_sweeps]
        peaks = [sweep["channels"][channel - 1]["inband_peak_db"] for sweep in scored_sweeps]
        counts.append(
            {
                "ch": channel,
                "quiet": labels.count("quiet"),
                "busy": labels.count("busy"),
                "parasite": labels.count("parasite"),
                "barrage": labels.count("barrage"),
                "median_occupancy": round(statistics.median(occupancies), 4),
                "median_inband_median_db": q2(statistics.median(medians)),
                "median_inband_peak_db": q2(statistics.median(peaks)),
            }
        )
    configs = [json.dumps(sweep["config"], sort_keys=True) for sweep in sweeps]
    return {
        "tool": "grime24",
        "version": "0.1.0",
        "role": "receiver-side scorer",
        "source": source,
        "stamp": stamp_from(sweeps),
        "n_sweeps": len(sweeps),
        "band_mhz": [BAND_LO_MHZ, BAND_HI_MHZ],
        "gain_uniform": len(set(configs)) == 1,
        "thresholds": {
            "channels": [CHANNEL_LO, CHANNEL_HI],
            "mask_half_mhz": MASK_HALF_MHZ,
            "occupancy_above_floor_db": OCC_ABOVE_FLOOR_DB,
            "parasite_above_inband_median_db": PARASITE_ABOVE_MEDIAN_DB,
            "parasite_narrower_than_mhz": PARASITE_NARROWER_THAN_MHZ,
            "barrage_inband_median_above_floor_db": BARRAGE_ABOVE_FLOOR_DB,
            "barrage_occupancy_min": BARRAGE_OCCUPANCY_MIN,
            "busy_occupancy_min": BUSY_OCCUPANCY_MIN,
            "floor": (
                "median of bins outside every channel mask; "
                "quietest 20% of bins if none are outside"
            ),
            "label_order": (
                "barrage if occupancy >= 0.50 and in-band median is more than "
                "10 dB above the floor; else busy if a >12 dB run is at least "
                "3 MHz wide; else parasite if a >12 dB run is narrower than "
                "3 MHz; else busy if occupancy >= 0.25; else quiet"
            ),
        },
        "caveats": [
            "Uncalibrated HackRF dB at the logged gain, not dBm.",
            "Channel 1–13 masks of 20 MHz overlap, so one spike is scored on every channel that covers it.",
            "With these masks the only bins outside every mask on a 2400–2484 sweep are the band edges.",
            "A barrage label is wide received energy. A normal transmission during the dwell can have the same shape. This is not an identification of a jammer.",
            "1 MHz bins do not separate Wi-Fi OFDM, BLE, a microwave, or a spur.",
            "The median row scores the bin-wise median spectrum. A hit that shows up in one dwell is kept on that sweep and does not have to move the median.",
        ],
        "sweeps": scored_sweeps,
        "median": {
            "method": "bin-wise median spectrum, scored with the same rules",
            **median,
            "sweep_counts": counts,
        },
    }


def score_path(path: Path) -> dict:
    sweeps = load_sweeps(path)
    shown = path if path.is_absolute() else Path.cwd() / path
    return score_sweeps(sweeps, str(shown))


def fmt_run(run: dict) -> str:
    mhzs = run["bins_mhz"]
    if len(mhzs) == 1:
        span = f"{mhzs[0]:.0f}"
    else:
        span = f"{mhzs[0]:.0f}-{mhzs[-1]:.0f}"
    width = run["width_mhz"]
    width_txt = f"{width:.0f}" if abs(width - round(width)) < 1e-6 else f"{width:.1f}"
    return f"{span} ({width_txt} MHz)"


def fmt_runs(runs: list[dict]) -> str:
    if not runs:
        return "-"
    return ", ".join(fmt_run(run) for run in runs)


def channel_table(channels: list[dict]) -> list[str]:
    parasite_width = 18
    header = (
        f"{'ch':>2}  {'MHz':>4}  {'floor':>7}  {'med':>6}  {'peak':>6}  "
        f"{'occ':>5}  {'parasite':<{parasite_width}}  label"
    )
    rule = (
        f"{'--':>2}  {'----':>4}  {'-------':>7}  {'------':>6}  {'------':>6}  "
        f"{'-----':>5}  {'-' * parasite_width}  -----"
    )
    lines = [header, rule]
    for row in channels:
        median_txt = "  n/a" if row["inband_median_db"] is None else f"{row['inband_median_db']:>6.2f}"
        peak_txt = "   n/a" if row["inband_peak_db"] is None else f"{row['inband_peak_db']:>6.2f}"
        occ_txt = "  n/a" if row["occupancy"] is None else f"{row['occupancy']:>5.2f}"
        lines.append(
            f"{row['ch']:>2}  {row['center_mhz']:>4.0f}  "
            f"{row['floor_db']:>7.2f}  {median_txt}  {peak_txt}  {occ_txt}  "
            f"{fmt_runs(row['parasites']):<{parasite_width}}  {row['label']}"
        )
    return lines


def gain_text(report: dict) -> str:
    if not report["gain_uniform"]:
        return "gain     mixed across sweeps (see JSON)"
    config = report["sweeps"][0]["config"] or {}
    if not config:
        return "gain     not recorded"
    return (
        f"gain     LNA {config.get('lna_db')} dB  VGA {config.get('vga_db')} dB  "
        f"amp {config.get('amp')}  bin_hz {config.get('bin_hz')}  "
        f"(uncalibrated dB, not dBm)"
    )


def result_line(report: dict) -> str:
    hits = []
    for sweep in report["sweeps"]:
        for row in sweep["channels"]:
            if row["label"] != "quiet":
                hits.append(row["label"])
    n_barrage = hits.count("barrage")
    n_parasite = hits.count("parasite")
    n_busy = hits.count("busy")
    median_labels = {row["label"] for row in report["median"]["channels"]}
    if median_labels == {"quiet"}:
        median_txt = "median spectrum is quiet on every channel"
    else:
        median_txt = "median spectrum labels: " + ", ".join(
            f"{row['ch']} {row['label']}"
            for row in report["median"]["channels"]
            if row["label"] != "quiet"
        )
    return (
        f"hits     {n_parasite} parasite, {n_busy} busy, {n_barrage} barrage "
        f"across {report['n_sweeps']} sweeps (overlapping masks, so one spike "
        f"counts on each channel it covers). {median_txt}."
    )


def format_report(report: dict) -> str:
    lines: list[str] = []
    add = lines.append
    add("grime24  2.4 GHz channel scorer  (receive only, no transmit)")
    add(f"source   {report['source']}")
    add(f"sweeps   {report['n_sweeps']}   stamp {report['stamp']}")
    add(gain_text(report))
    add(
        f"band     {BAND_LO_MHZ:.0f}–{BAND_HI_MHZ:.0f} MHz   "
        f"channels {CHANNEL_LO}–{CHANNEL_HI}   "
        f"mask center±{MASK_HALF_MHZ:.0f} MHz, clipped to the band"
    )
    add(
        "floor    median of bins outside every Wi-Fi mask "
        "(else quietest 20% of bins)"
    )
    add(
        "rules    occupancy: share of in-mask bins > floor+8 dB; "
        "parasite: run < 3 MHz and > in-band median+12 dB; "
        "barrage: occupancy >= 0.50 and in-band median > floor+10 dB; "
        "busy: a >= 3 MHz hot run, or occupancy >= 0.25, and not the cases above"
    )
    add(result_line(report))
    add("")
    add("median spectrum (bin-wise median of the sweeps, then scored)")
    floor = report["median"]
    add(
        f"floor {floor['floor_db']:.2f} dB via {floor['floor_method']} "
        f"(n_outside {floor['n_outside']}); quietest 20% {floor['quietest_20_db']:.2f} dB "
        f"(stored, not used while outside bins exist)"
    )
    lines.extend(channel_table(floor["channels"]))
    add("")
    add("per-sweep labels (median column is the spectrum above, not a vote)")
    header = "ch  " + "  ".join(f"s{sweep['index']:<9}" for sweep in report["sweeps"]) + "  median"
    add(header)
    for channel in range(CHANNEL_LO, CHANNEL_HI + 1):
        cells = [
            f"{sweep['channels'][channel - 1]['label']:<9}"
            for sweep in report["sweeps"]
        ]
        med = report["median"]["channels"][channel - 1]["label"]
        add(f"{channel:>2}  " + "  ".join(cells) + f"  {med}")
    add("")
    add("non-quiet hits")
    hit_lines = 0
    for sweep in report["sweeps"]:
        for row in sweep["channels"]:
            if row["label"] == "quiet":
                continue
            hit_lines += 1
            detail = fmt_runs(row["parasites"])
            wide = [
                run
                for run in row["hot_runs"]
                if run["width_mhz"] >= PARASITE_NARROWER_THAN_MHZ
            ]
            extra = ""
            if wide and row["label"] != "parasite":
                extra = "  wide " + fmt_runs(wide)
            add(
                f"  s{sweep['index']} {sweep['ts']}  ch {row['ch']:>2}  "
                f"{row['label']:<9} peak {row['inband_peak_db']:7.2f} at "
                f"{row['inband_peak_mhz']:.0f}  med {row['inband_median_db']:7.2f}  "
                f"occ {row['occupancy']:.2f}  parasite {detail}{extra}"
            )
    if hit_lines == 0:
        add("  none")
    add("")
    add("per-sweep detail")
    for sweep in report["sweeps"]:
        add("")
        add(
            f"sweep {sweep['index']}  {sweep['ts']}  "
            f"floor {sweep['floor_db']:.2f} dB ({sweep['floor_method']}, "
            f"n_outside {sweep['n_outside']})  "
            f"quietest20 {sweep['quietest_20_db']:.2f} dB"
        )
        lines.extend(channel_table(sweep["channels"]))
    add("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] in {"-h", "--help"}:
        print("usage: python3 -m grime24 SWEEPS.jsonl", file=sys.stderr)
        return 0 if args and args[0] in {"-h", "--help"} else 2
    path = Path(args[0])
    if not path.is_file():
        print(f"grime24: not a file: {path}", file=sys.stderr)
        return 1
    try:
        report = score_path(path)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"grime24: {exc}", file=sys.stderr)
        return 1
    text = format_report(report)
    print(text, end="")
    out_dir = ROOT / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"score-{report['stamp']}.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
