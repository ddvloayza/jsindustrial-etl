"""Build an editable Excalidraw ER diagram and an SVG preview from schema.json."""

import html
import json
import math
import random
from pathlib import Path


ROOT = Path(__file__).parent
SCHEMA = json.loads((ROOT / "schema.json").read_text())
RNG = random.Random(20261024)
ELEMENTS = []
SVG = []

COLORS = {
    "ink": "#172554",
    "muted": "#475569",
    "line": "#94a3b8",
    "header": "#1e3a8a",
    "body": "#ffffff",
    "page": "#f8fafc",
    "pk": "#1d4ed8",
    "fk": "#0f766e",
}


def common(kind, x, y, width, height, group=None):
    return {
        "id": f"mantra-{len(ELEMENTS):04d}",
        "type": kind,
        "x": x, "y": y, "width": width, "height": height,
        "angle": 0,
        "strokeColor": COLORS["ink"],
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [group] if group else [],
        "frameId": None,
        "roundness": None,
        "seed": RNG.randrange(1, 2**31),
        "version": 1,
        "versionNonce": RNG.randrange(1, 2**31),
        "isDeleted": False,
        "boundElements": None,
        "updated": 1792886400000,
        "link": None,
        "locked": False,
    }


def rectangle(x, y, w, h, fill, stroke, group=None, sw=1):
    e = common("rectangle", x, y, w, h, group)
    e.update(backgroundColor=fill, strokeColor=stroke, strokeWidth=sw)
    ELEMENTS.append(e)
    SVG.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" rx="6"/>')


def text(x, y, value, size=15, color=None, bold=False, mono=False, group=None, width=None):
    color = color or COLORS["ink"]
    width = width or max(20, len(value) * size * (0.6 if mono else 0.55))
    height = size * 1.35
    e = common("text", x, y, width, height, group)
    e.update(
        strokeColor=color, text=value, originalText=value, fontSize=size,
        fontFamily=3 if mono else 1, textAlign="left", verticalAlign="top",
        containerId=None, autoResize=False, lineHeight=1.25,
    )
    ELEMENTS.append(e)
    family = "monospace" if mono else "Arial, sans-serif"
    weight = "700" if bold else "400"
    SVG.append(f'<text x="{x}" y="{y + size}" fill="{color}" font-family="{family}" font-size="{size}" font-weight="{weight}" xml:space="preserve">{html.escape(value)}</text>')


def line(x1, y1, x2, y2, color, sw=1, group=None):
    e = common("line", x1, y1, abs(x2-x1), abs(y2-y1), group)
    e.update(strokeColor=color, strokeWidth=sw, points=[[0, 0], [x2-x1, y2-y1]], lastCommittedPoint=None, startBinding=None, endBinding=None, startArrowhead=None, endArrowhead=None)
    ELEMENTS.append(e)
    SVG.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"/>')


def row_label(column, foreign_columns):
    marker = "PK/FK" if column["primary_key"] and column["name"] in foreign_columns else ("PK" if column["primary_key"] else ("FK" if column["name"] in foreign_columns else ""))
    nullability = "NULL" if column["nullable"] else "NOT NULL"
    return f'{marker:<5} {column["name"]:<21} {column["type"]:<16} {nullability}'


text(70, 35, "MANTRA  ·  DIAGRAMA DE ENTIDADES", 30, COLORS["ink"], bold=True)
text(72, 82, "Esquema dbo  |  2 tablas  |  108 campos  |  1 relación declarada", 17, COLORS["muted"])

layout = {
    "dbo.CotizacionesC": (70, 150),
    "dbo.CotizacionesD": (1320, 150),
}
CARD_WIDTH = 1050
HEADER_HEIGHT = 82
ROW_HEIGHT = 26
BODY_TOP = 100
COL_WIDTH = 507

# Relationship is drawn behind the entity cards.
line(1120, 290, 1320, 290, COLORS["fk"], 3)
text(1162, 244, "1 : N", 20, COLORS["fk"], bold=True)
text(1134, 310, "codidtcot", 16, COLORS["fk"], mono=True)
text(1129, 348, "FK en detalle", 13, COLORS["muted"])

foreign_columns = {}
for fk in SCHEMA["foreign_keys"]:
    foreign_columns.setdefault(fk["from_table"], set()).update(pair[0] for pair in fk["column_pairs"])

for table in SCHEMA["tables"]:
    name = table["name"]
    x, y = layout[name]
    group = f'entity-{name.replace(".", "-")}'
    columns = table["columns"]
    half = math.ceil(len(columns) / 2)
    rows = half
    body_height = BODY_TOP + rows * ROW_HEIGHT + 22
    rectangle(x, y, CARD_WIDTH, body_height, COLORS["body"], COLORS["line"], group, 2)
    rectangle(x, y, CARD_WIDTH, HEADER_HEIGHT, COLORS["header"], COLORS["header"], group, 1)
    text(x + 24, y + 13, name, 25, "#ffffff", bold=True, group=group)
    primary_columns = [c for i in table["indexes"] if i["primary_key"] for c in i["columns"]]
    subtitle = f'{len(columns)} campos  ·  PK: {", ".join(primary_columns)}'
    text(x + 25, y + 51, subtitle, 14, "#dbeafe", group=group)
    line(x + 21, y + 93, x + CARD_WIDTH - 21, y + 93, COLORS["line"], 1, group)
    line(x + 526, y + 105, x + 526, y + body_height - 17, "#e2e8f0", 1, group)

    for idx, column in enumerate(columns):
        column_number = 0 if idx < half else 1
        row = idx if idx < half else idx - half
        tx = x + 24 + column_number * COL_WIDTH
        ty = y + BODY_TOP + row * ROW_HEIGHT
        color = COLORS["pk"] if column["primary_key"] else (COLORS["fk"] if column["name"] in foreign_columns.get(name, set()) else COLORS["ink"])
        text(tx, ty, row_label(column, foreign_columns.get(name, set())), 15, color, mono=True, group=group, width=480)

legend_y = 1180
text(70, legend_y, "LEYENDA", 17, COLORS["ink"], bold=True)
text(70, legend_y + 31, "PK = clave primaria     FK = clave foránea     NULL / NOT NULL = permite / no permite valores nulos", 15, COLORS["muted"], mono=True)
text(70, legend_y + 61, "CotizacionesD.codidtcot → CotizacionesC.codidtcot   |   Una cabecera puede tener varios renglones de detalle.", 15, COLORS["fk"])
text(70, legend_y + 89, "Fuente: backup BD_MANTRA.bak; las relaciones mostradas son las declaradas en SQL Server.", 14, COLORS["muted"])

excalidraw = {
    "type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
    "elements": ELEMENTS,
    "appState": {"viewBackgroundColor": COLORS["page"], "gridSize": None},
    "files": {},
}
(ROOT / "BD_MANTRA_ER.excalidraw").write_text(json.dumps(excalidraw, ensure_ascii=False, indent=2) + "\n")

svg = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="2440" height="1320" viewBox="0 0 2440 1320">'
    f'<rect width="2440" height="1320" fill="{COLORS["page"]}"/>'
    + "\n".join(SVG) + "</svg>\n"
)
(ROOT / "BD_MANTRA_ER.svg").write_text(svg)
print(f'Wrote {len(ELEMENTS)} Excalidraw elements and SVG preview')
