import hashlib
import json
from io import BytesIO

import pytest

from src.plugin_marketplace import PLUGIN_API_VERSION, PluginMarketplace


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def test_fetch_validates_catalog_and_install_verifies_hash(tmp_path, monkeypatch):
    plugin_bytes = b"from src.plugin_system import BasePlugin\n"
    entry = {
        "name": "demo_plugin", "version": "1.2.0", "url": "https://example.test/demo.py",
        "sha256": hashlib.sha256(plugin_bytes).hexdigest(),
        "api_version": PLUGIN_API_VERSION, "description": "Demo",
    }
    catalog = json.dumps({"api_version": PLUGIN_API_VERSION, "plugins": [entry]}).encode()
    monkeypatch.setattr("src.plugin_marketplace.urlopen", lambda request, timeout: FakeResponse(
        catalog if request.full_url.endswith("index.json") else plugin_bytes))
    marketplace = PluginMarketplace(tmp_path / "plugins")
    fetched = marketplace.fetch("https://example.test/index.json")
    assert fetched == [entry]
    path = marketplace.install(fetched[0])
    assert path.read_bytes() == plugin_bytes
    assert marketplace.remove("demo_plugin")
    assert not path.exists()
    assert marketplace.remove("demo_plugin") is False


def test_rejects_http_catalog(tmp_path):
    with pytest.raises(ValueError, match="HTTPS"):
        PluginMarketplace(tmp_path).fetch("http://example.test/index.json")


def test_rejects_https_download_redirected_to_http(tmp_path, monkeypatch):
    class RedirectedResponse(FakeResponse):
        def geturl(self):
            return "http://example.test/plugin.py"

    monkeypatch.setattr("src.plugin_marketplace.urlopen", lambda *a, **k:
                        RedirectedResponse(b'{"api_version": 1, "plugins": []}'))
    with pytest.raises(ValueError, match="HTTPS"):
        PluginMarketplace(tmp_path).fetch("https://example.test/index.json")


def test_rejects_incompatible_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr("src.plugin_marketplace.urlopen", lambda *a, **k:
                        FakeResponse(b'{"api_version": 99, "plugins": []}'))
    with pytest.raises(ValueError, match="incompatible"):
        PluginMarketplace(tmp_path).fetch("https://example.test/index.json")


def test_rejects_checksum_mismatch(tmp_path, monkeypatch):
    entry = {
        "name": "demo_plugin", "version": "1", "url": "https://example.test/demo.py",
        "sha256": "0" * 64, "api_version": PLUGIN_API_VERSION,
    }
    monkeypatch.setattr("src.plugin_marketplace.urlopen", lambda *a, **k: FakeResponse(b"not matching"))
    with pytest.raises(ValueError, match="checksum"):
        PluginMarketplace(tmp_path).install(entry)


def _fetch_catalog(tmp_path, monkeypatch, plugins):
    catalog = json.dumps({"api_version": PLUGIN_API_VERSION, "plugins": plugins}).encode()
    monkeypatch.setattr("src.plugin_marketplace.urlopen", lambda *a, **k: FakeResponse(catalog))
    return PluginMarketplace(tmp_path / "plugins").fetch("https://example.test/index.json")


def test_rejects_oversized_download(tmp_path, monkeypatch):
    from src import plugin_marketplace as pm

    monkeypatch.setattr(pm, "urlopen", lambda *a, **k: FakeResponse(b"x" * 100))
    with pytest.raises(ValueError, match="size limit"):
        pm._download("https://example.test/plugin.py", 10)


def test_rejects_catalog_without_plugins_list(tmp_path, monkeypatch):
    catalog = json.dumps({"api_version": PLUGIN_API_VERSION, "plugins": {}}).encode()
    monkeypatch.setattr("src.plugin_marketplace.urlopen", lambda *a, **k: FakeResponse(catalog))
    with pytest.raises(ValueError, match="plugins list"):
        PluginMarketplace(tmp_path).fetch("https://example.test/index.json")


def test_rejects_non_dict_plugin_entry(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="Invalid plugin entry"):
        _fetch_catalog(tmp_path, monkeypatch, ["not-a-dict"])


def test_rejects_duplicate_or_invalid_plugin_names(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="unique"):
        _fetch_catalog(tmp_path, monkeypatch, [
            {"name": "bad name!", "version": "1", "url": "https://e.test/p.py",
             "sha256": "0" * 64},
        ])
    entry = {"name": "demo", "version": "1", "url": "https://e.test/p.py",
             "sha256": "0" * 64}
    with pytest.raises(ValueError, match="unique"):
        _fetch_catalog(tmp_path, monkeypatch, [entry, dict(entry)])


def test_rejects_invalid_plugin_checksum_in_catalog(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="SHA-256"):
        _fetch_catalog(tmp_path, monkeypatch, [
            {"name": "demo", "version": "1", "url": "https://e.test/p.py",
             "sha256": "not-hex"},
        ])


def test_install_rejects_invalid_name_and_version(tmp_path):
    marketplace = PluginMarketplace(tmp_path)
    base = {"version": "1", "url": "https://e.test/p.py", "sha256": "0" * 64,
            "api_version": PLUGIN_API_VERSION}
    with pytest.raises(ValueError, match="Invalid plugin name"):
        marketplace.install(dict(base, name="bad name!"))
    with pytest.raises(ValueError, match="incompatible"):
        marketplace.install(dict(base, name="demo", api_version=99))
    with pytest.raises(ValueError, match="checksum"):
        marketplace.install(dict(base, name="demo", sha256="zz"))


def test_remove_rejects_invalid_name(tmp_path):
    with pytest.raises(ValueError, match="Invalid plugin name"):
        PluginMarketplace(tmp_path).remove("bad name!")


def test_manifest_with_wrong_shape_is_rejected(tmp_path):
    marketplace = PluginMarketplace(tmp_path)
    marketplace.manifest_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest is invalid"):
        marketplace.remove("demo")


def test_remove_cannot_delete_unmanaged_plugin(tmp_path):
    marketplace = PluginMarketplace(tmp_path)
    unmanaged = tmp_path / "my_plugin.py"
    unmanaged.write_text("# local plugin", encoding="utf-8")
    assert not marketplace.remove("my_plugin")
    assert unmanaged.exists()


def test_install_cannot_overwrite_unmanaged_plugin(tmp_path, monkeypatch):
    payload = b"print('marketplace')"
    entry = {
        "name": "local_plugin", "version": "1", "url": "https://example.test/plugin.py",
        "sha256": hashlib.sha256(payload).hexdigest(), "api_version": PLUGIN_API_VERSION,
    }
    monkeypatch.setattr("src.plugin_marketplace.urlopen", lambda *a, **k: FakeResponse(payload))
    existing = tmp_path / "local_plugin.py"
    existing.write_text("# preserve local code", encoding="utf-8")
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        PluginMarketplace(tmp_path).install(entry)
    assert existing.read_text(encoding="utf-8") == "# preserve local code"
