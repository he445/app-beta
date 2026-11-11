"""``SettingsSource`` em camadas.

Padrões, arquivo da máquina, arquivo do usuário, variáveis ``QA_*`` e argumentos.

Cada camada sobrescreve a anterior e é validada sozinha contra
``contracts/schemas/settings.schema.json``, para o erro dizer a chave e o
arquivo. O arquivo da máquina pode travar chaves (``[locked] keys = [...]``):
as camadas seguintes não as mudam.
"""

from __future__ import annotations

import json
import os
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from qa_engine.adapters.paths import AppPaths, program_dir
from qa_engine.application.contracts import validator
from qa_engine.application.settings import (
    LOCKED,
    SCHEMA,
    ResolvedSettings,
    SettingsError,
    SettingsProblem,
    check_layer,
    known_keys,
    settings_from_values,
)

ENV_KEYS: dict[str, str] = {
    "QA_WORKERS": "workers",
    "QA_MAX_MEMORY_MB": "max_memory_mb",
    "QA_DATA_DIR": "data_dir",
    "QA_OUTPUT_DIR": "output_dir",
    "QA_TEMP_DIR": "temp_dir",
    "QA_ALLOWED_ROOTS": "allowed_roots",
    "QA_DEFAULT_STATION": "default_station",
    "QA_BATCH_SETTLE_SECONDS": "batch_settle_seconds",
    "QA_RETENTION_DAYS": "retention_days",
    "QA_RETENTION_HOURS": "retention_days",
    "QA_LOG_LEVEL": "log_level",
    "QA_PROFILES_DIR": "profiles_dir",
    "QA_UI_DIR": "ui_dir",
    "QA_DEMO_DIR": "demo_dir",
    "QA_MAX_UPLOAD_MB": "max_upload_mb",
    "QA_CORS_ORIGINS": "cors_origins",
    "QA_API_TOKEN": "api_token",
}
"""Variável de ambiente → chave. São as mesmas que o motor em servidor sempre leu."""
LIST_SEPARATORS = {"allowed_roots": ";", "cors_origins": ","}


def _kinds(key: str) -> set[str]:
    prop = validator(SCHEMA).schema["properties"].get(key, {})
    kinds: set[str] = set()
    for option in [prop, *prop.get("oneOf", [])]:
        kind = option.get("type")
        kinds.update(kind if isinstance(kind, list) else [kind] if kind else [])
    return kinds


def coerce(key: str, raw: str) -> Any:
    """Converte o texto de uma variável ou argumento para o tipo que o esquema espera.

    O que não converte volta como texto, e a validação acusa com a origem certa.
    """
    kinds = _kinds(key)
    text = raw.strip()
    if "array" in kinds:
        separator = LIST_SEPARATORS.get(key, ",")
        return [part.strip() for part in text.split(separator) if part.strip()]
    if text == "" and "null" in kinds:
        return None
    if "integer" in kinds:
        try:
            return int(text)
        except ValueError:
            pass
    if "number" in kinds:
        try:
            return float(text)
        except ValueError:
            pass
    return text


def env_layer(env: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, str]]:
    """Valores vindos das variáveis ``QA_*`` e o nome da variável de cada chave."""
    values: dict[str, Any] = {}
    names: dict[str, str] = {}
    for name, key in ENV_KEYS.items():
        raw = env.get(name)
        if raw is None or raw == "":
            continue
        value = coerce(key, raw)
        if name == "QA_RETENTION_HOURS":
            if "QA_RETENTION_DAYS" in names.values():
                continue
            value = value / 24.0 if isinstance(value, (int, float)) else value
        values[key] = value
        names[key] = name
    return values, names


def parse_overrides(items: Sequence[str]) -> dict[str, Any]:
    """Argumentos ``chave=valor`` da linha de comando viram a camada mais forte.

    Raises:
        SettingsError: item sem ``=``.
    """
    values: dict[str, Any] = {}
    for item in items:
        key, sep, raw = item.partition("=")
        if not sep:
            raise SettingsError([SettingsProblem(item, "argumento --set", "chave=valor", item)])
        values[key.strip()] = coerce(key.strip(), raw)
    return values


def read_toml(path: Path) -> dict[str, Any]:
    """Lê um arquivo de configuração.

    Raises:
        SettingsError: o arquivo não é TOML válido.
    """
    try:
        return tomllib.loads(path.read_text("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise SettingsError(
            [SettingsProblem("<arquivo>", str(path), "arquivo TOML válido", str(exc))]
        ) from exc


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    # Texto básico do TOML aceita os mesmos escapes do JSON (inclusive ``\\`` de caminho Windows).
    return json.dumps(str(value), ensure_ascii=False)


def dump_toml(values: Mapping[str, Any]) -> str:
    """Serializa a configuração do usuário: chaves simples, sem valores vazios."""
    lines = ["# Gravado pela tela de Configurações. Chave ausente = valor herdado."]
    lines += [f"{key} = {_toml_value(value)}" for key, value in values.items() if value is not None]
    return "\n".join(lines) + "\n"


def server_defaults() -> dict[str, Any]:
    """Padrões do motor em servidor (nuvem ou rede interna)."""
    return {
        "workers": "auto",
        "max_memory_mb": "auto",
        "data_dir": "./data",
        "output_dir": None,
        "temp_dir": None,
        "allowed_roots": [],
        "default_station": None,
        "batch_settle_seconds": 0,
        "retention_days": 1,
        "log_level": "info",
        "profiles_dir": str(program_dir() / "profiles"),
        "ui_dir": None,
        "demo_dir": None,
        "max_upload_mb": 2048,
        "cors_origins": [],
        "api_token": None,
    }


def desktop_defaults(paths: AppPaths) -> dict[str, Any]:
    """Padrões do programa na estação."""
    ui = paths.program_dir / "ui"
    return {
        **server_defaults(),
        "data_dir": str(paths.data_dir),
        "output_dir": str(paths.output_dir),
        "batch_settle_seconds": 30,
        "retention_days": 30,
        "profiles_dir": str(paths.program_dir / "profiles"),
        "ui_dir": str(ui) if (ui / "index.html").is_file() else None,
    }


class LayeredSettings:
    """Combina as cinco camadas e grava a do usuário."""

    def __init__(
        self,
        defaults: Mapping[str, Any],
        *,
        machine_file: Path | None = None,
        user_file: Path | None = None,
        env: Mapping[str, str] | None = None,
        args: Mapping[str, Any] | None = None,
    ) -> None:
        self.defaults = dict(defaults)
        self.machine_file = machine_file
        self.user_file = user_file
        self.env = dict(os.environ if env is None else env)
        self.args = dict(args or {})

    @classmethod
    def for_server(cls, env: Mapping[str, str] | None = None) -> LayeredSettings:
        """Motor em servidor: padrões e variáveis ``QA_*``; sem arquivos."""
        return cls(server_defaults(), env=env)

    @classmethod
    def for_desktop(
        cls,
        paths: AppPaths,
        env: Mapping[str, str] | None = None,
        args: Mapping[str, Any] | None = None,
    ) -> LayeredSettings:
        """Programa na estação: as cinco camadas."""
        return cls(
            desktop_defaults(paths),
            machine_file=paths.machine_config,
            user_file=paths.user_config,
            env=env,
            args=args,
        )

    def _file(self, path: Path | None) -> dict[str, Any]:
        return read_toml(path) if path is not None and path.is_file() else {}

    def load(self) -> ResolvedSettings:
        """Combina as camadas.

        Raises:
            SettingsError: alguma camada tem chave desconhecida ou valor fora do esquema.
        """
        machine = self._file(self.machine_file)
        user = self._file(self.user_file)
        env, env_names = env_layer(self.env)
        problems = check_layer(machine, str(self.machine_file))
        problems += check_layer(user, str(self.user_file))
        if LOCKED in user:
            problems.append(
                SettingsProblem(
                    LOCKED,
                    str(self.user_file),
                    "só o arquivo da máquina trava chaves",
                    user[LOCKED],
                )
            )
        for problem in check_layer(env, "variável de ambiente"):
            name = env_names.get(problem.key, "QA_*")
            problems.append(
                SettingsProblem(problem.key, f"variável {name}", problem.expected, self.env[name])
            )
        problems += [
            SettingsProblem(p.key, f"argumento --set {p.key}", p.expected, p.value)
            for p in check_layer(self.args, "argumento")
        ]
        if problems:
            raise SettingsError(problems)

        locked = frozenset(machine.get(LOCKED, {}).get("keys", []))
        values = dict(self.defaults)
        origins = dict.fromkeys(values, "default")
        layers = (("machine", machine), ("user", user), ("env", env), ("args", self.args))
        for origin, layer in layers:
            for key, value in layer.items():
                if key == LOCKED or (origin != "machine" and key in locked):
                    continue
                values[key] = value
                origins[key] = origin
        return ResolvedSettings(
            settings=settings_from_values(values),
            values={key: values.get(key) for key in known_keys()},
            origins={key: origins.get(key, "default") for key in known_keys()},
            locked=locked,
            files={
                "machine": str(self.machine_file) if self.machine_file else None,
                "user": str(self.user_file) if self.user_file else None,
            },
        )

    def save_user(self, changes: Mapping[str, Any], reset: Sequence[str] = ()) -> ResolvedSettings:
        """Grava mudanças no arquivo do usuário e devolve a configuração resultante.

        Args:
            changes: chaves a definir.
            reset: chaves a tirar do arquivo do usuário (voltam a herdar).

        Raises:
            SettingsError: valor fora do esquema, chave travada ou programa sem arquivo de usuário.
        """
        if self.user_file is None:
            raise SettingsError(
                [SettingsProblem("<arquivo>", "motor em servidor", "arquivo do usuário", None)]
            )
        current = self.load()
        source = str(self.user_file)
        touched = set(changes) | set(reset)
        problems = [
            SettingsProblem(key, source, "chave travada pelo arquivo da máquina", changes.get(key))
            for key in sorted(touched & current.locked)
        ]
        if "api_token" in touched:
            problems.append(
                SettingsProblem("api_token", source, "token só por variável ou argumento", None)
            )
        user = {k: v for k, v in self._file(self.user_file).items() if k not in reset}
        user.update(changes)
        problems += check_layer(user, source)
        if problems:
            raise SettingsError(problems)
        self.user_file.parent.mkdir(parents=True, exist_ok=True)
        partial = self.user_file.with_name(self.user_file.name + ".part")
        partial.write_text(dump_toml(user), "utf-8")
        partial.replace(self.user_file)
        return self.load()
