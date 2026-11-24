"""A single match and its reversible, validated action history."""

from dataclasses import dataclass
from typing import Optional

from .board import Board, GameError, Stone
from .rules import GoRules, GomokuRules, Outcome, Rules


@dataclass(frozen=True)
class Turn:
    action: str
    side: Stone
    previous_passes: int
    index: Optional[int] = None
    captured: tuple[int, ...] = ()


class Game:
    undo_limit = 3

    def __init__(self, kind: str, size: int):
        choices = {"go": GoRules, "gomoku": GomokuRules}
        if not isinstance(kind, str) or kind not in choices:
            raise GameError("棋种必须是 go（围棋）或 gomoku（五子棋）。")
        self.kind = kind
        self.rules: Rules = choices[kind]()
        self.board = Board(size)
        self.next_side = Stone.BLACK
        self.passes = 0
        self.outcome: Optional[Outcome] = None
        self.undos_used = 0
        self._turns: list[Turn] = []
        self._positions = {bytes(self.board.cells)} if self.rules.tracks_positions else set()
        self._captures = [0, 0, 0]

    def _require_active(self):
        if self.outcome is not None:
            raise GameError("对局已结束，可开始新局或悔棋。")

    def play(self, coordinate: str) -> str:
        self._require_active()
        index = self.board.index(coordinate)
        side = self.next_side
        if self.board.cells[index] != Stone.EMPTY:
            raise GameError("该落点已有棋子。")
        captured = self.rules.captures(self.board, index, side, self._positions)
        self.board.cells[index] = side
        for removed in captured:
            self.board.cells[removed] = Stone.EMPTY
        if self.rules.tracks_positions:
            self._positions.add(bytes(self.board.cells))
        self._captures[side] += len(captured)
        self._turns.append(Turn("play", side, self.passes, index, captured))
        self.passes = 0
        self.next_side = side.opponent
        self.outcome = self.rules.after_play(self.board, index, side, self._positions)
        message = f"{side.label}落子 {self.board.coordinate(index)}"
        if captured:
            message += f"，提子 {len(captured)} 枚"
        return self._describe(message + "。")

    def pass_turn(self) -> str:
        self._require_active()
        if not self.rules.allows_pass:
            raise GameError("只有围棋支持虚着。")
        side = self.next_side
        self._turns.append(Turn("pass", side, self.passes))
        self.passes += 1
        self.next_side = side.opponent
        if self.passes == 2:
            self.outcome = self.rules.after_passes(self.board)
        return self._describe(f"{side.label}虚着。")

    def resign(self) -> str:
        self._require_active()
        side = self.next_side
        self._turns.append(Turn("resign", side, self.passes))
        self.outcome = Outcome(side.opponent, f"{side.label}认负")
        return self.outcome.message

    def undo(self) -> str:
        if not self._turns:
            raise GameError("无操作可悔。")
        if self.undos_used >= self.undo_limit:
            raise GameError("本局悔棋次数已用完。")
        turn = self._turns.pop()
        if turn.index is not None:
            if self.rules.tracks_positions:
                self._positions.remove(bytes(self.board.cells))
            self.board.cells[turn.index] = Stone.EMPTY
            for captured in turn.captured:
                self.board.cells[captured] = turn.side.opponent
            self._captures[turn.side] -= len(turn.captured)
        self.next_side = turn.side
        self.passes = turn.previous_passes
        self.outcome = None
        self.undos_used += 1
        return f"已悔棋一步，轮到{turn.side.label}。"

    def _describe(self, message: str) -> str:
        if self.outcome is None:
            return message
        return f"{message}{self.outcome.message}"

    def action_log(self) -> list[list[str]]:
        return [
            [turn.action] if turn.index is None
            else [turn.action, self.board.coordinate(turn.index)]
            for turn in self._turns
        ]

    def view(self) -> dict:
        last = next((turn.index for turn in reversed(self._turns) if turn.index is not None), None)
        return {
            "kind": self.kind,
            "label": self.rules.label,
            "size": self.board.size,
            "cells": list(self.board.cells),
            "side": self.next_side,
            "outcome": self.outcome.message if self.outcome is not None else None,
            "turns": len(self._turns),
            "undo_left": self.undo_limit - self.undos_used,
            "passes": self.passes,
            "captures": self._captures[1:],
            "last": last,
            "allows_pass": self.rules.allows_pass,
        }
