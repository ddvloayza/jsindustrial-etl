"""Prueba aislada de credenciales, contacto y plantilla Mantra sin SQL Server."""

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
    parser.add_argument("--send-template", action="store_true", help="Envía realmente la plantilla al número de prueba")
    args = parser.parse_args()

    required = ["MANTRA_GROUP_ID", "MANTRA_API_KEY"]
    if args.send_template:
        required.append("MANTRA_TEMPLATE_ID")
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

    if not args.name and not args.send_template:
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

    if not args.name:
        print("Para enviar plantilla debes indicar --name para crear/actualizar primero el contacto", file=sys.stderr)
        return 2
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
    if not args.send_template:
        return 0
    try:
        response = post(session, "/contacts/send", {
            **credentials, "templateId": os.environ["MANTRA_TEMPLATE_ID"],
            "phone": phone, "countryCode": args.country_code,
        }, retry_upsert=False)
    except requests.RequestException as exc:
        print(f"Resultado de plantilla incierto ({type(exc).__name__}); verifica en Mantra antes de repetir", file=sys.stderr)
        return 1
    if response.status_code == 201:
        print("Plantilla aceptada por Mantra: HTTP 201")
        return 0
    print(f"Plantilla no confirmada: HTTP {response.status_code}; {response_detail(response)}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
