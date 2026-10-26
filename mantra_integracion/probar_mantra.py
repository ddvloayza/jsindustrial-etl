"""Prueba aislada de credenciales y creación de contacto Mantra sin SQL Server."""

import argparse
import os
import sys

import requests

from exportar_contactos import BASE_URL, normalize_phone, post, response_detail


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba la conexión con Mantra sin mostrar credenciales")
    parser.add_argument("--phone", required=True, help="Número de prueba autorizado, con o sin prefijo de país")
    parser.add_argument("--country-code", default="51")
    parser.add_argument("--name", help="Nombre para crear o actualizar el contacto de prueba")
    args = parser.parse_args()

    required = ["MANTRA_GROUP_ID", "MANTRA_API_KEY"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        print("Faltan variables: " + ", ".join(missing), file=sys.stderr)
        return 2
    phone = normalize_phone(args.phone, args.country_code)
    if not phone:
        print("Teléfono inválido para el código de país indicado", file=sys.stderr)
        return 2
    credentials = {"groupId": os.environ["MANTRA_GROUP_ID"], "apiKey": os.environ["MANTRA_API_KEY"]}
    session = requests.Session()

    if not args.name:
        try:
            response = post(session, "/contacts/byphone", {
                **credentials, "phone": phone, "countryCode": args.country_code,
            }, retry_upsert=False)
        except requests.RequestException as exc:
            print(f"No se pudo conectar: {type(exc).__name__}", file=sys.stderr)
            return 1
        if response.status_code in (200, 404):
            print(f"Credenciales aceptadas por /contacts/byphone (HTTP {response.status_code}). No se modificó ningún contacto.")
            return 0
        print(f"Verificación no concluyente o fallida: HTTP {response.status_code}; {response_detail(response)}", file=sys.stderr)
        return 1

    data = {"name": args.name.strip(), "phone": phone, "countryCode": args.country_code}
    try:
        response = post(session, "/contacts/new", {**credentials, "data": data}, retry_upsert=True)
    except requests.RequestException as exc:
        print(f"No se pudo crear/actualizar el contacto: {type(exc).__name__}", file=sys.stderr)
        return 1
    if response.status_code not in (200, 201):
        print(f"Contacto rechazado: HTTP {response.status_code}; {response_detail(response)}", file=sys.stderr)
        return 1
    print(f"Contacto de prueba creado/actualizado: HTTP {response.status_code}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
