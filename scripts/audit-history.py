#!/usr/bin/env python3
"""Extract repository references from explicitly supplied local histories. No network."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import stat

MAX_DEPTH = 64
MAX_EVIDENCE = 10000
REPO_PATTERN = re.compile(
    r"(?P<prefix>https?://(?:www\.)?github\.com/|https?://raw\.githubusercontent\.com/|git@github\.com[:/])"
    r"(?P<owner>[A-Za-z0-9][A-Za-z0-9-]{0,38})/(?P<repo>[A-Za-z0-9_.-]{1,100})",
    re.IGNORECASE,
)
REA_PATTERN = re.compile(r"\bREA\b", re.IGNORECASE)
RESERVED = {
    "orgs", "users", "settings", "login", "logout", "search", "topics", "marketplace",
    "apps", "features", "notifications", "sponsors", "collections", "organizations",
    "new", "codespaces", "security", "about", "site", "pricing", "contact",
    "enterprise", "readme", "explore", "pulls", "issues", "account",
}
EXCLUDED_DIRS = {".git", "node_modules", ".ssh", ".aws", ".config", "__pycache__"}
EXCLUDED_NAMES = {"auth.json", "credentials.json", "credentials", "config.json", "config.toml", ".env"}

def repository_links(text):
    result = {}
    for match in REPO_PATTERN.finditer(text):
        owner, repo = match["owner"], match["repo"].rstrip(".")
        if repo.lower().endswith(".git"):
            repo = repo[:-4]
        if owner.lower() in RESERVED or not repo or repo in {".", ".."}:
            continue
        name = owner + "/" + repo
        result.setdefault(name.lower(), {"repository": name, "url": "https://github.com/" + name})
    return list(result.values())

def text_units(value, location="$", depth=0):
    if depth > MAX_DEPTH:
        raise ValueError("nesting_limit")
    if isinstance(value, str):
        yield location, value
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from text_units(item, location + "[" + str(i) + "]", depth + 1)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from text_units(item, location + "[" + json.dumps(str(key), ensure_ascii=False) + "]", depth + 1)

def has_symlink(path):
    return any(part.is_symlink() for part in (path, *path.parents))

def is_excluded(path):
    name = path.name.lower()
    return name in EXCLUDED_NAMES or name.startswith(".env.") or "credential" in name or name.endswith(".pem")

def origin_of(record):
    if not isinstance(record, dict):
        return "unknown"
    payload = record.get("payload", record)
    if not isinstance(payload, dict):
        return "unknown"
    author = payload.get("author")
    role = author.get("role") if isinstance(author, dict) else payload.get("role")
    if role in {"user", "assistant", "system", "developer", "tool"}:
        return role
    event = payload.get("type")
    if event == "user_message":
        return "user"
    if event == "agent_message":
        return "assistant"
    return "metadata_or_unknown"

def source_id(record):
    if not isinstance(record, dict):
        return None
    value = record.get("conversation_id", record.get("session_id", record.get("id")))
    return value if isinstance(value, str) and 0 < len(value) <= 256 else None

class Auditor:
    def __init__(self, max_bytes=32 * 1024 * 1024):
        self.max_bytes = max_bytes
        self.sessions = {}
        self.files = []
        self.errors = []
        self.skipped = []
        self.pagination = []
        self.evidence_count = 0

    def session(self, key, sid=None):
        if key not in self.sessions:
            self.sessions[key] = {"source_session_id": sid, "source_files": set(),
                                  "references": [], "rea_mentions": [], "rea_candidates": []}
        return self.sessions[key]

    def consume(self, key, value, file, location, sid=None, origin=None):
        session = self.session(key, sid)
        session["source_files"].add(file)
        role = origin or origin_of(value)
        for locator, text in text_units(value, location):
            links = repository_links(text)
            rea = bool(REA_PATTERN.search(text))
            if not links and not rea:
                continue
            self.evidence_count += len(links) + int(rea)
            if self.evidence_count > MAX_EVIDENCE:
                raise ValueError("evidence_limit")
            evidence = {"file": file, "locator": locator, "origin": role}
            for link in links:
                session["references"].append({**link, "evidence": evidence})
                if rea:
                    session["rea_candidates"].append({**link, "evidence": evidence,
                        "classification": "same_text_unit_only", "definition_confirmed": False})
            if rea:
                session["rea_mentions"].append({**evidence, "term": "REA"})

    def json_document(self, data, file):
        prefix = "json:" + file
        if isinstance(data, dict):
            for key in ("sessions", "conversations", "threads"):
                if isinstance(data.get(key), list):
                    if data.get("next_cursor") or data.get("nextCursor") or data.get("has_more") is True:
                        self.pagination.append({"file": file, "reason": "continuation_declared"})
                    for i, record in enumerate(data[key]):
                        self.json_session(record, file, "$[" + json.dumps(key) + "][" + str(i) + "]", prefix + ":" + str(i))
                    return
            self.json_session(data, file, "$", prefix)
        elif isinstance(data, list) and all(isinstance(item, dict) for item in data):
            # A list of messages is one session; a list of conversations is many.
            if data and all("role" in item and "content" in item for item in data):
                for i, item in enumerate(data):
                    self.consume(prefix, item, file, "$[" + str(i) + "]")
            else:
                for i, record in enumerate(data):
                    self.json_session(record, file, "$[" + str(i) + "]", prefix + ":" + str(i))
        else:
            raise ValueError("unsupported_json_structure")

    def json_session(self, record, file, location, fallback):
        if not isinstance(record, dict):
            raise ValueError("unsupported_session_structure")
        sid = source_id(record)
        key = ("json-id:" + sid) if sid else fallback
        mapping = record.get("mapping")
        if isinstance(mapping, dict):
            self.session(key, sid)["source_files"].add(file)
            for node_id, node in mapping.items():
                if isinstance(node, dict) and isinstance(node.get("message"), dict):
                    loc = location + '["mapping"][' + json.dumps(str(node_id)) + ']["message"]'
                    self.consume(key, node["message"], file, loc, sid)
            return
        self.consume(key, record, file, location, sid)

    def json_lines(self, stream, file):
        key, sid = "jsonl:" + file, None
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("unsupported_jsonl_record")
            except (ValueError, RecursionError):
                self.errors.append({"file": file, "line": number, "reason": "invalid_jsonl_record"})
                continue
            if record.get("type") == "session_meta" and isinstance(record.get("payload"), dict):
                new_sid = source_id(record["payload"])
                if new_sid:
                    # JSONL headers usually precede all messages. Keep source IDs scoped by format.
                    sid = new_sid
                    key = "jsonl-id:" + sid
            self.consume(key, record, file, "line:" + str(number), sid)

    def read_file(self, path):
        file = str(path.absolute())
        if has_symlink(path):
            self.skipped.append({"file": file, "reason": "symlink"})
            return
        if is_excluded(path):
            self.skipped.append({"file": file, "reason": "credential_or_configuration_file"})
            return
        try:
            before = len(self.errors)
            info = path.stat()
            if info.st_size > self.max_bytes:
                self.skipped.append({"file": file, "reason": "size_limit", "bytes": info.st_size})
                return
            if not path.is_file():
                self.skipped.append({"file": file, "reason": "not_regular_file"})
                return
            # Enforce a second size check on actual bytes in case a file grows during the audit.
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            fd = os.open(path, flags)
            with os.fdopen(fd, "rb") as raw:
                if not stat.S_ISREG(os.fstat(raw.fileno()).st_mode):
                    raise ValueError("not_regular_file")
                data = raw.read(self.max_bytes + 1)
            if len(data) > self.max_bytes:
                self.skipped.append({"file": file, "reason": "size_limit"})
                return
            text = data.decode("utf-8-sig")
            suffix = path.suffix.lower()
            if suffix == ".jsonl":
                self.json_lines(text.splitlines(), file)
            elif suffix == ".json":
                self.json_document(json.loads(text), file)
            elif suffix in {".txt", ".md"}:
                self.consume("text:" + file, text, file, "text", origin="unknown")
            else:
                self.skipped.append({"file": file, "reason": "unsupported_extension"})
                return
            self.files.append({"file": file, "fully_parsed": len(self.errors) == before})
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            reason = str(exc) if isinstance(exc, ValueError) and str(exc) in {
                "nesting_limit", "evidence_limit", "unsupported_json_structure", "unsupported_session_structure"
            } else type(exc).__name__
            self.errors.append({"file": file, "reason": reason})

    def audit(self, inputs, include_text=False):
        selected = []
        extensions = {".json", ".jsonl"} | ({".md", ".txt"} if include_text else set())
        seen = set()
        for source in inputs:
            path = Path(source).expanduser()
            if path.is_symlink():
                self.skipped.append({"file": str(path.absolute()), "reason": "symlink"})
                continue
            if path.is_dir():
                def walk_error(error):
                    self.errors.append({"file": str(error.filename), "reason": "directory_read_error"})
                for base, dirs, names in os.walk(path, followlinks=False, onerror=walk_error):
                    for name in list(dirs):
                        candidate = Path(base) / name
                        if candidate.is_symlink():
                            self.skipped.append({"file": str(candidate.absolute()), "reason": "symlink_directory"})
                            dirs.remove(name)
                        elif name in EXCLUDED_DIRS:
                            self.skipped.append({"file": str(candidate.absolute()), "reason": "excluded_directory"})
                            dirs.remove(name)
                    selected.extend(Path(base) / name for name in names if Path(name).suffix.lower() in extensions)
            else:
                selected.append(path)
        for path in sorted(selected, key=lambda p: str(p)):
            key = str(path.absolute())
            if key in seen:
                continue
            seen.add(key)
            self.read_file(path)
        repositories = {}
        sessions = []
        for key, session in self.sessions.items():
            references = session["references"]
            for item in references:
                name = item["repository"].lower()
                target = repositories.setdefault(name, {
                    "repository": item["repository"], "url": item["url"], "evidence": []})
                if item["evidence"] not in target["evidence"]:
                    target["evidence"].append(item["evidence"])
            sessions.append({**session, "source_files": sorted(session["source_files"])})
        return {
            "schema_version": 1, "source_scope": "provided_local_files",
            "cloud_history_accessed": False, "account_audit_complete": False,
            "all_provided_files_parsed": bool(self.files) and not self.errors and not self.skipped and not self.pagination,
            "files_discovered": len(seen), "files_parsed": len(self.files),
            "files_skipped": self.skipped, "files": self.files, "errors": self.errors,
            "pagination_pending": self.pagination, "sessions_read": len(sessions),
            "sessions": sessions, "repositories": sorted(repositories.values(), key=lambda r: r["repository"].lower()),
            "rea_definition_confirmed": False,
            "note": "Cobertura apenas dos arquivos fornecidos. Referências e coocorrências não são instruções nem comprovam o significado de REA.",
        }

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, help="Arquivo ou diretório autorizado; pode repetir")
    parser.add_argument("--output", help="Novo arquivo JSON; recusa sobrescrita")
    parser.add_argument("--include-text", action="store_true", help="Incluir TXT/MD ao percorrer diretórios")
    parser.add_argument("--max-file-mib", type=int, choices=range(1, 129), default=32)
    args = parser.parse_args(argv)
    output = Path(args.output).expanduser() if args.output else None
    if output and (output.exists() or output.is_symlink()):
        parser.error("O arquivo de saída já existe; escolha um novo caminho.")
    report = Auditor(args.max_file_mib * 1024 * 1024).audit(args.input, args.include_text)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    try:
        if output:
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(rendered)
            print(json.dumps({"output": str(output), "repositories": len(report["repositories"]),
                              "sessions_read": report["sessions_read"],
                              "all_provided_files_parsed": report["all_provided_files_parsed"]}, ensure_ascii=False))
        else:
            sys.stdout.write(rendered)
    except OSError as exc:
        print(json.dumps({"error": type(exc).__name__}), file=sys.stderr)
        return 1
    return 0 if report["all_provided_files_parsed"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
