"""
Testy dla biblioteki snippetów (poz. 5), autouzupełniania (poz. 3)
oraz kompletności tłumaczeń etykiet opakowanych w _trw (poz. 1).
"""

import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import baza_skryptow as bs
from baza_skryptow import (
    PLACEHOLDER_RE,
    PY_BUILTINS,
    PY_KEYWORDS,
    collect_py_symbols,
    snippet_normalize,
    snippets_load,
    snippets_save,
    MENU_EN,
)

SRC_FILE = Path(__file__).parent.parent / "baza_skryptow.py"


class TestSnippetNormalize:
    """Testy normalizacji rekordu snippetu."""

    def test_none_gives_defaults(self):
        it = snippet_normalize(None)
        assert it["nazwa"] == "snippet"
        assert it["kategoria"] in bs.CATEGORIES
        assert it["tagi"] == ""
        assert it["tresc"] == ""
        assert it["id"]
        assert it["zmieniony"]

    def test_keeps_existing_fields(self):
        it = snippet_normalize({
            "id": "abc", "nazwa": "  Hello  ", "kategoria": "Python",
            "tagi": "a, b", "tresc": "print(1)", "zmieniony": "2020-01-01",
        })
        assert it["id"] == "abc"
        assert it["nazwa"] == "Hello"
        assert it["kategoria"] == "Python"
        assert it["tagi"] == "a, b"
        assert it["tresc"] == "print(1)"
        assert it["zmieniony"] == "2020-01-01"

    def test_invalid_category_falls_back(self):
        it = snippet_normalize({"kategoria": "ZupełnieNieznana"})
        assert it["kategoria"] in bs.CATEGORIES

    def test_generates_unique_ids(self):
        a = snippet_normalize({})["id"]
        b = snippet_normalize({})["id"]
        assert a != b

    def test_coerces_tresc_to_str(self):
        it = snippet_normalize({"tresc": 123})
        assert it["tresc"] == "123"


class TestSnippetsStore:
    """Testy zapisu i odczytu pliku JSON z snippetami."""

    def _use_tmp(self, monkeypatch, tmp_path):
        target = tmp_path / "snip.json"
        monkeypatch.setattr(bs, "SNIPPETS_FILE", target)
        return target

    def test_load_missing_file_returns_starter(self, monkeypatch, tmp_path):
        self._use_tmp(monkeypatch, tmp_path)
        items = snippets_load()
        assert len(items) > 0
        assert all("nazwa" in it and "tresc" in it for it in items)

    def test_load_missing_file_saves_starter(self, monkeypatch, tmp_path):
        target = self._use_tmp(monkeypatch, tmp_path)
        snippets_load()
        assert target.exists()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["schema"] == 1
        assert len(data["snippety"]) > 0

    def test_save_load_roundtrip(self, monkeypatch, tmp_path):
        self._use_tmp(monkeypatch, tmp_path)
        items = [snippet_normalize({"nazwa": "X", "tresc": "print('x')"})]
        snippets_save(items)
        loaded = snippets_load()
        assert len(loaded) == 1
        assert loaded[0]["nazwa"] == "X"
        assert loaded[0]["tresc"] == "print('x')"

    def test_saved_file_has_schema(self, monkeypatch, tmp_path):
        target = self._use_tmp(monkeypatch, tmp_path)
        snippets_save([])
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["schema"] == 1
        assert data["snippety"] == []

    def test_load_accepts_dict_wrapper(self, monkeypatch, tmp_path):
        target = self._use_tmp(monkeypatch, tmp_path)
        target.write_text(json.dumps({"snippety": [{"nazwa": "A"}]}),
                          encoding="utf-8")
        loaded = snippets_load()
        assert len(loaded) == 1
        assert loaded[0]["nazwa"] == "A"

    def test_load_bare_list(self, monkeypatch, tmp_path):
        target = self._use_tmp(monkeypatch, tmp_path)
        target.write_text(json.dumps([{"nazwa": "B"}]), encoding="utf-8")
        assert snippets_load()[0]["nazwa"] == "B"

    def test_load_corrupt_json_returns_empty(self, monkeypatch, tmp_path):
        target = self._use_tmp(monkeypatch, tmp_path)
        target.write_text("{nie-json", encoding="utf-8")
        assert snippets_load() == []

    def test_load_non_list_returns_empty(self, monkeypatch, tmp_path):
        target = self._use_tmp(monkeypatch, tmp_path)
        target.write_text(json.dumps({"snippety": "zle"}), encoding="utf-8")
        assert snippets_load() == []


class TestPlaceholders:
    """Testy wzorca placeholderów ${nazwa}."""

    def test_matches_simple(self):
        assert PLACEHOLDER_RE.findall("x = ${value}") == ["value"]

    def test_matches_multiple(self):
        assert PLACEHOLDER_RE.findall("${a} + ${b}") == ["a", "b"]

    def test_matches_space_and_dash(self):
        assert PLACEHOLDER_RE.findall("${my name}") == ["my name"]

    def test_no_match_without_dollar(self):
        assert PLACEHOLDER_RE.findall("{value}") == []


class TestCollectPySymbols:
    """Testy zbierania symboli Pythona dla autouzupełniania."""

    def test_import(self):
        assert "os" in collect_py_symbols("import os")

    def test_import_asname(self):
        assert "np" in collect_py_symbols("import numpy as np")

    def test_import_from(self):
        syms = collect_py_symbols("from pathlib import Path")
        assert "Path" in syms

    def test_function_and_class(self):
        syms = collect_py_symbols("def foo():\n    pass\nclass Bar:\n    pass\n")
        assert "foo" in syms and "Bar" in syms

    def test_arguments(self):
        assert "arg" in collect_py_symbols("def f(arg):\n    return arg\n")

    def test_assignment_name(self):
        assert "x" in collect_py_symbols("x = 1")

    def test_syntax_error_returns_empty(self):
        assert collect_py_symbols("def (") == []

    def test_empty_code(self):
        assert collect_py_symbols("") == []

    def test_result_is_sorted_and_unique(self):
        syms = collect_py_symbols("x = 1\nx = 2\nimport os")
        assert syms == sorted(set(syms))

    def test_keywords_and_builtins_nonempty(self):
        assert "def" in PY_KEYWORDS
        assert "print" in PY_BUILTINS


class TestI18nLabelCoverage:
    """Regresja poz. 1: każda etykieta owinięta w _trw ma tłumaczenie EN."""

    def _wrapped_labels(self):
        src = SRC_FILE.read_text(encoding="utf-8")
        tree = ast.parse(src)
        labels = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "_trw"
                    and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and isinstance(node.args[1].value, str)):
                labels.add(node.args[1].value)
        return labels

    def test_all_trw_labels_translated(self):
        missing = [lbl for lbl in self._wrapped_labels() if lbl not in MENU_EN]
        assert not missing, f"Brak tłumaczeń EN dla: {missing}"

    def test_labels_found(self):
        assert len(self._wrapped_labels()) > 50
