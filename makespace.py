"""MakeSpace - schafft Platz im Node Graph ober- bzw. unterhalb eines Nodes.

Nuke 16.0v3 / Python 3.11

Ablauf (beschrieben fuer "nach unten", "nach oben" ist exakt gespiegelt):
  1. Genau ein Node/Dot muss selektiert sein (Referenz-Nd), sonst passiert nichts.
  2. Alle Nodes, die ueber echte Pipes (Inputs/Outputs, inkl. Masken, ohne
     Hidden Inputs) durchgaengig mit dem Referenz-Nd verbunden sind und deren
     Mittelpunkt echt unterhalb des Referenz-Nd liegt, werden verschoben.
     Ein Zweig wird abgebrochen, sobald ein Node auf gleicher Hoehe oder
     darueber erreicht wird.
  3. Lose Nodes (ganz ohne Verbindungen) und StickyNotes im Umkreis der
     verschobenen Nodes werden mitverschoben, sofern sie unterhalb liegen.
  4. Backdrops, die den Referenz-Nd enthalten, werden vergroessert. Alle
     anderen betroffenen Backdrops wandern komplett mit ihrem Inhalt mit.
"""

import nuke

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# True: Der Code wird bei jedem Tastendruck neu geladen (fuer die Entwicklung).
DEV_MODE = True

# Faktor fuer den grossen Schritt (Ctrl+Shift+Pfeil).
BIG_STEP_FACTOR = 4

# Umkreis fuer lose Nodes / StickyNotes / Backdrops in Rastereinheiten.
PROXIMITY_GRID_UNITS = 3

# Fallback-Werte, falls die Preferences nicht gelesen werden koennen.
DEFAULT_GRID_WIDTH = 110
DEFAULT_GRID_HEIGHT = 24

# Fallback-Groessen fuer Nodes, die noch nicht gezeichnet wurden.
DEFAULT_NODE_SIZE = (80, 18)
DEFAULT_DOT_SIZE = (12, 12)

DOWN = 1
UP = -1

BACKDROP = "BackdropNode"
STICKY = "StickyNote"


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _grid_size():
    """Rasterbreite und -hoehe aus den Nuke-Preferences."""
    try:
        prefs = nuke.toNode("preferences")
        return (int(prefs["GridWidth"].value()) or DEFAULT_GRID_WIDTH,
                int(prefs["GridHeight"].value()) or DEFAULT_GRID_HEIGHT)
    except Exception:
        return DEFAULT_GRID_WIDTH, DEFAULT_GRID_HEIGHT


def _current_group():
    """Die Gruppe, in deren Node Graph zuletzt gearbeitet wurde."""
    try:
        group = nuke.lastHitGroup()
    except Exception:
        group = None
    return group or nuke.root()


def _rect(node):
    """(x, y, w, h) eines Nodes im Node Graph."""
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
    """True, wenn der Mittelpunkt echt unterhalb (DOWN) bzw. oberhalb (UP) liegt."""
    return (_center(node)[1] - ref_cy) * direction > 0


def _contains(backdrop, point):
    x, y, w, h = _rect(backdrop)
    px, py = point
    return x <= px <= x + w and y <= py <= y + h


def _is_near(a, b, margin_x, margin_y):
    """True, wenn sich die um den Umkreis erweiterte Box von a mit b ueberschneidet."""
    ax, ay, aw, ah = _rect(a)
    bx, by, bw, bh = _rect(b)
    return (ax - margin_x < bx + bw and bx < ax + aw + margin_x and
            ay - margin_y < by + bh and by < ay + ah + margin_y)


def _hides_inputs(node):
    knob = node.knob("hide_input")
    return bool(knob and knob.value())


def _connections(nodes):
    """Pipe-Nachbarn je Node sowie die Menge aller Nodes mit irgendeiner Verbindung.

    Fuer die Suche zaehlen nur sichtbare Pipes. "Lose" ist ein Node aber nur,
    wenn er gar keine Verbindung hat, auch keine versteckte.
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
# Sammeln der zu verschiebenden Nodes
# ---------------------------------------------------------------------------

def _collect_connected(ref, neighbours, direction):
    """Alle ueber Pipes durchgaengig erreichbaren Nodes jenseits des Referenz-Nd."""
    ref_cy = _center(ref)[1]
    found = {}
    visited = {ref.name()}
    stack = [ref]
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


def collect(ref, nodes, direction, grid=None):
    """Ermittelt, was verschoben und was vergroessert wird.

    Rueckgabe: (zu verschiebende Nodes als dict name->node,
                zu vergroessernde Backdrops als Liste)
    """
    grid_w, grid_h = grid or _grid_size()
    margin_x = PROXIMITY_GRID_UNITS * grid_w
    margin_y = PROXIMITY_GRID_UNITS * grid_h
    ref_center = _center(ref)
    ref_cy = ref_center[1]

    neighbours, connected = _connections(nodes)

    # 1. Verbundene Nodes (inkl. seitlicher Zweige und Viewer).
    moved = _collect_connected(ref, neighbours, direction)
    anchors = list(moved.values())

    # 2. Lose Nodes und StickyNotes im Umkreis (keine Kettenreaktion).
    for node in nodes:
        name = node.name()
        if name in moved or name == ref.name() or name in connected:
            continue
        if node.Class() == BACKDROP:
            continue
        if not _is_beyond(node, ref_cy, direction):
            continue
        if any(_is_near(anchor, node, margin_x, margin_y) for anchor in anchors):
            moved[name] = node

    # 3. Backdrops.
    backdrops = [n for n in nodes if n.Class() == BACKDROP]
    grow = [b for b in backdrops if _contains(b, ref_center)]
    grow_names = {b.name() for b in grow}

    moved_centers = [_center(n) for n in moved.values()]
    moving_backdrops = []
    for backdrop in backdrops:
        if backdrop.name() in grow_names:
            continue
        holds_moved = any(_contains(backdrop, c) for c in moved_centers)
        is_near = (_is_beyond(backdrop, ref_cy, direction) and
                   any(_is_near(anchor, backdrop, margin_x, margin_y)
                       for anchor in anchors))
        if holds_moved or is_near:
            moving_backdrops.append(backdrop)

    # Wandernde Backdrops nehmen ihren gesamten Inhalt mit.
    excluded = grow_names | {ref.name()}
    for backdrop in moving_backdrops:
        moved[backdrop.name()] = backdrop
        for node in nodes:
            if node.name() in excluded or node.name() in moved:
                continue
            if _contains(backdrop, _center(node)):
                moved[node.name()] = node

    return moved, grow


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------

def make_space(direction=DOWN, factor=1):
    """Schafft Platz unter (DOWN) bzw. ueber (UP) dem selektierten Node."""
    with _current_group():
        selection = nuke.selectedNodes()
        if len(selection) != 1:
            return
        ref = selection[0]
        if ref.Class() in (BACKDROP, STICKY):
            return

        grid = _grid_size()
        step = grid[1] * factor
        moved, grow = collect(ref, nuke.allNodes(), direction, grid)

        undo = nuke.Undo()
        undo.begin("MakeSpace")
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
