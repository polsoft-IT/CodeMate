"""
Testy lintera (poz. 7) — analiza statyczna kodu Python przed uruchomieniem.

Sprawdzają zarówno publiczne API ``lint_python`` (ruff → pyflakes → AST),
jak i wbudowany analizator AST ``_lint_builtin`` działający jako fallback.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import baza_skryptow as bs
from baza_skryptow import LINT_ERROR, LINT_WARNING, lint_python

REQUIRED_KEYS = {"line", "col", "code", "message", "severity"}


class TestLintBuiltin:
    """Testy wbudowanego analizatora AST (fallback bez ruff/pyflakes)."""

    def test_syntax_error_is_error(self):
        issues = bs._lint_builtin("def (")
        assert issues
        assert issues[0]["severity"] == LINT_ERROR
        assert issues[0]["code"] == "E999"

    def test_unused_import_reported(self):
        issues = bs._lint_builtin("import os\n")
        assert any(i["code"] == "F401" for i in issues)

    def test_used_import_ok(self):
        assert bs._lint_builtin("import os\nprint(os.getcwd())\n") == []

    def test_from_import_alias_used(self):
        code = "from pathlib import Path as P\nprint(P('.'))\n"
        assert bs._lint_builtin(code) == []

    def test_bare_except_reported(self):
        code = "try:\n    pass\nexcept:\n    pass\n"
        assert any(i["code"] == "E722" for i in bs._lint_builtin(code))

    def test_eval_warning(self):
        assert any(i["code"] == "S307" for i in bs._lint_builtin("eval('1')\n"))

    def test_empty_code_returns_empty(self):
        assert bs._lint_builtin("") == []

    def test_issue_shape(self):
        for issue in bs._lint_builtin("import os\n"):
            assert REQUIRED_KEYS <= set(issue)


class TestLintPython:
    """Testy publicznego API lint_python (używa dostępnego silnika)."""

    def test_clean_code_has_no_errors(self):
        issues = lint_python("x = 1\nprint(x)\n")
        assert all(i["severity"] != LINT_ERROR for i in issues)

    def test_syntax_error_reported_as_error(self):
        issues = lint_python("def (")
        assert any(i["severity"] == LINT_ERROR for i in issues)

    def test_unused_import_is_warning(self):
        issues = lint_python("import os\nimport sys\n")
        assert issues
        assert all(i["severity"] == LINT_WARNING for i in issues)

    def test_issues_sorted_by_line(self):
        issues = lint_python("import os\nimport sys\n")
        lines = [i["line"] for i in issues]
        assert lines == sorted(lines)

    def test_empty_code_no_issues(self):
        assert lint_python("") == []

    def test_issue_keys_present(self):
        for issue in lint_python("import os\n"):
            assert REQUIRED_KEYS <= set(issue)


class TestSelfCheck:
    """Regresja ``self_check`` — brak fałszywych alarmów (m.in. o metodach self)."""

    def test_reports_no_structure_problems(self, capsys):
        rc = bs.self_check()
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "nieistniejących metod" not in out
