"""Exporta contactos de SQL Server a Mantra y, opcionalmente, envía una plantilla.

El SP conserva las 23 columnas originales. La API documentada admite name,
phone, countryCode, email y 10 campos custom; su selección vive en config.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pymssql
import requests


BASE_URL = "https://wbpback.mantra.chat"
ALL_COLUMNS = [
    "N° Cotización", "Fecha", "Cliente", "Condicion de venta", "Vendedor",
    "Fuente de contacto", "Referencia", "Nombre del contacto", "Cargo",
    "Area", "Telefono", "email", "Moneda", "Total Docum.",
    "Total M.N.", "Invent. Disponible", "% Invent. Dispon.",
    "tasa_exito_cierre", "fec_Estim_Cierre", "Status_Oferta",
    "Generó O/V", "Comentario", "Usuario",
]


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    custom = config.get("custom_fields", {})
    if not isinstance(custom, dict) or len(custom) > 10:
        raise ValueError("custom_fields debe contener como máximo 10 entradas")
    allowed = {f"custom_{i}" for i in range(1, 11)}
    if set(custom) - allowed:
        raise ValueError("Solo se permiten custom_1 a custom_10")
    missing = set(custom.values()) - set(ALL_COLUMNS)
    if missing:
        raise ValueError(f"Columnas del SP no reconocidas: {sorted(missing)}")
    return config


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
    phone = normalize_phone(row.get("Telefono"), country_code)
    if not phone:
        raise ValueError("Teléfono inválido o ausente")
    name = value_as_text(row.get("Nombre del contacto")) or value_as_text(row.get("Cliente"))
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


def fetch_rows(config: dict, run_date: date) -> list[dict]:
    sql = config["sql"]
    connection = pymssql.connect(
        server=sql["server"], port=int(sql.get("port", 1433)),
        user=os.environ["MANTRA_SQL_USER"], password=os.environ["MANTRA_SQL_PASSWORD"],
        database=sql["database"], as_dict=True, login_timeout=10, timeout=120,
    )
    try:
        cursor = connection.cursor()
        cursor.execute(
            "EXEC dbo.usp_ExportarCotizacionesMantra @FechaDesde=%s, @FechaHasta=%s, @ComoJson=0",
            (run_date, run_date),
        )
        rows = cursor.fetchall()
        if cursor.description:
            columns = {item[0] for item in cursor.description}
            if not set(ALL_COLUMNS) <= columns:
                raise RuntimeError(f"El SP no devolvió estas columnas: {sorted(set(ALL_COLUMNS)-columns)}")
        return rows
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


def already_sent(log_dir: Path) -> set[str]:
    sent = set()
    for path in log_dir.glob("mantra_*.txt"):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("etapa") == "plantilla" and record.get("resultado") in ("ENVIADO", "INCIERTO"):
                sent.add(str(record.get("lead")))
    return sent


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


def run(config: dict, run_date: date, send: bool, contacts_only: bool = False) -> dict:
    rows = fetch_rows(config, run_date)
    log_dir = Path(config["log_dir"])
    sent = already_sent(log_dir)
    summary = {"seleccionados": len(rows), "contactos_ok": 0, "plantillas_ok": 0, "omitidos": 0, "errores": 0}
    group_id = os.getenv("MANTRA_GROUP_ID")
    api_key = os.getenv("MANTRA_API_KEY")
    template_id = os.getenv("MANTRA_TEMPLATE_ID")
    if send and (not group_id or not api_key or (not contacts_only and not template_id)):
        raise ValueError("Faltan MANTRA_GROUP_ID, MANTRA_API_KEY o MANTRA_TEMPLATE_ID")
    session = requests.Session()
    for row in rows:
        lead_id = value_as_text(row.get("N° Cotización")) or "SIN_ID"
        if not contacts_only and lead_id in sent:
            summary["omitidos"] += 1
            append_log(log_dir, lead_id, "seleccion", "OMITIDO", detail="Plantilla enviada o estado incierto según TXT previo")
            continue
        try:
            phone, data = build_contact(row, config)
        except ValueError as exc:
            summary["errores"] += 1
            append_log(log_dir, lead_id, "validacion", "ERROR", detail=str(exc))
            continue
        if not send:
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
        summary["contactos_ok"] += 1
        append_log(log_dir, lead_id, "contacto", "OK", contact_response.status_code, response_detail(contact_response))
        if contacts_only:
            continue
        try:
            send_response = post(session, "/contacts/send", {
                **credentials, "templateId": template_id,
                "phone": phone, "countryCode": data["countryCode"],
            }, retry_upsert=False)
        except requests.RequestException as exc:
            summary["errores"] += 1
            append_log(log_dir, lead_id, "plantilla", "INCIERTO", detail=f"Red: {type(exc).__name__}; verificar en Mantra antes de reintentar")
            continue
        if send_response.status_code == 201:
            summary["plantillas_ok"] += 1
            sent.add(lead_id)
            append_log(log_dir, lead_id, "plantilla", "ENVIADO", 201, response_detail(send_response))
        else:
            summary["errores"] += 1
            uncertain = send_response.status_code >= 500
            append_log(log_dir, lead_id, "plantilla", "INCIERTO" if uncertain else "ERROR", send_response.status_code, response_detail(send_response))
            if send_response.status_code == 403:
                break
    session.close()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta contactos de SQL Server a Mantra")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--fecha", type=date.fromisoformat, help="Fecha a procesar, AAAA-MM-DD; por defecto ayer en Lima")
    parser.add_argument("--send", action="store_true", help="Habilita llamadas reales al API")
    parser.add_argument("--contacts-only", action="store_true", help="Crea/actualiza contactos sin enviar plantilla")
    args = parser.parse_args()
    config = load_config(args.config)
    run_date = args.fecha or (datetime.now(ZoneInfo("America/Lima")).date() - timedelta(days=1))
    summary = run(config, run_date, args.send, args.contacts_only)
    print(json.dumps({"fecha": run_date.isoformat(), "modo": "ENVIO" if args.send else "DRY_RUN", **summary}, ensure_ascii=False))
    return 1 if summary["errores"] else 0


if __name__ == "__main__":
    sys.exit(main())
