#!/usr/bin/env python3
"""E-paper client packaged into the dcsbpi package.
"""
import argparse
import re
import threading
import time
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    print("Pillow is required: pip install pillow")
    raise

import serial


def find_epd_module():
    candidates = [
        "epd2in13", "waveshare_epd.epd2in13", "waveshare_epd.epd2in13_V2", "epd2in13_V2"
    ]
    for name in candidates:
        try:
            mod = __import__(name)
            return mod
        except Exception:
            continue
    return None


class EpaperDisplay:
    def __init__(self):
        self.epd = find_epd_module()
        self.initialized = False
        self.width = 250
        self.height = 122
        self.font = None
        try:
            self.font = ImageFont.load_default()
        except Exception:
            self.font = None

    def init(self):
        if not self.epd:
            print("No e-paper driver found; falling back to image output and console")
            return
        try:
            EPD = getattr(self.epd, "EPD", None)
            if EPD is None:
                EPD = getattr(self.epd, "EPD2in13", None)
            if EPD is None:
                self.epd.init()
                self.initialized = True
                return
            self.epd_dev = EPD()
            self.epd_dev.init()
            self.epd_dev.Clear(0xFF)
            self.width = getattr(self.epd_dev, 'width', self.width)
            self.height = getattr(self.epd_dev, 'height', self.height)
            self.initialized = True
        except Exception as e:
            print("E-Paper init failed:", e)
            self.epd = None

    def show_text(self, text: str):
        img = Image.new('1', (self.width, self.height), 255)
        draw = ImageDraw.Draw(img)
        font = self.font
        lines = text.split('\n')
        y = 4
        for line in lines:
            w, h = draw.textsize(line, font=font)
            x = max((self.width - w) // 2, 0)
            draw.text((x, y), line, fill=0, font=font)
            y += h + 2

        if self.initialized and self.epd:
            try:
                if hasattr(self.epd_dev, 'display'):
                    buf = self.epd_dev.getbuffer(img)
                    self.epd_dev.display(buf)
                elif hasattr(self.epd, 'display'):
                    self.epd.display(self.epd.getbuffer(img))
                else:
                    if hasattr(self.epd, 'Display'):
                        self.epd.Display(self.epd.getbuffer(img))
                    else:
                        raise RuntimeError('Unknown epd API')
                print("Updated e-paper display")
                return
            except Exception as e:
                print("E-paper display update failed:", e)

        out = Path('/tmp') / 'dcsb_pi_epaper.png'
        img.save(out)
        print(f"Saved preview image to {out} — text:\n{text}")


class EpaperClient:
    def __init__(self, port: str, baud: int, regex: str, label: str = None):
        self.port = port
        self.baud = baud
        self.regex = re.compile(regex)
        self.label = label
        self.serial = None
        self.display = EpaperDisplay()

    def connect(self):
        print(f"Opening serial {self.port} @ {self.baud}")
        self.serial = serial.Serial(self.port, self.baud, timeout=1)
        self.display.init()

    def _read_loop(self):
        while True:
            try:
                lineb = self.serial.readline()
            except Exception as e:
                print("Serial read error:", e)
                break
            if not lineb:
                time.sleep(0.01)
                continue
            try:
                line = lineb.decode('utf-8', errors='ignore').strip()
            except Exception:
                continue
            if not line:
                continue
            m = self.regex.search(line)
            if m:
                val = m.group(1) if m.groups() else m.group(0)
                disp_text = f"{self.label}\n{val}" if self.label else val
                print("Matched:", val)
                self.display.show_text(disp_text)

    def run(self):
        self.connect()
        t = threading.Thread(target=self._read_loop, daemon=True)
        t.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping e-paper client")
        finally:
            if self.serial and self.serial.is_open:
                self.serial.close()


def main():
    p = argparse.ArgumentParser(description='E-paper display for DCS-BIOS values')
    p.add_argument('--port', default='/dev/ttyUSB0')
    p.add_argument('--baud', type=int, default=115200)
    p.add_argument('--regex', default=r'(\d{2,3}\.\d{2})', help='Regex with one group capturing frequency')
    p.add_argument('--label', default='VOR/ILS')
    args = p.parse_args()

    client = EpaperClient(args.port, args.baud, args.regex, args.label)
    client.run()


if __name__ == '__main__':
    main()
