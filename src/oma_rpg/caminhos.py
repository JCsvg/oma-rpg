"""Onde cada coisa mora.

config   $XDG_CONFIG_HOME/oma-rpg   balanceamento.toml (opcional, sobrepõe o padrão do pacote)
dados    $XDG_DATA_HOME/oma-rpg     rpg.sqlite3 (WAL) e a pasta da taverna (sessões do claude)
runtime  $XDG_RUNTIME_DIR/oma-rpg   socket do serviço, chave do jogador, trava, abertura do boot e contexto da interface
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _xdg(var: str, padrao: str) -> Path:
    v = os.environ.get(var)
    return Path(v) if v else Path.home() / padrao


def pasta_config() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "oma-rpg"


def pasta_dados() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / "oma-rpg"


def pasta_runtime() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base and os.path.isdir(base):
        return Path(base) / "oma-rpg"
    return Path(tempfile.gettempdir()) / f"oma-rpg-{os.getuid()}"


def arquivo_banco() -> Path:
    return pasta_dados() / "rpg.sqlite3"


def arquivo_socket() -> Path:
    return pasta_runtime() / "servico.sock"


def arquivo_chave() -> Path:
    """Chave do papel de jogador: o serviço gera ao iniciar, só a interface lê (o CLI nunca)."""
    return pasta_runtime() / "jogador.chave"


def arquivo_balanceamento_usuario() -> Path:
    return pasta_config() / "balanceamento.toml"


def arquivo_mestre() -> Path:
    return pasta_config() / "mestre.json"


def garantir(p: Path, modo: int = 0o700) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(p, modo)
    except OSError:
        pass
    return p
