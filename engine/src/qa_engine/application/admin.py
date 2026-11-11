"""Token de administrador: gerado uma vez, guardado só o hash (scrypt), com limite de tentativas.

``qa admin token`` mostra o token uma única vez e grava o hash no arquivo de
configuração da máquina. Sem hash configurado, a área de administração fica
desligada. Cinco tentativas erradas bloqueiam por um minuto.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections.abc import Callable

PREFIX = "scrypt"
N, R, P = 2**14, 8, 1
MAX_ATTEMPTS = 5
LOCK_SECONDS = 60.0


def new_token() -> str:
    """Token aleatório para mostrar uma vez à pessoa."""
    return secrets.token_urlsafe(24)


def hash_token(token: str, salt: bytes | None = None) -> str:
    """``scrypt$n$r$p$sal$hash`` (biblioteca padrão do Python)."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(token.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=32)
    encode = base64.urlsafe_b64encode
    return f"{PREFIX}${N}${R}${P}${encode(salt).decode()}${encode(digest).decode()}"


def verify_token(token: str, stored: str) -> bool:
    """Confere o token contra o hash guardado, em tempo constante."""
    try:
        prefix, n, r, p, salt, digest = stored.split("$")
        if prefix != PREFIX:
            return False
        expected = base64.urlsafe_b64decode(digest)
        given = hashlib.scrypt(
            token.encode("utf-8"),
            salt=base64.urlsafe_b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(given, expected)


class AttemptLimiter:
    """Bloqueia por ``LOCK_SECONDS`` depois de ``MAX_ATTEMPTS`` erros seguidos."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._failures = 0
        self._locked_until = 0.0
        self._lock = threading.Lock()

    def blocked_for(self) -> float:
        """Segundos que faltam de bloqueio (0 = liberado)."""
        with self._lock:
            return max(0.0, self._locked_until - self._clock())

    def success(self) -> None:
        """Zera a contagem."""
        with self._lock:
            self._failures = 0

    def failure(self) -> None:
        """Conta um erro; no quinto, bloqueia."""
        with self._lock:
            self._failures += 1
            if self._failures >= MAX_ATTEMPTS:
                self._failures = 0
                self._locked_until = self._clock() + LOCK_SECONDS
