"""smaMakeSpace - makes space in the Node Graph above or below a node.

Nuke 16.0v3 / Python 3.11

Behaviour (described for "down", "up" is exactly mirrored):
  1. Exactly one node/Dot must be selected (the reference node), otherwise
     nothing happens.
  2. All nodes that are continuously connected to the reference node via real
     pipes (inputs/outputs incl. masks, excluding hidden inputs) and whose
     center lies below the reference node are moved. A branch stops as soon
     as a node at the same height (within SAME_HEIGHT_TOLERANCE) or above is
     reached.
  3. Loose nodes (without any connection) and StickyNotes near the moved
     nodes are moved as well, as long as they lie below.
  4. Backdrops containing the reference node are enlarged. All other affected
     backdrops move completely, together with their contents.
  5. Anything below the reference node that a moved node, a moved backdrop or
     a growing backdrop would overlap (or come closer to than COLLISION_GAP)
     is pushed along: a node together with its whole pipe below the reference
     node, a backdrop with its entire contents. This repeats until nothing
     collides.
"""

import nuke

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# True: the code is reloaded on every key press (for development).
DEV_MODE = True

# Factor for the big step (Ctrl+Shift+Arrow).
BIG_STEP_FACTOR = 4

# Proximity radius for loose nodes / StickyNotes / backdrops, in grid units.
PROXIMITY_GRID_UNITS = 3

# Max. vertical deviation (in Node Graph units) between node centers that still
# counts as "same height" as the reference node. Such nodes are not moved.
SAME_HEIGHT_TOLERANCE = 10

# Minimum distance (in Node Graph units) a moved node must keep from nodes that
# are not moved. Anything closer after the move is pushed along as well.
COLLISION_GAP = 12

# Fallback values in case the preferences cannot be read.
DEFAULT_GRID_WIDTH = 110
DEFAULT_GRID_HEIGHT = 24

# Fallback sizes for nodes that have not been drawn yet.
DEFAULT_NODE_SIZE = (80, 18)
DEFAULT_DOT_SIZE = (12, 12)

DOWN = 1
UP = -1

BACKDROP = "BackdropNode"
STICKY = "StickyNote"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grid_size():
    """Grid width and height from the Nuke preferences."""
    try:
        prefs = nuke.toNode("preferences")
        return (int(prefs["GridWidth"].value()) or DEFAULT_GRID_WIDTH,
                int(prefs["GridHeight"].value()) or DEFAULT_GRID_HEIGHT)
    except Exception:
        return DEFAULT_GRID_WIDTH, DEFAULT_GRID_HEIGHT


def _current_group():
    """The group whose Node Graph was used last."""
    try:
        group = nuke.lastHitGroup()
    except Exception:
        group = None
    return group or nuke.root()


def _rect(node):
    """(x, y, w, h) of a node in the Node Graph."""
    x, y = node.xpos(), node.ypos()
    if node.Class() == BACKDROP:
        return x, y, int(node["bdwidth"].value()), int(node["bdheight"].value())
    w, h = node.screenWidth(), node.screenHeight()
    if not w or not h:
        w, h = DEFAULT_DOT_SIZE if node.Class() == "Dot" else DEFAULT_NODE_SIZE
    return x, y, w, h


def _center(node):
    x, y, w, h = _rect(node)
    return x + w / 2.0, y + h / 2.0


def _is_beyond(node, ref_cy, direction):
    """True if the node center lies below (DOWN) or above (UP) ref_cy by more
    than SAME_HEIGHT_TOLERANCE."""
    return (_center(node)[1] - ref_cy) * direction > SAME_HEIGHT_TOLERANCE


def _contains(backdrop, point):
    x, y, w, h = _rect(backdrop)
    px, py = point
    return x <= px <= x + w and y <= py <= y + h


def _expand(rect, margin_x, margin_y):
    x, y, w, h = rect
    return x - margin_x, y - margin_y, w + 2 * margin_x, h + 2 * margin_y


def _overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def _is_near(a, b, margin_x, margin_y):
    """True if the box of a, expanded by the margins, overlaps b."""
    return _overlaps(_expand(_rect(a), margin_x, margin_y), _rect(b))


def _hides_inputs(node):
    knob = node.knob("hide_input")
    return bool(knob and knob.value())


def _connections(nodes):
    """Pipe neighbours per node, plus the set of all nodes with any connection.

    Only visible pipes count for the search. A node is only "loose", however,
    if it has no connection at all, not even a hidden one.
    """
    neighbours = {}
    connected = set()
    for node in nodes:
        if node.Class() in (BACKDROP, STICKY):
            continue
        hidden = _hides_inputs(node)
        for i in range(node.inputs()):
            inp = node.input(i)
            if inp is None:
                continue
            connected.update((node.name(), inp.name()))
            if hidden:
                continue
            neighbours.setdefault(node.name(), []).append(inp)
            neighbours.setdefault(inp.name(), []).append(node)
    return neighbours, connected


# ---------------------------------------------------------------------------
# Collecting the nodes to move
# ---------------------------------------------------------------------------

def _reachable(start, neighbours, ref_cy, direction):
    """All nodes beyond ref_cy that are continuously reachable from start via
    pipes (start itself excluded)."""
    found = {}
    visited = {start.name()}
    stack = [start]
    while stack:
        current = stack.pop()
        for node in neighbours.get(current.name(), ()):
            if node.name() in visited:
                continue
            visited.add(node.name())
            if _is_beyond(node, ref_cy, direction):
                found[node.name()] = node
                stack.append(node)
    return found


def _target_rect(rect, step, direction, growing):
    """Rect after the move: shifted, or enlarged for a growing backdrop."""
    x, y, w, h = rect
    if not growing:
        return x, y + step * direction, w, h
    if direction == UP:
        return x, y - step, w, h + step
    return x, y, w, h + step


def _add_backdrop(backdrop, nodes, moved, excluded):
    """Adds a backdrop and its entire contents to moved; returns what was added."""
    added = [backdrop]
    moved[backdrop.name()] = backdrop
    for node in nodes:
        if node.name() in excluded or node.name() in moved:
            continue
        if _contains(backdrop, _center(node)):
            moved[node.name()] = node
            added.append(node)
    return added


def _push_colliding(moved, grow, nodes, candidates, excluded, neighbours,
                    ref_cy, direction, step):
    """Adds everything that a moved node, a moved backdrop or a growing
    backdrop would newly collide with. A hit node brings its whole pipe beyond
    ref_cy, a hit backdrop its entire contents. Repeats for the added items
    until nothing collides any more."""
    pending = [(n, False) for n in moved.values()] + [(b, True) for b in grow]
    while pending:
        node, growing = pending.pop()
        rect = _rect(node)
        before = _expand(rect, COLLISION_GAP, COLLISION_GAP)
        after = _expand(_target_rect(rect, step, direction, growing),
                        COLLISION_GAP, COLLISION_GAP)
        for other in candidates:
            if other.name() in moved or not _is_beyond(other, ref_cy, direction):
                continue
            other_rect = _rect(other)
            # Only collisions caused by the move count, not existing overlaps.
            if not _overlaps(after, other_rect) or _overlaps(before, other_rect):
                continue
            if other.Class() == BACKDROP:
                added = _add_backdrop(other, nodes, moved, excluded)
            else:
                group = {other.name(): other}
                group.update(_reachable(other, neighbours, ref_cy, direction))
                added = [n for name, n in group.items() if name not in moved]
                for n in added:
                    moved[n.name()] = n
            pending.extend((n, False) for n in added)


def collect(ref, nodes, direction, grid=None, step=None):
    """Determines what gets moved and what gets enlarged.

    Returns: (nodes to move as dict name->node,
              backdrops to enlarge as list)
    """
    grid_w, grid_h = grid or _grid_size()
    if step is None:
        step = grid_h
    margin_x = PROXIMITY_GRID_UNITS * grid_w
    margin_y = PROXIMITY_GRID_UNITS * grid_h
    ref_center = _center(ref)
    ref_cy = ref_center[1]

    neighbours, connected = _connections(nodes)
    backdrops = [n for n in nodes if n.Class() == BACKDROP]
    grow = [b for b in backdrops if _contains(b, ref_center)]
    grow_names = {b.name() for b in grow}
    excluded = grow_names | {ref.name()}
    candidates = [n for n in nodes if n.name() not in excluded]

    # 1. Connected nodes (incl. side branches and viewers).
    moved = _reachable(ref, neighbours, ref_cy, direction)

    # Each of the following rules can add nodes that trigger the others again,
    # so repeat until nothing changes any more.
    while True:
        count = len(moved)

        # 2. Nodes and backdrops in the way (chain reaction).
        _push_colliding(moved, grow, nodes, candidates, excluded, neighbours,
                        ref_cy, direction, step)

        # 3. Nearby loose nodes and StickyNotes (only around connected nodes).
        anchors = [n for n in moved.values() if n.name() in connected]
        for node in candidates:
            name = node.name()
            if name in moved or name in connected or node.Class() == BACKDROP:
                continue
            if not _is_beyond(node, ref_cy, direction):
                continue
            if any(_is_near(anchor, node, margin_x, margin_y) for anchor in anchors):
                moved[name] = node

        # 4. Affected backdrops move completely, together with their contents.
        moved_centers = [_center(n) for n in moved.values() if n.Class() != BACKDROP]
        for backdrop in backdrops:
            if backdrop.name() in grow_names or backdrop.name() in moved:
                continue
            holds_moved = any(_contains(backdrop, c) for c in moved_centers)
            is_near = (_is_beyond(backdrop, ref_cy, direction) and
                       any(_is_near(anchor, backdrop, margin_x, margin_y)
                           for anchor in anchors))
            if holds_moved or is_near:
                _add_backdrop(backdrop, nodes, moved, excluded)

        if len(moved) == count:
            return moved, grow


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def make_space(direction=DOWN, factor=1):
    """Makes space below (DOWN) or above (UP) the selected node."""
    with _current_group():
        selection = nuke.selectedNodes()
        if len(selection) != 1:
            return
        ref = selection[0]
        if ref.Class() in (BACKDROP, STICKY):
            return

        grid = _grid_size()
        step = grid[1] * factor
        moved, grow = collect(ref, nuke.allNodes(), direction, grid, step)

        undo = nuke.Undo()
        undo.begin("smaMakeSpace")
        try:
            for node in moved.values():
                node.setYpos(int(node.ypos() + step * direction))
            for backdrop in grow:
                height = backdrop["bdheight"]
                height.setValue(int(height.value()) + step)
                if direction == UP:
                    backdrop.setYpos(int(backdrop.ypos() - step))
        finally:
            undo.end()
