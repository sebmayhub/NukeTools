"""smaAlignNodes - aligns the selected nodes with a mouse gesture.

Nuke 13+ / Python 3.7+ (PySide2 or PySide6)

Hold GESTURE_MODIFIERS (default Alt+Shift), press the left mouse button in a
Node Graph, drag and release:

  up    -> all selected nodes move to the height of the highest one
  down  -> all selected nodes move to the height of the lowest one
  left  -> all selected nodes move to the column of the leftmost one
  right -> all selected nodes move to the column of the rightmost one

Nodes are aligned by their center, so nodes of different size (Dots, nodes
with labels or postage stamps) end up on one line. The dominant axis of the
drag decides the direction; drags shorter than MIN_DISTANCE screen pixels do
nothing. Backdrops are ignored. Every gesture is a single undo step.

With nothing selected the gesture does not start and the click is passed on
to Nuke unchanged.
"""

import nuke

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

__version__ = "1.0.0"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Modifier keys that must be held when pressing the left mouse button.
# Possible values: QtCore.Qt.ShiftModifier, ControlModifier, AltModifier,
# MetaModifier, combined with "|".
GESTURE_MODIFIERS = QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier

# Minimum drag distance in screen pixels (independent of the Node Graph zoom).
MIN_DISTANCE = 50

# True: the code is reloaded on every gesture (for development) and the
# Script Editor shows what happened.
DEV_MODE = False

# Node classes that are never moved.
IGNORED_CLASSES = ("BackdropNode",)

UP, DOWN, LEFT, RIGHT = "up", "down", "left", "right"


# ---------------------------------------------------------------------------
# Logic (no Qt)
# ---------------------------------------------------------------------------

def direction_from_delta(dx, dy, min_distance=MIN_DISTANCE):
    """Returns the gesture direction for a screen-space drag, or None.

    Screen y grows downwards, like the Node Graph.
    """
    if max(abs(dx), abs(dy)) < min_distance:
        return None
    if abs(dx) > abs(dy):
        return RIGHT if dx > 0 else LEFT
    return DOWN if dy > 0 else UP


def _center(node, axis):
    if axis == 0:
        return node.xpos() + node.screenWidth() / 2.0
    return node.ypos() + node.screenHeight() / 2.0


def align(nodes, direction):
    """Moves the nodes so their centers line up with the outermost node."""
    nodes = [n for n in nodes if n.Class() not in IGNORED_CLASSES]
    if len(nodes) < 2:
        return
    axis = 0 if direction in (LEFT, RIGHT) else 1
    pick = min if direction in (LEFT, UP) else max
    target = pick(_center(n, axis) for n in nodes)
    for n in nodes:
        if axis == 0:
            n.setXpos(int(round(target - n.screenWidth() / 2.0)))
        else:
            n.setYpos(int(round(target - n.screenHeight() / 2.0)))


def _group():
    try:
        return nuke.lastHitGroup()
    except Exception:
        return nuke.root()


def selected_nodes():
    with _group():
        return [n for n in nuke.selectedNodes() if n.Class() not in IGNORED_CLASSES]


def run(direction):
    """Aligns the selected nodes of the current Node Graph as one undo step."""
    with _group():
        nodes = [n for n in nuke.selectedNodes() if n.Class() not in IGNORED_CLASSES]
        if len(nodes) < 2:
            return
        undo = nuke.Undo()
        undo.begin("Align Nodes " + direction)
        try:
            align(nodes, direction)
        finally:
            undo.end()
    if DEV_MODE:
        print("smaAlignNodes: aligned %d nodes %s" % (len(nodes), direction))


# ---------------------------------------------------------------------------
# Mouse gesture (Qt)
# ---------------------------------------------------------------------------

def _is_dag(widget):
    """True if the widget belongs to a Node Graph (main or group)."""
    while widget is not None:
        if widget.objectName().startswith("DAG"):
            return True
        widget = widget.parentWidget()
    return False


def _gesture_module():
    if not DEV_MODE:
        return globals()
    import importlib
    import smaAlignNodes
    return vars(importlib.reload(smaAlignNodes))


class GestureFilter(QtCore.QObject):
    """Application-wide event filter; only reacts inside Node Graphs."""

    def __init__(self, parent=None):
        super(GestureFilter, self).__init__(parent)
        self._start = None

    def eventFilter(self, obj, event):
        etype = event.type()
        if self._start is not None:
            if etype == QtCore.QEvent.MouseMove:
                return True
            if etype == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                end = QtGui.QCursor.pos()
                dx, dy = end.x() - self._start.x(), end.y() - self._start.y()
                self._start = None
                mod = _gesture_module()
                direction = mod["direction_from_delta"](dx, dy, mod["MIN_DISTANCE"])
                if direction:
                    mod["run"](direction)
                return True
            return False

        if (etype == QtCore.QEvent.MouseButtonPress
                and event.button() == QtCore.Qt.LeftButton
                and event.modifiers() == GESTURE_MODIFIERS
                and isinstance(obj, QtWidgets.QWidget)
                and _is_dag(obj)
                and selected_nodes()):
            self._start = QtGui.QCursor.pos()
            return True
        return False


_filter = None


def install():
    """Installs the gesture filter once (called from menu.py)."""
    global _filter
    app = QtWidgets.QApplication.instance()
    if app is None or _filter is not None:
        return
    _filter = GestureFilter(app)
    app.installEventFilter(_filter)
