# MakeSpace

Nuke-Tool (16.0v3), das im Node Graph Platz unter bzw. über einem selektierten Node schafft.

## Bedienung

Genau einen Node oder Dot selektieren (Referenz-Node), dann im Node Graph:

| Kürzel | Aktion |
| --- | --- |
| `Shift+↓` | Platz nach unten (1 Rasterhöhe) |
| `Shift+↑` | Platz nach oben (1 Rasterhöhe) |
| `Ctrl+Shift+↓` / `Ctrl+Shift+↑` | dasselbe mit 4-facher Schrittweite |

Jeder Tastendruck ist ein eigener Undo-Schritt (`Ctrl+Z`). Die Befehle stehen auch im
Rechtsklick-Menü des Node Graph unter **MakeSpace**.

## Regeln (für „nach unten“, „nach oben“ ist gespiegelt)

- Der Referenz-Node bleibt stehen.
- Verschoben werden alle Nodes, die über echte Pipes (inkl. Masken, ohne Hidden Inputs)
  durchgängig mit dem Referenz-Node verbunden sind und deren Mittelpunkt unterhalb von ihm
  liegt – auch seitliche Zweige und Viewer. Ein Zweig endet am ersten Node auf gleicher Höhe
  oder darüber.
- Lose Nodes (ohne Verbindungen) und StickyNotes im Umkreis von 3 Rastereinheiten um
  verschobene Nodes werden mitgenommen.
- Backdrops um den Referenz-Node werden vergrößert; alle anderen betroffenen Backdrops
  wandern komplett mit ihrem Inhalt mit.

## Installation

In `~/.nuke/init.py`:

```python
nuke.pluginAddPath("D:/AI/Claude/MakeSpace")  # Pfad zu diesem Ordner
```

Konfiguration (Schrittfaktor, Umkreis, `DEV_MODE`) oben in `makespace.py`.
Mit `DEV_MODE = True` wird der Code bei jedem Tastendruck neu geladen.

## Tests

```bash
python -m unittest discover -s tests
```
