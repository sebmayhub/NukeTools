"""Registriert die MakeSpace-Tastenkuerzel im Node Graph."""

import importlib

import nuke


def _run(direction, big=False):
    import makespace
    if makespace.DEV_MODE:
        makespace = importlib.reload(makespace)
    factor = makespace.BIG_STEP_FACTOR if big else 1
    makespace.make_space(direction, factor)


_menu = nuke.menu("Node Graph").addMenu("MakeSpace")
_menu.addCommand("Space Down", lambda: _run(1), "Shift+Down", shortcutContext=2)
_menu.addCommand("Space Up", lambda: _run(-1), "Shift+Up", shortcutContext=2)
_menu.addCommand("Space Down (big)", lambda: _run(1, True), "Ctrl+Shift+Down", shortcutContext=2)
_menu.addCommand("Space Up (big)", lambda: _run(-1, True), "Ctrl+Shift+Up", shortcutContext=2)
