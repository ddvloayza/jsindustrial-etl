import io
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import probar_mantra


class CredentialProbeTests(unittest.TestCase):
    def test_missing_variables_stops_before_http(self):
        with patch.object(probar_mantra, "load_dotenv"), patch.dict(probar_mantra.os.environ, {}, clear=True), patch.object(
            sys, "argv", ["probar_mantra.py", "--phone", "987654321"]
        ), patch.object(probar_mantra, "post") as post, patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(probar_mantra.main(), 2)
            post.assert_not_called()
            self.assertIn("MANTRA_GROUP_ID", stderr.getvalue())

    def test_read_only_404_confirms_credentials_without_write(self):
        response = Mock(status_code=404)
        with patch.object(probar_mantra, "load_dotenv"), patch.dict(probar_mantra.os.environ, {
            "MANTRA_GROUP_ID": "test-group", "MANTRA_API_KEY": "test-key"
        }), patch.object(sys, "argv", ["probar_mantra.py", "--phone", "987654321"]), patch.object(
            probar_mantra, "post", return_value=response
        ) as post, patch("sys.stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(probar_mantra.main(), 0)
            self.assertEqual(post.call_args.args[1], "/contacts/byphone")
            self.assertIn("Credenciales aceptadas", stdout.getvalue())

    def test_upsert_uses_only_contacts_new(self):
        response = Mock(status_code=201)
        with patch.object(probar_mantra, "load_dotenv"), patch.dict(probar_mantra.os.environ, {
            "MANTRA_GROUP_ID": "test-group", "MANTRA_API_KEY": "test-key"
        }), patch.object(sys, "argv", ["probar_mantra.py", "--phone", "987654321", "--name", "Prueba"]), patch.object(
            probar_mantra, "post", return_value=response
        ) as post, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(probar_mantra.main(), 0)
            self.assertEqual(post.call_count, 1)
            self.assertEqual(post.call_args.args[1], "/contacts/new")


if __name__ == "__main__":
    unittest.main()
