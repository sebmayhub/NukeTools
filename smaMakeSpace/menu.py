"""Registers the smaMakeSpace shortcuts in the Node Graph."""

import importlib

import nuke


def _run(action, direction):
    import smaMakeSpace
    if smaMakeSpace.DEV_MODE:
        smaMakeSpace = importlib.reload(smaMakeSpace)
    getattr(smaMakeSpace, action)(getattr(smaMakeSpace, direction))


_menu = nuke.menu("Node Graph").addMenu("smaMakeSpace")

# The arrow is always the direction the nodes move in: making space pushes the
# nodes on that side away, closing space pulls the nodes on the opposite side in.
for _label, _action, _direction, _shortcut in (
    ("Make Space Below", "make_space", "DOWN", "Shift+Down"),
    ("Make Space Above", "make_space", "UP", "Shift+Up"),
    ("Make Space Right", "make_space", "RIGHT", "Shift+Right"),
    ("Make Space Left", "make_space", "LEFT", "Shift+Left"),
    ("Close Space Below", "close_space", "DOWN", "Ctrl+Shift+Up"),
    ("Close Space Above", "close_space", "UP", "Ctrl+Shift+Down"),
    ("Close Space Right", "close_space", "RIGHT", "Ctrl+Shift+Left"),
    ("Close Space Left", "close_space", "LEFT", "Ctrl+Shift+Right"),
):
    _menu.addCommand(_label, lambda a=_action, d=_direction: _run(a, d),
                     _shortcut, shortcutContext=2)
