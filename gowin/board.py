"""Board geometry and public coordinates, shared by both games."""

import re
from enum import IntEnum


class Stone(IntEnum):
    EMPTY = 0
    BLACK = 1
    WHITE = 2

    @property
    def label(self) -> str:
        return ("空", "黑方", "白方")[self]

    @property
    def opponent(self) -> "Stone":
        return Stone(3 - self)


class GameError(ValueError):
    """An action the player can correct."""


class Board:
    def __init__(self, size: int):
        if type(size) is not int or not 8 <= size <= 19:
            raise GameError("棋盘边长必须是 8 至 19 的整数。")
        self.size = size
        self.cells = bytearray(size * size)
        self.neighbors = tuple(self._neighbors_at(i) for i in range(len(self.cells)))

    def _neighbors_at(self, index: int) -> tuple[int, ...]:
        row, col = divmod(index, self.size)
        return tuple(
            r * self.size + c
            for r, c in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1))
            if 0 <= r < self.size and 0 <= c < self.size
        )

    def index(self, coordinate: str) -> int:
        if not isinstance(coordinate, str):
            raise GameError("请使用 A1 形式的交叉点坐标。")
        match = re.fullmatch(r"([A-Za-z])([1-9][0-9]?)", coordinate)
        if not match:
            raise GameError("请使用 A1 形式的交叉点坐标。")
        col = ord(match[1].upper()) - ord("A")
        row = int(match[2]) - 1
        if not (0 <= row < self.size and 0 <= col < self.size):
            raise GameError("落点超出棋盘。")
        return row * self.size + col

    def coordinate(self, index: int) -> str:
        row, col = divmod(index, self.size)
        return f"{chr(ord('A') + col)}{row + 1}"
