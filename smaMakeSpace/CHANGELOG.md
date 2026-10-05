# Changelog

All notable changes to smaMakeSpace. Versions follow `MAJOR.MINOR.PATCH`:
PATCH for fixes, MINOR for new features, MAJOR for changes that alter existing behaviour
or shortcuts. The current version is also available as `smaMakeSpace.__version__`.

## 1.0.0 – 2026-10-05

First versioned release.

- Make space next to the selected node in all four directions (`Shift+Arrow`): everything
  connected on that side is pushed one grid step away, including side branches and viewers.
- Close space again (`Ctrl+Shift+Arrow`): the same items are pulled back towards the
  selected node without anything ever overlapping.
- Vertically, closing ends at an even gap of `MIN_GAP` between nodes of any height.
- Nodes level with the selected node (within `ALIGN_TOLERANCE`) stay in place.
- Loose nodes and StickyNotes near moved nodes follow along.
- Backdrops around the selected node grow and shrink; other affected backdrops move with
  their entire contents.
- Nodes, pipes and backdrops in the way are pushed along instead of being overlapped.
- Every key press is a single undo step.
