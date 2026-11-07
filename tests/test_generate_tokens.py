from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / ".agents/skills/design-system/scripts/generate-tokens.cjs"
STARTER = REPO / ".agents/skills/design-system/templates/design-tokens-starter.json"


@unittest.skipUnless(shutil.which("node"), "node não disponível")
class GenerateTokensTailwindTests(unittest.TestCase):
    def generate(self, tokens):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config, output = Path(tmp.name) / "tokens.json", Path(tmp.name) / "colors.cjs"
        config.write_text(json.dumps(tokens) if not isinstance(tokens, Path) else tokens.read_text())
        result = subprocess.run(["node", str(SCRIPT), "--config", str(config), "--format", "tailwind",
                                 "--output", str(output)], capture_output=True, text=True)
        return result, output

    def test_starter_tokens_load_as_module(self):
        result, output = self.generate(STARTER)
        self.assertEqual(result.returncode, 0, result.stderr)
        loaded = subprocess.run(["node", "-e", "console.log(Object.keys(require(process.argv[1]).colors).length)",
                                 str(output)], capture_output=True, text=True, check=True)
        self.assertGreater(int(loaded.stdout), 0)

    def test_quote_in_token_name_is_rejected_not_executed(self):
        for name in ["x':(globalThis.__TOKEN_POC=1337),//", 'x"y', "a\\b", "a\nb", "a b", "a*/b"]:
            with self.subTest(name=name):
                result, output = self.generate({"semantic": {"color": {name: {"$value": "#fff"}}}})
                self.assertEqual(result.returncode, 1)
                self.assertIn("Invalid token name", result.stderr)
                self.assertFalse(output.exists())


    def test_dtcg_metadata_keys_are_not_token_names(self):
        # $extensions (e outros metadados $) num grupo não são tokens e não podem barrar a geração.
        tokens = {"semantic": {"color": {"$extensions": {"org.example": {"source": "brand"}},
                                         "$description": "cores", "primary": {"$value": "#fff"}}}}
        result, output = self.generate(tokens)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.exists())

if __name__ == "__main__":
    unittest.main()
