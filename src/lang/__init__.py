# ── Metadane ──────────────────────────────────────────────────────────────────
# Moduł: src/lang/__init__.py
# Opis:  Pakiet tłumaczeń interfejsu (i18n)
# ──────────────────────────────────────────────────────────────────────────────
"""Pakiet tłumaczeń interfejsu Bazy Skryptów.

Językiem źródłowym jest polski (teksty bazowe wbudowane w kod aplikacji).
Moduły językowe (np. `en`) dostarczają tłumaczenia kluczy i tekstów UI.
"""

from . import en

# Rejestr dostępnych modułów językowych: kod języka -> moduł
LANG_MODULES = {
    en.LANG_CODE: en,
}

# Kody obsługiwanych języków (źródłowy "pl" jest wbudowany w kod aplikacji)
AVAILABLE_LANGS = ("pl",) + tuple(LANG_MODULES)

__all__ = ["en", "LANG_MODULES", "AVAILABLE_LANGS"]
