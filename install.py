#!/usr/bin/env python3
"""Fennec installer — compatibility entry point for the portable bootstrap.

`python install.py ...` keeps the historical behavior of downloading the selected
repos; an explicit --plan/--fetch-only/--install/--build always wins. Use
`python bootstrap.py --install ...` when dependencies should also be installed
and the shared runtime config written.

    python install.py                                    # interactive menu
    python install.py --features inference,desktop --yes  # fetch sources
    python install.py --all --yes                         # fetch everything
    python install.py --update --yes                      # update installed checkouts
    python install.py --install --features inference,desktop --yes

The engine is Fennec (https://github.com/Liso7150/fennec), the suite's only engine:
a native Rust binary built with `cargo build --release` and launched directly.
The desktop is the native Rust/GPUI `fennec-desktop-gui` window. The core-supervised
PWA/API front door is `fennec-core/server.py`, launched by the installed Python
`fennec-agent serve` on 127.0.0.1:8787; the Rust `fennec-agent` from
fennec-coding-agent is an auxiliary/chat service on 127.0.0.1:8788.

Credits: the engine's base idea is Colibri (https://github.com/JustVugg/colibri);
fine-tuning uses AirLLM (https://github.com/lyogavin/airllm).
"""
import sys

from bootstrap import main

MODES = {"--plan", "--dry-run", "--fetch-only", "--install", "--build", "--help", "-h"}


def run(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not MODES.intersection(argv):
        argv.append("--fetch-only")
    return main(argv)


if __name__ == "__main__":
    sys.exit(run())