"""Rule strategies. Trials on the live board always restore it before returning."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Container, Optional

from .board import Board, GameError, Stone


@dataclass(frozen=True)
class Outcome:
    winner: Optional[Stone]
    reason: str
    black_area: Optional[int] = None
    white_area: Optional[int] = None
    komi: float = 0.0

    @property
    def message(self) -> str:
        result = "平局" if self.winner is None else f"{self.winner.label}胜"
        if self.black_area is not None:
            white_score = self.white_area + self.komi
            return (f"{self.reason}，{result}。黑方 {self.black_area}，"
                    f"白方 {self.white_area} + {self.komi:g} = {white_score:g}。")
        return f"{self.reason}，{result}。"


class Rules(ABC):
    label: str
    allows_pass = False
    tracks_positions = False

    @abstractmethod
    def captures(self, board: Board, index: int, side: Stone,
                 positions: Container[bytes]) -> tuple[int, ...]:
        """Validate an unoccupied point and return the stones to remove."""

    @abstractmethod
    def after_play(self, board: Board, index: int, side: Stone,
                   positions: Container[bytes]) -> Optional[Outcome]:
        """Evaluate a committed move."""

    def after_passes(self, board: Board) -> Outcome:
        raise GameError("本棋种不支持虚着。")


class GomokuRules(Rules):
    label = "五子棋"

    def captures(self, board, index, side, positions):
        return ()

    def after_play(self, board, index, side, positions):
        row, col = divmod(index, board.size)
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            count = 1
            for sign in (-1, 1):
                y, x = row + sign * dy, col + sign * dx
                while 0 <= y < board.size and 0 <= x < board.size:
                    if board.cells[y * board.size + x] != side:
                        break
                    count += 1
                    y, x = y + sign * dy, x + sign * dx
            if count >= 5:
                return Outcome(side, "连成五子")
        if Stone.EMPTY not in board.cells:
            return Outcome(None, "棋盘已满")
        return None


class GoRules(Rules):
    label = "围棋"
    allows_pass = True
    tracks_positions = True
    komi = 7.5

    @staticmethod
    def _region(board: Board, start: int) -> tuple[set[int], set[int]]:
        """Collect the same-color component and its adjacent colors."""
        color = board.cells[start]
        members = {start}
        boundary = set()
        pending = [start]
        while pending:
            for neighbor in board.neighbors[pending.pop()]:
                neighbor_color = board.cells[neighbor]
                if neighbor_color != color:
                    boundary.add(neighbor_color)
                elif neighbor not in members:
                    members.add(neighbor)
                    pending.append(neighbor)
        return members, boundary

    def captures(self, board, index, side, positions):
        cells = board.cells
        enemy = side.opponent
        removed = []
        checked = set()
        cells[index] = side
        try:
            for neighbor in board.neighbors[index]:
                if cells[neighbor] != enemy or neighbor in checked:
                    continue
                group, boundary = self._region(board, neighbor)
                checked.update(group)
                if Stone.EMPTY not in boundary:
                    removed.extend(group)
            for captured in removed:
                cells[captured] = Stone.EMPTY
            if Stone.EMPTY not in self._region(board, index)[1]:
                raise GameError("禁入点：落子后己方棋块无气。")
            if bytes(cells) in positions:
                raise GameError("全局同形：落子会重现已出现的棋盘。")
            return tuple(removed)
        finally:
            cells[index] = Stone.EMPTY
            for captured in removed:
                cells[captured] = enemy

    def _can_play(self, board: Board, side: Stone, positions: Container[bytes]) -> bool:
        for index, cell in enumerate(board.cells):
            if cell != Stone.EMPTY:
                continue
            try:
                self.captures(board, index, side, positions)
            except GameError:
                continue
            return True
        return False

    def after_play(self, board, index, side, positions):
        if self._can_play(board, side.opponent, positions) or self._can_play(board, side, positions):
            return None
        return self._score(board, "双方均无合法落点")

    def after_passes(self, board):
        return self._score(board, "双方连续虚着")

    def _score(self, board: Board, reason: str) -> Outcome:
        black = board.cells.count(Stone.BLACK)
        white = board.cells.count(Stone.WHITE)
        seen = set()
        for index, cell in enumerate(board.cells):
            if cell != Stone.EMPTY or index in seen:
                continue
            region, boundary = self._region(board, index)
            seen.update(region)
            if boundary == {Stone.BLACK}:
                black += len(region)
            if boundary == {Stone.WHITE}:
                white += len(region)
        winner = Stone.BLACK if black > white + self.komi else Stone.WHITE
        return Outcome(winner, reason, black, white, self.komi)
