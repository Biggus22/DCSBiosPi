# DCSBiosPi (repository scaffold)

This repository is a standalone scaffold for the DCSBiosPi Raspberry Pi companion.

Purpose

- Provide a minimal Python package structure and CI for the Pi-side clients (GPIO, e-paper, serial helpers).
- Make it easy to extract the current `DCSBiosPi/` folder from the firmware repository into this new repo.

Quickstart

1. Copy the runtime code from the firmware repo (one-time):

```bash
# from the firmware repo root
mkdir -p /tmp/dcsbpi_copy
cp -r DCSBiosPi/* /tmp/dcsbpi_copy/
mv /tmp/dcsbpi_copy/* .
rm -rf /tmp/dcsbpi_copy
```

Or use `git subtree` or `git filter-repo` to preserve history (see the "Preserve history" section below).

2. Create virtualenv and install:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Run one of the example clients (after configuring serial/mapping/drivers):

```bash
python -m dcsbpi.cli --help
```

Preserve history

If you want to preserve commit history for the `DCSBiosPi/` folder, use `git subtree split` on the firmware repo and push to a new repo. Example:

```bash
# in firmware repo
# git subtree split -P DCSBiosPi -b dcsbpi-history
# git remote add neworigin <git@github.com:you/DCSBiosPi.git>
# git push neworigin dcsbpi-history:main
```

UDP <-> Serial bridge

The package includes a bridge that joins a UDP multicast group and forwards
packets between the DCS-BIOS multicast network and a local serial device.
It can also use `mapping.yaml` to convert GPIO input events into commands.

Run the bridge:

```bash
# multicast group and port are configurable; defaults shown
PYTHONPATH=src python -m dcsbpi.udp_serial_bridge --mcast-group 239.255.250.250 --mcast-port 5005 --serial /dev/ttyUSB0 --mapping src/dcsbpi/mapping.example.yaml
```

Notes

- The default multicast group/port are examples; set them to match your DCS-BIOS setup.
- If `--serial` is omitted the bridge will still relay multicast messages and can be used to inject commands into the multicast network.
- For GPIO mapping, provide a YAML mapping file similar to `src/dcsbpi/mapping.example.yaml`.
