# Changelog

All notable changes to smaAlignNodes. Versions follow `MAJOR.MINOR.PATCH`:
PATCH for fixes, MINOR for new features, MAJOR for changes that alter existing behaviour
or the gesture. The current version is also available as `smaAlignNodes.__version__`.

## 1.0.0 – 2026-11-10

First release.

- Align the selected nodes with a mouse gesture (`Alt+Shift` + left-drag) in any Node Graph,
  including group graphs: up/down aligns to the highest/lowest node, left/right to the
  leftmost/rightmost node.
- Nodes are aligned by their center; the dominant drag axis decides the direction.
- Minimum drag distance of 50 screen pixels (`MIN_DISTANCE`), independent of zoom.
- Backdrops are ignored. Every gesture is a single undo step.
- Runs on Nuke 13 and later (PySide2 and PySide6).
