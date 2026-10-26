"""Restore a local SQL Server backup temporarily and export its catalog as JSON."""

import json
import os
import time
from pathlib import Path

import pymssql


OUT = Path(__file__).with_name("schema.json")
PASSWORD = os.environ["MANTRA_SQL_PASSWORD"]


def connect(database="master"):
    for attempt in range(60):
        try:
            return pymssql.connect(
                server="127.0.0.1",
                port=14333,
                user="sa",
                password=PASSWORD,
                database=database,
                autocommit=True,
                as_dict=True,
                login_timeout=5,
                timeout=120,
            )
        except pymssql.OperationalError:
            if attempt == 59:
                raise
            time.sleep(2)


def fetch(connection, query):
    cursor = connection.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return result


with connect() as conn:
    files = fetch(conn, "RESTORE FILELISTONLY FROM DISK = '/backup/BD_MANTRA.bak'")
    print("Backup files:", [(f["LogicalName"], f["Type"]) for f in files])
    moves = []
    for f in files:
        extension = "ldf" if f["Type"] == "L" else "mdf"
        logical = f["LogicalName"].replace("'", "''")
        target = f"/var/opt/mssql/data/mantra_{len(moves)}.{extension}"
        moves.append(f"MOVE N'{logical}' TO N'{target}'")
    restore = "RESTORE DATABASE [MANTRA_DIAGRAM] FROM DISK = '/backup/BD_MANTRA.bak' WITH " + ", ".join(moves) + ", REPLACE, RECOVERY"
    cursor = conn.cursor()
    cursor.execute(restore)
    while cursor.nextset():
        pass
    cursor.close()

with connect("MANTRA_DIAGRAM") as conn:
    tables = fetch(conn, """
        SELECT s.name AS schema_name, t.name AS table_name, t.object_id
        FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
        WHERE t.is_ms_shipped = 0 ORDER BY s.name, t.name
    """)
    columns = fetch(conn, """
        SELECT c.object_id, c.column_id, c.name AS column_name,
               ty.name AS type_name, c.max_length, c.precision, c.scale,
               c.is_nullable, c.is_identity, c.is_computed,
               dc.definition AS default_definition
        FROM sys.columns c
        JOIN sys.types ty ON ty.user_type_id = c.user_type_id
        LEFT JOIN sys.default_constraints dc ON dc.object_id = c.default_object_id
        WHERE c.object_id IN (SELECT object_id FROM sys.tables WHERE is_ms_shipped = 0)
        ORDER BY c.object_id, c.column_id
    """)
    indexes = fetch(conn, """
        SELECT i.object_id, i.name AS index_name, i.is_primary_key, i.is_unique,
               ic.key_ordinal, c.name AS column_name
        FROM sys.indexes i
        JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE i.object_id IN (SELECT object_id FROM sys.tables WHERE is_ms_shipped = 0)
          AND (i.is_primary_key = 1 OR i.is_unique = 1) AND ic.key_ordinal > 0
        ORDER BY i.object_id, i.index_id, ic.key_ordinal
    """)
    foreign_keys = fetch(conn, """
        SELECT fk.name AS fk_name, fk.parent_object_id, fk.referenced_object_id,
               fkc.constraint_column_id, pc.name AS parent_column, rc.name AS referenced_column,
               fk.delete_referential_action_desc AS on_delete,
               fk.update_referential_action_desc AS on_update
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
        JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
        JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
        ORDER BY fk.name, fkc.constraint_column_id
    """)

names = {t["object_id"]: f'{t["schema_name"]}.{t["table_name"]}' for t in tables}


def data_type(c):
    name = c["type_name"]
    if name in ("varchar", "char", "varbinary", "binary"):
        size = "max" if c["max_length"] == -1 else str(c["max_length"])
        return f"{name}({size})"
    if name in ("nvarchar", "nchar"):
        size = "max" if c["max_length"] == -1 else str(c["max_length"] // 2)
        return f"{name}({size})"
    if name in ("decimal", "numeric"):
        return f'{name}({c["precision"]},{c["scale"]})'
    if name in ("datetime2", "datetimeoffset", "time"):
        return f'{name}({c["scale"]})'
    return name


schema = {"database": "MANTRA_DIAGRAM", "tables": [], "foreign_keys": []}
for t in tables:
    object_id = t["object_id"]
    table_indexes = {}
    for i in indexes:
        if i["object_id"] == object_id:
            record = table_indexes.setdefault(i["index_name"], {
                "name": i["index_name"],
                "primary_key": bool(i["is_primary_key"]),
                "unique": bool(i["is_unique"]),
                "columns": [],
            })
            record["columns"].append(i["column_name"])
    primary_columns = {c for i in table_indexes.values() if i["primary_key"] for c in i["columns"]}
    schema["tables"].append({
        "name": names[object_id],
        "schema": t["schema_name"],
        "columns": [{
            "name": c["column_name"],
            "type": data_type(c),
            "nullable": bool(c["is_nullable"]),
            "identity": bool(c["is_identity"]),
            "computed": bool(c["is_computed"]),
            "default": c["default_definition"],
            "primary_key": c["column_name"] in primary_columns,
        } for c in columns if c["object_id"] == object_id],
        "indexes": list(table_indexes.values()),
    })

fk_groups = {}
for row in foreign_keys:
    key = row["fk_name"]
    group = fk_groups.setdefault(key, {
        "name": key,
        "from_table": names[row["parent_object_id"]],
        "to_table": names[row["referenced_object_id"]],
        "column_pairs": [],
        "on_delete": row["on_delete"],
        "on_update": row["on_update"],
    })
    group["column_pairs"].append([row["parent_column"], row["referenced_column"]])
schema["foreign_keys"] = list(fk_groups.values())

OUT.write_text(json.dumps(schema, ensure_ascii=False, indent=2, default=str) + "\n")
print(f'Exported {len(tables)} tables, {len(columns)} columns, {len(fk_groups)} foreign keys to {OUT}')
