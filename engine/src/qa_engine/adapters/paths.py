r"""Pastas padrão do programa em cada sistema operacional (``platformdirs``).

No Windows: configuração da máquina em ``%PROGRAMDATA%\SOSDocs\QA``, dados e
configuração do usuário em ``%LOCALAPPDATA%\SOSDocs\QA`` e saída em
``Documentos\QA\Saída``. Nada disso exige administrador.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import platformdirs

APP_NAME = "QA"
APP_AUTHOR = "SOSDocs"
CONFIG_NAME = "config.toml"


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Onde o programa lê a configuração e guarda os dados numa estação."""

    machine_config: Path
    """Arquivo da máquina, colocado pela TI; pode travar chaves."""
    user_config: Path
    """Arquivo do usuário, gravado pela tela de Configurações."""
    data_dir: Path
    output_dir: Path
    program_dir: Path
    """Pasta do programa: onde ficam ``profiles``, ``ui`` e ``models`` no pacote."""

    @classmethod
    def detect(cls) -> AppPaths:
        """Pastas do sistema para o usuário atual."""
        data = Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR, roaming=False))
        machine = Path(platformdirs.site_config_dir(APP_NAME, APP_AUTHOR))
        documents = Path(platformdirs.user_documents_dir())
        return cls(
            machine_config=machine / CONFIG_NAME,
            user_config=data / CONFIG_NAME,
            data_dir=data,
            output_dir=documents / "QA" / "Saída",
            program_dir=program_dir(),
        )


def program_dir() -> Path:
    """Pasta do executável empacotado ou, em desenvolvimento, a raiz do repositório."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[4]
