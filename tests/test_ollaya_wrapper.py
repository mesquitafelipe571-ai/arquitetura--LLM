"""Testes do scripts/ollaya.sh (instalação local do Ollaya)."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


@unittest.skipIf(sys.platform == "win32", "script POSIX")
class OllayaWrapperTests(unittest.TestCase):
    SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ollaya.sh"

    def run_install(self, curl_body, approve=True, extra_env=None, script=None):
        script = script or self.SCRIPT
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        curl = Path(tmp.name) / "curl"
        curl.write_text("#!/bin/sh\n" + curl_body)
        curl.chmod(0o755)
        env = {"PATH": f"{tmp.name}:/usr/bin:/bin", "HOME": tmp.name, "MARK": tmp.name, **(extra_env or {})}
        if not approve:
            result = subprocess.run(["sh", str(script), "install"], capture_output=True, text=True,
                                    env=env, stdin=subprocess.DEVNULL, timeout=30)
            return result, Path(tmp.name)
        # Aprovação como uma pessoa faria: "s" digitado num terminal (pseudo-TTY).
        import pty
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        os.write(master, b"s\n")
        try:
            result = subprocess.run(["sh", str(script), "install"], capture_output=True, text=True,
                                    env=env, stdin=slave, timeout=30)
        finally:
            os.close(slave)
        return result, Path(tmp.name)

    def test_install_without_confirmation_downloads_nothing(self):
        # Sem terminal (como um agente), para antes do download.
        result, tmp = self.run_install('touch "$MARK/curl-called"\n', approve=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("não confirmada", result.stderr)
        self.assertFalse((tmp / "curl-called").exists())

    def test_env_var_does_not_skip_confirmation(self):
        # A antiga OLLAYA_APPROVE_INSTALL=1 deixava um agente sem TTY liberar o download sozinho.
        result, tmp = self.run_install('touch "$MARK/curl-called"\n', approve=False,
                                       extra_env={"OLLAYA_APPROVE_INSTALL": "1"})
        self.assertEqual(result.returncode, 1)
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


    # Instalador falso: pede o sha256sum.txt de novo, como o real, e guarda o que recebeu.
    FAKE_INSTALLER = ('curl -fsSL -o "$MARK/got-sums" '
                      'https://github.com/ollaya-dev/ollaya/releases/download/v0.18.0/sha256sum.txt')
    # Serve o instalador falso; o sha256sum.txt pedido pelo instalador (com OLLAYA_VERSION) vem trocado.
    FAKE_CURL = ('while [ "$1" != -o ]; do shift; done\n'
                 'case $3 in\n'
                 f'  */install.sh) printf "%s\\n" {FAKE_INSTALLER!r} > "$2" ;;\n'
                 '  */sha256sum.txt) if [ -n "${OLLAYA_VERSION:-}" ]; then echo evil > "$2"; '
                 'else echo ${FIRST_SUMS:-good} > "$2"; fi ;;\n'
                 'esac\n')

    def pinned_copy(self):
        import hashlib, re
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        text = self.SCRIPT.read_text()
        text = re.sub(r"INSTALLER_SHA256=\w+", "INSTALLER_SHA256=" + hashlib.sha256((self.FAKE_INSTALLER + "\n").encode()).hexdigest(), text)
        text = re.sub(r"SUMS_SHA256=\w+", "SUMS_SHA256=" + hashlib.sha256(b"good\n").hexdigest(), text)
        script = Path(tmp.name) / "scripts/ollaya.sh"
        script.parent.mkdir()
        script.write_text(text)
        return script

    def test_installer_gets_the_pinned_release_checksums(self):
        # Assets reenviados com um sha256sum.txt novo não passam: o instalador recebe a cópia fixada.
        result, tmp = self.run_install(self.FAKE_CURL, script=self.pinned_copy())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((tmp / "got-sums").read_text(), "good\n")

    def test_release_checksums_with_wrong_hash_stop_the_install(self):
        result, tmp = self.run_install(self.FAKE_CURL, script=self.pinned_copy(), extra_env={"FIRST_SUMS": "evil"})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("sha256sum.txt da release com checksum inesperado", result.stderr)
        self.assertFalse((tmp / "got-sums").exists())


if __name__ == "__main__":
    unittest.main()
