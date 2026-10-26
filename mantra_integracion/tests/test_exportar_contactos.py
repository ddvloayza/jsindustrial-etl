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
        self.row = {name: None for name in app.ALL_JSON_FIELDS}
        self.row.update({
            "numero_cotizacion": "0001-0027924-1", "fecha": "2026-02-02",
            "cliente": "CLIENTE PRUEBA", "nombre_contacto": "MIGUEL MORALES",
            "telefono": "+51 987 549 210", "email": "miguel@example.com",
            "moneda": "US$", "total_documento": 100,
        })

    def test_phone_and_ten_custom_fields(self):
        phone, data = app.build_contact(self.row, self.config)
        self.assertEqual(phone, "987549210")
        self.assertEqual(data["countryCode"], "51")
        self.assertEqual(data["name"], "MIGUEL MORALES")
        self.assertEqual(data["custom_1"], "0001-0027924-1")
        self.assertEqual(data["custom_9"], "100")
        self.assertNotIn("custom_11", data)

    def test_invalid_phone_is_not_sent(self):
        self.row["telefono"] = "012345678"
        with self.assertRaisesRegex(ValueError, "Teléfono inválido"):
            app.build_contact(self.row, self.config)

    def test_sp_json_is_read(self):
        cursor = Mock()
        cursor.fetchall.return_value = [{"payload_json": json.dumps([self.row])}]
        connection = Mock()
        connection.cursor.return_value = cursor
        with patch.object(app.pymssql, "connect", return_value=connection), patch.dict(
            app.os.environ, {"MANTRA_SQL_USER": "test", "MANTRA_SQL_PASSWORD": "test"}
        ):
            rows = app.fetch_rows(self.config, date(2026, 2, 2))
        self.assertEqual(rows, [self.row])
        self.assertIn("@ComoJson=1", cursor.execute.call_args.args[0])
        connection.close.assert_called_once()

    def test_json_requires_ten_custom_fields_and_contact_details(self):
        with self.assertRaisesRegex(ValueError, "le faltan propiedades"):
            app.parse_contacts_json('[{"telefono":"987549210"}]')
        with self.assertRaisesRegex(ValueError, "propiedades no exportables"):
            app.parse_contacts_json(json.dumps([{**self.row, "comentario": "No exportar"}]))

    def test_upsert_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.config["log_dir"] = temporary
            contact_response = Mock(status_code=201)
            contact_response.json.return_value = {"resultOp": "created"}
            with patch.dict(app.os.environ, {
                "MANTRA_GROUP_ID": "test-group", "MANTRA_API_KEY": "test-key",
            }), patch.object(app, "fetch_rows", return_value=[self.row]), patch.object(
                app, "post", return_value=contact_response
            ) as request:
                summary = app.run(self.config, date(2026, 2, 2), apply_changes=True)
            self.assertEqual(summary["contactos_ok"], 1)
            self.assertEqual([c.args[1] for c in request.call_args_list], ["/contacts/new"])
            self.assertEqual(request.call_args_list[0].args[2]["data"]["phone"], "987549210")
            self.assertIn("contacto", next(Path(temporary).glob("mantra_*.txt")).read_text())

    def test_sample_json_dry_run(self):
        sample = app.parse_contacts_json((ROOT / "contactos_prueba.json").read_text(encoding="utf-8"))
        self.assertEqual(len(sample[0]), 13)
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
            with self.assertRaisesRegex(ValueError, "no se puede enviar"):
                app.run(self.config, date(2026, 2, 2), True, ROOT / "contactos_prueba.json")


if __name__ == "__main__":
    unittest.main()
