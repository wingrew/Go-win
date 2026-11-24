import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from gowin.board import Board, GameError, Stone
from gowin.game import Game
from gowin.platform import Platform
from gowin.rules import GoRules
from gowin.storage import Archive


def play(game, *coordinates):
    for coordinate in coordinates:
        game.play(coordinate)


class GomokuTests(unittest.TestCase):
    def test_five_in_all_directions(self):
        for line in ("A1 B1 C1 D1 E1", "A1 A2 A3 A4 A5",
                     "A1 B2 C3 D4 E5", "E1 D2 C3 B4 A5"):
            with self.subTest(line=line):
                game = Game("gomoku", 8)
                for black, white in zip(line.split(), ("A8", "B8", "C8", "D8", None)):
                    game.play(black)
                    if white:
                        game.play(white)
                self.assertEqual(game.outcome.winner, Stone.BLACK)
                self.assertIn("连成五子", game.outcome.message)
                with self.assertRaisesRegex(GameError, "已结束"):
                    game.play("H8")
                game.undo()
                self.assertIsNone(game.outcome)
                self.assertEqual(game.next_side, Stone.BLACK)

    def test_freestyle_overline(self):
        game = Game("gomoku", 8)
        play(game, "A1", "A8", "B1", "B8", "C1", "D8", "E1", "F8", "F1", "H8", "D1")
        self.assertEqual(game.outcome.winner, Stone.BLACK)

    def test_full_board_draw(self):
        game = Game("gomoku", 8)
        positions = {0: [], 1: []}
        for row in range(8):
            for col in range(8):
                positions[(row + col // 2) % 2].append(game.board.coordinate(row * 8 + col))
        for black, white in zip(positions[0], positions[1]):
            play(game, black, white)
        self.assertEqual(game.view()["turns"], 64)
        self.assertEqual(game.outcome.message, "棋盘已满，平局。")


class GoTests(unittest.TestCase):
    def test_capture_suicide_and_undo(self):
        game = Game("go", 8)
        play(game, "B1", "A1")
        self.assertIn("提子 1 枚", game.play("A2"))
        before = game.view()
        self.assertEqual(before["cells"][0], Stone.EMPTY)
        self.assertEqual(before["captures"], [1, 0])
        with self.assertRaisesRegex(GameError, "禁入点"):
            game.play("A1")
        self.assertEqual(game.view(), before)
        game.undo()
        self.assertEqual(game.view()["cells"][0], Stone.WHITE)
        self.assertEqual(game.view()["captures"], [0, 0])
        self.assertEqual(game.next_side, Stone.BLACK)
        self.assertIn("提子 1 枚", game.play("A2"))

    def test_multi_stone_capture(self):
        game = Game("go", 8)
        play(game, "B1", "A1", "B2", "A2")
        self.assertIn("提子 2 枚", game.play("A3"))
        self.assertEqual(game.view()["captures"], [2, 0])

    def test_ko_survives_save_and_pass(self):
        game = Game("go", 8)
        play(game, "A2", "C1", "B1", "D2", "B3", "C3", "H8", "B2", "C2")
        game = Archive.decode(Archive.encode(game))
        before = game.view()
        with self.assertRaisesRegex(GameError, "全局同形"):
            game.play("B2")
        self.assertEqual(game.view(), before)
        game.pass_turn()
        game.undo()
        with self.assertRaisesRegex(GameError, "全局同形"):
            game.play("B2")
        play(game, "H7", "G8", "B2")
        self.assertEqual(game.view()["captures"], [1, 1])

    def test_pass_scoring_and_neutral_regions(self):
        game = Game("go", 8)
        play(game, "B1", "H8", "A2")
        game.pass_turn()
        self.assertEqual(game.passes, 1)
        game.play("F6")
        self.assertEqual(game.passes, 0)
        game.pass_turn()
        result = game.pass_turn()
        self.assertIn("双方连续虚着，白方胜。黑方 4，白方 1 + 7.5 = 8.5", result)
        game.undo()
        self.assertIsNone(game.outcome)
        self.assertEqual(game.passes, 1)
        self.assertEqual(game.pass_turn(), result)

    def test_no_legal_placement_ends_match(self):
        board = Board(8)
        board.cells[:] = bytes([Stone.BLACK] * 64)
        board.cells[0] = Stone.EMPTY
        board.cells[63] = Stone.EMPTY
        black_candidate = bytearray(board.cells)
        black_candidate[0] = Stone.BLACK
        black_other_candidate = bytearray(board.cells)
        black_other_candidate[63] = Stone.BLACK
        positions = {bytes(board.cells), bytes(black_candidate), bytes(black_other_candidate)}
        outcome = GoRules().after_play(board, 1, Stone.BLACK, positions)
        self.assertEqual(outcome.reason, "双方均无合法落点")
        self.assertEqual(outcome.black_area, 64)
        self.assertEqual(board.cells.count(Stone.EMPTY), 2)


class PlatformTests(unittest.TestCase):
    def test_lifecycle_and_errors(self):
        platform = Platform()
        for kind, size in (("go", 7), ("gomoku", 20), ("chess", 8), ("go", "8")):
            with self.assertRaises(GameError):
                platform.start(kind, size)
            self.assertIsNone(platform.view())
        platform.start("gomoku", 19)
        for action in ("undo", "pass"):
            with self.assertRaises(GameError):
                platform.act(action)
        for bad in ("T1", "A0", "A20", "AA1", None):
            with self.assertRaises(GameError):
                platform.act("play", bad)
        platform.act("play", "S19")
        with self.assertRaisesRegex(GameError, "已有棋子"):
            platform.act("play", "S19")
        with self.assertRaisesRegex(GameError, "进行中"):
            platform.start("go", 8)
        platform.restart()
        self.assertEqual(platform.view()["turns"], 0)
        self.assertEqual(platform.view()["side"], Stone.BLACK)
        self.assertIn("黑方认负，白方胜", platform.act("resign"))
        platform.start("go", 8)
        self.assertEqual(platform.view()["kind"], "go")

    def test_undo_budget_persists_and_invalid_load_is_atomic(self):
        platform = Platform()
        platform.start("go", 8)
        for _ in range(3):
            platform.act("play", "A1")
            platform.act("undo")
        platform.act("play", "A1")
        archived = platform.archive()
        before = platform.view()
        for payload in (
            b"not JSON",
            b"[" * 2000,
            b'{"version":2,"game":"go","size":8,"undos_used":0,"moves":[]}',
            b'{"version":1,"game":"go","size":8,"undos_used":0,"moves":[["play","A1"],["play","A1"]]}',
            b'{"version":1,"game":"go","size":8,"undos_used":0,"moves":[["resign"],["pass"]]}',
        ):
            with self.assertRaises(GameError):
                platform.restore(payload)
            self.assertEqual(platform.view(), before)
        platform.restart()
        platform.restore(archived)
        self.assertEqual(platform.view(), before)
        with self.assertRaisesRegex(GameError, "已用完"):
            platform.act("undo")

    def test_file_round_trip_and_write_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test save.json"
            game = Game("go", 8)
            play(game, "B1", "A1", "A2")
            game.pass_turn()
            game.resign()
            Archive.write(path, Archive.encode(game))
            loaded = Archive.decode(Archive.read(path))
            self.assertEqual(loaded.view(), game.view())
            loaded.undo()
            self.assertEqual(loaded.passes, 1)
            with self.assertRaisesRegex(GameError, "保存失败"):
                Archive.write(path / "invalid.json", Archive.encode(game))
            with self.assertRaisesRegex(GameError, "读取失败"):
                Archive.read(path / "missing.json")

    def test_console_entry_point(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test save.json"
            commands = ["hints off", "new go 8", "play B1", "play A1", "play A2",
                        f'save "{path}"', "restart", f"load {path}", "hints on",
                        "play A1", "pass", "pass", "nonsense", "quit"]
            result = subprocess.run(
                [sys.executable, "-B", "-m", "gowin"],
                input="\n".join(commands), capture_output=True, text=True, check=True,
                encoding="utf-8",
            )
            for fragment in ("已隐藏操作提示", "已显示操作提示", "提子 1 枚", "已保存到",
                             "已重新开始", "已读取 8×8 围棋", "禁入点", "黑方 64",
                             "未知命令或参数", "已退出"):
                self.assertIn(fragment, result.stdout)
            self.assertEqual(json.loads(path.read_text())["moves"][-1], ["play", "A2"])


if __name__ == "__main__":
    unittest.main()
