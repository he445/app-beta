"""Configuração em camadas (ADR-0012): precedência, chaves travadas e erros com origem."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from qa_engine.adapters.paths import AppPaths
from qa_engine.adapters.settings import (
    LayeredSettings,
    dump_toml,
    parse_overrides,
    read_toml,
    server_defaults,
)
from qa_engine.application.settings import Settings, SettingsError, known_keys


@pytest.fixture
def paths(tmp_path: Path) -> AppPaths:
    return AppPaths(
        machine_config=tmp_path / "ProgramData" / "config.toml",
        user_config=tmp_path / "LocalAppData" / "config.toml",
        data_dir=tmp_path / "LocalAppData",
        output_dir=tmp_path / "Documentos" / "QA" / "Saída",
        program_dir=tmp_path / "programa",
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")


def layered(paths: AppPaths, env: dict[str, str] | None = None, **args: Any) -> LayeredSettings:
    return LayeredSettings.for_desktop(paths, env=env or {}, args=args)


def test_defaults_cover_every_key_of_the_schema() -> None:
    assert set(server_defaults()) == set(known_keys())


def test_desktop_defaults(paths: AppPaths) -> None:
    resolved = layered(paths).load()
    assert resolved.settings.data_dir == paths.data_dir
    assert resolved.settings.output_root == paths.output_dir
    assert resolved.settings.temp_root == paths.data_dir / "tmp"
    assert resolved.settings.retention_hours == 30 * 24
    assert resolved.settings.batch_settle_seconds == 30
    assert resolved.settings.workers is None
    assert set(resolved.origins.values()) == {"default"}


def test_each_layer_overrides_the_previous_one(paths: AppPaths) -> None:
    """Padrão < máquina < usuário < variável < argumento, e a origem acompanha."""
    source = layered(paths)
    assert source.load().values["workers"] == "auto"

    write(paths.machine_config, "workers = 2\nlog_level = 'warning'\nretention_days = 7\n")
    resolved = layered(paths).load()
    assert (resolved.values["workers"], resolved.origins["workers"]) == (2, "machine")

    write(paths.user_config, "workers = 3\nlog_level = 'debug'\n")
    resolved = layered(paths).load()
    assert (resolved.values["workers"], resolved.origins["workers"]) == (3, "user")
    assert (resolved.values["retention_days"], resolved.origins["retention_days"]) == (7, "machine")

    resolved = layered(paths, env={"QA_WORKERS": "4"}).load()
    assert (resolved.values["workers"], resolved.origins["workers"]) == (4, "env")
    assert resolved.origins["log_level"] == "user"

    resolved = layered(paths, env={"QA_WORKERS": "4"}, workers=5).load()
    assert (resolved.values["workers"], resolved.origins["workers"]) == (5, "args")
    assert resolved.settings.workers == 5
    assert resolved.origins["data_dir"] == "default"


def test_locked_keys_cannot_be_changed_by_later_layers(paths: AppPaths) -> None:
    write(
        paths.machine_config,
        'allowed_roots = ["//servidor/digitalizacao"]\n'
        '[locked]\nkeys = ["allowed_roots", "workers"]\n',
    )
    write(paths.user_config, 'allowed_roots = ["C:/qualquer"]\nworkers = 8\nlog_level = "debug"\n')
    resolved = layered(paths, env={"QA_ALLOWED_ROOTS": "D:/outra"}, workers=9).load()
    assert resolved.values["allowed_roots"] == ["//servidor/digitalizacao"]
    assert resolved.origins["allowed_roots"] == "machine"
    assert resolved.values["workers"] == "auto"  # travada no padrão: ninguém acima muda
    assert resolved.locked == {"allowed_roots", "workers"}
    assert resolved.values["log_level"] == "debug"


def test_invalid_value_reports_key_file_and_expected(paths: AppPaths) -> None:
    write(paths.user_config, 'workers = 0\nretention_days = "muito"\nlog_level = "verbose"\n')
    with pytest.raises(SettingsError) as info:
        layered(paths).load()
    problems = {p.key: p for p in info.value.problems}
    assert set(problems) == {"workers", "retention_days", "log_level"}
    assert problems["workers"].source == str(paths.user_config)
    assert problems["workers"].value == 0
    assert '"auto"' in problems["workers"].expected and "≥ 1" in problems["workers"].expected
    assert "número > 0" in problems["retention_days"].expected
    assert "debug" in problems["log_level"].expected
    assert str(paths.user_config) in str(info.value)


def test_unknown_key_and_broken_toml_are_errors(paths: AppPaths) -> None:
    write(paths.machine_config, "trabalhadores = 4\n")
    with pytest.raises(SettingsError) as info:
        layered(paths).load()
    (problem,) = info.value.problems
    assert problem.key == "trabalhadores" and problem.source == str(paths.machine_config)
    assert "workers" in problem.expected

    write(paths.machine_config, "workers = = 4\n")
    with pytest.raises(SettingsError) as info:
        layered(paths).load()
    assert info.value.problems[0].expected == "arquivo TOML válido"


def test_env_and_args_errors_name_the_variable(paths: AppPaths) -> None:
    with pytest.raises(SettingsError) as info:
        layered(paths, env={"QA_WORKERS": "muitos", "QA_MAX_UPLOAD_MB": "-1"}).load()
    sources = {p.key: p.source for p in info.value.problems}
    assert sources == {
        "workers": "variável QA_WORKERS",
        "max_upload_mb": "variável QA_MAX_UPLOAD_MB",
    }
    assert {p.value for p in info.value.problems} == {"muitos", "-1"}

    with pytest.raises(SettingsError) as info:
        layered(paths, **parse_overrides(["batch_settle_seconds=-5"])).load()
    assert info.value.problems[0].source == "argumento --set batch_settle_seconds"
    with pytest.raises(SettingsError):
        parse_overrides(["semigual"])


def test_user_file_cannot_lock_keys(paths: AppPaths) -> None:
    write(paths.user_config, '[locked]\nkeys = ["workers"]\n')
    with pytest.raises(SettingsError) as info:
        layered(paths).load()
    assert info.value.problems[0].key == "locked"


def test_env_layer_reads_the_server_variables(tmp_path: Path) -> None:
    env = {
        "QA_DATA_DIR": str(tmp_path / "dados"),
        "QA_PROFILES_DIR": str(tmp_path / "perfis"),
        "QA_API_TOKEN": "segredo",
        "QA_CORS_ORIGINS": "https://a.exemplo, https://b.exemplo/",
        "QA_RETENTION_HOURS": "12",
        "QA_MAX_UPLOAD_MB": "64",
        "QA_WORKERS": "1",
        "QA_DEMO_DIR": str(tmp_path / "demo"),
        "QA_UI_DIR": str(tmp_path / "ui"),
        "QA_ALLOWED_ROOTS": r"\\servidor\lotes;D:\Lotes",
    }
    settings = LayeredSettings.for_server(env).load().settings
    assert settings == Settings(
        data_dir=tmp_path / "dados",
        profiles_dir=tmp_path / "perfis",
        api_token="segredo",
        cors_origins=("https://a.exemplo", "https://b.exemplo/"),
        retention_hours=12.0,
        max_upload_mb=64,
        workers=1,
        demo_dir=tmp_path / "demo",
        ui_dir=tmp_path / "ui",
        allowed_roots=(Path(r"\\servidor\lotes"), Path(r"D:\Lotes")),
    )
    assert LayeredSettings.for_server({}).load().settings.retention_hours == 24.0
    both = {"QA_RETENTION_HOURS": "12", "QA_RETENTION_DAYS": "3"}
    assert LayeredSettings.for_server(both).load().settings.retention_hours == 72.0


def test_save_user_validates_before_writing(paths: AppPaths) -> None:
    source = layered(paths)
    with pytest.raises(SettingsError) as info:
        source.save_user({"workers": 0, "output_dir": r"D:\Saída"})
    assert info.value.problems[0].key == "workers"
    assert not paths.user_config.exists()

    resolved = source.save_user({"workers": 2, "output_dir": r"D:\Saída do QA\ção"})
    assert resolved.origins["workers"] == "user"
    assert read_toml(paths.user_config) == {"workers": 2, "output_dir": r"D:\Saída do QA\ção"}

    resolved = source.save_user({"log_level": "debug"}, reset=["workers"])
    assert resolved.values["workers"] == "auto" and resolved.origins["workers"] == "default"
    assert resolved.values["log_level"] == "debug"


def test_save_user_refuses_locked_keys_and_token(paths: AppPaths) -> None:
    write(paths.machine_config, '[locked]\nkeys = ["allowed_roots"]\n')
    with pytest.raises(SettingsError) as info:
        layered(paths).save_user({"allowed_roots": ["C:/x"], "api_token": "x"})
    assert {p.key for p in info.value.problems} == {"allowed_roots", "api_token"}
    with pytest.raises(SettingsError):
        LayeredSettings.for_server({}).save_user({"workers": 2})


def test_view_never_exposes_the_token(paths: AppPaths) -> None:
    view = layered(paths, env={"QA_API_TOKEN": "segredo"}).load().json()
    assert view["values"]["api_token"] is None
    assert view["origins"]["api_token"] == "env"
    assert "segredo" not in str(view)


def test_toml_roundtrip_with_windows_paths() -> None:
    values = {
        "data_dir": r"C:\Users\José\AppData\Local\SOSDocs\QA",
        "allowed_roots": [r"\\srv\a b"],
    }
    text = dump_toml({**values, "default_station": None})
    assert "default_station" not in text
    import tomllib

    assert tomllib.loads(text) == values


def test_effective_workers_respects_cores_and_memory(tmp_path: Path) -> None:
    base = LayeredSettings.for_server({"QA_DATA_DIR": str(tmp_path)}).load().settings
    assert base.effective_workers(cpu_count=8, memory_mb=None) == 7
    assert base.effective_workers(cpu_count=1) == 1
    assert base.effective_workers(cpu_count=8, memory_mb=2048) == 2  # metade de 2 GB / 400 MB
    fixed = LayeredSettings.for_server({"QA_WORKERS": "6", "QA_MAX_MEMORY_MB": "800"}).load()
    assert fixed.settings.effective_workers(cpu_count=8, memory_mb=64000) == 2
