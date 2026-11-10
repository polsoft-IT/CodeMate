"""Konfiguracja pytest — dodaje stopkę z podpisem do raportu HTML pokrycia."""

from pathlib import Path

import pytest

_SIGNATURE = " Sebastian Januchowski ⌁ polsoft.ITS™ Dev"
_SIGNATURE_HTML = (
    '<p style="text-align:center">' + _SIGNATURE + "</p>\n"
)


@pytest.fixture(autouse=True)
def _reset_ui_language():
    """Przywraca domyślny język EN po każdym teście (izolacja i18n)."""
    yield
    try:
        import baza_skryptow as bs
        bs._set_lang("en")
    except Exception:
        pass


@pytest.hookimpl(trylast=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Dopisuje podpis na dole każdego pliku htmlcov/*.html.

    Uruchamia się po raporcie pytest-cov (trylast), więc pokrywa pliki
    dopiero co wygenerowane przez ``--cov-report=html``.
    """
    cov_dir = Path("htmlcov")
    if not cov_dir.is_dir():
        return
    try:
        for html_file in cov_dir.glob("*.html"):
            text = html_file.read_text(encoding="utf-8")
            if _SIGNATURE in text or "</footer>" not in text:
                continue
            html_file.write_text(
                text.replace("</footer>", _SIGNATURE_HTML + "</footer>", 1),
                encoding="utf-8")
    except OSError:
        pass
