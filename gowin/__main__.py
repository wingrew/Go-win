"""Run in the terminal by default, or launch the local graphical client."""

import argparse


def main():
    parser = argparse.ArgumentParser(description="Go-win 围棋与五子棋双人对战")
    parser.add_argument("--gui", action="store_true", help="打开本机浏览器图形界面")
    parser.add_argument("--port", type=int, default=0, help="图形界面端口，0 表示自动分配")
    parser.add_argument("--no-browser", action="store_true", help="仅启动图形界面服务")
    args = parser.parse_args()
    if args.gui:
        from .web import run_gui
        if not 0 <= args.port <= 65535:
            parser.error("端口必须介于 0 与 65535。")
        try:
            run_gui(args.port, not args.no_browser)
        except OSError as error:
            parser.exit(1, f"图形界面启动失败：{error}\n")
    else:
        from .cli import run_cli
        run_cli()


if __name__ == "__main__":
    main()
