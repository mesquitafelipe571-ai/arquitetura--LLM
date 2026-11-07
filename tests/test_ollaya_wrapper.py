"""Testes do scripts/ollaya.sh (instalação local do Ollaya)."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipIf(sys.platform == "win32", "script POSIX")
class OllayaWrapperTests(unittest.TestCase):
    SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ollaya.sh"

    def run_install(self, curl_body):
        with tempfile.TemporaryDirectory() as tmp:
            curl = Path(tmp) / "curl"
            curl.write_text("#!/bin/sh\n" + curl_body)
            curl.chmod(0o755)
            env = {"PATH": f"{tmp}:/usr/bin:/bin", "HOME": tmp}
            return subprocess.run(["sh", str(self.SCRIPT), "install"], capture_output=True, text=True,
                                  env=env, timeout=30)

    def test_install_fails_when_download_fails(self):
        result = self.run_install("exit 22\n")
        self.assertEqual(result.returncode, 22, result.stderr)

    def test_install_runs_downloaded_installer_with_local_settings(self):
        # O curl falso grava, no arquivo de -o, um instalador que só mostra as variáveis.
        result = self.run_install(
            'while [ "$1" != -o ]; do shift; done\n'
            'printf \'echo "$OLLAYA_VERSION $OLLAYA_NO_SERVICE $OLLAYA_HOST ${OLLAYA_INSTALL_DIR##*/.runtime/}"\' > "$2"\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "0.18.0 1 127.0.0.1:11435 ollaya")



if __name__ == "__main__":
    unittest.main()
