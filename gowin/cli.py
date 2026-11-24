"""Terminal command parsing and independently composable display panes."""

from pathlib import Path
from typing import Callable, Optional

from .board import GameError, Stone
from .platform import Platform
from .storage import Archive


class ConsoleView:
    def __init__(self, panels: tuple[Callable, ...]):
        self._panels = panels

    def render(self, state: Optional[dict], show_help: bool) -> str:
        return "\n".join(text for panel in self._panels if (text := panel(state, show_help)))


class ConsoleViewBuilder:
    def __init__(self):
        self._panels: list[Callable] = []

    def add(self, panel: Callable) -> "ConsoleViewBuilder":
        self._panels.append(panel)
        return self

    def build(self) -> ConsoleView:
        return ConsoleView(tuple(self._panels))


def board_panel(state, _):
    if state is None:
        return ""
    size = state["size"]
    symbols = {Stone.EMPTY: "·", Stone.BLACK: "X", Stone.WHITE: "O"}
    lines = ["   " + " ".join(chr(ord("A") + i) for i in range(size))]
    for row in range(size):
        line = state["cells"][row * size:(row + 1) * size]
        lines.append(f"{row + 1:2} " + " ".join(symbols[cell] for cell in line))
    return "\n".join(lines)


def status_panel(state, _):
    if state is None:
        return "当前没有对局。"
    result = state["outcome"] or f"轮到 {Stone(state['side']).label}。"
    status = (f"{state['label']} {state['size']}×{state['size']} | X 黑方 · O 白方 | "
              f"第 {state['turns']} 步 | 剩余悔棋 {state['undo_left']} 次\n{result}")
    if state["allows_pass"]:
        black, white = state["captures"]
        status += f" 提子 黑 {black}／白 {white} | 连续虚着 {state['passes']} 次"
    return status


def help_panel(_, show_help):
    if not show_help:
        return ""
    return (
        "操作：new <go|gomoku> <8–19>  restart  play <坐标>  pass  undo  resign\n"
        "      save <文件>  load <文件>  hints off/on  help  quit"
    )


class Console:
    def __init__(self, platform: Platform, view: ConsoleView):
        self.platform = platform
        self.view = view
        self.show_help = True

    def run(self):
        print("Go-win 棋类对战平台")
        print(self.view.render(self.platform.view(), self.show_help))
        while True:
            try:
                line = input("go-win> ")
            except (EOFError, KeyboardInterrupt):
                print("\n已退出。")
                return
            try:
                message = self.execute(line)
            except GameError as error:
                print(f"错误：{error}")
                continue
            if message is None:
                print("已退出。")
                return
            print(message)
            print(self.view.render(self.platform.view(), self.show_help))

    def execute(self, line: str) -> Optional[str]:
        parts = line.split(maxsplit=1)
        command = parts[0].lower() if parts else ""
        value = parts[1].strip() if len(parts) == 2 else ""
        args = value.split()
        if command == "new" and len(args) == 2:
            try:
                size = int(args[1])
            except ValueError as error:
                raise GameError("棋盘边长必须是 8 至 19 的整数。") from error
            return self.platform.start(args[0].lower(), size)
        if command == "play" and len(args) == 1:
            return self.platform.act(command, args[0])
        if command in ("save", "load") and value:
            if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
                value = value[1:-1]
            if not value:
                raise GameError("请指定文件路径。")
            path = Path(value)
            if command == "load":
                return self.platform.restore(Archive.read(path))
            Archive.write(path, self.platform.archive())
            return f"已保存到 {path}。"
        if command == "hints" and args in (["on"], ["off"]):
            self.show_help = args == ["on"]
            return "已显示操作提示。" if self.show_help else "已隐藏操作提示。"
        if not args:
            if command == "quit":
                return None
            if command == "help":
                self.show_help = True
                return "已显示操作提示。"
            if command == "restart":
                return self.platform.restart()
            if command in ("pass", "undo", "resign"):
                return self.platform.act(command)
        raise GameError("未知命令或参数不正确。输入 help 查看操作提示。")


def run_cli():
    view = ConsoleViewBuilder().add(board_panel).add(status_panel).add(help_panel).build()
    Console(Platform(), view).run()
