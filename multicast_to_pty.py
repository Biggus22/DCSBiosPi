#!/usr/bin/env python3
"""Bridge multicast UDP -> PTY slave

Usage:
  multicast_to_pty.py <MCAST_ADDR> [PORT] [SYMLINK_PATH]

Defaults to port 5010 when PORT is omitted.
Writes received UDP payloads directly to the PTY master so a serial-based
client can open the PTY slave as if it were a serial port.
"""
import os
import sys
import socket
import struct
import time


def main():
    if len(sys.argv) < 2:
        print("Usage: multicast_to_pty.py <MCAST_ADDR> [PORT] [SYMLINK_PATH]")
        return 2

    group = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) >= 3 else 5010
    symlink = sys.argv[3] if len(sys.argv) >= 4 else None

    master_fd, slave_fd = os.openpty()
    slave_name = os.ttyname(slave_fd)
    output_path = slave_name
    if symlink:
        try:
            if os.path.exists(symlink):
                os.remove(symlink)
            os.symlink(slave_name, symlink)
            output_path = symlink
        except OSError:
            print("Warning: could not create symlink; using actual slave:", slave_name)

    # Create UDP socket and join multicast group
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("", port))
    except Exception as e:
        print("Failed to bind port", port, e)
        return 3

    try:
        mreq = struct.pack('4s4s', socket.inet_aton(group), socket.inet_aton('0.0.0.0'))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    except Exception as e:
        print("Failed to join multicast group", group, e)
        s.close()
        return 4

    print(f"Listening multicast {group}:{port} -> {output_path}")

    # Ensure the PTY slave is in raw 8N1 mode so bytes are passed through
    # without terminal translations (parity, newline conversion, flow control).
    try:
        import termios
        attrs = termios.tcgetattr(slave_fd)
        iflag, oflag, cflag, lflag, ispeed, ospeed, cc = attrs

        # raw input: disable canonical mode, echo, signals
        lflag &= ~(termios.ICANON | termios.ECHO | termios.ECHOE | termios.ECHOK | termios.ISIG | termios.IEXTEN)
        # raw input flags: disable IXON/IXOFF and CR/NL translations
        iflag &= ~(termios.IXON | termios.IXOFF | termios.IXANY | termios.INLCR | termios.ICRNL | termios.IGNCR)
        # raw output: disable post-processing
        oflag &= ~termios.OPOST
        # set 8N1: clear size and parity, set CS8
        cflag &= ~(termios.CSIZE | termios.PARENB | termios.PARODD)
        cflag |= termios.CS8

        # control chars: return as soon as at least 1 byte is available
        cc[termios.VMIN] = 1
        cc[termios.VTIME] = 0

        new_attrs = [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
        termios.tcsetattr(slave_fd, termios.TCSANOW, new_attrs)
    except Exception:
        # If termios is unavailable or setting fails, continue; user can set
        # the slave manually with `stty -F /path raw -echo cs8`.
        pass

    try:
        while True:
            data, addr = s.recvfrom(8192)
            if not data:
                continue
            try:
                os.write(master_fd, data)
            except BrokenPipeError:
                # no reader attached; sleep briefly
                time.sleep(0.1)
            except Exception as e:
                print("Write to PTY failed:", e)
                time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            s.close()
        except Exception:
            pass
        try:
            os.close(master_fd)
        except Exception:
            pass
        try:
            os.close(slave_fd)
        except Exception:
            pass

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
