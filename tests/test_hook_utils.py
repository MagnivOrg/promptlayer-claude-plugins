import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK_CLI = REPO_ROOT / "plugins" / "trace" / "hooks" / "py" / "cli.py"


def run_hook_cli(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, str(HOOK_CLI), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class HookUtilsIdTests(unittest.TestCase):
    def test_generate_trace_id_returns_32_lower_hex(self) -> None:
        trace_id = run_hook_cli("generate-trace-id")
        self.assertRegex(trace_id, r"^[0-9a-f]{32}$")

    def test_generate_span_id_returns_16_lower_hex(self) -> None:
        span_id = run_hook_cli("generate-span-id")
        self.assertRegex(span_id, r"^[0-9a-f]{16}$")

    def test_generate_session_id_returns_uuid_string(self) -> None:
        session_id = run_hook_cli("generate-session-id")
        self.assertRegex(session_id, r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class HookUtilsSettingsTests(unittest.TestCase):
    def test_write_settings_env_creates_new_settings_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = pathlib.Path(tmpdir) / "settings.json"
            run_hook_cli(
                "write-settings-env",
                str(settings_path),
                "pl_test_key",
                "https://api.promptlayer.com/v1/traces",
                "false",
            )

            with settings_path.open(encoding="utf-8") as f:
                settings = json.load(f)

            self.assertEqual(settings["env"]["TRACE_TO_PROMPTLAYER"], "true")
            self.assertEqual(settings["env"]["PROMPTLAYER_API_KEY"], "pl_test_key")
            self.assertEqual(settings["env"]["PROMPTLAYER_OTLP_ENDPOINT"], "https://api.promptlayer.com/v1/traces")
            self.assertEqual(settings["env"]["PROMPTLAYER_CC_DEBUG"], "false")

    def test_write_settings_env_merges_existing_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = pathlib.Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps({"foo": "bar", "env": {"EXISTING": "1", "PROMPTLAYER_CC_DEBUG": "true"}}),
                encoding="utf-8",
            )

            run_hook_cli(
                "write-settings-env",
                str(settings_path),
                "pl_test_key",
                "https://example.com/v1/traces",
                "false",
            )

            with settings_path.open(encoding="utf-8") as f:
                settings = json.load(f)

            self.assertEqual(settings["foo"], "bar")
            self.assertEqual(settings["env"]["EXISTING"], "1")
            self.assertEqual(settings["env"]["PROMPTLAYER_API_KEY"], "pl_test_key")
            self.assertEqual(settings["env"]["PROMPTLAYER_OTLP_ENDPOINT"], "https://example.com/v1/traces")
            self.assertEqual(settings["env"]["PROMPTLAYER_CC_DEBUG"], "false")

    def test_write_settings_env_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = pathlib.Path(tmpdir) / "settings.json"
            settings_path.write_text("{not valid json", encoding="utf-8")

            with self.assertRaises(subprocess.CalledProcessError):
                run_hook_cli(
                    "write-settings-env",
                    str(settings_path),
                    "pl_test_key",
                    "https://example.com/v1/traces",
                    "false",
                )


if __name__ == "__main__":
    unittest.main()
