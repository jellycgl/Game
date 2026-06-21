"""Maniac Music — entry point.

Usage:
    python main.py                 # launch the game
    python main.py --server        # run only the PvP server (headless)
    python main.py --no-demo       # skip generating built-in demo songs

The game opens at the login screen. The first account you register becomes the
administrator. Pick 单机模式 (single-player) or 联机对战 (online battle) from the
main menu.
"""
from __future__ import annotations

import argparse


def run_server() -> None:
    from maniac.config import Settings
    from maniac.net.server import GameServer

    settings = Settings.load()
    GameServer("0.0.0.0", settings.net_port).serve_forever()


def run_game(generate_demo: bool = True) -> None:
    from maniac import charts
    from maniac.config import Settings
    from maniac.engine import App
    from maniac.scenes.login import LoginScene

    if generate_demo:
        charts.generate_demo_songs()

    settings = Settings.load()
    app = App(settings)
    app.run(LoginScene(app))


def main() -> None:
    parser = argparse.ArgumentParser(description="Maniac Music rhythm game")
    parser.add_argument("--server", action="store_true",
                        help="run the PvP relay server only")
    parser.add_argument("--no-demo", action="store_true",
                        help="do not generate built-in demo songs")
    args = parser.parse_args()

    if args.server:
        run_server()
    else:
        run_game(generate_demo=not args.no_demo)


if __name__ == "__main__":
    main()
