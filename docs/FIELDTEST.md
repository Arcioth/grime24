# Field test — M5Stick later

The M5Stick is not in the lab this session (2026-09-28). Nothing was flashed. This is the pass to run when the stick is back. grime24 stays a receiver.

## Gear

- M5Stick (M5Stack stick). Not here today.
- 2.4 GHz. Walk Wi-Fi channels 1–13.
- HackRF stays the reference recorder. Score those sweeps with grime24. If the ranks should be comparable to `examples/score-20260928.txt`, keep the same kind of setup noted there: LNA 24 dB, VGA 20 dB, amp off. Do not change gain in the middle of the walk.

## What the stick should log

CSV, header required, one row per channel dwell.

| Column | Meaning |
|---|---|
| utc | ISO-8601 UTC, for example `2026-09-28T19:12:05Z` |
| channel | Wi-Fi channel 1–13 |
| rssi_dbm | RSSI or channel energy, as that firmware reports it |
| noise_floor_dbm | Stick noise floor if it has one, otherwise empty |
| note | Place, facing, anything observed. Not a transmit procedure. |

```csv
utc,channel,rssi_dbm,noise_floor_dbm,note
2026-09-28T19:12:05Z,1,-67,-92,hallway facing east
2026-09-28T19:12:10Z,6,-54,-91,hallway facing east
```

## Pass

1. Pick a spot. Put it in `note`. Do not transmit for this test.
2. Start the HackRF sweep log (hack24tron) so the reference covers the same minutes as the walk.
3. On the stick, dwell channels 1 through 13 in order. A few seconds each is the intent. The firmware is not written yet, so the exact dwell waits until the stick is here.
4. Repeat the walk once if you can. Two passes show what was only a burst.
5. Save the CSV. A later ingest step will read it from `examples/`. That step is not built yet.

## What we will compare

- Which channels the stick ranks loud, against grime24 labels on the HackRF sweeps from the same time.
- `rssi_dbm - noise_floor_dbm` when both cells are filled, against grime24 occupancy and `inband_median_db - floor_db`.
- `utc` against the sweep timestamps.

HackRF numbers are uncalibrated dB at a fixed gain. Stick numbers are whatever RSSI that firmware reports. Compare order and which channels stand out. Do not subtract one instrument from the other.

## What we will not do

- No transmit test.
- No jammer, no interference source, no check that "the link dies" if something is keyed.
- The stick is a logger. The HackRF is the reference recorder. grime24 only scores energy that was already received.
- A `barrage` or `parasite` label is a shape in the bins. It does not name a device, and it is not evidence of hostile jamming.

## This session

Stick absent. The scorer ran on the six HackRF sweeps already on disk. See `examples/score-20260928.txt`.
