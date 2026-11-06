#!/usr/bin/env python3
"""Control a Paperclip npm installation kept in a dedicated local runtime."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import urllib.request

def paths(root):
    node = json.loads((root / "state/node-artifact.json").read_text())
    return {
        "node": Path(node["bin"]) / "node",
        "cli": root / "app/node_modules/paperclipai/dist/index.js",
        "config": root / "data/paperclip/instances/default/config.json",
        "env": root / "config/paperclip.env",
        "pid": root / "state/native-service.json",
        "log": root / "state/native-service.log",
    }

def identity(pid):
    try:
        proc = Path("/proc") / str(pid)
        fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        argv = [part.decode() for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
        return {"pid": pid, "start_ticks": fields[19], "command": argv}
    except (OSError, IndexError):
        return None

def owned_process(p):
    if not p["pid"].is_file() or p["pid"].is_symlink():
        return None
    saved = json.loads(p["pid"].read_text())
    current = identity(saved["pid"])
    if (current and current["start_ticks"] == saved["start_ticks"]
            and current["command"] == service_command(p)):
        return saved["pid"]
    return None

def service_command(p):
    return [str(p["node"]), "--env-file=" + str(p["env"]), str(p["cli"]),
            "run", "--config", str(p["config"]), "--no-repair"]

def health(port):
    # Loopback only. External requests retain the platform's configured proxies.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("http://127.0.0.1:" + str(port) + "/api/health", timeout=5) as response:
        data = json.load(response)
    if data.get("status") != "ok":
        raise ValueError("Aplicação ainda não está pronta.")
    return {key: data[key] for key in ("status", "version", "commit", "deploymentMode", "bootstrapStatus") if key in data}

def environment(root, p):
    excluded = {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                "BETTER_AUTH_SECRET", "PAPERCLIP_TOOL_ACTION_SIGNING_SECRET", "PAPERCLIP_AGENT_JWT_SECRET"}
    env = {key: value for key, value in os.environ.items() if key not in excluded}
    env["PATH"] = str(p["node"].parent) + os.pathsep + env.get("PATH", "")
    env.update({
        "PAPERCLIP_HOME": str(root / "data/paperclip"),
        "PAPERCLIP_CONFIG": str(p["config"]),
        "PAPERCLIP_INSTANCE_ID": "default",
        "PAPERCLIP_DEPLOYMENT_MODE": "authenticated",
        "PAPERCLIP_DEPLOYMENT_EXPOSURE": "private",
        "PAPERCLIP_PUBLIC_URL": "http://localhost:3100",
        "HOST": "127.0.0.1", "PORT": "3100", "SERVE_UI": "true",
        "PAPERCLIP_TELEMETRY_DISABLED": "1", "NODE_USE_ENV_PROXY": "1",
        "npm_config_cache": str(root / "cache/npm"),
    })
    for key, relative in {
        "XDG_DATA_HOME": "data/xdg", "XDG_STATE_HOME": "state/xdg",
        "XDG_CONFIG_HOME": "config/xdg", "XDG_CACHE_HOME": "cache",
    }.items():
        path = root / relative
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        env[key] = str(path)
    if env.get("CODEX_PROXY_CERT"):
        env["NODE_EXTRA_CA_CERTS"] = env["CODEX_PROXY_CERT"]
    return env

def control(root, action):
    p = paths(root)
    config = json.loads(p["config"].read_text())
    port = config["server"]["port"]
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("Porta inválida.")
    pid = owned_process(p)
    if action == "logs":
        return {"log_file": str(p["log"]), "private": True}
    if action == "status":
        return {"pid": pid, "running": pid is not None,
                "health": health(port) if pid else None}
    if action == "stop":
        if not pid:
            return {"running": False}
        if os.getpgid(pid) != pid:
            raise ValueError("Grupo do processo não corresponde ao serviço.")
        os.killpg(pid, signal.SIGTERM)
        deadline = time.monotonic() + 60
        while owned_process(p):
            if time.monotonic() >= deadline:
                raise ValueError("Parada solicitada; processo ainda está encerrando.")
            time.sleep(0.25)
        return {"running": False, "data": "preserved"}
    if pid:
        return {"pid": pid, "already_running": True, "health": health(port)}
    for name in ("node", "cli", "env"):
        if not p[name].is_file():
            raise ValueError("Instalação/configuração ausente: " + str(p[name]))
    if p["env"].is_symlink() or p["env"].stat().st_mode & 0o077:
        raise ValueError("Configuração de segredos requer arquivo regular com modo 600.")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
    command = service_command(p)
    logfd = os.open(p["log"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(logfd, "ab") as log:
        process = subprocess.Popen(command, cwd=root / "app", env=environment(root, p),
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
    record = identity(process.pid)
    if not record:
        raise ValueError("O processo encerrou durante a inicialização; consulte o log privado.")
    fd = os.open(p["pid"], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as out:
        json.dump(record, out)
    print(json.dumps({"pid": process.pid, "status": "starting", "log_file": str(p["log"])}), flush=True)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ValueError("O serviço encerrou; consulte o log privado.")
        try:
            return {"pid": process.pid, "health": health(port), "url": "http://127.0.0.1:" + str(port)}
        except (OSError, ValueError):
            time.sleep(1)
    raise ValueError("Serviço ainda está inicializando; consulte status e o log privado.")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("action", choices=("start", "status", "stop", "logs"))
    args = parser.parse_args()
    try:
        root = Path(args.root).expanduser().resolve()
        if args.action in {"start", "stop"}:
            lock = root / "state/native-control.lock"
            if lock.is_symlink():
                raise ValueError("Lock do serviço não pode ser um symlink.")
            with lock.open("a") as stream:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError("Outra operação já está controlando este serviço.")
                result = control(root, args.action)
        else:
            result = control(root, args.action)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
