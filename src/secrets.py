# ── Metadane ──────────────────────────────────────────────────────────────────
# Moduł:   src/secrets.py
# Opis:    Menedżer sekretów — szyfrowanie Fernet + magazyn klucza (keyring)
# Wersja:  1.0.0
# Autor:   Sebastian Januchowski
# Firma:   polsoft.ITS(TM) Group
# E-mail:  polsoft.its@mail.com
# GitHub:  https://github.com/polsoft-it
# ──────────────────────────────────────────────────────────────────────────────
"""Sejf na sekrety (tokeny/hasła) z wstrzykiwaniem jako zmienne środowiskowe.

Wartości sekretów szyfrowane są algorytmem Fernet (biblioteka ``cryptography``).
Klucz szyfrujący trafia do systemowego magazynu poświadczeń (``keyring``), a gdy
ten jest niedostępny — do lokalnego pliku klucza z ograniczonymi uprawnieniami
(``<plik>.key``). Gdy ``keyring`` działa, klucz zapisywany jest także w pliku
jako kopia bezpieczeństwa (odczyt: najpierw keyring, potem plik).

Format pliku ``baza_skryptow.sekrety.json``::

    {
      "schema": 1,
      "sekrety": [
        {"id": "...", "nazwa": "API_KEY", "zakres": "global",
         "skrypt": "", "wartosc": "<token Fernet>", "opis": "...",
         "zmieniony": "2026-11-05 12:00:00"}
      ]
    }

Zakres sekretu:

* ``global`` — wstrzykiwany przy każdym uruchomieniu skryptu,
* ``skrypt`` — tylko gdy uruchamiany jest skrypt o podanej nazwie.
"""

import os
import re
import json
import uuid
import logging
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:  # pragma: no cover - zależność opcjonalna
    from cryptography.fernet import Fernet, InvalidToken
    _HAS_CRYPTO = True
except ImportError:  # pragma: no cover
    Fernet = None            # type: ignore[assignment,misc]
    InvalidToken = Exception  # type: ignore[assignment,misc]
    _HAS_CRYPTO = False

try:  # pragma: no cover - zależność opcjonalna
    import keyring
    _HAS_KEYRING = True
except ImportError:  # pragma: no cover
    keyring = None       # type: ignore[assignment]
    _HAS_KEYRING = False

KEYRING_SERVICE = "CodeMate"
KEYRING_USER = "secrets-key"

#: Poprawna nazwa zmiennej środowiskowej (litery, cyfry, podkreślenia).
RE_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Obsługiwane zakresy sekretów.
ZAKRESY = ("global", "skrypt")


def now_str() -> str:
    """Zwraca bieżący znacznik czasu w formacie ``RRRR-MM-DD GG:MM:SS``."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def env_name_valid(nazwa: str) -> bool:
    """Sprawdza, czy nazwa nadaje się na zmienną środowiskową."""
    return bool(RE_ENV_NAME.match(str(nazwa or "").strip()))


def secret_normalize(rec: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sprowadza rekord sekretu do jednolitego słownika i uzupełnia brakujące pola."""
    rec = rec if isinstance(rec, dict) else {}
    zakres = rec.get("zakres") if rec.get("zakres") in ZAKRESY else "global"
    return {
        "id": str(rec.get("id") or uuid.uuid4().hex),
        "nazwa": str(rec.get("nazwa") or "").strip(),
        "zakres": zakres,
        "skrypt": str(rec.get("skrypt") or "").strip(),
        "wartosc": str(rec.get("wartosc") or ""),
        "opis": str(rec.get("opis") or ""),
        "zmieniony": rec.get("zmieniony") or now_str(),
    }


class SecretsStore:
    """Magazyn zaszyfrowanych sekretów powiązanych z projektem lub skryptem.

    Args:
        path: Ścieżka do pliku JSON z zaszyfrowanymi sekretami.
        key: Opcjonalny klucz Fernet (bytes/str) — używany głównie w testach;
            gdy podany, ``keyring``/plik klucza nie są wykorzystywane.
        use_keyring: Czy używać systemowego magazynu poświadczeń.
    """

    def __init__(self, path: Path, key: Optional[Any] = None,
                 use_keyring: bool = True) -> None:
        self.path = Path(path)
        self._key = key.encode() if isinstance(key, str) else key
        self._use_keyring = use_keyring
        self._fernet: Optional[Any] = None
        self.sekrety: List[Dict[str, Any]] = []
        if self._key and _HAS_CRYPTO:
            self._fernet = Fernet(self._key)
        self.load()

    # ── klucz szyfrujący ──────────────────────────────────────────────────────
    def _key_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".key")

    def _read_key(self) -> Optional[bytes]:
        """Odczytuje klucz: keyring → plik klucza. Brak = None."""
        if self._use_keyring and _HAS_KEYRING:
            try:
                val = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
                if val:
                    return val.encode()
            except Exception as e:  # pragma: no cover - zależne od systemu
                logging.warning(f"Keyring: nie można odczytać klucza: {e}")
        kp = self._key_path()
        try:
            if kp.exists():
                return kp.read_bytes().strip()
        except OSError as e:  # pragma: no cover
            logging.warning(f"Nie można odczytać pliku klucza: {e}")
        return None

    def _write_key(self, key: bytes) -> None:
        """Zapisuje klucz do keyring (jeśli dostępny) i do pliku jako kopię."""
        if self._use_keyring and _HAS_KEYRING:
            try:
                keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key.decode())
            except Exception as e:  # pragma: no cover - zależne od systemu
                logging.warning(f"Keyring: nie można zapisać klucza: {e}")
        kp = self._key_path()
        try:
            kp.write_bytes(key)
            if os.name != "nt":
                os.chmod(kp, 0o600)  # pragma: no cover - chmod tylko na POSIX
        except OSError as e:  # pragma: no cover
            logging.error(f"Nie można zapisać pliku klucza: {e}")

    def _ensure_fernet(self) -> bool:
        """Zapewnia gotowy obiekt Fernet (tworzy klucz, gdy brak). Zwraca sukces."""
        if self._fernet is not None:
            return True
        if not _HAS_CRYPTO:
            return False
        if self._key:
            self._fernet = Fernet(self._key)
            return True
        key = self._read_key()
        if not key:
            key = Fernet.generate_key()
            self._write_key(key)
        self._key = key
        self._fernet = Fernet(key)
        return True

    # ── informacje ────────────────────────────────────────────────────────────
    def available(self) -> bool:
        """Czy szyfrowanie jest możliwe (obecna biblioteka ``cryptography``)."""
        return _HAS_CRYPTO

    def keyring_available(self) -> bool:
        """Czy dostępny jest systemowy magazyn poświadczeń."""
        return _HAS_KEYRING

    # ── wejście/wyjście ───────────────────────────────────────────────────────
    def load(self) -> None:
        """Wczytuje sekrety z pliku (brak pliku = pusta lista)."""
        try:
            if not self.path.exists():
                self.sekrety = []
                return
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as e:
            logging.warning(f"Błąd wczytywania sekretów: {e}")
            self.sekrety = []
            return
        if isinstance(data, dict):
            data = data.get("sekrety", [])
        if not isinstance(data, list):
            self.sekrety = []
            return
        self.sekrety = [secret_normalize(r) for r in data]

    def save(self) -> None:
        """Zapisuje sekrety do pliku JSON (atomowo)."""
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            tmp.write_text(
                json.dumps({"schema": 1, "sekrety": self.sekrety},
                           ensure_ascii=False, indent=2),
                encoding="utf-8")
            Path(tmp).replace(self.path)
        except OSError as e:
            logging.error(f"Błąd zapisu sekretów: {e}")

    # ── CRUD ──────────────────────────────────────────────────────────────────
    def find(self, sid: str) -> Optional[Dict[str, Any]]:
        """Zwraca rekord sekretu o podanym identyfikatorze lub None."""
        for rec in self.sekrety:
            if rec["id"] == sid:
                return rec
        return None

    def set(self, nazwa: str, wartosc: str, zakres: str = "global",
            skrypt: str = "", opis: str = "") -> Tuple[bool, str]:
        """Dodaje lub aktualizuje sekret. Zwraca ``(sukces, komunikat)``.

        Sekret identyfikowany jest przez trójkę ``(nazwa, zakres, skrypt)``.
        """
        nazwa = str(nazwa or "").strip()
        if not env_name_valid(nazwa):
            return False, "Nieprawidłowa nazwa zmiennej (dozwolone A-Z, 0-9, _)."
        if zakres not in ZAKRESY:
            zakres = "global"
        if zakres == "skrypt" and not str(skrypt or "").strip():
            return False, "Wskaż skrypt dla zakresu „skrypt”."
        if not self._ensure_fernet() or self._fernet is None:
            return False, "Brak biblioteki „cryptography” — nie można szyfrować."
        token = self._fernet.encrypt(str(wartosc).encode("utf-8")).decode("ascii")
        skrypt = str(skrypt or "").strip() if zakres == "skrypt" else ""
        for rec in self.sekrety:
            if rec["nazwa"] == nazwa and rec["zakres"] == zakres and rec["skrypt"] == skrypt:
                rec["wartosc"] = token
                rec["opis"] = str(opis or rec["opis"] or "")
                rec["zmieniony"] = now_str()
                self.save()
                return True, "Zaktualizowano sekret."
        self.sekrety.append(secret_normalize({
            "nazwa": nazwa, "zakres": zakres, "skrypt": skrypt,
            "wartosc": token, "opis": opis}))
        self.save()
        return True, "Dodano sekret."

    def delete(self, sid: str) -> bool:
        """Usuwa sekret o podanym identyfikatorze. Zwraca, czy usunięto."""
        before = len(self.sekrety)
        self.sekrety = [r for r in self.sekrety if r["id"] != sid]
        if len(self.sekrety) != before:
            self.save()
            return True
        return False

    def get_value(self, sid: str) -> Optional[str]:
        """Zwraca odszyfrowaną wartość sekretu lub None (brak/błąd)."""
        rec = self.find(sid)
        if not rec or not rec["wartosc"]:
            return None
        if not self._ensure_fernet() or self._fernet is None:
            return None
        try:
            return str(
                self._fernet.decrypt(rec["wartosc"].encode("ascii")).decode("utf-8"))
        except InvalidToken:
            logging.warning(f"Sekret {rec['nazwa']}: nie można odszyfrować (inny klucz).")
            return None
        except Exception as e:  # pragma: no cover
            logging.warning(f"Sekret {rec['nazwa']}: błąd odszyfrowania: {e}")
            return None

    def resolve_env(self, nazwa_skrypt: str = "") -> Dict[str, str]:
        """Zwraca słownik zmiennych środowiskowych dla danego skryptu.

        Najpierw sekrety globalne, potem sekrety powiązane ze skryptem
        (mogą nadpisać wartości globalne o tej samej nazwie).
        """
        env: Dict[str, str] = {}
        for scope in ("global", "skrypt"):
            for rec in self.sekrety:
                if rec["zakres"] != scope:
                    continue
                if scope == "skrypt" and rec.get("skrypt") != nazwa_skrypt:
                    continue
                val = self.get_value(rec["id"])
                if val is not None:
                    env[rec["nazwa"]] = val
        return env
