# smaTools

A collection of custom tools for Foundry Nuke. Each tool lives in its own folder and states
the Nuke versions it supports in its README. The GitHub repository is called
[NukeTools](https://github.com/sebmayhub/NukeTools); locally it is checked out as
`~/.nuke/smaTools`.

| Tool | Version | Description |
| --- | --- | --- |
| [smaAlignNodes](smaAlignNodes) | 1.0.0 | Aligns the selected nodes horizontally or vertically via mouse gesture (Alt+Shift + drag). |
| [smaMakeSpace](smaMakeSpace) | 1.2.0 | Makes or closes space in the Node Graph next to a selected node (in all four directions) via shortcut. |

Each tool is versioned on its own; releases are tagged as `<tool>-v<version>`.

## Installation

Clone the repository into the Nuke user folder as `smaTools`:

```bash
git clone https://github.com/sebmayhub/NukeTools.git ~/.nuke/smaTools
```

Then add one line per tool to `~/.nuke/init.py` (relative paths resolve against `~/.nuke`):

```python
nuke.pluginAddPath("./smaTools/smaAlignNodes")
nuke.pluginAddPath("./smaTools/smaMakeSpace")
```

See each tool's README for details.
