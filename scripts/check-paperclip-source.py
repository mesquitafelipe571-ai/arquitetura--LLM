#!/usr/bin/env python3
"""Confere a origem e o commit do Paperclip incluído como submódulo."""
import argparse
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


def check(require_checkout=False):
    components = json.loads((REPO / "config/components.lock.json").read_text())["components"]
    component = next(c for c in components if c["id"] == "paperclip")
    path = "vendor/paperclip"
    expected_url = "https://github.com/" + component["repository"] + ".git"
    if git("config", "-f", ".gitmodules", "submodule.paperclip.path") != path:
        raise ValueError("Caminho do submódulo divergente.")
    if git("config", "-f", ".gitmodules", "submodule.paperclip.url") != expected_url:
        raise ValueError("Origem do submódulo divergente do catálogo.")
    entry = git("ls-files", "--stage", "--", path)
    if entry != "160000 " + component["commit"] + " 0\t" + path:
        raise ValueError("Gitlink do Paperclip divergente do commit fixado no catálogo.")
    if require_checkout:
        source = REPO / path
        if Path(git("-C", path, "rev-parse", "--show-toplevel")).resolve() != source.resolve():
            raise ValueError("Submódulo ausente; execute git submodule update --init --recursive.")
        if git("-C", path, "rev-parse", "HEAD") != component["commit"]:
            raise ValueError("Checkout do Paperclip em commit divergente.")
        if git("-C", path, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError("Checkout do Paperclip contém alterações locais.")
        for required in ("LICENSE", "package.json", "pnpm-lock.yaml", "Dockerfile"):
            if not (source / required).is_file():
                raise ValueError("Fonte incompleta: " + required)
    return {"component": "paperclip", "path": path, "commit": component["commit"],
            "repository": component["repository"], "checkout_verified": require_checkout}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", action="store_true", help="Também verifica a fonte baixada.")
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.checkout), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, StopIteration, subprocess.CalledProcessError) as exc:
        parser.exit(1, "Falha ao verificar Paperclip: " + str(exc) + "\n")
