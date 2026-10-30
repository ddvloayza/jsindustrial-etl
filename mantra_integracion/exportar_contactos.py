"""Crea o actualiza contactos de SQL Server en Mantra. No envía mensajes.

El SP entrega un arreglo JSON con 20 campos personalizados y los datos de contacto.
El API guarda custom_1 a custom_20; nombre, teléfono y correo van aparte.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pymssql
import pyodbc
import requests
from dotenv import load_dotenv


BASE_URL = "https://wbpback.mantra.chat"
ALL_JSON_FIELDS = [
    "numero_cotizacion", "fecha", "cliente", "condicion_venta", "vendedor",
    "fuente_contacto", "referencia", "moneda", "total_documento",
    "estado_oferta", "total_moneda_nacional", "tasa_exito_cierre",
    "genero_orden_venta", "comentario", "usuario", "cargo", "area",
    "inventario_disponible", "porcentaje_inventario_disponible",
    "fecha_estimada_cierre", "nombre_contacto", "telefono", "email",
]


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    auth = config.get("sql", {}).get("authentication", "sql")
    if auth not in ("sql", "windows"):
        raise ValueError("sql.authentication debe ser 'sql' o 'windows'")
    custom = config.get("custom_fields", {})
    if not isinstance(custom, dict) or len(custom) > 20:
        raise ValueError("custom_fields debe contener como máximo 20 entradas")
    allowed = {f"custom_{i}" for i in range(1, 21)}
    if set(custom) - allowed:
        raise ValueError("Solo se permiten custom_1 a custom_20")
    missing = set(custom.values()) - set(ALL_JSON_FIELDS)
    if missing:
        raise ValueError(f"Propiedades JSON del SP no reconocidas: {sorted(missing)}")
    return config


def connect_sql(config: dict, *, query_timeout: int):
    sql = config["sql"]
    if sql.get("authentication", "sql") == "windows":
        driver = sql.get("odbc_driver", "ODBC Driver 18 for SQL Server")
        server = sql["server"]
        if sql.get("port"):
            server = f"{server},{int(sql['port'])}"
        connection = pyodbc.connect(
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={sql['database']};"
            "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=no;",
            timeout=10,
        )
        connection.timeout = query_timeout
        return connection
    if not os.getenv("MANTRA_SQL_USER") or not os.getenv("MANTRA_SQL_PASSWORD"):
        raise ValueError("Faltan MANTRA_SQL_USER o MANTRA_SQL_PASSWORD para autenticación SQL")
    return pymssql.connect(
        server=sql["server"], port=int(sql.get("port", 1433)),
        user=os.environ["MANTRA_SQL_USER"], password=os.environ["MANTRA_SQL_PASSWORD"],
        database=sql["database"], as_dict=True, login_timeout=10, timeout=query_timeout,
    )


def sql_placeholder(config: dict) -> str:
    return "?" if config["sql"].get("authentication", "sql") == "windows" else "%s"


def normalize_phone(raw: object, country_code: str) -> str | None:
    digits = re.sub(r"\D", "", str(raw or ""))
    if country_code == "51":
        if len(digits) == 11 and digits.startswith("51"):
            digits = digits[2:]
        if len(digits) != 9 or not digits.startswith("9"):
            return None
    elif not 6 <= len(digits) <= 15:
        return None
    return digits


def value_as_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    text = str(value).strip()
    return text or None


def build_contact(row: dict, config: dict) -> tuple[str, dict]:
    country_code = str(config.get("country_code", "51"))
    phone = normalize_phone(row.get("telefono"), country_code)
    if not phone:
        raise ValueError("Teléfono inválido o ausente")
    name = value_as_text(row.get("nombre_contacto")) or value_as_text(row.get("cliente"))
    if not name:
        raise ValueError("Nombre de contacto y cliente ausentes")
    data = {"name": name, "phone": phone, "countryCode": country_code}
    email = value_as_text(row.get("email"))
    if email and "@" in email:
        data["email"] = email
    for target, source in config.get("custom_fields", {}).items():
        value = value_as_text(row.get(source))
        if value is not None:
            data[target] = value
    return phone, data


def parse_contacts_json(payload: str) -> list[dict]:
    try:
        rows = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("El SP no devolvió JSON válido") from exc
    if not isinstance(rows, list):
        raise ValueError("El JSON debe ser un arreglo de contactos")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"El contacto {index + 1} no es un objeto JSON")
        missing = set(ALL_JSON_FIELDS) - set(row)
        if missing:
            raise ValueError(f"Al contacto {index + 1} le faltan propiedades: {sorted(missing)}")
        extra = set(row) - set(ALL_JSON_FIELDS)
        if extra:
            raise ValueError(f"El contacto {index + 1} tiene propiedades no exportables: {sorted(extra)}")
    return rows


def fetch_rows(config: dict, run_date: date) -> list[dict]:
    connection = connect_sql(config, query_timeout=120)
    try:
        cursor = connection.cursor()
        placeholder = sql_placeholder(config)
        cursor.execute(
            f"EXEC dbo.usp_ExportarCotizacionesMantra @FechaProceso={placeholder}, @ComoJson=1",
            (run_date,),
        )
        rows = cursor.fetchall()
        if rows and not isinstance(rows[0], dict):
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in rows]
        if len(rows) != 1 or not {"payload_json", "ids_json"} <= set(rows[0]):
            raise RuntimeError("El SP debe devolver payload_json e ids_json")
        contacts = parse_contacts_json(rows[0]["payload_json"])
        ids = json.loads(rows[0]["ids_json"])
        if not isinstance(ids, list) or len(ids) != len(contacts):
            raise RuntimeError("Los IDs internos no coinciden con los contactos")
        seen = set()
        for contact, item in zip(contacts, ids):
            key = item.get("codidtcot") if isinstance(item, dict) else None
            phone = item.get("telefono") if isinstance(item, dict) else None
            if (not isinstance(key, str) or not key.strip()
                    or not isinstance(phone, str) or not re.fullmatch(r"9\d{8}", phone)
                    or phone in seen):
                raise RuntimeError("El SP devolvió un ID o teléfono inválido o duplicado")
            seen.add(phone)
            contact["_codidtcot"] = key
            contact["_telefono_normalizado"] = phone
        return contacts
    finally:
        connection.close()


def confirm_sent(config: dict, codidtcot: str, phone: str, http_status: int) -> None:
    connection = connect_sql(config, query_timeout=30)
    try:
        cursor = connection.cursor()
        placeholder = sql_placeholder(config)
        cursor.execute(
            f"EXEC dbo.usp_ConfirmarExportacionMantra @Codidtcot={placeholder}, "
            f"@Telefono={placeholder}, @HttpStatus={placeholder}",
            (codidtcot, phone, http_status),
        )
        connection.commit()
    finally:
        connection.close()


def append_log(log_dir: Path, lead_id: str, stage: str, status: str, http: int | None = None, detail: str = "") -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    local_now = datetime.now(ZoneInfo("America/Lima"))
    record = {
        "fecha_hora": local_now.isoformat(timespec="seconds"),
        "lead": lead_id, "etapa": stage, "http": http,
        "resultado": status, "detalle": detail[:300],
    }
    with (log_dir / f"mantra_{local_now:%Y%m%d}.txt").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def post(session: requests.Session, path: str, payload: dict, retry_upsert: bool) -> requests.Response:
    attempts = 3 if retry_upsert else 1
    for attempt in range(attempts):
        try:
            response = session.post(BASE_URL + path, json=payload, timeout=(10, 30))
        except requests.RequestException:
            if attempt + 1 == attempts:
                raise
            time.sleep(2 ** attempt)
            continue
        if retry_upsert and response.status_code >= 500 and attempt + 1 < attempts:
            time.sleep(2 ** attempt)
            continue
        return response
    raise RuntimeError("No se obtuvo respuesta HTTP")


def response_detail(response: requests.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            return str(body.get("message") or body.get("error") or body.get("resultOp") or body.get("ok") or "")
    except ValueError:
        pass
    return "Respuesta sin detalle estructurado"


def run(config: dict, run_date: date, apply_changes: bool, json_file: Path | None = None) -> dict:
    if apply_changes and json_file:
        raise ValueError("El envío real debe leer el SP para registrar los éxitos y evitar reenvíos")
    rows = parse_contacts_json(json_file.read_text(encoding="utf-8")) if json_file else fetch_rows(config, run_date)
    log_dir = Path(config["log_dir"])
    summary = {"seleccionados": len(rows), "contactos_ok": 0, "errores": 0}
    group_id = os.getenv("MANTRA_GROUP_ID")
    api_key = os.getenv("MANTRA_API_KEY")
    if apply_changes and (not group_id or not api_key):
        raise ValueError("Faltan MANTRA_GROUP_ID o MANTRA_API_KEY")
    session = requests.Session()
    for row in rows:
        lead_id = value_as_text(row.get("numero_cotizacion")) or "SIN_ID"
        try:
            phone, data = build_contact(row, config)
            if apply_changes and phone != row["_telefono_normalizado"]:
                raise ValueError("El teléfono del SP no coincide con el teléfono del contacto")
        except (ValueError, KeyError) as exc:
            summary["errores"] += 1
            append_log(log_dir, lead_id, "validacion", "ERROR", detail=str(exc))
            continue
        if not apply_changes:
            append_log(log_dir, lead_id, "contacto", "DRY_RUN", detail="Contacto validado; no se llamó al API")
            continue
        credentials = {"groupId": group_id, "apiKey": api_key}
        try:
            contact_response = post(session, "/contacts/new", {**credentials, "data": data}, retry_upsert=True)
        except requests.RequestException as exc:
            summary["errores"] += 1
            append_log(log_dir, lead_id, "contacto", "ERROR", detail=f"Red: {type(exc).__name__}")
            continue
        if contact_response.status_code not in (200, 201):
            summary["errores"] += 1
            append_log(log_dir, lead_id, "contacto", "ERROR", contact_response.status_code, response_detail(contact_response))
            if contact_response.status_code == 403:
                break
            continue
        try:
            confirm_sent(config, row["_codidtcot"], phone, contact_response.status_code)
        except (pymssql.Error, pyodbc.Error, KeyError, OSError) as exc:
            summary["errores"] += 1
            append_log(log_dir, lead_id, "confirmacion_sql", "ERROR", contact_response.status_code,
                       f"Mantra aceptó el contacto, pero SQL no confirmó: {type(exc).__name__}")
            continue
        summary["contactos_ok"] += 1
        append_log(log_dir, lead_id, "contacto", "OK", contact_response.status_code, response_detail(contact_response))
    session.close()
    return summary


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(description="Exporta contactos de SQL Server a Mantra")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--fecha", type=date.fromisoformat, help="Fecha de ejecución, AAAA-MM-DD; por defecto hoy en Lima")
    parser.add_argument("--json-file", type=Path, help="Lee contactos desde un JSON local en vez del SP")
    parser.add_argument("--log-dir", type=Path, help="Carpeta de logs para esta ejecución")
    parser.add_argument("--apply", action="store_true", help="Crea/actualiza contactos reales en Mantra")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.log_dir:
        config["log_dir"] = str(args.log_dir)
    run_date = args.fecha or datetime.now(ZoneInfo("America/Lima")).date()
    summary = run(config, run_date, args.apply, args.json_file)
    print(json.dumps({"fecha": run_date.isoformat(), "modo": "APLICAR" if args.apply else "DRY_RUN", **summary}, ensure_ascii=False))
    return 1 if summary["errores"] else 0


if __name__ == "__main__":
    sys.exit(main())
