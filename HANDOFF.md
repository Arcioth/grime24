# HANDOFF — grime24

Updated: 2026-09-28

## State

Receiver-side scorer only. No transmitter and no stick firmware.

Run from this directory:

```bash
python3 -m grime24 SWEEPS.jsonl
```

That prints the channel table and writes `examples/score-YYYYMMDD.json` from the sweep timestamp.

Scored `/home/arcioth/Documents/hack24tron/logs/sweeps.jsonl`. Six sweeps, 2026-09-28 around 19:12 UTC, LNA 24 dB, VGA 20 dB, amp off, 1 MHz bins, 2400–2484 MHz. Copies: `examples/score-20260928.txt`, `examples/score-20260928.json`.

Floor is the median of bins outside every channel 1–13 mask. On this span that is four edge bins (2400, 2401, 2483, 2484 MHz), about −61 to −64 dB. The quietest 20% is stored on each sweep and used only when no bin sits outside the masks.

The median row is the same scorer on the bin-wise median spectrum. It is quiet on all 13 channels. No hit in this set survives all six dwells.

Per sweep, masks overlap, so one spike is listed on every channel that covers it:

- No barrage.
- Sweep 1: all quiet.
- Narrow hits, each on one or two dwells: 2411–2417 MHz, 2445 MHz, 2459 MHz, 2475–2476 MHz.
- Sweep 5 is the loud dwell. Energy about 5 MHz wide near 2405–2409, 2415–2419, and 2435–2439 MHz, peak −27.96 dB at 2438 MHz. Labeled busy, not barrage, because the channel median stays within 10 dB of the floor.
- Channels 10 and 11 were quiet on every sweep.

The M5Stick is not in the lab this session. The later pass is `docs/FIELDTEST.md`. CSV ingest is not written.

## Next

Ingest an M5 CSV after the field test. Columns: `utc,channel,rssi_dbm,noise_floor_dbm,note`. Compare which channels the stick ranks as loud with these labels. Do not subtract stick dBm from HackRF dB.

## Open

- The busy cut (occupancy ≥ 0.25, or a hot run at least 3 MHz wide) is a choice, not a standard. Barrage needs occupancy ≥ 0.50 and an in-band median more than 10 dB above the floor. This log never reached that.
- On sweep 0 the 2445 MHz bin was about 11.6 dB over the channel 6 median, just under the 12 dB parasite cut, so that channel stayed quiet.
- Six dwells of about 91 ms are not an occupancy study. A normal transmission that fills the dwell can look busy, or like barrage if it fills the mask. The label is an energy shape, not an ID of a jammer.
- 1 MHz bins cannot separate Wi-Fi OFDM, BLE, a microwave, or a spur. BLE advertising frequencies are 2402, 2426, and 2480 MHz. A narrow bin there is still just a bin.
- The edge-bin floor sits near the modal level of this radio. The quietest 20% is several dB lower because of deep nulls. Using those nulls as the floor would mark ordinary ripple as barrage, so that estimate stays the fallback.
- Stick model, which RSSI field it reports, and how long it dwells are unknown until the device is back.
