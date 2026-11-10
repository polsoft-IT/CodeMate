"""HTTPS plugin catalog with SHA-256 verified, managed installs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

PLUGIN_API_VERSION = 1
MAX_INDEX_BYTES = 1_000_000
MAX_PLUGIN_BYTES = 2_000_000
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def _https_url(value: str) -> str:
    parsed = urlsplit(str(value or ""))
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Marketplace URLs must use HTTPS and cannot embed credentials")
    return value


def _download(url: str, limit: int) -> bytes:
    url = _https_url(url)
    request = Request(url, headers={"User-Agent": "CodeMate/3.5"})
    with urlopen(request, timeout=15) as response:
        final_url = response.geturl() if hasattr(response, "geturl") else url
        _https_url(final_url)
        payload = response.read(limit + 1)
    if len(payload) > limit:
        raise ValueError("Marketplace response exceeds the size limit")
    return bytes(payload)


class PluginMarketplace:
    """Loads a compatible JSON catalog and manages only marketplace-owned files."""

    def __init__(self, plugins_dir: Path | str):
        self.plugins_dir = Path(plugins_dir).resolve()
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.plugins_dir / ".marketplace.json"

    def fetch(self, index_url: str) -> List[Dict[str, Any]]:
        payload = _download(index_url, MAX_INDEX_BYTES)
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict) or data.get("api_version") != PLUGIN_API_VERSION:
            raise ValueError("Marketplace API version is incompatible")
        entries = data.get("plugins")
        if not isinstance(entries, list):
            raise ValueError("Marketplace index must contain a plugins list")
        result = []
        seen = set()
        for item in entries:
            if not isinstance(item, dict):
                raise ValueError("Invalid plugin entry")
            name, version = str(item.get("name") or ""), str(item.get("version") or "")
            digest = str(item.get("sha256") or "").lower()
            if not NAME_RE.fullmatch(name) or not version or name in seen:
                raise ValueError("Plugin names must be unique and versions non-empty")
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"Invalid SHA-256 for plugin {name}")
            _https_url(str(item.get("url") or ""))
            seen.add(name)
            result.append({
                "name": name,
                "version": version,
                "url": item["url"],
                "sha256": digest,
                "api_version": item.get("api_version"),
                "description": str(item.get("description") or ""),
            })
        return result

    def install(self, entry: Dict[str, Any]) -> Path:
        name = str(entry.get("name") or "")
        if not NAME_RE.fullmatch(name):
            raise ValueError("Invalid plugin name")
        if entry.get("api_version") != PLUGIN_API_VERSION:
            raise ValueError("Plugin API version is incompatible")
        expected = str(entry.get("sha256") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid plugin checksum")
        payload = _download(str(entry.get("url") or ""), MAX_PLUGIN_BYTES)
        if not hashlib.sha256(payload).hexdigest() == expected:
            raise ValueError("Plugin checksum does not match the catalog")
        payload.decode("utf-8")
        target = self.plugins_dir / f"{name}.py"
        manifest = self._manifest()
        if target.exists() and name not in manifest:
            raise ValueError("Refusing to overwrite a plugin not managed by the marketplace")
        temporary = target.with_suffix(".py.tmp")
        temporary.write_bytes(payload)
        temporary.replace(target)
        manifest[name] = {"version": str(entry.get("version") or ""), "sha256": expected}
        self._write_manifest(manifest)
        return target

    def remove(self, name: str) -> bool:
        if not NAME_RE.fullmatch(str(name or "")):
            raise ValueError("Invalid plugin name")
        manifest = self._manifest()
        if name not in manifest:
            return False
        target = self.plugins_dir / f"{name}.py"
        if target.is_file() and target.resolve().parent == self.plugins_dir:
            target.unlink()
        manifest.pop(name)
        self._write_manifest(manifest)
        return True

    def _manifest(self) -> Dict[str, Any]:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict):
            raise ValueError("Marketplace install manifest is invalid")
        return data

    def _write_manifest(self, data: Dict[str, Any]) -> None:
        temporary = self.manifest_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.manifest_path)