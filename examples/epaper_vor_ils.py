#!/usr/bin/env python3
"""Display F-4E VOR/ILS frequency on Waveshare 2.13"""
import argparse
import socket
import struct
import re
import threading
import time
from PIL import Image, ImageDraw, ImageFont

# Try to import Waveshare epd driver; fall back to image file output
try:
    from waveshare_epd import epd2in13
    EPAPER_AVAILABLE = True
except Exception:
    epd2in13 = None
    EPAPER_AVAILABLE = False

# Default resolution for Waveshare 2.13 inch
EPD_WIDTH = 250
EPD_HEIGHT = 122

FREQ_RE = re.compile(r"(\b\d{2,3}\.\d{2}\b)")


def create_image(freq_text: str, label: str = "F-4E VOR/ILS") -> Image.Image:
    img = Image.new('1', (EPD_WIDTH, EPD_HEIGHT), 255)  # 1-bit white
    draw = ImageDraw.Draw(img)
    try:
        font_large = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 36)
        font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Draw label
    draw.text((6, 6), label, font=font_small, fill=0)

    # Center frequency
    w, h = draw.textsize(freq_text, font=font_large)
    x = max(0, (EPD_WIDTH - w) // 2)
    y = (EPD_HEIGHT - h) // 2
    draw.text((x, y), freq_text, font=font_large, fill=0)
    return img


class McastListener(threading.Thread):
    def __init__(self, mcast_group: str, mcast_port: int, update_cb):
        super().__init__(daemon=True)
        self.group = mcast_group
        self.port = mcast_port
        self.cb = update_cb
        self.sock = None
        self.running = False

    def run(self):
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("", self.port))
        except Exception as e:
            print("Failed to bind port:", e)
            return
        try:
            mreq = struct.pack('4s4s', socket.inet_aton(self.group), socket.inet_aton('0.0.0.0'))
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception as e:
            print("Failed to join multicast group:", e)
            return

        while self.running:
            try:
                data, addr = self.sock.recvfrom(8192)
                # try to decode text and search for a frequency
                try:
                    s = data.decode('utf-8', errors='ignore')
                except Exception:
                    s = ''
                m = FREQ_RE.search(s)
                if m:
                    freq = m.group(1)
                    self.cb(freq)
            except Exception:
                time.sleep(0.1)

    def stop(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mcast-group', default='239.255.50.10')
    p.add_argument('--mcast-port', type=int, default=5010)
    p.add_argument('--label', default='F-4E VOR/ILS')
    p.add_argument('--outfile', default=None, help='If epaper hardware not available, write PNG here')
    args = p.parse_args()

    current = '---.---'

    def update(freq):
        nonlocal current
        current = freq
        print('Frequency update:', freq)
        img = create_image(current, label=args.label)
        if EPAPER_AVAILABLE and epd2in13 is not None:
            try:
                epd = epd2in13.EPD()
                epd.init(epd.FULL_UPDATE)
                epd.Clear(0xFF)
                epd.display(epd.getbuffer(img))
                epd.sleep()
            except Exception as e:
                print('Epaper display failed:', e)
                if args.outfile:
                    img.save(args.outfile)
        else:
            if args.outfile:
                img.save(args.outfile)
            else:
                # fallback: save to /tmp/epaper_vor_ils.png
                img.save('/tmp/epaper_vor_ils.png')

    listener = McastListener(args.mcast_group, args.mcast_port, update)
    listener.start()

    # initial draw
    update(current)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listener.stop()


if __name__ == '__main__':
    main()
