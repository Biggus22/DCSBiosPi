# DCSBiosPi — Raspberry Pi companion (minimal scaffold)

This is a fresh scaffold for a small Raspberry Pi companion that bridges
DCS‑BIOS multicast traffic to local clients (serial devices or PTYs) and
provides a minimal CLI for running the bridge.

Quickstart

1. Create a venv and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Run the bridge (defaults shown):

```bash
python -m dcsbpi.cli --mcast-group 239.255.50.10 --mcast-port 5010
```

3. To expose a PTY for multicast packets, run `multicast_to_pty.py`:

```bash
python multicast_to_pty.py 239.255.50.10 5010 /tmp/dcsbpi-pty
```

This scaffold intentionally keeps implementation minimal so you can extend
parsers, mapping files and GPIO integration as needed.
