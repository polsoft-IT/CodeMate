"""
Testy grafu zależności skryptów (poz. 8 planu działania).

Sprawdzają czyste funkcje: ``module_key``, ``collect_py_imports``,
``build_dep_graph``, ``find_cycles`` oraz ``find_isolated``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from baza_skryptow import (
    build_dep_graph,
    collect_py_imports,
    find_cycles,
    find_isolated,
    module_key,
)


class TestModuleKey:
    """Normalizacja nazwy skryptu do klucza modułu."""

    def test_plain_name(self):
        assert module_key("utils") == "utils"

    def test_spaces_and_case(self):
        assert module_key("Moja Biblio") == "moja_biblio"

    def test_strips_py_extension(self):
        assert module_key("Moja Biblio.py") == "moja_biblio"

    def test_non_identifier_chars(self):
        assert module_key("Util-2") == "util_2"

    def test_empty_or_junk(self):
        assert module_key("") == "bez_nazwy"
        assert module_key("!!!") == "bez_nazwy"
        assert module_key(None) == "bez_nazwy"


class TestCollectPyImports:
    """Zbieranie importów najwyższego poziomu."""

    def test_simple_import(self):
        assert collect_py_imports("import os") == ["os"]

    def test_dotted_import_top_level(self):
        assert collect_py_imports("import a.b.c") == ["a"]

    def test_from_import(self):
        assert collect_py_imports("from c.d import e") == ["c"]

    def test_multiple_sorted_unique(self):
        code = "import os\nimport sys\nimport os\nfrom json import loads"
        assert collect_py_imports(code) == ["json", "os", "sys"]

    def test_relative_import_ignored(self):
        assert collect_py_imports("from . import x") == []
        assert collect_py_imports("from .mod import y") == []

    def test_syntax_error_returns_empty(self):
        assert collect_py_imports("def :") == []

    def test_empty_code(self):
        assert collect_py_imports("") == []


def _skrypt(nazwa, kod, kategoria="Python", **kw):
    d = {"nazwa": nazwa, "kod": kod, "kategoria": kategoria}
    d.update(kw)
    return d


class TestBuildDepGraph:
    """Budowa grafu z importów skryptów Python."""

    def test_edge_between_scripts(self):
        g = build_dep_graph([
            _skrypt("biblio", "x = 1"),
            _skrypt("glowny", "import biblio\n"),
        ])
        assert ("glowny", "biblio") in g["edges"]
        assert set(g["nodes"]) == {"biblio", "glowny"}

    def test_external_imports_collected(self):
        g = build_dep_graph([_skrypt("glowny", "import os\nimport requests\n")])
        assert g["external"]["glowny"] == ["os", "requests"]

    def test_import_of_unknown_module_is_external(self):
        g = build_dep_graph([_skrypt("glowny", "import biblio\n")])
        assert g["external"]["glowny"] == ["biblio"]
        assert g["edges"] == set()

    def test_self_import_not_an_edge(self):
        g = build_dep_graph([_skrypt("a", "import a\n")])
        assert g["edges"] == set()

    def test_non_python_scripts_excluded(self):
        g = build_dep_graph([
            _skrypt("glowny", "import skrypt_bash\n"),
            _skrypt("skrypt_bash", "echo hi", kategoria="Bash"),
        ])
        assert g["nodes"] == {"glowny": g["nodes"]["glowny"]}
        assert "skrypt_bash" not in g["nodes"]
        assert g["edges"] == set()

    def test_deleted_scripts_skipped(self):
        g = build_dep_graph([_skrypt("a", "x = 1", usuniety="2020-01-01")])
        assert g["nodes"] == {}

    def test_syntax_error_still_a_node(self):
        g = build_dep_graph([_skrypt("a", "def :")])
        assert "a" in g["nodes"]
        assert g["edges"] == set()


class TestFindCycles:
    """Detekcja cykli (SCC > 1 lub pętle własne)."""

    def test_no_cycles(self):
        nodes = {"a": {}, "b": {}, "c": {}}
        assert find_cycles(nodes, {("a", "b"), ("b", "c")}) == []

    def test_simple_cycle(self):
        nodes = {"a": {}, "b": {}}
        assert find_cycles(nodes, {("a", "b"), ("b", "a")}) == [["a", "b"]]

    def test_self_loop(self):
        nodes = {"a": {}}
        assert find_cycles(nodes, {("a", "a")}) == [["a"]]

    def test_cycle_among_many(self):
        nodes = {n: {} for n in "abcd"}
        edges = {("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")}
        cyc = find_cycles(nodes, edges)
        assert cyc == [["a", "b", "c"]]

    def test_two_separate_cycles(self):
        nodes = {n: {} for n in "abcd"}
        edges = {("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")}
        assert find_cycles(nodes, edges) == [["a", "b"], ["c", "d"]]


class TestFindIsolated:
    """Wykrywanie modułów bez połączeń."""

    def test_isolated_detected(self):
        nodes = {"a": {}, "b": {}, "c": {}}
        assert find_isolated(nodes, {("a", "b")}) == ["c"]

    def test_all_connected(self):
        nodes = {"a": {}, "b": {}}
        assert find_isolated(nodes, {("a", "b")}) == []

    def test_no_edges_all_isolated(self):
        nodes = {"a": {}, "b": {}}
        assert find_isolated(nodes, set()) == ["a", "b"]
