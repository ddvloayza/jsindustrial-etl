import json
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

    def test_contact_then_template_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.config["log_dir"] = temporary
            contact_response = Mock(status_code=201)
            contact_response.json.return_value = {"resultOp": "created"}
            template_response = Mock(status_code=201)
            template_response.json.return_value = {"ok": True}
            with patch.dict(app.os.environ, {
                "MANTRA_GROUP_ID": "test-group", "MANTRA_API_KEY": "test-key",
                "MANTRA_TEMPLATE_ID": "test-template",
            }), patch.object(app, "fetch_rows", return_value=[self.row]), patch.object(
                app, "post", side_effect=[contact_response, template_response]
            ) as request:
                summary = app.run(self.config, date(2026, 2, 2), send=True)
            self.assertEqual(summary["contactos_ok"], 1)
            self.assertEqual(summary["plantillas_ok"], 1)
            self.assertEqual([c.args[1] for c in request.call_args_list], ["/contacts/new", "/contacts/send"])
            self.assertEqual(request.call_args_list[0].args[2]["data"]["phone"], "987549210")
            self.assertEqual(request.call_args_list[1].args[2]["phone"], "987549210")
            self.assertIn("0001-0027924-1", app.already_sent(Path(temporary)))
            with patch.object(app, "fetch_rows", return_value=[self.row]), patch.object(app, "post") as second_request:
                summary = app.run(self.config, date(2026, 2, 2), send=False)
            self.assertEqual(summary["omitidos"], 1)
            second_request.assert_not_called()

    def test_uncertain_template_response_blocks_resend(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.config["log_dir"] = temporary
            contact_response = Mock(status_code=201)
            contact_response.json.return_value = {"resultOp": "created"}
            template_response = Mock(status_code=500)
            template_response.json.return_value = {"message": "Error interno"}
            with patch.dict(app.os.environ, {
                "MANTRA_GROUP_ID": "test-group", "MANTRA_API_KEY": "test-key",
                "MANTRA_TEMPLATE_ID": "test-template",
            }), patch.object(app, "fetch_rows", return_value=[self.row]), patch.object(
                app, "post", side_effect=[contact_response, template_response]
            ):
                summary = app.run(self.config, date(2026, 2, 2), send=True)
            self.assertEqual(summary["errores"], 1)
            self.assertIn("0001-0027924-1", app.already_sent(Path(temporary)))


if __name__ == "__main__":
    unittest.main()
