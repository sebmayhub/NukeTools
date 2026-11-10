# smaAlignNodes

Nuke tool (13 and later) that aligns the selected nodes in the Node Graph with a mouse gesture.

Version 1.0.0 – see the [changelog](CHANGELOG.md).

## Usage

Select the nodes to align, then in the Node Graph hold `Alt+Shift`, press the left mouse
button, drag in one direction and release:

| Drag | Result |
| --- | --- |
| up | all selected nodes move to the height of the highest selected node |
| down | all selected nodes move to the height of the lowest selected node |
| left | all selected nodes move to the column of the leftmost selected node |
| right | all selected nodes move to the column of the rightmost selected node |

- Nodes are aligned by their **center**, so Dots and nodes of different height end up on one line.
- The dominant axis of the drag decides; diagonal drags count as whichever axis moved more.
- Drags shorter than 50 screen pixels (`MIN_DISTANCE`) do nothing. The distance is measured
  on screen, so the Node Graph zoom does not matter.
- With nothing selected the gesture does not start and Nuke gets the click as usual.
- Backdrops are ignored. Every gesture is a single undo step (`Ctrl+Z`).
- Works in the main Node Graph and in group Node Graphs.

## Installation

In `~/.nuke/init.py`:

```python
nuke.pluginAddPath("D:/AI/Claude/NukeTools/smaAlignNodes")  # path to this folder
```

Configuration (`GESTURE_MODIFIERS`, `MIN_DISTANCE`, `DEV_MODE`) is at the top of
`smaAlignNodes.py`. With `DEV_MODE = True` the logic is reloaded on every gesture and the
Script Editor reports what happened.

## Tests

```bash
python -m unittest discover -s tests
```
