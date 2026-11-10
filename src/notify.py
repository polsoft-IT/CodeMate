# ── Metadane ──────────────────────────────────────────────────────────────────
# Moduł:   src/notify.py
# Opis:    Powiadomienia systemowe (toast) z bezpieczną degradacją
# Wersja:  1.0.0
# Autor:   Sebastian Januchowski
# Firma:   polsoft.ITS(TM) Group
# E-mail:  polsoft.its@mail.com
# GitHub:  https://github.com/polsoft-it
# ──────────────────────────────────────────────────────────────────────────────
"""Powiadomienia systemowe (toast).

Cienka warstwa nad opcjonalną biblioteką ``plyer``. Gdy ``plyer`` jest
niedostępny lub zgłosi błąd, funkcje zwracają ``False`` — wywołujący powinien
wtedy użyć własnego (w oknie aplikacji) mechanizmu powiadomień.
"""

NOTIFY_TIMEOUT = 8
NOTIFY_APP_NAME = "CodeMate"

try:
    from plyer import notification as _notification  # type: ignore[import-untyped]
    _PLYER_OK = True
except Exception:  # pragma: no cover - zależność opcjonalna
    _notification = None
    _PLYER_OK = False


def notify_available() -> bool:
    """Informuje, czy dostępny jest natywny backend powiadomień (``plyer``)."""
    return _PLYER_OK


def send_native(title: str, message: str, timeout: int = NOTIFY_TIMEOUT,
                app_name: str = NOTIFY_APP_NAME) -> bool:
    """Wysyła natywne powiadomienie systemowe.

    Args:
        title: Tytuł powiadomienia.
        message: Treść powiadomienia.
        timeout: Czas wyświetlania w sekundach.
        app_name: Nazwa aplikacji prezentowana w powiadomieniu.

    Returns:
        bool: ``True`` gdy powiadomienie zostało wysłane, w przeciwnym razie
        ``False`` (brak ``plyer`` lub błąd backendu).
    """
    if not _PLYER_OK or _notification is None:
        return False
    try:
        _notification.notify(
            title=str(title or ""),
            message=str(message or ""),
            app_name=str(app_name or NOTIFY_APP_NAME),
            timeout=int(timeout or NOTIFY_TIMEOUT),
        )
        return True
    except Exception:
        return False
