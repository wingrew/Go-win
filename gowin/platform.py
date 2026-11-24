"""Facade used by the terminal and browser clients."""

from typing import Optional

from .board import GameError
from .game import Game
from .storage import Archive


class Platform:
    def __init__(self):
        self._game: Optional[Game] = None

    def _require_game(self) -> Game:
        if self._game is None:
            raise GameError("请先开始游戏或读取存档。")
        return self._game

    def start(self, kind: str, size: int) -> str:
        if self._game is not None and self._game.outcome is None:
            raise GameError("已有进行中的对局。请重新开始、认负或先完成当前对局。")
        self._game = Game(kind, size)
        return f"已开始 {size}×{size} {self._game.rules.label}，黑方先行。"

    def restart(self) -> str:
        game = self._require_game()
        if game.outcome is not None:
            raise GameError("对局已结束，请开始新局。")
        self._game = Game(game.kind, game.board.size)
        return f"已重新开始{game.rules.label}，黑方先行。"

    def act(self, action: str, coordinate: Optional[str] = None) -> str:
        if not isinstance(action, str) or action not in ("play", "pass", "resign", "undo"):
            raise GameError("未知的对局操作。")
        game = self._require_game()
        if action == "play":
            return game.play(coordinate)
        if coordinate is not None:
            raise GameError("该操作无需坐标。")
        return {"pass": game.pass_turn, "resign": game.resign, "undo": game.undo}[action]()

    def archive(self) -> bytes:
        return Archive.encode(self._require_game())

    def restore(self, payload: bytes) -> str:
        self._game = Archive.decode(payload)
        return f"已读取 {self._game.board.size}×{self._game.board.size} {self._game.rules.label}存档。"

    def view(self) -> Optional[dict]:
        return None if self._game is None else self._game.view()
