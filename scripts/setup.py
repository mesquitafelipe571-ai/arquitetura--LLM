#!/usr/bin/env python3
"""Workspace manager for a single Google VM. Python stdlib only."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path.home() / ".local/share/arquitetura-llm"
SECRET_KEYS = ("BETTER_AUTH_SECRET", "PAPERCLIP_TOOL_ACTION_SIGNING_SECRET",
               "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")

def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))

def run(argv, **kwargs):
    return subprocess.run([str(a) for a in argv], check=True, **kwargs)

def capture(argv, **kwargs):
    return run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs).stdout.strip()

def load_components():
    data = json.loads((REPO / "config/components.lock.json").read_text())
    if data.get("schema_version") != 1:
        raise ValueError("Versão de manifesto não suportada.")
    result = {}
    for c in data["components"]:
        if not re.fullmatch(r"[a-z0-9-]+", c["id"]) or c["id"] in result:
            raise ValueError("ID de componente inválido ou duplicado.")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", c["repository"]):
            raise ValueError("Repositório inválido.")
        if not re.fullmatch(r"[a-f0-9]{40}", c["commit"]):
            raise ValueError("É necessário um commit SHA completo.")
        result[c["id"]] = c
    return result

def source_path(root, component):
    return root / "sources" / component["id"] / component["commit"]

def safe_root(value):
    root = Path(value).expanduser().resolve()
    if root == Path("/") or root == Path.home().resolve() or root == REPO or REPO in root.parents:
        raise ValueError("Use um diretório de runtime dedicado fora deste repositório.")
    return root

def atomic_json(path, value):
    # Replace only owned state files. Never follow a destination symlink.
    if path.is_symlink():
        raise ValueError("Destino de estado é um symlink: " + str(path))
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as tmp:
        json.dump(value, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        name = tmp.name
    os.chmod(name, 0o600)
    os.replace(name, path)

@contextmanager
def mutation_lock(root):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = root / ".setup.lock"
    if lock.is_symlink():
        raise ValueError("Lock não pode ser um symlink.")
    with lock.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Outra operação já está usando este runtime.")
        yield

def initialize(root):
    for relative in ("config", "sources", "data/paperclip", "state", "backups"):
        current = root
        for part in Path(relative).parts:
            current /= part
            if current.is_symlink():
                raise ValueError("Diretório de runtime é um symlink: " + str(current))
            current.mkdir(exist_ok=True, mode=0o700)
    envfile = root / "config/paperclip.env"
    if envfile.is_symlink():
        raise ValueError("Configuração não pode ser symlink.")
    if not envfile.exists():
        if any((root / "data/paperclip").iterdir()):
            raise ValueError("Dados existentes sem configuração: restaure paperclip.env do backup; não gere novos segredos.")
        content = (
            "# Local à VM. Nunca versionar. Preserve os segredos nos backups.\n"
            "BETTER_AUTH_SECRET=" + secrets.token_hex(32) + "\n"
            "PAPERCLIP_TOOL_ACTION_SIGNING_SECRET=" + secrets.token_hex(32) + "\n"
            "OPENAI_API_KEY=\nANTHROPIC_API_KEY=\nGEMINI_API_KEY=\n"
        )
        fd = os.open(envfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as out:
            out.write(content)
    elif envfile.stat().st_mode & 0o077:
        raise ValueError("Configuração deve ser privada: chmod 600 " + str(envfile))
    return envfile

def verify_source(path, component):
    if path.is_symlink() or not (path / ".git").is_dir():
        raise ValueError("Checkout ausente ou inválido: " + str(path))
    if capture(["git", "-C", path, "rev-parse", "HEAD"]) != component["commit"]:
        raise ValueError("Commit divergente: " + str(path))
    expected = "https://github.com/" + component["repository"] + ".git"
    if capture(["git", "-C", path, "remote", "get-url", "origin"]) != expected:
        raise ValueError("Origem divergente: " + str(path))
    if capture(["git", "-C", path, "status", "--porcelain", "--untracked-files=all", "--ignored"]):
        raise ValueError("Checkout contém alterações; preserve-as antes de continuar: " + str(path))

def sync_component(root, component):
    target = source_path(root, component)
    if target.exists() or target.is_symlink():
        verify_source(target, component)
        return {"component": component["id"], "status": "already_present", "commit": component["commit"]}
    parent = target.parent
    if parent.is_symlink():
        raise ValueError("Diretório do componente não pode ser symlink.")
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".fetch-", dir=parent))
    try:
        url = "https://github.com/" + component["repository"] + ".git"
        capture(["git", "init", "--quiet", staging])
        capture(["git", "-C", staging, "remote", "add", "origin", url])
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        capture(["git", "-C", staging, "fetch", "--depth=1", "--no-tags", "origin", component["commit"]], env=env, timeout=600)
        capture(["git", "-C", staging, "checkout", "--detach", "--quiet", component["commit"]])
        verify_source(staging, component)
        staging.rename(target)
    finally:
        # Only this invocation's unpublished staging directory is removed.
        if staging.exists():
            shutil.rmtree(staging)
    return {"component": component["id"], "status": "downloaded", "commit": component["commit"]}

def sync_all(root, components, jobs):
    results = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        tasks = {pool.submit(sync_component, root, c): c for c in components}
        for task in as_completed(tasks):
            c = tasks[task]
            try:
                results.append(task.result())
            except Exception as exc:
                results.append({"component": c["id"], "status": "failed", "error": str(exc)})
    results.sort(key=lambda r: r["component"])
    atomic_json(root / "state/sync.json", {"results": results})
    return results

def tree_digest(folder):
    digest = hashlib.sha256()
    for p in sorted(folder.rglob("*")):
        if p.is_symlink():
            raise ValueError("Symlink não permitido em skill: " + str(p))
        if p.is_file():
            digest.update(str(p.relative_to(folder)).encode() + b"\0" + p.read_bytes())
    return digest.hexdigest()

def export_skills(root, component, project, selected):
    source = source_path(root, component)
    verify_source(source, component)
    project = Path(project).expanduser().resolve()
    if not project.is_dir() or project == root or root in project.parents:
        raise ValueError("Escolha um projeto existente fora do runtime.")
    for part in (project / ".agents", project / ".agents/skills"):
        if part.is_symlink():
            raise ValueError("Destino de skills não pode ser um symlink.")
        part.mkdir(exist_ok=True)
    target_root = project / ".agents/skills"
    metadata = target_root / ".arquitetura-llm-sources.json"
    if metadata.is_symlink():
        raise ValueError("Manifesto de skills não pode ser um symlink.")
    previous = json.loads(metadata.read_text()) if metadata.exists() else {}
    planned = []
    for name in selected:
        if name not in component.get("skills", []):
            raise ValueError("Skill não está no catálogo curado: " + name)
        src = source / "skills" / name
        dst = target_root / name
        if src.is_symlink() or not (src / "SKILL.md").is_file():
            raise ValueError("Skill inválida: " + name)
        digest = tree_digest(src)
        if dst.exists() or dst.is_symlink():
            if dst.is_symlink() or not dst.is_dir() or tree_digest(dst) != digest:
                raise ValueError("Colisão: destino preservado, sem sobrescrita: " + str(dst))
        planned.append((name, src, dst, digest))
    license_dir = project / ".agents/upstream-licenses"
    if license_dir.is_symlink():
        raise ValueError("Diretório de licenças não pode ser symlink.")
    license_file = next((source / n for n in ("LICENSE", "LICENSE.md") if (source / n).is_file()), None)
    if not license_file or license_file.is_symlink():
        raise ValueError("Licença upstream ausente ou inválida.")
    if license_file:
        dest = license_dir / (component["id"] + "-" + component["commit"] + ".txt")
        if dest.is_symlink() or (dest.exists() and dest.read_bytes() != license_file.read_bytes()):
            raise ValueError("Colisão de licença.")
    # All conflicts, including licenses, were checked before writing any skill.
    license_dir.mkdir(exist_ok=True)
    for name, src, dst, digest in planned:
        if not dst.exists():
            shutil.copytree(src, dst)
        previous[name] = {"repository": component["repository"], "commit": component["commit"],
                          "source": "skills/" + name, "sha256": digest, "license": component["license"]}
    if not dest.exists():
        shutil.copyfile(license_file, dest)
    atomic_json(metadata, previous)
    return {"project": str(project), "skills": [p[0] for p in planned]}

def compose(root, component, sudo):
    verify_source(source_path(root, component), component)
    envfile = root / "config/paperclip.env"
    if not envfile.is_file() or envfile.is_symlink() or envfile.stat().st_mode & 0o077:
        raise ValueError("Execute init; configuração precisa existir com modo 600.")
    env = {k: v for k, v in os.environ.items() if k not in SECRET_KEYS}
    env["ALM_PAPERCLIP_SOURCE"] = str(source_path(root, component))
    env["ALM_PAPERCLIP_DATA"] = str(root / "data/paperclip")
    # sudo normally drops env; pass only the non-secret interpolation paths explicitly.
    prefix = ["sudo", "env", "ALM_PAPERCLIP_SOURCE=" + env["ALM_PAPERCLIP_SOURCE"],
              "ALM_PAPERCLIP_DATA=" + env["ALM_PAPERCLIP_DATA"]] if sudo else []
    project_name = "alm-" + hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12]
    cmd = prefix + ["docker", "compose", "--project-name", project_name,
                    "--env-file", str(envfile), "-f", str(REPO / "compose.paperclip.json")]
    return cmd, env

def health():
    with urllib.request.urlopen("http://127.0.0.1:3100/api/health", timeout=10) as response:
        data = json.load(response)
    if data.get("status") != "ok":
        raise ValueError("Serviço ainda não está pronto: " + str(data.get("status")))
    return {k: data[k] for k in ("status", "commit", "bootstrapStatus") if k in data}

def paperclip(root, component, sudo, action):
    cmd, env = compose(root, component, sudo)
    if action == "build":
        run(cmd + ["build", "paperclip"], env=env)
        image = "arquitetura-llm/paperclip:" + component["commit"]
        docker = (["sudo"] if sudo else []) + ["docker"]
        image_id = capture(docker + ["image", "inspect", "--format", "{{.Id}}", image])
        receipt = {"source_commit": component["commit"], "image_id": image_id,
                   "built_at": datetime.now(timezone.utc).isoformat(),
                   "note": "Upstream inclui tags/dependências mutáveis; o SHA fixa somente o código."}
        atomic_json(root / "state/paperclip-build.json", receipt)
        return receipt
    if action == "up":
        receipt_file = root / "state/paperclip-build.json"
        if not receipt_file.exists():
            raise ValueError("Execute paperclip build antes de iniciar.")
        receipt = json.loads(receipt_file.read_text())
        docker = (["sudo"] if sudo else []) + ["docker"]
        actual = capture(docker + ["image", "inspect", "--format", "{{.Id}}",
                                 "arquitetura-llm/paperclip:" + component["commit"]])
        if actual != receipt["image_id"] or component["commit"] != receipt["source_commit"]:
            raise ValueError("Imagem difere do recibo de build.")
        run(cmd + ["up", "-d", "--no-build", "--wait", "--wait-timeout", "240"], env=env)
        return health()
    if action == "stop":
        run(cmd + ["stop", "paperclip"], env=env)
        return {"status": "stopped", "data": "preserved"}
    if action == "logs":
        run(cmd + ["logs", "--tail=100", "paperclip"], env=env)
        return {"note": "Logs podem conter dados privados; não publique sem revisar."}
    if action == "status":
        run(cmd + ["ps"], env=env)
        return health()
    if action == "backup":
        docker = (["sudo"] if sudo else []) + ["docker"]
        container = capture(cmd + ["ps", "-a", "-q", "paperclip"], env=env)
        if not container or "\n" in container:
            raise ValueError("Backup requer exatamente um container Paperclip existente.")
        mounts = json.loads(capture(docker + ["inspect", "--format", "{{json .Mounts}}", container]))
        expected = str((root / "data/paperclip").resolve())
        if not any(m["Destination"] == "/paperclip" and m["Source"] == expected and m["Type"] == "bind" for m in mounts):
            raise ValueError("Volume do container não corresponde a este runtime.")
        original_image = capture(docker + ["inspect", "--format", "{{.Image}}", container])
        source_revision = capture(docker + ["image", "inspect", "--format",
                                  '{{index .Config.Labels "org.opencontainers.image.revision"}}', original_image])
        if not re.fullmatch(r"[a-f0-9]{40}", source_revision):
            raise ValueError("Imagem original sem revisão comprovada; backup automático recusado.")
        running = capture(docker + ["inspect", "--format", "{{.State.Running}}", container]) == "true"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup = root / "backups" / stamp
        backup.mkdir(mode=0o700)
        try:
            run(docker + ["stop", "--time", "90", container])
            with (backup / "data.tar").open("xb") as out:
                os.chmod(backup / "data.tar", 0o600)
                run(docker + ["run", "--rm", "--pull", "never", "--network", "none",
                             "--user", "0", "--entrypoint", "tar", "--mount",
                             "type=bind,src=" + expected + ",dst=/data,readonly",
                             original_image, "-C", "/data", "-cf", "-", "."], stdout=out)
            shutil.copy2(root / "config/paperclip.env", backup / "paperclip.env")
            shutil.copy2(REPO / "config/components.lock.json", backup / "components.lock.json")
            atomic_json(backup / "manifest.json", {"complete": True, "container_id": container,
                        "image_id": original_image, "source_commit": source_revision})
        finally:
            if running:
                # Resume the SAME container/image; never recreate it during backup.
                run(docker + ["start", container])
                deadline = time.monotonic() + 240
                while capture(docker + ["inspect", "--format", "{{.State.Health.Status}}", container]) != "healthy":
                    if time.monotonic() >= deadline:
                        raise ValueError("Container retomado, mas healthcheck não ficou saudável em 240s.")
                    time.sleep(2)
        return {"backup": str(backup), "contains_secrets": True}

def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(DEFAULT_ROOT))
    p.add_argument("--sudo-docker", action="store_true", help="Executar somente Docker com sudo")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    sub.add_parser("init")
    sub.add_parser("doctor")
    sync = sub.add_parser("sync")
    sync.add_argument("--component", action="append", default=[])
    sync.add_argument("--jobs", type=int, choices=range(1, 7), default=3)
    skills = sub.add_parser("skills")
    skills.add_argument("component", choices=("ecc", "ponytail"))
    skills.add_argument("--project", required=True)
    skills.add_argument("--skill", action="append", default=[])
    app = sub.add_parser("paperclip")
    app.add_argument("action", choices=("build", "up", "status", "stop", "logs", "backup"))
    return p

def main():
    args = parser().parse_args()
    try:
        root = safe_root(args.root)
        components = load_components()
        if args.command == "plan":
            emit({"runtime": str(root), "components": list(components.values()),
                  "parallel_downloads": 3, "cloud_chats_connected": False})
            return 0
        if args.command == "doctor":
            docker = (["sudo"] if args.sudo_docker else []) + ["docker"]
            checks = {"git": bool(shutil.which("git")), "python_3_10_plus": sys.version_info >= (3, 10)}
            try:
                capture(docker + ["compose", "version"])
                capture(docker + ["buildx", "version"])
                capture(docker + ["info", "--format", "{{.ServerVersion}}"])
                checks["docker_and_compose"] = True
            except (OSError, subprocess.SubprocessError):
                checks["docker_and_compose"] = False
            emit({"checks": checks, "runtime": str(root), "secrets_printed": False})
            return 0 if all(checks.values()) else 1
        # All mutations are serialized across invocations; sync workers own distinct checkouts.
        with mutation_lock(root):
            if args.command == "init":
                initialize(root)
                emit({"runtime": str(root), "configuration": str(root / "config/paperclip.env"), "secrets": "preserved_or_created"})
                return 0
            if not (root / "config/paperclip.env").is_file() or not (root / "state").is_dir():
                raise ValueError("Runtime não inicializado. Execute init; se havia dados, restaure o backup.")
            if args.command == "sync":
                selected = [components[name] for name in dict.fromkeys(args.component)] if args.component else [
                    c for c in components.values() if c["identity"] == "verified"]
                results = sync_all(root, selected, args.jobs)
                emit({"results": results})
                return 1 if any(r["status"] == "failed" for r in results) else 0
            elif args.command == "skills":
                c = components[args.component]
                emit(export_skills(root, c, args.project, args.skill or c["skills"]))
            else:
                emit(paperclip(root, components["paperclip"], args.sudo_docker, args.action))
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        emit({"error": str(exc)})
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
