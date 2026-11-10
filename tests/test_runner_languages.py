"""
Testy obsługi dodatkowych języków w runnerze:
Batch (.bat/.cmd), VBScript (.vbs), Java (.java) oraz JAR (.jar).

Sprawdzają budowę poleceń (``runner_cmd``), zapis plików tymczasowych
(``runner_save_temp``), kontrole przed uruchomieniem (``runner_analyze``)
oraz mapy kategorii/rozszerzeń.
"""

import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from baza_skryptow import (
    _CATEGORY_LEXER,
    AUTO_KEYWORDS,
    BIN_EXT,
    CATEGORIES,
    EXT_KAT,
    KAT_COLOR,
    KAT_ICON,
    LINT_ERROR,
    LINT_WARNING,
    OBSL_GRUPY,
    RUNNER_EXT,
    AutoCompleter,
    _c_tool,
    _interp_tool,
    _interp_warning,
    _java_available,
    _java_tool,
    _tool_available,
    discover_venv_tools,
    jar_base64,
    jar_bytes,
    kat_label,
    lint_code,
    lint_supported,
    runner_analyze,
    runner_cmd,
    runner_jar_main_class,
    runner_java_class,
    runner_java_package,
    runner_parse_error,
    runner_save_temp,
)


class TestCategoryMaps:
    """Kategorie i rozszerzenia nowych języków."""

    def test_categories_include_new(self):
        for kat in ("Batch", "VBScript", "Java", "JAR"):
            assert kat in CATEGORIES

    def test_runner_ext(self):
        assert RUNNER_EXT["Batch"] == ".bat"
        assert RUNNER_EXT["VBScript"] == ".vbs"
        assert RUNNER_EXT["Java"] == ".java"
        assert RUNNER_EXT["JAR"] == ".jar"

    def test_ext_kat(self):
        assert EXT_KAT[".bat"] == "Batch"
        assert EXT_KAT[".cmd"] == "Batch"
        assert EXT_KAT[".vbs"] == "VBScript"
        assert EXT_KAT[".java"] == "Java"
        assert EXT_KAT[".jar"] == "JAR"

    def test_discover_venv_tools_uses_builtin_venv_fallback(self):
        checked = []

        def fake_which(tool):
            checked.append(tool)
            return r"C:\Tools\poetry.exe" if tool == "poetry" else None

        tools = discover_venv_tools(fake_which)

        assert tools == {
            "venv": "built-in",
            "virtualenv": "",
            "pipenv": "",
            "poetry": r"C:\Tools\poetry.exe",
            "conda": "",
        }
        assert checked == ["venv", "virtualenv", "pipenv", "poetry", "conda"]

    def test_bin_ext(self):
        assert ".jar" in BIN_EXT

    def test_obsl_grupy_consistency(self):
        seen = set()
        for grupa, wpisy in OBSL_GRUPY:
            assert grupa and wpisy
            for rozsz, kat, run in wpisy:
                assert kat in CATEGORIES, kat
                assert kat not in seen, f"duplikat kategorii {kat}"
                seen.add(kat)
                for ext in rozsz.replace(" ", "").split(","):
                    assert EXT_KAT.get(ext, kat) == kat, (ext, kat)

    def test_obsl_covers_categories_and_extensions(self):
        covered = {k for _, wpisy in OBSL_GRUPY for _, k, _ in wpisy}
        assert covered == set(CATEGORIES)
        exts = {e for _, wpisy in OBSL_GRUPY for rozsz, _, _ in wpisy
                for e in rozsz.replace(" ", "").split(",")}
        for ext in EXT_KAT:
            assert ext in exts, ext


class TestRunnerCmd:
    """Budowa poleceń uruchomieniowych."""

    def test_batch(self):
        cmd = runner_cmd("Batch", r"C:\tmp\skrypt.bat")
        assert "-c" in cmd or "/c" in cmd
        assert cmd[-1].lower().endswith("skrypt.bat")

    def test_batch_custom_interpreter(self):
        cmd = runner_cmd("Batch", r"C:\tmp\a.bat", interpreter=r"C:\Windows\cmd.exe")
        assert cmd[0] == r"C:\Windows\cmd.exe"

    def test_vbscript(self):
        cmd = runner_cmd("VBScript", r"C:\tmp\skrypt.vbs")
        assert "//nologo" in cmd
        assert cmd[-1].lower().endswith("skrypt.vbs")

    def test_jar(self):
        cmd = runner_cmd("JAR", r"C:\tmp\app.jar")
        assert os.path.basename(cmd[0]).lower().startswith("java")
        assert "-jar" in cmd

    def test_jar_encoding_flags(self):
        cmd = runner_cmd("JAR", r"C:\tmp\app.jar")
        assert "-Dfile.encoding=UTF-8" in cmd

    def test_jar_custom_interpreter(self):
        cmd = runner_cmd("JAR", r"C:\tmp\app.jar", interpreter=r"C:\jdk\bin\java.exe")
        assert cmd[0] == r"C:\jdk\bin\java.exe"

    def test_java_uses_launcher(self):
        cmd = runner_cmd("Java", r"C:\tmp\Main.java")
        assert cmd[-1].lower().endswith("run_java.bat")


class TestJavaHelpers:
    """Pomocniki analizy źródeł Java."""

    def test_public_class(self):
        assert runner_java_class("public class Foo {}") == "Foo"

    def test_falls_back_to_any_class(self):
        assert runner_java_class("class Bar {}") == "Bar"

    def test_default_main(self):
        assert runner_java_class("int x = 1;") == "Main"

    def test_interface_and_enum(self):
        assert runner_java_class("public interface A {}") == "A"
        assert runner_java_class("public enum E { X }") == "E"

    def test_package(self):
        assert runner_java_package("package com.example;\nclass A {}") == "com.example"

    def test_no_package(self):
        assert runner_java_package("class A {}") == ""


class TestJarEncoding:
    """Kodowanie/dekodowanie archiwum JAR (base64)."""

    def test_roundtrip(self, tmp_path):
        payload = b"PK\x03\x04dane-jar"
        src = tmp_path / "app.jar"
        src.write_bytes(payload)
        enc = jar_base64(str(src))
        assert jar_bytes(enc) == payload

    def test_bad_base64_returns_empty(self):
        assert jar_bytes("!!!nie-base64!!!") == b""

    def test_empty_input(self):
        assert jar_bytes("") == b""


class TestRunnerSaveTemp:
    """Zapis kodu do plików tymczasowych."""

    def test_java_writes_source_and_launcher(self, tmp_path):
        kod = "public class Demo { public static void main(String[] a){} }"
        path = runner_save_temp(kod, "Java", str(tmp_path))
        assert os.path.basename(path) == "Demo.java"
        assert (tmp_path / "Demo.java").read_text(encoding="utf-8") == kod
        bat = tmp_path / "run_java.bat"
        assert bat.exists()
        content = bat.read_text(encoding="utf-8")
        assert "javac" in content and "Demo" in content

    def test_jar_writes_binary(self, tmp_path):
        enc = base64.b64encode(b"PK\x03\x04xxx").decode("ascii")
        path = runner_save_temp(enc, "JAR", str(tmp_path))
        assert path.endswith(".jar")
        assert Path(path).read_bytes() == b"PK\x03\x04xxx"

    def test_batch_extension(self, tmp_path):
        path = runner_save_temp("@echo off", "Batch", str(tmp_path))
        assert path.endswith(".bat")

    def test_vbscript_extension(self, tmp_path):
        path = runner_save_temp("MsgBox \"hi\"", "VBScript", str(tmp_path))
        assert path.endswith(".vbs")


class TestRunnerAnalyze:
    """Statyczna kontrola przed uruchomieniem."""

    def test_java_missing_class(self):
        ok, msg = runner_analyze("int x = 1;", "Java", "Main.java")
        assert not ok
        assert "klas" in msg.lower()

    def test_java_ok(self):
        ok, _ = runner_analyze("public class A {}", "Java", "A.java")
        assert ok

    def test_jar_empty(self):
        ok, msg = runner_analyze("", "JAR", "a.jar")
        assert not ok
        assert "JAR" in msg

    def test_jar_not_archive(self):
        enc = base64.b64encode(b"nie-zip").decode("ascii")
        ok, _ = runner_analyze(enc, "JAR", "a.jar")
        assert not ok

    def test_jar_valid(self):
        enc = base64.b64encode(b"PK\x03\x04").decode("ascii")
        ok, _ = runner_analyze(enc, "JAR", "a.jar")
        assert ok

    def test_batch_ok(self):
        ok, _ = runner_analyze("@echo off\necho hi", "Batch", "a.bat")
        assert ok

    def test_batch_risky_warns(self):
        ok, msg = runner_analyze("format C:", "Batch", "a.bat")
        assert ok
        assert "uwaga" in msg.lower()

    def test_vbscript_ok(self):
        ok, _ = runner_analyze("MsgBox \"hi\"", "VBScript", "a.vbs")
        assert ok

    def test_java_reports_main_class(self):
        ok, msg = runner_analyze("public class A { public static void main(String[] a){} }",
                                 "Java", "A.java")
        assert ok and "A" in msg

    def test_java_warns_missing_main(self):
        ok, msg = runner_analyze("public class A {}", "Java", "A.java")
        assert ok and "main" in msg


class TestJavaTool:
    """Rozwiązywanie ścieżek narzędzi JDK."""

    def test_explicit_java_interpreter(self):
        p = r"C:\jdk\bin\java.exe"
        assert _java_tool("java", p) == p

    def test_sibling_javac(self, tmp_path):
        bindir = tmp_path / "bin"
        bindir.mkdir()
        java = bindir / ("java.exe" if os.name == "nt" else "java")
        javac = bindir / ("javac.exe" if os.name == "nt" else "javac")
        java.write_text("")
        javac.write_text("")
        assert _java_tool("javac", str(java)) == str(javac)

    def test_unrelated_interpreter_not_returned(self):
        py = r"C:\Python311\python.exe"
        assert _java_tool("java", py) != py


class TestJavaAvailability:
    """Wykrywanie narzędzi JDK i ostrzeżenia przed uruchomieniem."""

    def test_available_via_explicit_path(self, tmp_path):
        java = tmp_path / ("java.exe" if os.name == "nt" else "java")
        java.write_text("")
        assert _java_available("java", str(java))

    def test_missing_tool_reported(self, monkeypatch):
        monkeypatch.setattr("baza_skryptow._java_tool", lambda *a, **k: "javac")
        monkeypatch.setattr("baza_skryptow.shutil.which", lambda *a, **k: None)
        assert not _java_available("javac", "")

    def test_analyze_warns_missing_jdk(self, monkeypatch):
        monkeypatch.setattr("baza_skryptow._java_available", lambda *a, **k: False)
        ok, msg = runner_analyze(
            "public class A { public static void main(String[] a){} }",
            "Java", "A.java")
        assert ok and "nie znaleziono" in msg

    def test_analyze_silent_when_jdk_present(self, monkeypatch):
        monkeypatch.setattr("baza_skryptow._java_available", lambda *a, **k: True)
        ok, msg = runner_analyze(
            "public class A { public static void main(String[] a){} }",
            "Java", "A.java")
        assert ok and "nie znaleziono" not in msg

    def test_jar_analyze_warns_missing_java(self, monkeypatch):
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/MANIFEST.MF",
                        "Manifest-Version: 1.0\r\nMain-Class: App\r\n")
        enc = base64.b64encode(buf.getvalue()).decode("ascii")
        monkeypatch.setattr("baza_skryptow._java_available", lambda *a, **k: False)
        ok, msg = runner_analyze(enc, "JAR", "a.jar")
        assert ok and "nie znaleziono java" in msg


class TestJarManifest:
    """Odczyt Main-Class z MANIFEST archiwum JAR."""

    @staticmethod
    def _jar(main=None):
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            mf = "Manifest-Version: 1.0\r\n"
            if main:
                mf += f"Main-Class: {main}\r\n"
            zf.writestr("META-INF/MANIFEST.MF", mf)
        return buf.getvalue()

    def test_reads_main_class(self):
        assert runner_jar_main_class(self._jar("com.example.Main")) == "com.example.Main"

    def test_no_main_class(self):
        assert runner_jar_main_class(self._jar()) == ""

    def test_not_a_zip(self):
        assert runner_jar_main_class(b"nie-zip") == ""

    def test_analyze_reports_main(self):
        enc = base64.b64encode(self._jar("App")).decode("ascii")
        ok, msg = runner_analyze(enc, "JAR", "a.jar")
        assert ok and "App" in msg

    def test_analyze_warns_without_main(self):
        enc = base64.b64encode(self._jar()).decode("ascii")
        ok, msg = runner_analyze(enc, "JAR", "a.jar")
        assert ok and "Main-Class" in msg


class TestBatchWrapper:
    """Launcher Batch: UTF-8 + przekazanie kodu wyjścia."""

    def test_wrapper_created(self, tmp_path):
        runner_save_temp("@echo off\necho hi", "Batch", str(tmp_path))
        wrapper = tmp_path / "run_batch.bat"
        assert wrapper.exists()
        content = wrapper.read_text(encoding="utf-8")
        assert "chcp 65001" in content
        assert "call" in content and "skrypt.bat" in content
        assert "%errorlevel%" in content

    def test_runner_cmd_prefers_wrapper(self, tmp_path):
        path = runner_save_temp("@echo off", "Batch", str(tmp_path))
        cmd = runner_cmd("Batch", path)
        assert cmd[-1].lower().endswith("run_batch.bat")


class TestVbscriptEncoding:
    """Kodowanie pliku .vbs (Windows Script Host)."""

    def test_ascii_stays_utf8(self, tmp_path):
        path = runner_save_temp('WScript.Echo "hi"', "VBScript", str(tmp_path))
        raw = Path(path).read_bytes()
        assert not raw.startswith(b"\xff\xfe")
        assert b"WScript" in raw

    def test_non_ascii_uses_utf16_bom(self, tmp_path):
        path = runner_save_temp('WScript.Echo "zażółć"', "VBScript", str(tmp_path))
        raw = Path(path).read_bytes()
        assert raw.startswith(b"\xff\xfe")          # BOM UTF-16 LE
        assert "zażółć" in raw.decode("utf-16")


class TestParseErrorNewLangs:
    """Rozpoznawanie błędów Batch / VBScript."""

    def test_vbscript_line(self):
        out = ("C:\\tmp\\skrypt.vbs(12, 3) Microsoft VBScript runtime error: "
               "Object required: 'x'")
        info = runner_parse_error(out, "VBScript")
        assert info and info["linia"] == 12
        assert "VBScript" in info["typ"]

    def test_batch_not_recognized(self):
        out = ("'foo' is not recognized as an internal or external command,\r\n"
               "operable program or batch file.")
        info = runner_parse_error(out, "Batch")
        assert info and info["typ"] == "Batch"
        assert "not recognized" in info["komunikat"]

    def test_batch_empty(self):
        assert runner_parse_error("", "Batch") is None

    def test_vbscript_no_match(self):
        assert runner_parse_error("zwykłe wyjście", "VBScript") is None


# ── Dodatkowe języki: Ruby, Perl, PHP, WSF, HTA, HTML, CSS, JSON, Markdown ──

NEW_CATEGORIES = ("Ruby", "Perl", "PHP", "WSF", "HTA", "HTML", "CSS", "JSON", "Markdown")


class TestExtraCategoryMaps:
    """Kategorie, rozszerzenia i lexery nowych formatów."""

    def test_categories_include_new(self):
        for kat in NEW_CATEGORIES:
            assert kat in CATEGORIES

    def test_runner_ext(self):
        assert RUNNER_EXT["Ruby"] == ".rb"
        assert RUNNER_EXT["Perl"] == ".pl"
        assert RUNNER_EXT["PHP"] == ".php"
        assert RUNNER_EXT["WSF"] == ".wsf"
        assert RUNNER_EXT["HTA"] == ".hta"
        assert RUNNER_EXT["HTML"] == ".html"
        assert RUNNER_EXT["CSS"] == ".css"
        assert RUNNER_EXT["JSON"] == ".json"
        assert RUNNER_EXT["Markdown"] == ".md"

    def test_ext_kat(self):
        assert EXT_KAT[".rb"] == "Ruby"
        assert EXT_KAT[".pl"] == "Perl"
        assert EXT_KAT[".php"] == "PHP"
        assert EXT_KAT[".wsf"] == "WSF"
        assert EXT_KAT[".hta"] == "HTA"
        assert EXT_KAT[".html"] == "HTML"
        assert EXT_KAT[".htm"] == "HTML"
        assert EXT_KAT[".css"] == "CSS"
        assert EXT_KAT[".json"] == "JSON"
        assert EXT_KAT[".md"] == "Markdown"
        assert EXT_KAT[".markdown"] == "Markdown"

    def test_lexers(self):
        assert _CATEGORY_LEXER["Ruby"] == "ruby"
        assert _CATEGORY_LEXER["Perl"] == "perl"
        assert _CATEGORY_LEXER["PHP"] == "php"
        assert _CATEGORY_LEXER["WSF"] == "xml"
        assert _CATEGORY_LEXER["HTA"] == "html"
        assert _CATEGORY_LEXER["HTML"] == "html"
        assert _CATEGORY_LEXER["CSS"] == "css"
        assert _CATEGORY_LEXER["JSON"] == "json"
        assert _CATEGORY_LEXER["Markdown"] == "markdown"


class TestExtraRunnerCmd:
    """Budowa poleceń dla nowych kategorii."""

    def test_ruby(self):
        cmd = runner_cmd("Ruby", r"C:\tmp\skrypt.rb")
        assert os.path.basename(cmd[0]).lower().startswith("ruby")
        assert cmd[-1].endswith("skrypt.rb")

    def test_perl(self):
        cmd = runner_cmd("Perl", r"C:\tmp\skrypt.pl")
        assert os.path.basename(cmd[0]).lower().startswith("perl")
        assert cmd[-1].endswith("skrypt.pl")

    def test_php(self):
        cmd = runner_cmd("PHP", r"C:\tmp\skrypt.php")
        assert os.path.basename(cmd[0]).lower().startswith("php")
        assert cmd[-1].endswith("skrypt.php")

    def test_custom_interpreter(self):
        assert runner_cmd("Ruby", r"C:\tmp\a.rb", interpreter=r"C:\Ruby\bin\ruby.exe")[0] \
            == r"C:\Ruby\bin\ruby.exe"

    def test_wsf_uses_cscript(self):
        cmd = runner_cmd("WSF", r"C:\tmp\skrypt.wsf")
        assert "//nologo" in cmd
        assert os.path.basename(cmd[0]).lower().startswith("cscript")
        assert cmd[-1].endswith("skrypt.wsf")

    def test_hta_uses_mshta(self):
        cmd = runner_cmd("HTA", r"C:\tmp\skrypt.hta")
        assert os.path.basename(cmd[0]).lower().startswith("mshta")
        assert cmd[-1].endswith("skrypt.hta")

    def test_html_opens_in_browser(self):
        cmd = runner_cmd("HTML", r"C:\tmp\strona.html")
        if os.name == "nt":
            assert cmd[:3] == ["cmd", "/c", "start"]
            assert cmd[-1].endswith("strona.html")
        else:
            assert cmd is None

    def test_documents_have_no_runner(self):
        for kat in ("CSS", "JSON", "Markdown"):
            assert runner_cmd(kat, r"C:\tmp\plik") is None


class TestExtraRunnerSaveTemp:
    """Zapis plików tymczasowych z właściwym rozszerzeniem."""

    def test_extensions(self, tmp_path):
        mapping = {"Ruby": ".rb", "Perl": ".pl", "PHP": ".php", "WSF": ".wsf",
                   "HTA": ".hta", "HTML": ".html", "CSS": ".css", "JSON": ".json",
                   "Markdown": ".md"}
        for kat, ext in mapping.items():
            path = runner_save_temp("treść", kat, str(tmp_path))
            assert path.endswith(ext), f"{kat} → {path}"


class TestExtraRunnerAnalyze:
    """Statyczna kontrola przed uruchomieniem nowych kategorii."""

    def test_json_valid(self):
        ok, msg = runner_analyze('{"a": 1}', "JSON", "a.json")
        assert ok and "JSON" in msg

    def test_json_invalid(self):
        ok, msg = runner_analyze('{"a": }', "JSON", "a.json")
        assert not ok and "JSON" in msg

    def test_wsf_requires_job(self):
        ok, _ = runner_analyze("<job></job>", "WSF", "a.wsf")
        assert ok
        ok, msg = runner_analyze("<script></script>", "WSF", "a.wsf")
        assert not ok and "job" in msg

    def test_hta(self):
        ok, msg = runner_analyze("<html><body>x</body></html>", "HTA", "a.hta")
        assert ok and "HTA" in msg

    def test_html(self):
        ok, msg = runner_analyze("<h1>Witaj</h1>", "HTML", "a.html")
        assert ok and "HTML" in msg

    def test_css_markdown_ruby_perl(self):
        for kat, nazwa in (("CSS", "a.css"), ("Markdown", "a.md"),
                           ("Ruby", "a.rb"), ("Perl", "a.pl")):
            ok, msg = runner_analyze("x", kat, nazwa)
            assert ok and kat in msg

    def test_php_warns_without_tag(self):
        ok, msg = runner_analyze("echo 'x';", "PHP", "a.php")
        assert ok and "<?php" in msg

    def test_php_ok(self):
        ok, msg = runner_analyze("<?php echo 'x';", "PHP", "a.php")
        assert ok and "<?php" not in msg


class TestExtraParseError:
    """Rozpoznawanie błędów Ruby / Perl / PHP / WSF."""

    def test_ruby_syntax(self):
        info = runner_parse_error("skrypt.rb:3: syntax error, unexpected end", "Ruby")
        assert info and info["linia"] == 3

    def test_ruby_runtime(self):
        info = runner_parse_error("skrypt.rb:7:in 'metoda': boom (RuntimeError)", "Ruby")
        assert info and info["linia"] == 7 and info["typ"] == "RuntimeError"

    def test_perl(self):
        info = runner_parse_error(
            'syntax error at skrypt.pl line 12, near "print"', "Perl")
        assert info and info["linia"] == 12

    def test_php_parse(self):
        out = ("PHP Parse error:  syntax error, unexpected '}' in "
               "C:\\tmp\\skrypt.php on line 9")
        info = runner_parse_error(out, "PHP")
        assert info and info["linia"] == 9
        assert "Parse Error" in info["typ"]

    def test_wsf_reuses_vbscript_format(self):
        out = "C:\\tmp\\skrypt.wsf(5, 2) Microsoft VBScript runtime error: boom"
        info = runner_parse_error(out, "WSF")
        assert info and info["linia"] == 5

    def test_plain_output_returns_none(self):
        for kat in ("Ruby", "Perl", "PHP", "WSF"):
            assert runner_parse_error("zwykłe wyjście", kat) is None


# ── Faza 2: usprawnienia (ikony, autouzupełnianie, preflight, linter) ────────


class TestKatIcons:
    """Ikony i kolory kategorii (kat_label / KAT_ICON / KAT_COLOR)."""

    def test_every_category_has_icon_and_color(self):
        for kat in CATEGORIES:
            assert kat in KAT_ICON, f"brak ikony dla {kat}"
            assert kat in KAT_COLOR, f"brak koloru dla {kat}"

    def test_kat_label_has_icon_prefix(self):
        assert kat_label("Python").endswith("Python")
        assert kat_label("Ruby").startswith(KAT_ICON["Ruby"])

    def test_kat_label_unknown_category(self):
        assert kat_label("Nieznana") == "Nieznana"

    def test_kat_label_empty(self):
        assert kat_label("") == ""


class TestAutoKeywords:
    """Słowa kluczowe autouzupełniania dla nowych kategorii."""

    def test_new_categories_have_keywords(self):
        for kat in ("Ruby", "Perl", "PHP", "HTML", "CSS", "JSON", "Markdown",
                    "HTA", "WSF"):
            assert AUTO_KEYWORDS.get(kat), f"brak słów kluczowych dla {kat}"

    def test_python_uses_symbols_and_keywords(self):
        names = AutoCompleter._candidates(None, "Python", "import os\nx = 1\n")
        assert "def" in names and "print" in names and "os" in names

    def test_ruby_keywords_present(self):
        names = AutoCompleter._candidates(None, "Ruby", "")
        assert "def" in names and "end" in names

    def test_unknown_category_empty(self):
        assert AutoCompleter._candidates(None, "Nieznana", "") == []

    def test_result_sorted(self):
        names = AutoCompleter._candidates(None, "PHP", "")
        assert names == sorted(names, key=str.lower)


class TestInterpTools:
    """Wykrywanie interpreterów i ostrzeżenia preflight."""

    def test_explicit_interpreter_returned(self):
        exe = "ruby.exe" if os.name == "nt" else "ruby"
        path = os.path.join("C:\\Ruby\\bin" if os.name == "nt" else "/usr/bin", exe)
        assert _interp_tool("ruby", path) == path

    def test_sibling_tool(self, tmp_path):
        exe = tmp_path / ("perl.exe" if os.name == "nt" else "perl")
        exe.write_text("")
        other = tmp_path / ("python.exe" if os.name == "nt" else "python")
        assert _interp_tool("perl", str(other)) == str(exe)

    def test_missing_tool_warning(self, monkeypatch):
        monkeypatch.setattr("baza_skryptow.shutil.which", lambda *a, **k: None)
        assert not _tool_available("ruby", "")
        assert "ruby" in _interp_warning("ruby", "")

    def test_available_tool_no_warning(self, monkeypatch):
        monkeypatch.setattr("baza_skryptow.shutil.which", lambda *a, **k: sys.executable)
        assert _tool_available("ruby", "")
        assert _interp_warning("ruby", "") == ""


class TestLintExtra:
    """Linter dla nowych kategorii (JSON / HTML / CSS / dyspozytor)."""

    def test_supported_categories(self):
        for kat in ("Python", "JSON", "HTML", "HTA", "CSS", "PHP", "Ruby", "Perl"):
            assert lint_supported(kat)

    def test_unsupported_category(self):
        assert not lint_supported("Markdown")
        assert lint_code("x", "Markdown") == []

    def test_json_valid(self):
        assert lint_code('{"a": 1}', "JSON") == []

    def test_json_invalid_is_error(self):
        issues = lint_code('{"a": }', "JSON")
        assert issues and issues[0]["severity"] == LINT_ERROR
        assert issues[0]["line"] == 1

    def test_json_error_line(self):
        issues = lint_code('{\n  "a": ,\n}', "JSON")
        assert issues and issues[0]["line"] == 2

    def test_html_balanced(self):
        assert lint_code("<div><span>x</span></div>", "HTML") == []

    def test_html_unclosed_tag(self):
        issues = lint_code("<div><span>x</span>", "HTML")
        assert issues and "div" in issues[0]["message"]

    def test_html_void_tags_ignored(self):
        assert lint_code("<img src='a'><br>", "HTML") == []

    def test_html_script_content_ignored(self):
        code = "<div>\n<script>if (a < b) { }</script>\n</div>"
        assert lint_code(code, "HTML") == []

    def test_html_unclosed_comment(self):
        issues = lint_code("<!-- brak końca", "HTML")
        assert any("komentarz" in i["message"] for i in issues)

    def test_css_balanced(self):
        assert lint_code("body { color: red; }", "CSS") == []

    def test_css_unclosed_block(self):
        issues = lint_code("body { color: red;", "CSS")
        assert issues and issues[0]["severity"] == LINT_WARNING

    def test_css_extra_brace(self):
        issues = lint_code("body { } }", "CSS")
        assert any("Nadmiarowy" in i["message"] for i in issues)

    def test_interpreter_missing_returns_empty(self, monkeypatch):
        monkeypatch.setattr("baza_skryptow.shutil.which", lambda *a, **k: None)
        assert lint_code("def (", "Ruby") == []
        assert lint_code("<?php echo", "PHP") == []

    def test_hta_uses_html_rules(self):
        assert lint_code("<html><body>x</body></html>", "HTA") == []


# ── Faza 3: obsługa C i C++ ──────────────────────────────────────────────────


class TestCCategories:
    """Kategorie i rozszerzenia C/C++."""

    def test_categories_include_c(self):
        assert "C" in CATEGORIES and "C++" in CATEGORIES

    def test_runner_ext(self):
        assert RUNNER_EXT["C"] == ".c"
        assert RUNNER_EXT["C++"] == ".cpp"

    def test_ext_kat(self):
        assert EXT_KAT[".c"] == "C" and EXT_KAT[".h"] == "C"
        for ext in (".cpp", ".cc", ".cxx", ".c++", ".hpp", ".hh", ".hxx"):
            assert EXT_KAT[ext] == "C++", ext

    def test_lexer(self):
        assert _CATEGORY_LEXER["C"] == "c"
        assert _CATEGORY_LEXER["C++"] == "cpp"

    def test_keywords(self):
        assert "printf" in AUTO_KEYWORDS["C"]
        assert "cout" in AUTO_KEYWORDS["C++"] and "class" in AUTO_KEYWORDS["C++"]


class TestCRunnerCmd:
    """Polecenia uruchomieniowe C/C++ (przez launcher kompilujący)."""

    def test_c_uses_launcher(self):
        cmd = runner_cmd("C", r"C:\tmp\skrypt.c")
        assert cmd[-1].lower().endswith(("run_c.bat", "run_c.sh"))

    def test_cpp_uses_launcher(self):
        cmd = runner_cmd("C++", r"C:\tmp\skrypt.cpp")
        assert cmd[-1].lower().endswith(("run_c.bat", "run_c.sh"))

    def test_args_forwarded(self):
        cmd = runner_cmd("C", r"C:\tmp\skrypt.c", args=["foo", "1"])
        assert cmd[-2:] == ["foo", "1"]

    def test_c_tool_prefers_gcc(self, monkeypatch):
        monkeypatch.setattr("baza_skryptow._tool_available",
                            lambda name, interpreter="": name == "gcc")
        assert _c_tool("C") == "gcc"
        assert _c_tool("C++") == "clang++" or _c_tool("C++")

    def test_c_tool_cpp_prefers_gpp(self, monkeypatch):
        monkeypatch.setattr("baza_skryptow._tool_available",
                            lambda name, interpreter="": name == "g++")
        assert _c_tool("C++") == "g++"


class TestCRunnerSaveTemp:
    """Zapis źródeł C/C++ i launcherów."""

    def test_c_writes_source_and_launcher(self, tmp_path):
        kod = 'int main(){return 0;}'
        path = runner_save_temp(kod, "C", str(tmp_path))
        assert os.path.basename(path) == "skrypt.c"
        assert (tmp_path / "skrypt.c").read_text(encoding="utf-8") == kod
        launcher = tmp_path / ("run_c.bat" if os.name == "nt" else "run_c.sh")
        assert launcher.exists()
        content = launcher.read_text(encoding="utf-8")
        assert "gcc" in content or "clang" in content

    def test_cpp_writes_source(self, tmp_path):
        kod = "int main(){return 0;}"
        path = runner_save_temp(kod, "C++", str(tmp_path))
        assert os.path.basename(path) == "skrypt.cpp"

    def test_launcher_lines_compile_and_run(self):
        lines = "\n".join(
            __import__("baza_skryptow").runner_c_launcher_lines(
                "skrypt.c", "gcc", "-std=c11"))
        assert "-o" in lines and "skrypt.c" in lines and "%*" in lines


class TestCRunnerAnalyze:
    """Kontrola przed uruchomieniem C/C++."""

    def test_missing_main_warns(self):
        ok, msg = runner_analyze("int x = 1;", "C", "a.c")
        assert ok and "main" in msg

    def test_with_main_ok(self):
        ok, msg = runner_analyze("int main(){return 0;}", "C++", "a.cpp")
        assert ok and "C++" in msg


class TestCParseError:
    """Parsowanie błędów kompilacji gcc/clang."""

    def test_error_with_column(self):
        out = "skrypt.c:12:5: error: expected ';' before '}'"
        info = runner_parse_error(out, "C")
        assert info and info["linia"] == 12 and info["typ"] == "C"

    def test_error_without_column(self):
        out = "skrypt.cpp:7: error: 'x' was not declared"
        info = runner_parse_error(out, "C++")
        assert info and info["linia"] == 7 and info["typ"] == "C++"

    def test_plain_output_none(self):
        assert runner_parse_error("hello world", "C") is None
