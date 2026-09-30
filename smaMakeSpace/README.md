# smaMakeSpace

Nuke tool (16.0v3) that makes space in the Node Graph below or above a selected node.

## Usage

Select exactly one node or Dot (the reference node), then in the Node Graph:

| Shortcut | Action |
| --- | --- |
| `Shift+↓` | Make space downwards (1 grid height) |
| `Shift+↑` | Make space upwards (1 grid height) |
| `Ctrl+Shift+↓` / `Ctrl+Shift+↑` | Same with a 4× step |

Each key press is a separate undo step (`Ctrl+Z`). The commands are also available in the
Node Graph right-click menu under **smaMakeSpace**.

## Rules (described for "down", "up" is mirrored)

- The reference node stays in place.
- All nodes that are continuously connected to the reference node via real pipes (incl. masks,
  excluding hidden inputs) and whose center lies below it are moved – including side branches
  and viewers. A branch ends at the first node at the same height or above.
- Loose nodes (without connections) and StickyNotes within 3 grid units of moved nodes are
  moved along.
- Backdrops around the reference node are enlarged; all other affected backdrops move
  completely, together with their contents.

## Installation

In `~/.nuke/init.py`:

```python
nuke.pluginAddPath("D:/AI/Claude/NukeTools/smaMakeSpace")  # path to this folder
```

Configuration (step factor, proximity radius, `DEV_MODE`) is at the top of `smaMakeSpace.py`.
With `DEV_MODE = True` the code is reloaded on every key press.

## Tests

```bash
python -m unittest discover -s tests
```
