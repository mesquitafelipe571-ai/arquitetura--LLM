"""Security regression tests for generate-tokens.cjs."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "generate-tokens.cjs"


def _run(tmp_path: Path, tokens: dict) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")

    config = tmp_path / "tokens.json"
    output = tmp_path / "tailwind.cjs"
    config.write_text(json.dumps(tokens), encoding="utf-8")
    return subprocess.run(
        [node, str(SCRIPT), "--config", str(config), "--format", "tailwind", "--output", str(output)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_rejects_token_names_that_can_inject_javascript(tmp_path):
    tokens = {
        "semantic": {
            "color": {
                "x':(globalThis.__TOKEN_POC=1337),//": {"$value": "#fff"}
            }
        }
    }

    result = _run(tmp_path, tokens)

    assert result.returncode != 0
    assert "Invalid token name" in result.stderr
    assert not (tmp_path / "tailwind.cjs").exists()


def test_tailwind_output_remains_valid_commonjs(tmp_path):
    result = _run(
        tmp_path,
        {"semantic": {"color": {"primary-hover": {"$value": "#fff"}}}},
    )

    assert result.returncode == 0, result.stderr
    output = (tmp_path / "tailwind.cjs").read_text(encoding="utf-8")
    assert '"primary.hover": "var(--color-primary-hover)"' in output
