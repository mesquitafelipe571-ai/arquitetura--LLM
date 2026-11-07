from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SHA = "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09"


class CheckRepoActionPinTests(unittest.TestCase):
    def run_check(self, workflow):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            shutil.copy(REPO / "scripts/check-repo.py", root / "scripts")
            (root / ".github/workflows").mkdir(parents=True)
            (root / ".github/workflows/ci.yml").write_text(workflow)
            subprocess.run(["git", "init", "-q", tmp], check=True)
            subprocess.run(["git", "-C", tmp, "add", "."], check=True)
            return subprocess.run([sys.executable, "scripts/check-repo.py"], cwd=tmp,
                                  capture_output=True, text=True)

    def test_accepts_full_sha_plain_quoted_and_local(self):
        result = self.run_check(
            "steps:\n"
            f"  - uses: actions/checkout@{SHA} # v5.1.0\n"
            f"  - uses: \"actions/checkout@{SHA}\"\n"
            f"  - uses: 'actions/checkout@{SHA}'\n"
            "  - uses: ./.github/actions/local\n"
            "  # uses: actions/checkout@v4\n"
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_rejects_tag_and_short_sha(self):
        result = self.run_check(
            "steps:\n"
            "  - uses: actions/checkout@v4\n"
            "  - uses: \"actions/setup-python@a26af69\"\n"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("ci.yml:2: Action sem SHA completo: actions/checkout@v4", result.stdout)
        self.assertIn("ci.yml:3: Action sem SHA completo: actions/setup-python@a26af69", result.stdout)


if __name__ == "__main__":
    unittest.main()
