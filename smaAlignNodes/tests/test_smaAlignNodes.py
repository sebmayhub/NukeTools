"""Tests for the smaAlignNodes logic using fake nuke / Qt modules.

Run:  python -m unittest discover -s tests
"""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Fakes ---------------------------------------------------------------------

sys.modules.setdefault("nuke", types.ModuleType("nuke"))

_qt = types.ModuleType("PySide2")
_qtcore = types.ModuleType("PySide2.QtCore")
_qtcore.Qt = types.SimpleNamespace(AltModifier=1, ShiftModifier=2)
_qtcore.QObject = object
_qt.QtCore, _qt.QtGui, _qt.QtWidgets = _qtcore, types.ModuleType("g"), types.ModuleType("w")
sys.modules.setdefault("PySide2", _qt)

import smaAlignNodes as sma  # noqa: E402


class Node:
    def __init__(self, x, y, w=80, h=18, cls="Grade"):
        self.x, self.y, self.w, self.h, self.cls = x, y, w, h, cls

    def Class(self): return self.cls
    def xpos(self): return self.x
    def ypos(self): return self.y
    def setXpos(self, v): self.x = v
    def setYpos(self, v): self.y = v
    def screenWidth(self): return self.w
    def screenHeight(self): return self.h


class DirectionTest(unittest.TestCase):
    def test_short_drag_does_nothing(self):
        self.assertIsNone(sma.direction_from_delta(30, -40, 50))

    def test_dominant_axis(self):
        self.assertEqual(sma.direction_from_delta(60, -40, 50), sma.RIGHT)
        self.assertEqual(sma.direction_from_delta(-60, 10, 50), sma.LEFT)
        self.assertEqual(sma.direction_from_delta(20, -70, 50), sma.UP)
        self.assertEqual(sma.direction_from_delta(-20, 70, 50), sma.DOWN)


class AlignTest(unittest.TestCase):
    def setUp(self):
        self.a = Node(0, 0)                    # center y 9
        self.dot = Node(200, 100, 12, 12, "Dot")  # center y 106
        self.b = Node(400, 50, 80, 40)         # center y 70
        self.nodes = [self.a, self.dot, self.b]

    def test_up_uses_highest_center(self):
        sma.align(self.nodes, sma.UP)
        for n in self.nodes:
            self.assertAlmostEqual(n.y + n.h / 2.0, 9, delta=0.5)
        self.assertEqual([n.x for n in self.nodes], [0, 200, 400])

    def test_down_uses_lowest_center(self):
        sma.align(self.nodes, sma.DOWN)
        self.assertEqual([n.y for n in self.nodes], [97, 100, 86])

    def test_left_and_right(self):
        sma.align(self.nodes, sma.LEFT)
        self.assertEqual([n.x for n in self.nodes], [0, 34, 0])
        sma.align(self.nodes, sma.RIGHT)
        self.assertEqual([n.x for n in self.nodes], [0, 34, 0])

    def test_backdrops_ignored(self):
        bd = Node(-500, -500, 1000, 1000, "BackdropNode")
        sma.align(self.nodes + [bd], sma.UP)
        self.assertEqual((bd.x, bd.y), (-500, -500))
        self.assertEqual(self.a.y, 0)


if __name__ == "__main__":
    unittest.main()
