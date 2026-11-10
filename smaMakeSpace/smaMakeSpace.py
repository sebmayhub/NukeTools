"""smaMakeSpace - makes or closes space in the Node Graph next to a node.

Nuke 16.0v3 / Python 3.11

Works in all four directions. Described here for "down"; "up" is mirrored, and
"right" / "left" are the same rules on the horizontal axis (read "same column"
for "same height", "grid width" for "grid height" and so on).

Making space:
  1. Exactly one node/Dot must be selected (the reference node), otherwise
     nothing happens.
  2. All nodes that are continuously connected to the reference node via real
     pipes (inputs/outputs incl. masks, excluding hidden inputs) and whose
     center lies below the reference node are moved. A branch stops as soon
     as a node at the same height (within ALIGN_TOLERANCE) or above is
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

Closing space is the reverse: the same items are pulled towards the reference
node by one step and its backdrops shrink. Nothing may end up overlapping:
  - Nodes connected to the reference node (and the backdrops holding them)
    are mandatory. If one of them cannot move, nothing happens at all.
  - Everything else (loose nodes, pipes and backdrops that are merely nearby
    or in the way) just follows. A follower that is blocked stays behind,
    together with its pipe / backdrop.
  - Everything keeps at least MIN_GAP of free space to whatever does not
    move, and no node may cross the height of the reference node.
  - Vertically the last step is shortened so that exactly MIN_GAP remains.
    Fully closed nodes are therefore evenly spaced, however tall they are.
  - Horizontally only whole grid steps are made, and nodes beside each other
    keep one grid width between their centers, so columns stay on the grid.
"""

import nuke

__version__ = "1.1.0"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# True: the code is reloaded on every key press (for development).
DEV_MODE = True

# Proximity radius for loose nodes / StickyNotes / backdrops, in grid units.
PROXIMITY_GRID_UNITS = 3

# Max. deviation (in Node Graph units) between node centers that still counts
# as "same height" (vertical moves) or "same column" (horizontal moves) as the
# reference node. Such nodes are not moved.
ALIGN_TOLERANCE = 10

# Minimum distance (in Node Graph units) a moved node must keep from nodes that
# are not moved. Anything closer after the move is pushed along as well.
COLLISION_GAP = 12

# Free space (in Node Graph units) that closing space leaves between moved
# items and items that are not moved. Vertically, fully closed nodes end up
# exactly this far apart. 6 is what two standard nodes on neighbouring grid
# rows have.
MIN_GAP = 6

# Fallback values in case the preferences cannot be read.
DEFAULT_GRID_WIDTH = 110
DEFAULT_GRID_HEIGHT = 24

# Fallback sizes for nodes that have not been drawn yet.
DEFAULT_NODE_SIZE = (80, 18)
DEFAULT_DOT_SIZE = (12, 12)

# Directions as (axis, sign). Axis 0 is x, axis 1 is y; rects are (x, y, w, h),
# so rect[axis] is the position and rect[axis + 2] the size along that axis.
RIGHT = (0, 1)
LEFT = (0, -1)
DOWN = (1, 1)
UP = (1, -1)

BACKDROP = "BackdropNode"
STICKY = "StickyNote"
SIZE_KNOBS = ("bdwidth", "bdheight")


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


def _set_pos(node, axis, value):
    if axis == 0:
        node.setXpos(int(value))
    else:
        node.setYpos(int(value))


def _is_beyond(node, ref_pos, direction):
    """True if the node center lies past ref_pos in the given direction by
    more than ALIGN_TOLERANCE."""
    axis, sign = direction
    return (_center(node)[axis] - ref_pos) * sign > ALIGN_TOLERANCE


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


def _gap_ahead(rect, other, direction, margin):
    """Free space between rect and other, if other lies ahead of rect in the
    given direction (within its lane, widened by margin). None if other is
    beside rect, behind it or already overlapping it."""
    axis, sign = direction
    across = 1 - axis
    if not (rect[across] - margin < other[across] + other[across + 2] and
            other[across] < rect[across] + rect[across + 2] + margin):
        return None
    if sign > 0:
        gap = other[axis] - (rect[axis] + rect[axis + 2])
    else:
        gap = rect[axis] - (other[axis] + other[axis + 2])
    return gap if gap >= 0 else None


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

def _reachable(start, neighbours, ref_pos, direction):
    """All nodes beyond ref_pos that are continuously reachable from start via
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
            if _is_beyond(node, ref_pos, direction):
                found[node.name()] = node
                stack.append(node)
    return found


def _resized(rect, amount, direction):
    """Rect of a backdrop enlarged by amount on the side the direction points
    to (negative: shrunk)."""
    axis, sign = direction
    resized = list(rect)
    resized[axis + 2] += amount
    if sign < 0:
        resized[axis] -= amount
    return tuple(resized)


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
                    ref_pos, direction, step):
    """Adds everything that a moved node, a moved backdrop or a growing
    backdrop would run into. A hit node brings its whole pipe beyond ref_pos,
    a hit backdrop its entire contents. Repeats for the added items until
    nothing collides any more."""
    pending = list(moved.values()) + list(grow)
    while pending:
        rect = _rect(pending.pop())
        for other in candidates:
            if other.name() in moved or not _is_beyond(other, ref_pos, direction):
                continue
            # Only what lies ahead counts, not what already overlaps.
            gap = _gap_ahead(rect, _rect(other), direction, COLLISION_GAP)
            if gap is None or gap - step >= COLLISION_GAP:
                continue
            if other.Class() == BACKDROP:
                added = _add_backdrop(other, nodes, moved, excluded)
            else:
                group = {other.name(): other}
                group.update(_reachable(other, neighbours, ref_pos, direction))
                added = [n for name, n in group.items() if name not in moved]
                for n in added:
                    moved[n.name()] = n
            pending.extend(added)


def collect(ref, nodes, direction, grid=None, step=None, followers=True):
    """Determines what gets moved and what gets enlarged.

    With followers=False only the nodes connected to the reference node and
    the backdrops holding them are collected, without anything that is merely
    nearby or in the way.

    Returns: (nodes to move as dict name->node,
              backdrops to enlarge as list)
    """
    axis = direction[0]
    grid = grid or _grid_size()
    if step is None:
        step = grid[axis]
    margin_x = PROXIMITY_GRID_UNITS * grid[0]
    margin_y = PROXIMITY_GRID_UNITS * grid[1]
    ref_center = _center(ref)
    ref_pos = ref_center[axis]

    neighbours, connected = _connections(nodes)
    backdrops = [n for n in nodes if n.Class() == BACKDROP]
    grow = [b for b in backdrops if _contains(b, ref_center)]
    grow_names = {b.name() for b in grow}
    excluded = grow_names | {ref.name()}
    candidates = [n for n in nodes if n.name() not in excluded]

    # 1. Connected nodes (incl. side branches and viewers).
    moved = _reachable(ref, neighbours, ref_pos, direction)

    # Each of the following rules can add nodes that trigger the others again,
    # so repeat until nothing changes any more.
    while True:
        count = len(moved)

        anchors = []
        if followers:
            # 2. Nodes and backdrops in the way (chain reaction).
            _push_colliding(moved, grow, nodes, candidates, excluded,
                            neighbours, ref_pos, direction, step)

            # 3. Nearby loose nodes and StickyNotes (only around connected nodes).
            anchors = [n for n in moved.values() if n.name() in connected]
            for node in candidates:
                name = node.name()
                if name in moved or name in connected or node.Class() == BACKDROP:
                    continue
                if not _is_beyond(node, ref_pos, direction):
                    continue
                if any(_is_near(anchor, node, margin_x, margin_y)
                       for anchor in anchors):
                    moved[name] = node

        # 4. Affected backdrops move completely, together with their contents.
        moved_centers = [_center(n) for n in moved.values() if n.Class() != BACKDROP]
        for backdrop in backdrops:
            if backdrop.name() in grow_names or backdrop.name() in moved:
                continue
            holds_moved = any(_contains(backdrop, c) for c in moved_centers)
            is_near = (_is_beyond(backdrop, ref_pos, direction) and
                       any(_is_near(anchor, backdrop, margin_x, margin_y)
                           for anchor in anchors))
            if holds_moved or is_near:
                _add_backdrop(backdrop, nodes, moved, excluded)

        if len(moved) == count:
            return moved, grow


# ---------------------------------------------------------------------------
# Closing space
# ---------------------------------------------------------------------------

def _groups(followers, neighbours):
    """Maps each follower name to the set of followers it belongs with (same
    pipe, or backdrop and contents). Such a group only moves as a unit."""
    group = {name: {name} for name in followers}

    def join(a, b):
        if group[a] is not group[b]:
            merged = group[a] | group[b]
            for name in merged:
                group[name] = merged

    for name, node in followers.items():
        if node.Class() == BACKDROP:
            for other_name, other in followers.items():
                if other_name != name and _contains(node, _center(other)):
                    join(name, other_name)
        else:
            for other in neighbours.get(name, ()):
                if other.name() in followers:
                    join(name, other.name())
    return group


def _room(mover, obstacles, direction):
    """How far the mover can be pulled towards the reference node until only
    MIN_GAP of free space is left to something that does not move.

    Returns (distance, obstacle), or (None, None) if nothing is in the way.
    """
    axis, sign = direction
    rect = _rect(mover)
    room, obstacle = None, None
    for other in obstacles:
        gap = _gap_ahead(rect, _rect(other), (axis, -sign), MIN_GAP)
        if gap is not None and (room is None or gap - MIN_GAP < room):
            room, obstacle = max(0, gap - MIN_GAP), other
    return room, obstacle


def _violations(moved, grow, stationary, ref, direction, grid_step, distance,
                aligning=()):
    """Checks the remaining rules for pulling the moved items by distance.
    Nodes named in aligning may come level with the reference node (the
    distance has been limited so they do not cross it).

    Returns a list of (item that cannot move, obstacle).
    """
    axis, sign = direction
    across = 1 - axis
    ref_pos = _center(ref)[axis]
    grow_names = {b.name() for b in grow}
    violations = []

    for mover in moved.values():
        if mover.Class() == BACKDROP:
            continue
        rect = _rect(mover)
        pos = _center(mover)[axis]
        target = pos - distance * sign

        # A node must not cross the line of the reference node.
        if (mover.name() not in aligning and _is_beyond(mover, ref_pos, direction)
                and (target - ref_pos) * sign <= ALIGN_TOLERANCE):
            violations.append((mover, ref))
            continue

        # Horizontally, nodes beside each other keep one grid width between
        # their centers, so that columns stay on the grid.
        if axis != 0:
            continue
        for other in stationary:
            if other.Class() == BACKDROP:
                continue
            other_rect = _rect(other)
            other_pos = _center(other)[axis]
            in_line = (rect[across] < other_rect[across] + other_rect[across + 2]
                       and other_rect[across] < rect[across] + rect[across + 2])
            if (in_line and (pos - other_pos) * sign > 0
                    and (target - other_pos) * sign < grid_step):
                violations.append((mover, other))
                break

    # A shrinking backdrop must keep everything inside that does not move.
    for backdrop in grow:
        shrunk = _resized(_rect(backdrop), -distance, direction)
        for other in stationary:
            if other.name() in grow_names or not _contains(backdrop, _center(other)):
                continue
            rect = _rect(other)
            if sign < 0:
                inside = rect[axis] - MIN_GAP >= shrunk[axis]
            else:
                inside = (rect[axis] + rect[axis + 2] + MIN_GAP
                          <= shrunk[axis] + shrunk[axis + 2])
            if not inside:
                violations.append((backdrop, other))
                break

    return violations


def plan_close(ref, nodes, direction, grid=None, step=None):
    """Determines what gets pulled towards the reference node, and how far.

    The items are the same as in collect(). Nodes connected to the reference
    node (and the backdrops holding them) are mandatory: if one of them is
    blocked, nothing moves at all. Everything else merely follows: a blocked
    follower stays behind, together with its group.

    Vertically the distance is shortened if less than a full step is left
    before a mandatory item reaches MIN_GAP, or before a mandatory node comes
    level with the reference node (from then on it counts as "same height"
    and stays). Horizontally it is always a full step.

    Returns: (nodes to move as dict name->node, backdrops to shrink as list,
              distance), or None if the move is blocked.
    """
    axis = direction[0]
    grid = grid or _grid_size()
    if step is None:
        step = grid[axis]
    moved, grow = collect(ref, nodes, direction, grid, step)
    mandatory, _ = collect(ref, nodes, direction, grid, step, followers=False)
    neighbours, _ = _connections(nodes)
    group = _groups({name: node for name, node in moved.items()
                     if name not in mandatory}, neighbours)
    grow_names = {b.name() for b in grow}
    ref_pos = _center(ref)[axis]
    sign = direction[1]

    def blocked(mover, obstacle):
        if DEV_MODE:
            print("smaMakeSpace: %s is blocked by %s" % (mover.name(), obstacle.name()))

    while True:
        stationary = [n for n in nodes if n.name() not in moved]
        obstacles = [n for n in stationary if n.name() not in grow_names]
        rooms = {name: _room(node, obstacles, direction)
                 for name, node in moved.items()}

        # The mandatory items set the distance.
        distance = step
        for name in moved:
            room, obstacle = rooms[name]
            if name in group or room is None or room >= distance:
                continue
            if room == 0 or axis == 0:
                blocked(moved[name], obstacle)
                return None
            distance = room

        # Vertically, a mandatory node may come at most level with the
        # reference node.
        aligning = set()
        if axis == 1:
            aligning = {name for name, node in moved.items()
                        if name not in group and node.Class() != BACKDROP}
            for name in aligning:
                node = moved[name]
                if not _is_beyond(node, ref_pos, direction):
                    continue
                level = int((_center(node)[axis] - ref_pos) * sign)
                if level < distance:
                    distance = level

        failed = [(moved[name], obstacle) for name, (room, obstacle) in rooms.items()
                  if room is not None and room < distance]
        failed += _violations(moved, grow, stationary, ref, direction,
                              grid[axis], distance, aligning)
        if not failed:
            return moved, grow, distance
        for mover, obstacle in failed:
            if mover.name() not in group:
                blocked(mover, obstacle)
                return None
        for mover, _ in failed:
            for name in group[mover.name()]:
                moved.pop(name, None)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def _reference_node():
    """The single selected node, or None if the selection does not qualify."""
    selection = nuke.selectedNodes()
    if len(selection) != 1 or selection[0].Class() in (BACKDROP, STICKY):
        return None
    return selection[0]


def _apply(moved, backdrops, direction, amount):
    """Moves the nodes by amount in the given direction and enlarges the
    backdrops by amount on that side (negative: back / shrink), as one undo
    step."""
    if not moved and not backdrops:
        return
    axis, sign = direction
    undo = nuke.Undo()
    undo.begin("smaMakeSpace")
    try:
        for node in moved.values():
            _set_pos(node, axis, _rect(node)[axis] + amount * sign)
        for backdrop in backdrops:
            size = backdrop[SIZE_KNOBS[axis]]
            size.setValue(int(size.value()) + amount)
            if sign < 0:
                _set_pos(backdrop, axis, _rect(backdrop)[axis] - amount)
    finally:
        undo.end()


def make_space(direction=DOWN):
    """Makes space next to the selected node: pushes everything on that side
    (DOWN, UP, RIGHT or LEFT) one grid step away."""
    with _current_group():
        ref = _reference_node()
        if ref is None:
            return
        grid = _grid_size()
        step = grid[direction[0]]
        moved, grow = collect(ref, nuke.allNodes(), direction, grid, step)
        _apply(moved, grow, direction, step)


def close_space(direction=DOWN):
    """Closes space next to the selected node: pulls everything on that side
    (DOWN, UP, RIGHT or LEFT) one grid step closer."""
    with _current_group():
        ref = _reference_node()
        if ref is None:
            return
        grid = _grid_size()
        step = grid[direction[0]]
        plan = plan_close(ref, nuke.allNodes(), direction, grid, step)
        if plan:
            moved, shrink, distance = plan
            _apply(moved, shrink, direction, -distance)
