"""DCS-BIOS packet framer for the DCSBiosPi package.

Finds 0x55 0x55 0x55 0x55 headers and emits framed packets via callback.
"""
import time

HEADER = b"\x55\x55\x55\x55"


class DcsbiosFramer:
    def __init__(self, on_packet):
        """on_packet(packet_bytes: bytes, timestamp: float) -> None"""
        self.on_packet = on_packet
        self.buf = bytearray()

    def feed(self, data: bytes):
        if not data:
            return
        self.buf.extend(data)
        while True:
            start = self.buf.find(HEADER)
            if start == -1:
                if len(self.buf) > 3:
                    self.buf = self.buf[-3:]
                break
            if start > 0:
                del self.buf[:start]
                start = 0
            next_h = self.buf.find(HEADER, start + len(HEADER))
            if next_h == -1:
                break
            packet = bytes(self.buf[start:next_h])
            ts = time.time()
            try:
                self.on_packet(packet, ts)
            except Exception as e:
                print("dcsbpi.dcsb_parser: packet callback error:", e)
            del self.buf[:next_h]
