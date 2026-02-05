"""Minimal DCS-BIOS helper for parsing messages, formatting commands,
and scheduling periodic requests on the Pi side.

This module is intentionally conservative: it provides a clear API for
clients to register handlers, parse incoming serial/UDP packets, and
schedule periodic messages. It can be expanded to match the exact
binary/text framing used by your firmware.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Pattern


@dataclass
class DcsMessage:
    name: str
    value: str
    raw: str
    timestamp: float


class DcsBios:
    """Parser, handler registry, and simple scheduler for DCS-BIOS messages.

    Usage:
      d = DcsBios()
      d.register_handler(r"VOR1|ILS1", lambda msg: print(msg))
      d.parse_packet(b"VOR1_FREQ:110.75\n")
"""

    def __init__(self):
        self.handlers: List[tuple[Pattern[str], Callable[[DcsMessage], None]]] = []
        self.last_messages: Dict[str, DcsMessage] = {}
        self._scheduler_threads: List[threading.Thread] = []
        self._scheduler_stop = threading.Event()

    def register_handler(self, pattern: str, callback: Callable[[DcsMessage], None]):
        """Register a handler called when message name matches the regex pattern."""
        pat = re.compile(pattern)
        self.handlers.append((pat, callback))

    def unregister_handler(self, callback: Callable[[DcsMessage], None]):
        self.handlers = [(p, cb) for (p, cb) in self.handlers if cb != callback]

    def parse_packet(self, data: bytes) -> List[DcsMessage]:
        """Parse incoming bytes (may contain multiple lines) into DcsMessage objects.

        The default parser treats each newline-terminated line as a message and
        attempts to split on the first ':' to obtain a `name` and `value`.
        """
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            text = str(data)
        messages: List[DcsMessage] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            name = line
            value = ""
            if ":" in line:
                parts = line.split(":", 1)
                name = parts[0]
                value = parts[1]
            msg = DcsMessage(name=name, value=value, raw=line, timestamp=time.time())
            self.last_messages[name] = msg
            messages.append(msg)
            # dispatch
            for (pat, cb) in self.handlers:
                if pat.search(name):
                    try:
                        cb(msg)
                    except Exception:
                        # handler errors must not break parsing
                        pass
        return messages

    def format_command(self, cmd: str) -> bytes:
        """Format an outgoing DCS-BIOS command.

        Many DCS-BIOS setups use simple newline-terminated ASCII commands (for
        example `K:IDENT:VALUE`). This helper ensures encoding and newline.
        """
        if not cmd.endswith("\n"):
            cmd = cmd + "\n"
        return cmd.encode("utf-8")

    def schedule_periodic(self, command: str, interval: float, send_func: Callable[[bytes], None]):
        """Schedule `command` to be sent every `interval` seconds via `send_func`.

        Returns a function that, when called, cancels the scheduled task.
        """
        stop_event = threading.Event()

        def worker():
            while not stop_event.is_set():
                try:
                    send_func(self.format_command(command))
                except Exception:
                    pass
                stop_event.wait(interval)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self._scheduler_threads.append(t)

        def cancel():
            stop_event.set()

        return cancel

    def stop_all_schedulers(self):
        self._scheduler_stop.set()


# convenience module-level instance
_default = DcsBios()

def register_handler(pattern: str, callback: Callable[[DcsMessage], None]):
    return _default.register_handler(pattern, callback)

def parse_packet(data: bytes) -> List[DcsMessage]:
    return _default.parse_packet(data)

def format_command(cmd: str) -> bytes:
    return _default.format_command(cmd)

def schedule_periodic(command: str, interval: float, send_func: Callable[[bytes], None]):
    return _default.schedule_periodic(command, interval, send_func)
