# grime24

Score 2.4 GHz Wi-Fi channels from a HackRF sweep log. Receive only. Each channel is labeled quiet, busy, parasite, or barrage. This repo does not transmit and does not describe how to cause interference.

## Run

From this directory:

```bash
python3 -m grime24 /home/arcioth/Documents/hack24tron/logs/sweeps.jsonl
```

Prints a channel table. Writes `examples/score-YYYYMMDD.json` from the date on the first sweep. The 2026-09-28 run is `examples/score-20260928.txt` and `examples/score-20260928.json`.

Python 3 standard library only.

## Rules

Channels 1–13. Center frequency is `2412 + (ch-1)*5` MHz. The mask is that center ± 10 MHz, clipped so it stays inside 2400–2484 MHz.

| Quantity | Rule |
|---|---|
| floor | Median dB of bins outside every mask. If no bin is outside, median of the quietest 20% of bins. |
| occupancy | Fraction of in-mask bins more than 8 dB above the floor. |
| parasite | Contiguous run narrower than 3 MHz, each bin more than 12 dB above the in-band median. |
| barrage | Occupancy at least 0.50 and in-band median more than 10 dB above the floor. |
| busy | A hot run at least 3 MHz wide, or occupancy at least 0.25, when the row is not barrage or a lone parasite. |
| quiet | None of the above. |

Label order: barrage, else a wide hot run as busy, else parasite, else busy from occupancy, else quiet.

The same rules run once per sweep and once on the bin-wise median of the sweeps. A spike in a single dwell stays on that sweep.

Numbers are uncalibrated HackRF dB at the gain in the log (this set: LNA 24 dB, VGA 20 dB, amp off). They are not dBm.

## This log

Six sweeps, 2026-09-28. The median spectrum is quiet on every channel. No channel met the barrage test. Narrow hits and one louder dwell are in `examples/score-20260928.txt`. Masks overlap, so one spike is repeated on every channel that covers it.

## Field test

The M5Stick is not here. When it is back, use `docs/FIELDTEST.md`. Do not flash a device from this repo.
