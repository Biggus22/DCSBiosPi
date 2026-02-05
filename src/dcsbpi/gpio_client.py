#!/usr/bin/env python3
"""GPIO bridge for DCSBiosPi package.

Same behavior as the top-level script but packaged for import.
"""
import argparse
import threading
import time
from pathlib import Path

import serial
import yaml
from gpiozero import Button, LED


class GPIOBridge:
    def __init__(self, port: str, baud: int, mapping_file: str):
        self.port = port
        self.baud = baud
        self.mapping_file = Path(mapping_file)
        self.serial = None
        self.inputs = []
        self.outputs = []
        self.led_map = {}

        self._load_mapping()

    def _load_mapping(self):
        if not self.mapping_file.exists():
            raise FileNotFoundError(f"Mapping file not found: {self.mapping_file}")
        with open(self.mapping_file, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        for inp in cfg.get("inputs", []):
            pin = int(inp["gpio"])
            btn = Button(pin, pull_up=True)
            on_cmd = inp.get("on_press")
            off_cmd = inp.get("on_release")

            if on_cmd:
                btn.when_pressed = lambda c=on_cmd: self._send_cmd(c)
            if off_cmd:
                btn.when_released = lambda c=off_cmd: self._send_cmd(c)

            self.inputs.append({"name": inp.get("name"), "button": btn})

        for out in cfg.get("outputs", []):
            pin = int(out["gpio"])
            led = LED(pin)
            self.led_map[out.get("match")] = {"led": led, "active_on": bool(out.get("active_on", True))}
            self.outputs.append({"name": out.get("name"), "led": led, "match": out.get("match")})

    def _send_cmd(self, cmd: str):
        if not self.serial:
            print("Serial not connected")
            return
        if not cmd.endswith("\n"):
            cmd = cmd + "\n"
        try:
            self.serial.write(cmd.encode("utf-8"))
            print(f"TX: {cmd.strip()}")
        except Exception as e:
            print("Serial write error:", e)

    def _serial_reader(self):
        while True:
            try:
                line = self.serial.readline()
            except Exception as e:
                print("Serial read error:", e)
                break
            if not line:
                time.sleep(0.01)
                continue
            try:
                text = line.decode("utf-8", errors="ignore").strip()
            except Exception:
                continue
            if not text:
                continue
            print("RX:", text)

            for match, info in self.led_map.items():
                if match in text:
                    if info["active_on"]:
                        info["led"].on()
                    else:
                        info["led"].off()
                else:
                    if info["active_on"]:
                        info["led"].off()

    def run(self):
        print(f"Opening serial {self.port} @ {self.baud}")
        self.serial = serial.Serial(self.port, self.baud, timeout=1)
        t = threading.Thread(target=self._serial_reader, daemon=True)
        t.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping GPIO bridge")
        finally:
            if self.serial and self.serial.is_open:
                self.serial.close()
            for out in self.outputs:
                out["led"].off()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="/dev/ttyUSB0")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--mapping", default="mapping.yaml")
    args = p.parse_args()

    bridge = GPIOBridge(args.port, args.baud, args.mapping)
    bridge.run()


if __name__ == "__main__":
    main()
