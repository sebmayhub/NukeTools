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
    """Fake node. The tests read and write x, y, w, h.

    With TRANSPOSED switched on, the Nuke API hands the tool the layout with
    x and y swapped. A test written for the vertical axis then exercises the
    horizontal axis, with the very same numbers.
    """

    TRANSPOSED = False
    _SWAPPED = {"bdwidth": "bdheight", "bdheight": "bdwidth"}

    def __init__(self, name, cls="Grade", x=0, y=0, w=80, h=18, inputs=(), **knobs):
        self._name, self._cls, self.x, self.y, self.w, self.h = name, cls, x, y, w, h
        self._inputs = list(inputs)
        self._knobs = {k: Knob(v) for k, v in knobs.items()}

    def _key(self, name):
        return self._SWAPPED.get(name, name) if Node.TRANSPOSED else name

    def name(self): return self._name
    def Class(self): return self._cls
    def xpos(self): return self.y if Node.TRANSPOSED else self.x
    def ypos(self): return self.x if Node.TRANSPOSED else self.y
    def setXpos(self, v): setattr(self, "y" if Node.TRANSPOSED else "x", v)
    def setYpos(self, v): setattr(self, "x" if Node.TRANSPOSED else "y", v)
    def screenWidth(self): return self.h if Node.TRANSPOSED else self.w
    def screenHeight(self): return self.w if Node.TRANSPOSED else self.h
    def inputs(self): return len(self._inputs)
    def input(self, i): return self._inputs[i]
    def knob(self, name): return self._knobs.get(self._key(name))
    def __getitem__(self, name): return self._knobs[self._key(name)]


def backdrop(name, x, y, w, h):
    return Node(name, "BackdropNode", x, y, 0, 0, bdwidth=w, bdheight=h)


def width(bd):
    return bd._knobs["bdwidth"].value()


def height(bd):
    return bd._knobs["bdheight"].value()


# Grid 110 x 24, handed over swapped when the layout is transposed.
PREFS = {"GridWidth": Knob(24), "GridHeight": Knob(110)}


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
fake.toNode = lambda name: PREFS if Node.TRANSPOSED else None  # None -> fallback grid
fake.NODES = []
fake.allNodes = lambda: list(fake.NODES)
fake.selectedNodes = lambda: [n for n in fake.NODES if n.knob("selected") and n["selected"].value()]
sys.modules["nuke"] = fake

import smaMakeSpace  # noqa: E402


DOWN, UP, RIGHT, LEFT = (smaMakeSpace.DOWN, smaMakeSpace.UP,
                         smaMakeSpace.RIGHT, smaMakeSpace.LEFT)


def by_axis(vertical, horizontal):
    """Expected value where the two axes deliberately behave differently."""
    return horizontal if Node.TRANSPOSED else vertical


def _real(direction):
    return {DOWN: RIGHT, UP: LEFT}[direction] if Node.TRANSPOSED else direction


def run(nodes, ref, direction=DOWN):
    ref._knobs["selected"] = Knob(True)
    fake.NODES = nodes
    smaMakeSpace.make_space(_real(direction))


def close(nodes, ref, direction=DOWN, times=1):
    ref._knobs["selected"] = Knob(True)
    fake.NODES = nodes
    for _ in range(times):
        smaMakeSpace.close_space(_real(direction))


# --- Tests -------------------------------------------------------------------

class MakeSpaceTests(unittest.TestCase):

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
        smaMakeSpace.make_space(DOWN)
        self.assertEqual(a.y, 200)

    def test_down_moves_downstream_side_branches_and_viewer(self):
        nodes = self.pipe()
        read, ref, a, side_src, side, merge, viewer = nodes
        run(list(nodes), ref)
        self.assertEqual((read.y, ref.y), (0, 100))
        for node, y in ((a, 200), (side_src, 150), (side, 200), (merge, 300), (viewer, 400)):
            self.assertEqual(node.y, y + 24, node.name())

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

    def test_tightly_stacked_foreign_node_is_pushed(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=200, inputs=[ref])
        f_src = Node("FSrc", "Read", 200, 0)
        f = Node("F", x=0, y=224, inputs=[f_src])             # only 6 below A
        run([ref, a, f_src, f], ref)
        self.assertEqual((a.y, f.y, f_src.y), (224, 248, 0))

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
        run([ref, a, f_src, f], ref, UP)
        self.assertEqual((a.y, f.y, f_src.y), (176, 145, 600))

    def test_moving_backdrop_pushes_loose_node_below(self):
        """Screenshot case: Write inside the green backdrop moves, the backdrop
        moves along and must push the loose node right below it."""
        ref = Node("Ref", y=100)
        write = Node("Write", "Write", 0, 300, inputs=[ref])
        green = backdrop("Green", -50, 250, 300, 200)         # bottom at 450
        loose = Node("Loose", "Read", 0, 463, 70, 80)         # just below, not near Write
        run([ref, write, green, loose], ref)
        self.assertEqual((write.y, green.y, loose.y), (324, 274, 487))

    def test_moving_backdrop_pushes_backdrop_below(self):
        ref = Node("Ref", y=100)
        write = Node("Write", "Write", 0, 300, inputs=[ref])
        green = backdrop("Green", -50, 250, 300, 200)
        pink = backdrop("Pink", -50, 463, 300, 150)
        inside = Node("Inside", "Read", 0, 550)
        run([ref, write, green, pink, inside], ref)
        self.assertEqual((pink.y, inside.y), (487, 574))

    def test_growing_backdrop_pushes_node_below(self):
        ref = Node("Ref", y=100)
        bd = backdrop("Bd", -50, 50, 300, 100)                # contains Ref, bottom 150
        loose = Node("Loose", "Read", 150, 163)
        run([ref, bd, loose], ref)
        self.assertEqual((height(bd), loose.y), (124, 187))

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
        self.assertEqual((outer.y, height(outer)), (0, 624))
        self.assertEqual((inner.y, height(inner)), (50, 124))
        self.assertEqual((lower.y, height(lower)), (274, 150))
        self.assertEqual((a.y, passenger.y), (324, 324))

    def test_up_is_mirrored(self):
        top = Node("Top", "Read", 0, 0)
        mid = Node("Mid", y=100, inputs=[top])
        ref = Node("Ref", y=200, inputs=[mid])
        below = Node("Below", y=300, inputs=[ref])
        bd = backdrop("Bd", -50, 150, 200, 100)               # contains Ref
        run([top, mid, ref, below, bd], ref, UP)
        self.assertEqual((top.y, mid.y, ref.y, below.y), (-24, 76, 200, 300))
        self.assertEqual((bd.y, height(bd)), (126, 124))


class CloseSpaceTests(unittest.TestCase):

    def setUp(self):
        smaMakeSpace.DEV_MODE = False  # no "blocked by" output during tests

    def test_pulls_until_one_grid_height_remains(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=196, inputs=[ref])                    # centers 96 apart
        b = Node("B", y=300, inputs=[a])
        nodes = [ref, a, b]
        close(nodes, ref, times=3)
        self.assertEqual((a.y, b.y), (124, 228))              # centers 24 apart
        close(nodes, ref)
        self.assertEqual((ref.y, a.y, b.y), (100, 124, 228))  # ignored

    def test_close_reverts_make_space(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=200, inputs=[ref])
        f_up = Node("FUp", "Read", 200, 40)
        f0 = Node("F0", x=200, y=150, inputs=[f_up])
        f1 = Node("F1", x=0, y=231, inputs=[f0])              # pushed by A
        f2 = Node("F2", x=0, y=330, inputs=[f1])
        g_src = Node("GSrc", "Read", 400, 700)
        g = Node("G", x=0, y=262, inputs=[g_src])             # pushed by F1
        h1 = Node("H1", "Read", 0, 500)
        h2 = Node("H2", x=0, y=600, inputs=[h1])
        sticky = Node("Sticky", "StickyNote", 100, 210)
        outer = backdrop("Outer", -50, 50, 600, 100)          # contains Ref
        nodes = [ref, a, f_up, f0, f1, f2, g_src, g, h1, h2, sticky, outer]
        before = [(n.name(), n.y) for n in nodes]
        run(nodes, ref)
        self.assertEqual((a.y, f1.y, g.y, sticky.y), (224, 255, 286, 234))
        self.assertEqual(height(outer), 124)
        close(nodes, ref)
        self.assertEqual([(n.name(), n.y) for n in nodes], before)
        self.assertEqual(height(outer), 100)

    def test_blocked_follower_stays_behind(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=172, inputs=[ref])
        sticky = Node("Sticky", "StickyNote", 200, 130)       # would cross Ref's height
        close([ref, a, sticky], ref)
        self.assertEqual((a.y, sticky.y), (148, 130))

    def test_blocked_follower_keeps_its_whole_pipe(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=200, inputs=[ref])
        w_src = Node("WSrc", "Read", 150, 0)
        wall = Node("Wall", x=150, y=183, inputs=[w_src])     # unrelated, does not move
        f_src = Node("FSrc", x=150, y=215)                    # right below Wall
        f1 = Node("F1", x=0, y=231, inputs=[f_src])           # in A's way -> follower
        close([ref, a, w_src, wall, f_src, f1], ref)
        self.assertEqual(a.y, 176)
        self.assertEqual((f1.y, f_src.y, wall.y), (231, 215, 183))

    def test_connected_side_branch_blocks_everything(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=300, inputs=[ref])
        s1 = Node("S1", "Dot", 300, 103, 12, 12)              # same height as Ref
        s2 = Node("S2", x=300, y=200, inputs=[s1])
        merge = Node("Merge", "Merge2", 0, 400, inputs=[s2, a])
        nodes = [ref, a, s1, s2, merge]
        close(nodes, ref, times=3)
        self.assertEqual((a.y, s2.y, merge.y), (228, 128, 328))
        # S2 has 7 left before it reaches S1: vertically everything moves
        # those 7, horizontally a full step is impossible.
        close(nodes, ref)
        expected = by_axis((221, 121, 321), (228, 128, 328))
        self.assertEqual((a.y, s2.y, merge.y), expected)
        close(nodes, ref)
        self.assertEqual((a.y, s2.y, merge.y), expected)

    def test_tall_node_does_not_overlap(self):
        ref = Node("Ref", y=100)
        tall = Node("Tall", "Read", 0, 129, 80, 80, inputs=[ref])  # 11 below Ref
        nodes = [ref, tall]
        close(nodes, ref, times=2)
        self.assertEqual(tall.y, by_axis(124, 129))           # 6 below Ref / not at all

    def test_backdrop_shrinks_but_keeps_reference_node(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=300, inputs=[ref])
        bd = backdrop("Bd", -50, 50, 300, 100)                # bottom 150
        nodes = [ref, a, bd]
        close(nodes, ref)
        self.assertEqual((a.y, bd.y, height(bd)), (276, 50, 76))
        close(nodes, ref)                                     # Ref would stick out
        self.assertEqual((a.y, height(bd)), (276, 76))

    def test_moving_backdrop_stops_below_reference_node(self):
        ref = Node("Ref", y=100)
        write = Node("Write", "Write", 0, 300, inputs=[ref])
        green = backdrop("Green", -50, 160, 300, 200)
        nodes = [ref, write, green]
        close(nodes, ref)
        self.assertEqual((write.y, green.y), (276, 136))
        close(nodes, ref, times=2)                            # Green must not cover Ref
        self.assertEqual((write.y, green.y), by_axis((264, 124), (276, 136)))

    def test_up_is_mirrored(self):
        top = Node("Top", "Read", 0, 100)
        a = Node("A", y=200, inputs=[top])
        ref = Node("Ref", y=300, inputs=[a])
        below = Node("Below", y=400, inputs=[ref])
        bd = backdrop("Bd", -50, 250, 200, 100)               # contains Ref
        close([top, a, ref, below, bd], ref, UP)
        self.assertEqual((top.y, a.y, ref.y, below.y), (124, 224, 300, 400))
        self.assertEqual((bd.y, height(bd)), (274, 76))

    def test_nothing_without_single_selection(self):
        ref = Node("Ref", y=100)
        a = Node("A", y=300, inputs=[ref])
        fake.NODES = [ref, a]
        smaMakeSpace.close_space(DOWN)
        self.assertEqual(a.y, 300)


class EvenSpacingTests(unittest.TestCase):
    """Vertically, fully closed nodes are MIN_GAP apart, whatever their height."""

    def setUp(self):
        smaMakeSpace.DEV_MODE = False

    def test_tall_reference_node_gets_the_same_gap_on_both_sides(self):
        merge = Node("Merge1", "Merge2", 0, 60)               # 22 above FrameHold
        hold = Node("FrameHold1", "FrameHold", 0, 100, 80, 30, inputs=[merge])
        transform = Node("Transform2", "Transform", 0, 152, inputs=[hold])  # 22 below
        blur = Node("Blur1", "Blur", 0, 200, inputs=[transform])
        nodes = [merge, hold, transform, blur]
        close(nodes, hold, DOWN, times=3)
        close(nodes, hold, UP, times=3)
        self.assertEqual(hold.y, 100)
        self.assertEqual(hold.y - (merge.y + 18), 6)
        self.assertEqual(transform.y - (hold.y + 30), 6)
        self.assertEqual(blur.y - transform.y, 48)            # layout below is kept

    def test_dot_gets_the_same_gap(self):
        ref = Node("Ref", y=100)
        dot = Node("Dot", "Dot", 34, 150, 12, 12, inputs=[ref])
        close([ref, dot], ref, times=3)
        self.assertEqual(dot.y - (ref.y + 18), 6)


class Transposed:
    """Runs the inherited tests on the horizontal axis (see Node)."""

    def setUp(self):
        super().setUp()
        Node.TRANSPOSED = True

    def tearDown(self):
        Node.TRANSPOSED = False
        super().tearDown()


class HorizontalMakeSpaceTests(Transposed, MakeSpaceTests):
    pass


class HorizontalCloseSpaceTests(Transposed, CloseSpaceTests):
    pass


class HorizontalLayoutTests(unittest.TestCase):
    """Untransposed: a side branch next to a vertical main pipe, real grid."""

    def setUp(self):
        smaMakeSpace.DEV_MODE = False

    def scene(self, side=1):
        top = Node("Top", "Read", 0, 0)
        src = Node("Src", "Read", 300 * side, 0)              # side column
        dot = Node("Dot", "Dot", 34 + 300 * side, 103, 12, 12, inputs=[src])
        ref = Node("Ref", "Merge2", 0, 100, inputs=[top, dot])
        below = Node("Below", y=200, inputs=[ref])            # same column -> stays
        bd = backdrop("Bd", -50, 50, 200, 100)                # contains Ref
        return top, src, dot, ref, below, bd

    def test_make_space_right_moves_side_branch_by_grid_width(self):
        nodes = top, src, dot, ref, below, bd = self.scene()
        run(list(nodes), ref, RIGHT)
        self.assertEqual((src.x, dot.x), (410, 444))
        self.assertEqual((top.x, ref.x, below.x), (0, 0, 0))
        self.assertEqual([n.y for n in nodes], [0, 0, 103, 100, 200, 50])
        self.assertEqual((bd.x, width(bd), height(bd)), (-50, 310, 100))

    def test_make_space_left_grows_backdrop_to_the_left(self):
        nodes = top, src, dot, ref, below, bd = self.scene(side=-1)
        run(list(nodes), ref, LEFT)
        self.assertEqual((src.x, dot.x), (-410, -376))
        self.assertEqual((top.x, ref.x, below.x), (0, 0, 0))
        self.assertEqual((bd.x, width(bd)), (-160, 310))

    def test_close_space_right_reverts_make_space(self):
        nodes = top, src, dot, ref, below, bd = self.scene()
        nodes = list(nodes)
        run(nodes, ref, RIGHT)
        close(nodes, ref, RIGHT)
        self.assertEqual((src.x, dot.x, bd.x, width(bd)), (300, 334, -50, 200))
        close(nodes, ref, RIGHT)                              # Ref would stick out of Bd
        self.assertEqual((src.x, dot.x, width(bd)), (300, 334, 200))

    def test_close_space_right_stops_at_one_grid_width(self):
        top = Node("Top", "Read", 0, 0)
        src = Node("Src", "Read", 330, 0)
        dot = Node("Dot", "Dot", 364, 103, 12, 12, inputs=[src])
        ref = Node("Ref", "Merge2", 0, 100, inputs=[top, dot])
        nodes = [top, src, dot, ref]
        close(nodes, ref, RIGHT, times=2)
        self.assertEqual((src.x, dot.x), (110, 144))          # centers 110 apart
        close(nodes, ref, RIGHT)
        self.assertEqual((src.x, dot.x, top.x, ref.x), (110, 144, 0, 0))


if __name__ == "__main__":
    unittest.main()
