#!/usr/bin/env python3
"""Listen for VOR/ILS frequency messages and show them on the e-paper display.

This adapts the RP2350 TM1637 logic to the Waveshare 2.13" e-paper: it
avoids redrawing unchanged values and formats the numeric frequency.
"""
import argparse
import time
from pathlib import Path

from dcsbpi.epaper_client import EpaperDisplay
from dcsbpi import dcsbios


class VorIlsPresenter:
    def __init__(self):
        self.display = EpaperDisplay()
        self.last_frequency = ""

    def format_frequency(self, raw: str) -> str:
        # raw might include leading spaces; trim
        s = raw.strip()
        # keep as-is if empty
        if not s:
            return ""
        # replicate digits-only extraction and decimal position logic
        digits_only = ""
        decimal_pos = -1
        for i, ch in enumerate(s):
            if ch == '.':
                decimal_pos = i
            elif ch.isdigit():
                digits_only += ch

        # pad/shift similar to firmware: create a left-shifted display value
        # we will render human-friendly frequency with decimal restored
        if decimal_pos != -1:
            # position of decimal within digits_only is decimal_pos minus number of non-digits before it
            # but simpler: reinsert decimal before last two digits if format like XXX.XX
            if len(digits_only) >= 3:
                # assume last two digits are decimals
                int_part = digits_only[:-2]
                dec_part = digits_only[-2:]
                return f"{int_part}.{dec_part}"
        # fallback: return original trimmed
        return s

    def handle_message(self, msg):
        # msg is DcsMessage
        # Accept both the printed label and the firmware buffer name
        if "VOR/ILS Frequency" in msg.name or "F_4E_PLT_VOR_ILS_FREQUENCY" in msg.name:
            val = msg.value.strip()
            formatted = self.format_frequency(val)
            if formatted and formatted != self.last_frequency:
                self.last_frequency = formatted
                text = f"VOR/ILS\n{formatted}"
                self.display.init()
                self.display.show_text(text)


def main():
    p = argparse.ArgumentParser(description="Show VOR/ILS frequency on e-paper")
    p.add_argument("--port", default="/dev/ttyUSB0")
    p.add_argument("--baud", type=int, default=115200)
    args = p.parse_args()

    presenter = VorIlsPresenter()

    # register a handler with the module-level dcsbios instance
    dcsbios.register_handler(r"VOR/ILS Frequency|F_4E_PLT_VOR_ILS_FREQUENCY", presenter.handle_message)

    # simple serial read loop
    try:
        import serial
    except Exception:
        print("pyserial required: pip install pyserial")
        raise

    ser = serial.Serial(args.port, args.baud, timeout=1)
    try:
        while True:
            line = ser.readline()
            if not line:
                time.sleep(0.01)
                continue
            dcsbios.parse_packet(line)
    except KeyboardInterrupt:
        print("Exiting")
    finally:
        ser.close()


if __name__ == '__main__':
    main()
