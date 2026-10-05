"""Registers the smaMakeSpace shortcuts in the Node Graph."""

import importlib

import nuke


def _run(action, direction):
    import smaMakeSpace
    if smaMakeSpace.DEV_MODE:
        smaMakeSpace = importlib.reload(smaMakeSpace)
    getattr(smaMakeSpace, action)(direction)


_menu = nuke.menu("Node Graph").addMenu("smaMakeSpace")
_menu.addCommand("Make Space Below", lambda: _run("make_space", 1), "Shift+Down", shortcutContext=2)
_menu.addCommand("Make Space Above", lambda: _run("make_space", -1), "Shift+Up", shortcutContext=2)
# For closing, the arrow is the direction the nodes move in.
_menu.addCommand("Close Space Below", lambda: _run("close_space", 1), "Ctrl+Shift+Up", shortcutContext=2)
_menu.addCommand("Close Space Above", lambda: _run("close_space", -1), "Ctrl+Shift+Down", shortcutContext=2)
