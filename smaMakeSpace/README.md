# smaMakeSpace

Nuke tool (16.0v3) that makes or closes space in the Node Graph below or above a selected node.

## Usage

Select exactly one node or Dot (the reference node), then in the Node Graph:

| Shortcut | Action |
| --- | --- |
| `Shift+↓` | Make space below: push everything below one grid height down |
| `Shift+↑` | Make space above: push everything above one grid height up |
| `Ctrl+Shift+↓` | Close space below: pull everything below one grid height up |
| `Ctrl+Shift+↑` | Close space above: pull everything above one grid height down |

Each key press is a separate undo step (`Ctrl+Z`). The commands are also available in the
Node Graph right-click menu under **smaMakeSpace**.

## Making space (described for "below", "above" is mirrored)

- The reference node stays in place.
- All nodes that are continuously connected to the reference node via real pipes (incl. masks,
  excluding hidden inputs) and whose center lies below it are moved – including side branches
  and viewers. A branch ends at the first node at the same height or above. Nodes whose
  center deviates by at most 10 units vertically (`SAME_HEIGHT_TOLERANCE`) count as
  "same height", so slightly offset horizontal connections stay in place.
- Loose nodes (without connections) and StickyNotes within 3 grid units of moved nodes are
  moved along.
- Backdrops around the reference node are enlarged; all other affected backdrops move
  completely, together with their contents.
- Nothing is pushed onto anything else: whatever below the reference node a moved node, a
  moved backdrop or a growing backdrop would overlap (or get closer to than
  `COLLISION_GAP` = 12 units) is pushed along – a node together with its whole pipe below
  the reference node, a backdrop with its entire contents. This repeats until nothing
  collides. Overlaps that already existed before the move are left alone.

## Closing space

The reverse of making space: the same items are pulled one grid height towards the reference
node, and the backdrops around it shrink. Closing never makes anything overlap:

- Nodes connected to the reference node, and the backdrops holding them, are mandatory. If
  one of them would get too close to something that does not move, the key press is ignored.
- Everything else (loose nodes, pipes and backdrops that are merely nearby or in the way)
  just follows. A follower that is blocked stays behind, together with its pipe / backdrop.
- "Too close" means:
  - nodes above each other keep at least one grid height between their centers
    (neighbouring grid rows),
  - everything keeps at least `MIN_GAP` = 6 units of free space,
  - no node crosses the height of the reference node,
  - a shrinking backdrop keeps everything inside that does not move.

With `DEV_MODE = True` the Script Editor shows what blocked an ignored key press.

## Installation

In `~/.nuke/init.py`:

```python
nuke.pluginAddPath("D:/AI/Claude/NukeTools/smaMakeSpace")  # path to this folder
```

Configuration (tolerances, gaps, proximity radius, `DEV_MODE`) is at the top of
`smaMakeSpace.py`. With `DEV_MODE = True` the code is reloaded on every key press.

## Tests

```bash
python -m unittest discover -s tests
```
