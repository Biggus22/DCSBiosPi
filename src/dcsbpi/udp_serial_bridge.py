"""UDP <-> Serial bridge with optional GPIO mapping for Pi inputs/outputs.

Behaviors:
- Joins a UDP multicast group and forwards received packets to the serial port.
- Reads serial data and multicasts it to the UDP group.
- Optionally loads a YAML mapping to send commands when GPIO inputs change.

This lets the Pi participate in the DCS-BIOS multicast network while also
exposing local GPIO inputs as command sources and driving local outputs.
"""
from __future__ import annotations

import argparse
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Optional

import yaml
from .dcsb_parser import DcsbiosFramer


class UDPSerialBridge:
    def __init__(self, mcast_group: str, mcast_port: int, serial_port: Optional[str] = None, baud: int = 115200, mapping: Optional[str] = None):
        self.group = mcast_group
        self.port = mcast_port
        self.serial_port = serial_port
        self.baud = baud
        self.mapping_file = Path(mapping) if mapping else None

        self.sock = None
        self.serial = None
        self.running = False
        self.mapping = None

    def _setup_udp(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # bind to all addresses on the port
        sock.bind(("", self.port))
        mreq = struct.pack("4sl", socket.inet_aton(self.group), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        self.sock = sock

    def _setup_serial(self):
        if not self.serial_port:
            return
        try:
            import serial
        except Exception:
            raise RuntimeError("pyserial required for serial support")
        self.serial = serial.Serial(self.serial_port, self.baud, timeout=1)

    def _load_mapping(self):
        if not self.mapping_file:
            return
        if not self.mapping_file.exists():
            raise FileNotFoundError(f"Mapping file not found: {self.mapping_file}")
        with open(self.mapping_file, "r", encoding="utf-8") as f:
            self.mapping = yaml.safe_load(f)

    def _udp_reader(self):
        # framer will assemble complete DCS-BIOS framed packets and call
        # the provided callback which writes to serial.
        def on_packet(packet: bytes, ts: float):
            if self.serial:
                try:
                    self.serial.write(packet)
                except Exception as e:
                    print("Serial write error in framer callback:", e)

        framer = DcsbiosFramer(on_packet)

        while self.running:
            try:
                data, addr = self.sock.recvfrom(2048)
            except Exception as e:
                print("UDP recv error:", e)
                break
            if not data:
                continue
            # feed raw UDP bytes into framer; it emits complete frames
            try:
                framer.feed(data)
            except Exception as e:
                print("Framer feed error:", e)

    def _serial_reader(self):
        while self.running and self.serial:
            try:
                data = self.serial.readline()
            except Exception as e:
                print("Serial read error:", e)
                break
            if not data:
                time.sleep(0.01)
                continue
            print("Serial RX:", data)
            # multicast serial data
            try:
                self.sock.sendto(data, (self.group, self.port))
            except Exception as e:
                print("UDP send error:", e)

    def _setup_gpio_callbacks(self):
        # mapping: inputs → on_press/on_release commands
        if not self.mapping:
            return
        try:
            from gpiozero import Button
        except Exception:
            print("gpiozero not available; skipping GPIO mapping")
            return

        for inp in self.mapping.get("inputs", []):
            pin = int(inp.get("gpio"))
            btn = Button(pin, pull_up=True)
            on_cmd = inp.get("on_press")
            off_cmd = inp.get("on_release")
            if on_cmd:
                btn.when_pressed = lambda c=on_cmd: self.send_command(c)
            if off_cmd:
                btn.when_released = lambda c=off_cmd: self.send_command(c)

    def send_command(self, cmd: str):
        if isinstance(cmd, str):
            b = cmd.encode("utf-8")
        else:
            b = bytes(cmd)
        # prefer serial if available, fallback to UDP
        if self.serial:
            try:
                if not cmd.endswith("\n"):
                    b = b + b"\n"
                self.serial.write(b)
                print("TX serial:", cmd)
                return
            except Exception as e:
                print("Serial TX error:", e)
        try:
            self.sock.sendto(b, (self.group, self.port))
            print("TX udp:", cmd)
        except Exception as e:
            print("UDP TX error:", e)

    def run(self):
        self._setup_udp()
        self._load_mapping()
        self._setup_serial()
        self._setup_gpio_callbacks()

        self.running = True
        threads = []
        t1 = threading.Thread(target=self._udp_reader, daemon=True)
        threads.append(t1)
        t1.start()
        if self.serial:
            t2 = threading.Thread(target=self._serial_reader, daemon=True)
            threads.append(t2)
            t2.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping bridge")
            self.running = False
        finally:
            if self.serial and self.serial.is_open:
                self.serial.close()
            if self.sock:
                self.sock.close()


def main():
    p = argparse.ArgumentParser(description="UDP <-> Serial bridge for DCS-BIOS with optional GPIO mapping")
    p.add_argument("--mcast-group", default="239.255.250.250")
    p.add_argument("--mcast-port", default=5005, type=int)
    p.add_argument("--serial", help="Serial device (e.g. /dev/ttyUSB0)")
    p.add_argument("--baud", default=115200, type=int)
    p.add_argument("--mapping", help="YAML mapping file for GPIO inputs/outputs")
    args = p.parse_args()

    bridge = UDPSerialBridge(args.mcast_group, args.mcast_port, args.serial, args.baud, args.mapping)
    bridge.run()


if __name__ == "__main__":
    main()
