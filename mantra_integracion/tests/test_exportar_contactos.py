import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import exportar_contactos as app


ROOT = Path(__file__).resolve().parents[1]


class ContactExportTests(unittest.TestCase):
    def setUp(self):
        self.config = app.load_config(ROOT / "config.example.json")
        self.config["sql"]["authentication"] = "sql"
        self.row = {name: None for name in app.ALL_JSON_FIELDS}
        self.row.update({
            "numero_cotizacion": "0001-0027924-1", "fecha": "2026-02-02",
            "cliente": "CLIENTE PRUEBA", "nombre_contacto": "MIGUEL MORALES",
            "telefono": "+51 987 549 210", "email": "miguel@example.com",
            "vendedor": "VEN001", "referencia": "MANTENIMIENTO",
            "genero_orden_venta": "-",
            "moneda": "US$", "total_documento": 100,
            "total_moneda_nacional": 375, "fecha_estimada_cierre": "2026-02-28",
        })

    def test_only_eight_requested_fields_are_sent(self):
        phone, data = app.build_contact(self.row, self.config)
        self.assertEqual(phone, "987549210")
        self.assertEqual(data["countryCode"], "51")
        self.assertEqual(data["name"], "MIGUEL MORALES")
        self.assertEqual(data["custom_1"], "0001-0027924-1")
        self.assertEqual(data["custom_5"], "VEN001")
        self.assertEqual(data["custom_7"], "MANTENIMIENTO")
        self.assertEqual(data["custom_13"], "-")
        self.assertEqual(set(data), {"name", "phone", "countryCode", *self.config["custom_fields"]})
        self.assertNotIn("email", data)

    def test_invalid_phone_is_not_sent(self):
        self.row["telefono"] = "012345678"
        with self.assertRaisesRegex(ValueError, "Teléfono inválido"):
            app.build_contact(self.row, self.config)

    def test_sp_json_is_read(self):
        cursor = Mock()
        cursor.fetchall.return_value = [{
            "payload_json": json.dumps([self.row]),
            "ids_json": json.dumps([{"codidtcot": "COT0000001", "telefono": "987549210"}]),
        }]
        connection = Mock()
        connection.cursor.return_value = cursor
        with patch.object(app.pymssql, "connect", return_value=connection), patch.dict(
            app.os.environ, {"MANTRA_SQL_USER": "test", "MANTRA_SQL_PASSWORD": "test"}
        ):
            rows = app.fetch_rows(self.config, date(2026, 2, 2))
        self.assertEqual(rows, [{**self.row, "_codidtcot": "COT0000001", "_telefono_normalizado": "987549210"}])
        self.assertIn("EXEC dbo.JS_usp_ExportarCotizacionesMantra", cursor.execute.call_args.args[0])
        self.assertIn("@FechaProceso=%s", cursor.execute.call_args.args[0])
        connection.close.assert_called_once()

    def test_sp_limit_is_passed_as_parameter(self):
        cursor = Mock()
        cursor.fetchall.return_value = [{"payload_json": "[]", "ids_json": "[]"}]
        connection = Mock()
        connection.cursor.return_value = cursor
        with patch.object(app.pymssql, "connect", return_value=connection), patch.dict(
            app.os.environ, {"MANTRA_SQL_USER": "test", "MANTRA_SQL_PASSWORD": "test"}
        ):
            self.assertEqual(app.fetch_rows(self.config, date(2026, 2, 5), limit=1), [])
        query, values = cursor.execute.call_args.args
        self.assertIn("@MaxContactos=%s", query)
        self.assertEqual(values, (date(2026, 2, 5), 1))

    def test_one_contact_dry_run_passes_limit_to_sp(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.config["log_dir"] = temporary
            with patch.object(app, "fetch_rows", return_value=[]) as fetch:
                summary = app.run(self.config, date(2026, 2, 5), False, limit=1)
        self.assertEqual(summary["seleccionados"], 0)
        fetch.assert_called_once_with(self.config, date(2026, 2, 5), limit=1)

    def test_sp_ids_must_match_contacts(self):
        cursor = Mock()
        cursor.fetchall.return_value = [{
            "payload_json": json.dumps([self.row]),
            "ids_json": "[]",
        }]
        connection = Mock()
        connection.cursor.return_value = cursor
        with patch.object(app.pymssql, "connect", return_value=connection), patch.dict(
            app.os.environ, {"MANTRA_SQL_USER": "test", "MANTRA_SQL_PASSWORD": "test"}
        ):
            with self.assertRaisesRegex(RuntimeError, "no coinciden"):
                app.fetch_rows(self.config, date(2026, 2, 2))

    def test_windows_auth_uses_job_identity_without_sql_password(self):
        self.config["sql"]["authentication"] = "windows"
        cursor = Mock()
        cursor.description = [("payload_json",), ("ids_json",)]
        cursor.fetchall.return_value = [(
            json.dumps([self.row]),
            json.dumps([{"codidtcot": "COT0000001", "telefono": "987549210"}]),
        )]
        connection = Mock()
        connection.cursor.return_value = cursor
        with patch.object(app.pyodbc, "connect", return_value=connection) as connect, patch.dict(
            app.os.environ, {"MANTRA_SQL_USER": "", "MANTRA_SQL_PASSWORD": ""}
        ):
            rows = app.fetch_rows(self.config, date(2026, 2, 2))
        self.assertEqual(rows[0]["_telefono_normalizado"], "987549210")
        self.assertIn("Trusted_Connection=yes", connect.call_args.args[0])
        self.assertNotIn("UID=", connect.call_args.args[0])
        self.assertIn("@FechaProceso=?", cursor.execute.call_args.args[0])
        connection.close.assert_called_once()

    def test_windows_auth_confirms_contact_with_odbc_parameters(self):
        self.config["sql"]["authentication"] = "windows"
        connection = Mock()
        with patch.object(app.pyodbc, "connect", return_value=connection):
            app.confirm_sent(self.config, "COT0000001", "987549210", 201)
        query, values = connection.cursor.return_value.execute.call_args.args
        self.assertIn("EXEC dbo.JS_usp_ConfirmarExportacionMantra", query)
        self.assertIn("@Codidtcot=?", query)
        self.assertIn("@Telefono=?", query)
        self.assertEqual(values, ("COT0000001", "987549210", 201))
        connection.commit.assert_called_once()

    def test_sp_json_requires_all_source_fields_and_contact_details(self):
        with self.assertRaisesRegex(ValueError, "le faltan propiedades"):
            app.parse_contacts_json('[{"telefono":"987549210"}]')
        with self.assertRaisesRegex(ValueError, "propiedades no exportables"):
            app.parse_contacts_json(json.dumps([{**self.row, "campo_extra": "No exportar"}]))

    def test_upsert_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.config["log_dir"] = temporary
            contact_response = Mock(status_code=201)
            contact_response.json.return_value = {"resultOp": "created"}
            with patch.dict(app.os.environ, {
                "MANTRA_GROUP_ID": "test-group", "MANTRA_API_KEY": "test-key",
            }), patch.object(app, "fetch_rows", return_value=[{**self.row, "_codidtcot": "COT0000001", "_telefono_normalizado": "987549210"}]), patch.object(
                app, "post", return_value=contact_response
            ) as request, patch.object(app, "confirm_sent") as confirm:
                summary = app.run(self.config, date(2026, 2, 2), apply_changes=True)
            self.assertEqual(summary["contactos_ok"], 1)
            self.assertEqual([c.args[1] for c in request.call_args_list], ["/contacts/new"])
            self.assertEqual(request.call_args_list[0].args[2]["data"]["phone"], "987549210")
            self.assertEqual(request.call_args_list[0].args[2]["data"]["custom_13"], "-")
            self.assertNotIn("email", request.call_args_list[0].args[2]["data"])
            confirm.assert_called_once_with(self.config, "COT0000001", "987549210", 201)
            self.assertIn("contacto", next(Path(temporary).glob("mantra_*.txt")).read_text())

    def test_failed_api_request_does_not_confirm_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.config["log_dir"] = temporary
            contact_response = Mock(status_code=403)
            contact_response.json.return_value = {"message": "Forbidden"}
            with patch.dict(app.os.environ, {
                "MANTRA_GROUP_ID": "test-group", "MANTRA_API_KEY": "test-key",
            }), patch.object(app, "fetch_rows", return_value=[{**self.row, "_codidtcot": "COT0000001", "_telefono_normalizado": "987549210"}]), patch.object(
                app, "post", return_value=contact_response
            ), patch.object(app, "confirm_sent") as confirm:
                summary = app.run(self.config, date(2026, 2, 2), apply_changes=True)
            self.assertEqual(summary["contactos_ok"], 0)
            confirm.assert_not_called()

    def test_sample_json_dry_run(self):
        sample = app.parse_contacts_json((ROOT / "contactos_prueba.json").read_text(encoding="utf-8"))
        self.assertEqual(len(sample[0]), 23)
        self.assertEqual([row["telefono"] for row in sample], ["987654321", "912345678", "923456789"])
        with tempfile.TemporaryDirectory() as temporary:
            self.config["log_dir"] = temporary
            with patch.object(app, "fetch_rows") as db, patch.object(app, "post") as request:
                summary = app.run(self.config, date(2026, 2, 2), False, ROOT / "contactos_prueba.json")
            self.assertEqual(summary["seleccionados"], 3)
            self.assertEqual(summary["errores"], 0)
            db.assert_not_called()
            request.assert_not_called()

    def test_sample_json_cannot_be_applied(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.config["log_dir"] = temporary
            with self.assertRaisesRegex(ValueError, "exportación manual con IDs"):
                app.run(self.config, date(2026, 2, 2), True, ROOT / "contactos_prueba.json")

    def test_export_json_keeps_contact_fields_and_sql_ids_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "pendientes.local.json"
            selected = {**self.row, "_codidtcot": "COT0000001", "_telefono_normalizado": "987549210"}
            with patch.object(app, "fetch_rows", return_value=[selected]) as fetch:
                count = app.save_manual_export(self.config, date(2026, 2, 5), path, "COT0000001")
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(count, 1)
            self.assertEqual(document["format"], app.MANUAL_EXPORT_FORMAT)
            self.assertEqual(set(document["contacts"][0]), set(app.ALL_JSON_FIELDS))
            self.assertEqual(document["ids"], [{"codidtcot": "COT0000001", "telefono": "987549210"}])
            fetch.assert_called_once_with(self.config, date(2026, 2, 5), "COT0000001")

    def test_manual_json_apply_rechecks_and_confirms(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "pendientes.local.json"
            self.config["log_dir"] = temporary
            selected = {**self.row, "_codidtcot": "COT0000001", "_telefono_normalizado": "987549210"}
            with patch.object(app, "fetch_rows", return_value=[selected]):
                app.save_manual_export(self.config, date(2026, 2, 5), path)
            response = Mock(status_code=201)
            response.json.return_value = {"resultOp": "created"}
            with patch.dict(app.os.environ, {"MANTRA_GROUP_ID": "test-group", "MANTRA_API_KEY": "test-key"}), \
                    patch.object(app, "fetch_rows", return_value=[selected]) as fetch, \
                    patch.object(app, "post", return_value=response) as request, \
                    patch.object(app, "confirm_sent") as confirm:
                summary = app.run(self.config, date(2026, 2, 5), True, path)
            self.assertEqual(summary["contactos_ok"], 1)
            self.assertEqual(summary["omitidos"], 0)
            self.assertEqual(len(fetch.call_args.args), 2)
            self.assertEqual(request.call_args.args[2]["data"]["phone"], "987549210")
            confirm.assert_called_once_with(self.config, "COT0000001", "987549210", 201)

    def test_manual_json_skips_contact_no_longer_pending(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "pendientes.local.json"
            self.config["log_dir"] = temporary
            selected = {**self.row, "_codidtcot": "COT0000001", "_telefono_normalizado": "987549210"}
            with patch.object(app, "fetch_rows", return_value=[selected]):
                app.save_manual_export(self.config, date(2026, 2, 5), path)
            with patch.dict(app.os.environ, {"MANTRA_GROUP_ID": "test-group", "MANTRA_API_KEY": "test-key"}), \
                    patch.object(app, "fetch_rows", return_value=[]), \
                    patch.object(app, "post") as request, patch.object(app, "confirm_sent") as confirm:
                summary = app.run(self.config, date(2026, 2, 5), True, path)
            self.assertEqual(summary["omitidos"], 1)
            self.assertEqual(summary["contactos_ok"], 0)
            request.assert_not_called()
            confirm.assert_not_called()

    def test_manual_json_skips_contact_changed_after_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "pendientes.local.json"
            self.config["log_dir"] = temporary
            selected = {**self.row, "_codidtcot": "COT0000001", "_telefono_normalizado": "987549210"}
            with patch.object(app, "fetch_rows", return_value=[selected]):
                app.save_manual_export(self.config, date(2026, 2, 5), path)
            changed = {**selected, "referencia": "Referencia modificada"}
            with patch.dict(app.os.environ, {"MANTRA_GROUP_ID": "test-group", "MANTRA_API_KEY": "test-key"}), \
                    patch.object(app, "fetch_rows", return_value=[changed]), \
                    patch.object(app, "post") as request, patch.object(app, "confirm_sent") as confirm:
                summary = app.run(self.config, date(2026, 2, 5), True, path)
            self.assertEqual(summary["omitidos"], 1)
            request.assert_not_called()
            confirm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
