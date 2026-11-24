"""Versioned JSON archives. Loading validates by replaying into a fresh match."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .board import GameError
from .game import Game


class Archive:
    max_bytes = 1024 * 1024
    version = 1

    @classmethod
    def encode(cls, game: Game) -> bytes:
        data = {
            "version": cls.version,
            "game": game.kind,
            "size": game.board.size,
            "undos_used": game.undos_used,
            "moves": game.action_log(),
        }
        payload = (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        if len(payload) > cls.max_bytes:
            raise GameError("局面超出 1 MiB 的存档上限。")
        return payload

    @classmethod
    def decode(cls, payload: bytes) -> Game:
        if len(payload) > cls.max_bytes:
            raise GameError("存档超过 1 MiB。")
        try:
            data = json.loads(payload.decode("utf-8"))
        except (ValueError, RecursionError) as error:
            raise GameError("存档必须是有效的 UTF-8 JSON。") from error
        if not isinstance(data, dict) or data.keys() != {"version", "game", "size", "undos_used", "moves"}:
            raise GameError("存档字段不完整或无法识别。")
        if type(data["version"]) is not int or data["version"] != cls.version:
            raise GameError("不支持该存档版本。")
        game = Game(data["game"], data["size"])
        used, moves = data["undos_used"], data["moves"]
        if type(used) is not int or not 0 <= used <= game.undo_limit or not isinstance(moves, list):
            raise GameError("存档中的悔棋次数或操作记录无效。")
        for number, move in enumerate(moves, 1):
            try:
                if isinstance(move, list) and len(move) == 2 and move[0] == "play":
                    game.play(move[1])
                elif move == ["pass"]:
                    game.pass_turn()
                elif move == ["resign"]:
                    game.resign()
                else:
                    raise GameError("无法识别的操作。")
            except GameError as error:
                raise GameError(f"存档第 {number} 步无效：{error}") from error
        game.undos_used = used
        return game

    @classmethod
    def read(cls, path: Path) -> bytes:
        try:
            with path.open("rb") as source:
                return source.read(cls.max_bytes + 1)
        except (OSError, ValueError) as error:
            raise GameError(f"读取失败：{error}") from error

    @staticmethod
    def write(path: Path, payload: bytes):
        temp = None
        try:
            with NamedTemporaryFile(dir=path.parent, prefix=".gowin-", delete=False) as destination:
                temp = Path(destination.name)
                destination.write(payload)
                destination.flush()
                os.fsync(destination.fileno())
            temp.replace(path)
        except (OSError, ValueError) as error:
            raise GameError(f"保存失败：{error}") from error
        finally:
            if temp is not None:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass
