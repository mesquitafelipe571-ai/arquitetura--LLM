#!/usr/bin/env python3
"""Confere skills, agentes e arquivos de configuração do repositório. Sai com 1 se houver erro."""
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
errors = []


def frontmatter_field(text, key):
    m = re.search(rf"^{key}:[ \t]*(.*)$", text, re.M)
    return m.group(1).strip().strip("\"'") if m else ""


def check_markdown(path, expected_name=None):
    m = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not m:
        errors.append(f"{path}: sem frontmatter (--- ... ---) no início")
        return None
    name = frontmatter_field(m.group(1), "name")
    if not name:
        errors.append(f"{path}: falta 'name'")
    elif expected_name and name != expected_name:
        errors.append(f"{path}: name '{name}' diferente da pasta '{expected_name}'")
    if not frontmatter_field(m.group(1), "description"):
        errors.append(f"{path}: falta 'description'")
    return name


def tracked(*patterns):
    out = subprocess.run(["git", "ls-files", *patterns], cwd=ROOT, check=True,
                         capture_output=True, text=True).stdout
    return [ROOT / p for p in out.splitlines()]


for skills_dir in (ROOT / ".agents/skills", ROOT / ".claude/skills"):
    for d in sorted(p for p in skills_dir.glob("*") if p.is_dir()):
        if not (d / "SKILL.md").is_file():
            errors.append(f"{d}: falta SKILL.md")
        else:
            check_markdown(d / "SKILL.md", d.name)

for agent in sorted((ROOT / ".claude/agents").glob("*.md")):
    check_markdown(agent, agent.stem)

for f in tracked("*.toml"):
    try:
        data = tomllib.loads(f.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        errors.append(f"{f}: TOML inválido: {e}")
        continue
    if f.parent == ROOT / ".codex/agents":
        for key in ("name", "developer_instructions"):
            if not str(data.get(key, "")).strip():
                errors.append(f"{f}: falta '{key}'")

for f in tracked("*.json"):
    try:
        json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"{f}: JSON inválido: {e}")

for e in errors:
    print(f"ERRO {e.replace(f'{ROOT}/', '')}")
print(f"{len(errors)} erro(s)." if errors else "Tudo certo.")
sys.exit(1 if errors else 0)
