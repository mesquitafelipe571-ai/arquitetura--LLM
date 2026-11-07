"""Testes do scripts/ollaya.sh (instalação local do Ollaya)."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipIf(sys.platform == "win32", "script POSIX")
class OllayaWrapperTests(unittest.TestCase):
    SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ollaya.sh"

    def run_install(self, curl_body, approve=True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        curl = Path(tmp.name) / "curl"
        curl.write_text("#!/bin/sh\n" + curl_body)
        curl.chmod(0o755)
        env = {"PATH": f"{tmp.name}:/usr/bin:/bin", "HOME": tmp.name, "MARK": tmp.name}
        if approve:
            env["OLLAYA_APPROVE_INSTALL"] = "1"
        result = subprocess.run(["sh", str(self.SCRIPT), "install"], capture_output=True, text=True,
                                env=env, stdin=subprocess.DEVNULL, timeout=30)
        return result, Path(tmp.name)

    def test_install_without_confirmation_downloads_nothing(self):
        # Sem terminal e sem OLLAYA_APPROVE_INSTALL=1 (como um agente), para antes do download.
        result, tmp = self.run_install('touch "$MARK/curl-called"\n', approve=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("não confirmada", result.stderr)
        self.assertFalse((tmp / "curl-called").exists())

    def test_install_fails_when_download_fails(self):
        result, _ = self.run_install("exit 22\n")
        self.assertEqual(result.returncode, 22, result.stderr)

    def test_installer_with_wrong_checksum_is_not_executed(self):
        # O curl falso grava, no arquivo de -o, um "instalador" que deixaria uma marca se rodasse.
        result, tmp = self.run_install(
            'while [ "$1" != -o ]; do shift; done\n'
            'echo \'touch "$MARK/installer-ran"\' > "$2"\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("checksum inesperado", result.stderr)
        self.assertFalse((tmp / "installer-ran").exists())


if __name__ == "__main__":
    unittest.main()
