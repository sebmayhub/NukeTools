"""Tests for the smaMakeSpace logic using a fake nuke module.

Run:  python -m unittest discover -s tests
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
fake.toNode = lambda name: None  # -> fallback grid 110 x 24
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
        """Read -> Ref -> A -> Merge(B: Side) -> Viewer; Side lies below Ref."""
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
        high = Node("High", "Read", 300, 50)                # above Ref -> branch stops
        above_child = Node("HighChild", x=300, y=60, inputs=[high])
        merge = Node("Merge", "Merge2", 0, 300, inputs=[high, a])
        same = Node("Same", "Read", 300, 100)               # same height -> stays
        merge2 = Node("Merge2", "Merge2", 0, 400, inputs=[same, merge])
        run([ref, a, high, above_child, merge, same, merge2], ref)
        self.assertEqual((high.y, above_child.y, same.y), (50, 60, 100))
        self.assertEqual((a.y, merge.y, merge2.y), (224, 324, 424))

    def test_same_height_tolerance(self):
        ref = Node("Ref", y=100)
        side_ok = Node("SideOk", "Dot", 200, 110 - 6 + 9, 12, 12, inputs=[ref])  # center +10 -> same height
        side_low = Node("SideLow", "Dot", 400, 110 - 6 + 11, 12, 12, inputs=[ref])  # center +11 -> below
        below_ok = Node("BelowOk", x=200, y=200, inputs=[side_ok])
        run([ref, side_ok, side_low, below_ok], ref)
        self.assertEqual((side_ok.y, below_ok.y), (113, 200))
        self.assertEqual(side_low.y, 115 + 24)

    def test_foreign_pipe_in_the_way_is_pushed_with_chain(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=200, inputs=[ref])                    # moves to 224
        f_up = Node("FUp", "Read", 200, 40)                   # above Ref -> stays
        f0 = Node("F0", x=200, y=150, inputs=[f_up])
        f1 = Node("F1", x=0, y=231, inputs=[f0])              # hit by A
        f2 = Node("F2", x=0, y=330, inputs=[f1])
        g_src = Node("GSrc", "Read", 400, 700)
        g = Node("G", x=0, y=262, inputs=[g_src])             # hit by F1 (chain)
        h1 = Node("H1", "Read", 0, 500)                       # far away -> stays
        h2 = Node("H2", x=0, y=600, inputs=[h1])
        run([ref, a, f_up, f0, f1, f2, g_src, g, h1, h2], ref)
        self.assertEqual((a.y, f0.y, f1.y, f2.y), (224, 174, 255, 354))
        self.assertEqual((g.y, g_src.y), (286, 724))
        self.assertEqual((f_up.y, h1.y, h2.y), (40, 500, 600))

    def test_existing_overlap_does_not_push(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=200, inputs=[ref])
        b_src = Node("BSrc", "Read", 90, -100)
        beside = Node("Beside", x=90, y=200, inputs=[b_src])  # already within gap
        run([ref, a, b_src, beside], ref)
        self.assertEqual((a.y, beside.y), (224, 200))

    def test_collision_up_is_mirrored(self):
        ref = Node("Ref", y=300)
        a = Node("A", y=200)
        ref._inputs = [a]
        f_src = Node("FSrc", "Read", 300, 600)
        f = Node("F", x=0, y=169, inputs=[f_src])             # hit by A moving up
        run([ref, a, f_src, f], ref, smaMakeSpace.UP)
        self.assertEqual((a.y, f.y, f_src.y), (176, 145, 600))

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
        chain = Node("Chain", "Grade", 200 + 3 * 110 + 50, 220)  # only near the sticky
        run([ref, a, sticky_near, loose_far, loose_above, chain], ref)
        self.assertEqual(sticky_near.y, 244)
        self.assertEqual((loose_far.y, loose_above.y, chain.y), (200, 60, 220))

    def test_backdrops_grow_and_move(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=300, inputs=[ref])
        outer = backdrop("Outer", -50, 0, 400, 600)
        inner = backdrop("Inner", -20, 50, 200, 100)          # contains Ref
        lower = backdrop("Lower", -20, 250, 300, 150)         # contains A
        passenger = Node("Passenger", "Read", 150, 300)       # inside Lower, unconnected
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
        bd = backdrop("Bd", -50, 150, 200, 100)               # contains Ref
        run([top, mid, ref, below, bd], ref, smaMakeSpace.UP)
        self.assertEqual((top.y, mid.y, ref.y, below.y), (-24, 76, 200, 300))
        self.assertEqual((bd.y, bd["bdheight"].value()), (126, 124))


if __name__ == "__main__":
    unittest.main()
