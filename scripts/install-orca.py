#!/usr/bin/env python3
"""Download and verify a pinned Orca package. --install installs without starting serve."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import tempfile
import urllib.request

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="Instalar .deb verificado com sudo apt-get")
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("Requer Linux Debian/Ubuntu.")
    arch = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine())
    if not arch:
        parser.error("Arquitetura não suportada.")
    lock = json.loads((Path(__file__).resolve().parents[1] / "config/components.lock.json").read_text())
    release = next(c for c in lock["components"] if c["id"] == "orca")["release"]
    asset = release["assets"][arch]
    with tempfile.TemporaryDirectory(prefix="arquitetura-orca-") as tmp:
        package = Path(tmp) / ("orca-ide_" + release["version"] + "_" + arch + ".deb")
        digest = hashlib.sha256()
        with urllib.request.urlopen(asset["url"], timeout=60) as response, package.open("wb") as out:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != asset["sha256"]:
            raise SystemExit("SHA256 divergente; instalação cancelada.")
        print(json.dumps({"version": release["version"], "architecture": arch, "sha256": digest.hexdigest(), "verified": True}))
        if args.install:
            subprocess.run(["sudo", "apt-get", "install", "-y", str(package)], check=True)
            installed = subprocess.run(["dpkg-query", "-W", "-f=${Version}", "orca-ide"], check=True, capture_output=True, text=True).stdout.strip()
            if installed != release["version"]:
                raise SystemExit("Versão instalada diverge do manifesto: " + installed)
            subprocess.run(["/usr/bin/orca-ide", "--version"], check=True)
            print("Orca instalado. Servidor não iniciado. Leia docs/COMPONENTES.md.")

if __name__ == "__main__":
    main()
