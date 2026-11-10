# Changelog

All notable changes to smaMakeSpace. Versions follow `MAJOR.MINOR.PATCH`:
PATCH for fixes, MINOR for new features, MAJOR for changes that alter existing behaviour
or shortcuts. The current version is also available as `smaMakeSpace.__version__`.

## 1.2.0 – 2026-11-11

- With several nodes selected, a message asks to select exactly one node (confirm with
  Enter). With nothing selected the shortcuts still do nothing.
- Backdrops around the selected node only grow as far as needed to keep `BACKDROP_MARGIN`
  (36 units, two standard node heights) between their edge and their contents; a backdrop
  with more room stays as it is. Closing space shrinks a backdrop back only while it fits
  its contents that tightly.

## 1.1.0 – 2026-11-11

- Closing space vertically no longer stops completely when a connected node would pass the
  height of the selected node. The step is shortened so that node lands exactly level with
  the selected node; from then on it stays, and the remaining nodes keep coming closer.

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
