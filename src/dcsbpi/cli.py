"""CLI for minimal dcsbpi bridge."""
import argparse
import sys
from .udp_serial_bridge import UdpSerialBridge


def main(argv=None):
    p = argparse.ArgumentParser(prog="dcsbpi")
    p.add_argument("--mcast-group", default="239.255.50.10")
    p.add_argument("--mcast-port", type=int, default=5010)
    p.add_argument("--dcs-pc-ip", default=None)
    p.add_argument("--udp-dest-port", type=int, default=None)
    p.add_argument("--serial", action='append', help="Serial devices in format name:port:baud (repeat)")
    args = p.parse_args(argv)

    serial_devices = []
    if args.serial:
        for s in args.serial:
            try:
                name, port, baud = s.split(":")
                serial_devices.append({"name": name, "port": port, "baudrate": int(baud), "enabled": True})
            except Exception:
                print("Invalid --serial value:", s)
                sys.exit(2)

    bridge = UdpSerialBridge(args.mcast_group, args.mcast_port, serial_ports=serial_devices, dcs_pc_ip=args.dcs_pc_ip, udp_dest_port=args.udp_dest_port)
    bridge.start()
    print(f"Started bridge {args.mcast_group}:{args.mcast_port}")
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
        bridge.stop()


if __name__ == '__main__':
    raise SystemExit(main())
