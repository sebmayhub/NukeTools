"""Registriert die smaMakeSpace-Tastenkuerzel im Node Graph."""

import importlib

import nuke


def _run(direction, big=False):
    import smaMakeSpace
    if smaMakeSpace.DEV_MODE:
        smaMakeSpace = importlib.reload(smaMakeSpace)
    factor = smaMakeSpace.BIG_STEP_FACTOR if big else 1
    smaMakeSpace.make_space(direction, factor)


_menu = nuke.menu("Node Graph").addMenu("smaMakeSpace")
_menu.addCommand("Space Down", lambda: _run(1), "Shift+Down", shortcutContext=2)
_menu.addCommand("Space Up", lambda: _run(-1), "Shift+Up", shortcutContext=2)
_menu.addCommand("Space Down (big)", lambda: _run(1, True), "Ctrl+Shift+Down", shortcutContext=2)
_menu.addCommand("Space Up (big)", lambda: _run(-1, True), "Ctrl+Shift+Up", shortcutContext=2)
