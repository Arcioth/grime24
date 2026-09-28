# grime24

Receiver-side scorer for 2.4 GHz Wi-Fi channels. Reads HackRF sweep bins and labels each channel quiet, busy, parasite, or barrage.

- Detection only. No transmitter, no jammer, no waveform, no firmware flash.
- The M5Stick is not in the lab. Do not invent a flash path. The later pass is `docs/FIELDTEST.md`.
- Python 3 standard library. Numpy does not import on this machine; do not add it.
- Score a log from this directory: `python3 -m grime24 PATH/sweeps.jsonl`.
- Reference sweeps stay in `~/Documents/hack24tron/logs/`. Do not edit that project from here.
- Update `HANDOFF.md` and `CHANGELOG.md` when the scorer or the field protocol changes.
