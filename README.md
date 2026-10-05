# NukeTools

A collection of custom tools for Foundry Nuke (16.0v3). Each tool lives in its own folder.

| Tool | Version | Description |
| --- | --- | --- |
| [smaMakeSpace](smaMakeSpace) | 1.0.0 | Makes or closes space in the Node Graph next to a selected node (in all four directions) via shortcut. |

Each tool is versioned on its own; releases are tagged as `<tool>-v<version>`.

## Installation

Add one line per tool to `~/.nuke/init.py`, e.g.:

```python
nuke.pluginAddPath("D:/AI/Claude/NukeTools/smaMakeSpace")
```

See each tool's README for details.
