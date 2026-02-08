"""Minimal UDP <-> Serial bridge.

This intentionally keeps framing/simple forwarding behavior so you can
add DCS-BIOS framing/parsing later.
"""
import socket
import struct
import threading
import time
import sys

try:
    import serial
except Exception:
    serial = None


class UdpSerialBridge:
    def __init__(self, mcast_group, mcast_port, serial_ports=None, dcs_pc_ip=None, udp_dest_port=None):
        self.mcast_group = mcast_group
        self.mcast_port = mcast_port
        self.dcs_pc_ip = dcs_pc_ip
        self.udp_dest_port = udp_dest_port
        self.serial_ports = serial_ports or []
        self.udp_sock = None
        self.running = False
        self.active_serials = []

    def start(self):
        self.running = True
        self._setup_udp()
        t = threading.Thread(target=self._udp_loop, daemon=True)
        t.start()
        for device in self.serial_ports:
            if device.get("enabled", False):
                thr = threading.Thread(target=self._serial_read_loop, args=(device,), daemon=True)
                thr.start()

    def _setup_udp(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", self.mcast_port))
        mreq = struct.pack("4s4s", socket.inet_aton(self.mcast_group), socket.inet_aton('0.0.0.0'))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        self.udp_sock = s

    def _open_serial(self, device):
        if serial is None:
            return None
        try:
            s = serial.Serial(device['port'], device.get('baudrate', 250000), timeout=0.1)
            return s
        except Exception:
            return None

    def _udp_loop(self):
        while self.running:
            try:
                data, addr = self.udp_sock.recvfrom(4096)
                # If configured, only accept from DCS PC ip
                if self.dcs_pc_ip and addr[0] != self.dcs_pc_ip:
                    continue
                # write to all active serials
                for entry in list(self.active_serials):
                    ser = entry.get('ser')
                    try:
                        if ser and ser.is_open:
                            ser.write(data)
                    except Exception:
                        try:
                            ser.close()
                        except Exception:
                            pass
                        self.active_serials.remove(entry)
                time.sleep(0)
            except Exception:
                time.sleep(0.1)

    def _serial_read_loop(self, device):
        name = device.get('name')
        ser = self._open_serial(device)
        if ser:
            self.active_serials.append({'name': name, 'ser': ser})
        while self.running:
            try:
                if ser and ser.is_open and ser.in_waiting:
                    data = ser.read(ser.in_waiting)
                    if data and self.udp_dest_port and self.dcs_pc_ip:
                        self.udp_sock.sendto(data, (self.dcs_pc_ip, self.udp_dest_port))
                else:
                    time.sleep(0.01)
            except Exception:
                time.sleep(1)

    def stop(self):
        self.running = False
        try:
            if self.udp_sock:
                self.udp_sock.close()
        except Exception:
            pass
        for entry in self.active_serials:
            try:
                entry['ser'].close()
            except Exception:
                pass
