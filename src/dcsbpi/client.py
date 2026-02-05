#!/usr/bin/env python3
"""Serial client for DCSBiosPi package.

Loads `dcsbios.py` from an explicit path (`DCSBIOS_PY_PATH` env var) or by
searching parent directories for the firmware repo layout. This keeps the
package flexible whether it's run in-repo or installed separately.
"""
import argparse
import os
import time
from pathlib import Path
import importlib.machinery
import importlib.util


def find_dcsbios_path():
    # 1) explicit env var
    env = os.environ.get("DCSBIOS_PY_PATH")
    if env:
        p = Path(env)
        if p.exists():
            return p

    # 2) search upward from this file for 'Python Scripts/dcsbios.py' or 'dcsbios.py'
    cur = Path(__file__).resolve()
    for _ in range(8):
        candidate = cur / "Python Scripts" / "dcsbios.py"
        if candidate.exists():
            return candidate
        candidate2 = cur / "dcsbios.py"
        if candidate2.exists():
            return candidate2
        if cur.parent == cur:
            break
        cur = cur.parent

    return None


def load_dcsbios_module():
    dcsbios_path = find_dcsbios_path()
    if not dcsbios_path:
        print("dcsbios.py not found (set DCSBIOS_PY_PATH or place dcsbios.py in a parent folder)")
        return None

    loader = importlib.machinery.SourceFileLoader("dcsbios", str(dcsbios_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    print(f"Loaded dcsbios from {dcsbios_path}")
    return module


class SerialClient:
    def __init__(self, port: str, baud: int = 115200):
        self.port = port
        self.baud = baud
        self.ser = None
        self.dcs = load_dcsbios_module()

    def connect(self):
        try:
            import serial
        except Exception:
            print("pyserial is required (pip install pyserial)")
            raise

        print(f"Opening serial port {self.port} @ {self.baud}")
        self.ser = serial.Serial(self.port, self.baud, timeout=1)

    def run(self):
        self.connect()
        try:
            while True:
                data = self.ser.readline()
                if not data:
                    time.sleep(0.01)
                    continue
                print("RX:", data)

                if self.dcs and hasattr(self.dcs, "parse_packet"):
                    try:
                        self.dcs.parse_packet(data)
                    except Exception as e:
                        print("dcsbios parse error:", e)

        except KeyboardInterrupt:
            print("Stopping client")
        finally:
            if self.ser:
                self.ser.close()


def main():
    p = argparse.ArgumentParser(description="DCSBiosPi serial client")
    p.add_argument("--port", default="/dev/ttyUSB0")
    p.add_argument("--baud", type=int, default=115200)
    args = p.parse_args()

    client = SerialClient(args.port, args.baud)
    client.run()


if __name__ == "__main__":
    main()
