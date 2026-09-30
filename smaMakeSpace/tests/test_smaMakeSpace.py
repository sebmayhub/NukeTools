"""Tests der smaMakeSpace-Logik mit einem simulierten nuke-Modul.

Ausfuehren:  python -m unittest discover -s tests
"""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- Fake nuke ---------------------------------------------------------------

class Knob:
    def __init__(self, value):
        self._v = value

    def value(self):
        return self._v

    def setValue(self, v):
        self._v = v


class Node:
    def __init__(self, name, cls="Grade", x=0, y=0, w=80, h=18, inputs=(), **knobs):
        self._name, self._cls, self.x, self.y, self.w, self.h = name, cls, x, y, w, h
        self._inputs = list(inputs)
        self._knobs = {k: Knob(v) for k, v in knobs.items()}

    def name(self): return self._name
    def Class(self): return self._cls
    def xpos(self): return self.x
    def ypos(self): return self.y
    def setYpos(self, y): self.y = y
    def screenWidth(self): return self.w
    def screenHeight(self): return self.h
    def inputs(self): return len(self._inputs)
    def input(self, i): return self._inputs[i]
    def knob(self, name): return self._knobs.get(name)
    def __getitem__(self, name): return self._knobs[name]


def backdrop(name, x, y, w, h):
    return Node(name, "BackdropNode", x, y, 0, 0, bdwidth=w, bdheight=h)


class Undo:
    def begin(self, name=None): pass
    def end(self): pass


class Ctx:
    def __enter__(self): return self
    def __exit__(self, *a): return False


fake = types.ModuleType("nuke")
fake.Undo = Undo
fake.lastHitGroup = lambda: Ctx()
fake.root = lambda: Ctx()
fake.toNode = lambda name: None  # -> Fallback-Raster 110 x 24
fake.NODES = []
fake.allNodes = lambda: list(fake.NODES)
fake.selectedNodes = lambda: [n for n in fake.NODES if n.knob("selected") and n["selected"].value()]
sys.modules["nuke"] = fake

import smaMakeSpace  # noqa: E402


def run(nodes, ref, direction=smaMakeSpace.DOWN, factor=1):
    ref._knobs["selected"] = Knob(True)
    fake.NODES = nodes
    smaMakeSpace.make_space(direction, factor)


# --- Tests -------------------------------------------------------------------

class smaMakeSpaceTests(unittest.TestCase):

    def pipe(self):
        """Read -> Ref -> A -> Merge(B: Side) -> Viewer; Side liegt unterhalb von Ref."""
        read = Node("Read", "Read", 0, 0)
        ref = Node("Ref", "Grade", 0, 100, inputs=[read])
        a = Node("A", "Grade", 0, 200, inputs=[ref])
        side_src = Node("SideSrc", "Read", 300, 150)
        side = Node("Side", "Grade", 300, 200, inputs=[side_src])
        merge = Node("Merge", "Merge2", 0, 300, inputs=[side, a])
        viewer = Node("Viewer1", "Viewer", 0, 400, inputs=[merge])
        return read, ref, a, side_src, side, merge, viewer

    def test_nothing_without_single_selection(self):
        read, ref, a, *_ = self.pipe()
        fake.NODES = [read, ref, a]
        smaMakeSpace.make_space(smaMakeSpace.DOWN)
        self.assertEqual(a.y, 200)

    def test_down_moves_downstream_side_branches_and_viewer(self):
        nodes = self.pipe()
        read, ref, a, side_src, side, merge, viewer = nodes
        run(list(nodes), ref)
        self.assertEqual((read.y, ref.y), (0, 100))
        for node, y in ((a, 200), (side_src, 150), (side, 200), (merge, 300), (viewer, 400)):
            self.assertEqual(node.y, y + 24, node.name())

    def test_big_step(self):
        nodes = self.pipe()
        run(list(nodes), nodes[1], factor=4)
        self.assertEqual(nodes[2].y, 200 + 96)

    def test_branch_stops_at_node_above_ref(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=200, inputs=[ref])
        high = Node("High", "Read", 300, 50)                # ueber Ref -> Abbruch
        above_child = Node("HighChild", x=300, y=60, inputs=[high])
        merge = Node("Merge", "Merge2", 0, 300, inputs=[high, a])
        same = Node("Same", "Read", 300, 100)               # gleiche Hoehe -> bleibt
        merge2 = Node("Merge2", "Merge2", 0, 400, inputs=[same, merge])
        run([ref, a, high, above_child, merge, same, merge2], ref)
        self.assertEqual((high.y, above_child.y, same.y), (50, 60, 100))
        self.assertEqual((a.y, merge.y, merge2.y), (224, 324, 424))

    def test_hidden_input_is_not_a_pipe(self):
        ref = Node("Ref", y=100)
        hidden = Node("Hidden", y=200, inputs=[ref], hide_input=True)
        run([ref, hidden], ref)
        self.assertEqual(hidden.y, 200)

    def test_loose_nodes_near_moved_nodes(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=200, inputs=[ref])
        sticky_near = Node("StickyNear", "StickyNote", 200, 220)
        loose_far = Node("LooseFar", "Grade", 1000, 200)
        loose_above = Node("LooseAbove", "Grade", 100, 60)
        chain = Node("Chain", "Grade", 200 + 3 * 110 + 50, 220)  # nur nahe am Sticky
        run([ref, a, sticky_near, loose_far, loose_above, chain], ref)
        self.assertEqual(sticky_near.y, 244)
        self.assertEqual((loose_far.y, loose_above.y, chain.y), (200, 60, 220))

    def test_backdrops_grow_and_move(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=300, inputs=[ref])
        outer = backdrop("Outer", -50, 0, 400, 600)
        inner = backdrop("Inner", -20, 50, 200, 100)          # enthaelt Ref
        lower = backdrop("Lower", -20, 250, 300, 150)         # enthaelt A
        passenger = Node("Passenger", "Read", 150, 300)       # im Lower, unverbunden
        run([ref, a, outer, inner, lower, passenger], ref)
        self.assertEqual((outer.y, outer["bdheight"].value()), (0, 624))
        self.assertEqual((inner.y, inner["bdheight"].value()), (50, 124))
        self.assertEqual((lower.y, lower["bdheight"].value()), (274, 150))
        self.assertEqual((a.y, passenger.y), (324, 324))

    def test_up_is_mirrored(self):
        top = Node("Top", "Read", 0, 0)
        mid = Node("Mid", y=100, inputs=[top])
        ref = Node("Ref", y=200, inputs=[mid])
        below = Node("Below", y=300, inputs=[ref])
        bd = backdrop("Bd", -50, 150, 200, 100)               # enthaelt Ref
        run([top, mid, ref, below, bd], ref, smaMakeSpace.UP)
        self.assertEqual((top.y, mid.y, ref.y, below.y), (-24, 76, 200, 300))
        self.assertEqual((bd.y, bd["bdheight"].value()), (126, 124))


if __name__ == "__main__":
    unittest.main()
