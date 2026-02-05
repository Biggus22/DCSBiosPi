"""CLI entry points for DCSBiosPi

Provides a simple CLI to run the bundled example clients.
"""
import argparse
import sys
from pathlib import Path

def run_epaper(argv):
    from dcsbpi import epaper_client
    epaper_client.main()

def run_gpio(argv):
    from dcsbpi import gpio_client
    gpio_client.main()

def run_serial(argv):
    from dcsbpi import client
    client.main()

def main(argv=None):
    p = argparse.ArgumentParser(prog="dcsbpi")
    p.add_argument("command", choices=["epaper", "gpio", "serial"], help="Which client to run")
    args, rest = p.parse_known_args(argv)
    if args.command == "epaper":
        run_epaper(rest)
    elif args.command == "gpio":
        run_gpio(rest)
    elif args.command == "serial":
        run_serial(rest)

if __name__ == "__main__":
    main()
