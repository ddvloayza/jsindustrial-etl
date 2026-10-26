import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import exportar_contactos as app


class ContactExportTests(unittest.TestCase):
    def setUp(self):
        self.config = app.load_config(Path(__file__).resolve().parents[1] / "config.example.json")
        self.row = {name: None for name in app.ALL_COLUMNS}
        self.row.update({
            "N° Cotización": "0001-0027924-1", "Fecha": date(2026, 2, 2),
            "Cliente": "CLIENTE PRUEBA", "Nombre del contacto": "MIGUEL MORALES",
            "Telefono": "+51 987 549 210", "email": "miguel@example.com",
            "Moneda": "US$", "Total Docum.": 100,
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
        self.row["Telefono"] = "012345678"
        with self.assertRaisesRegex(ValueError, "Teléfono inválido"):
            app.build_contact(self.row, self.config)

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

    def test_dry_run_does_not_call_api(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.config["log_dir"] = temporary
            with patch.object(app, "fetch_rows", return_value=[self.row]), patch.object(app, "post") as request:
                summary = app.run(self.config, date(2026, 2, 2), apply_changes=False)
            self.assertEqual(summary["errores"], 0)
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
