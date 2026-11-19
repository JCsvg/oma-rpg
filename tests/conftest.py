"""Fixtures: ambiente isolado (XDG em pasta temporária, fuso fixo), motor com relógio falso e o app de teste."""

from __future__ import annotations

import asyncio
import os
import random
import time

import pytest

FUSO = "America/Sao_Paulo"


def momento(dia: str, h: int, m: int = 0, s: int = 0) -> float:
    a, me, d = (int(x) for x in dia.split("-"))
    return time.mktime((a, me, d, h, m, s, 0, 0, -1))


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    """Nenhum teste toca no estado real, no socket real ou na barra."""
    for k, v in (("XDG_CONFIG_HOME", "cfg"), ("XDG_DATA_HOME", "dados"), ("XDG_RUNTIME_DIR", "run"),
                 ("XDG_STATE_HOME", "state"), ("XDG_CACHE_HOME", "cache")):
        monkeypatch.setenv(k, str(tmp_path / v))
        (tmp_path / v).mkdir()
    monkeypatch.setenv("TZ", FUSO)
    time.tzset()
    yield
    time.tzset()


@pytest.fixture
def cfg():
    from oma_rpg.config import Config
    return Config.carregar(usar_usuario=False)


@pytest.fixture
def relogio():
    from oma_rpg.nucleo.jogo import RelogioFalso
    return RelogioFalso(momento("2026-11-18", 8, 0))


@pytest.fixture
def banco(tmp_path):
    from oma_rpg.nucleo.banco import Banco
    b = Banco(tmp_path / "dados" / "oma-rpg" / "rpg.sqlite3")
    yield b
    b.fechar()


@pytest.fixture
def jogo(banco, cfg, relogio):
    """Motor sem conquistas, para as contas dos testes ficarem só com o que cada um mede (test_conquistas liga)."""
    from oma_rpg.nucleo.jogo import Jogo
    cfg["conquistas"] = {}
    j = Jogo(banco, cfg, relogio, random.Random(1))
    j.notas = []
    j.notificar = lambda t, c: j.notas.append((t, c))
    return j


@pytest.fixture
def heroi(jogo):
    jogo.criar_heroi("yahiro", "programa")
    jogo.soltar_eventos()
    return jogo


def pomodoro(j, minutos: float = 25, quest=None, pausa: bool = True):
    """Começa, deixa o relógio andar e conclui pelo tick; com pausa=True espera a pausa terminar também."""
    j.iniciar(quest)
    j.rel.avancar(minutos * 60)
    j.tick()
    if pausa:
        a = j.atual()
        if a["fase"] in ("pausa", "longa"):
            j.rel.avancar(a["duracao"])
            j.tick()


# ---------------------------------------------------------------- interface
@pytest.fixture
def app(tmp_path):
    from oma_rpg.falso import montar_demo
    from oma_rpg.ui.app import OmaRpgApp
    kw = montar_demo(pasta=tmp_path / "demo", fixo=True)
    a = OmaRpgApp(**kw, abertura=False)
    yield a
    kw["cliente"].fechar()


async def esperar(pilot, cond, tempo: float = 3.0) -> bool:
    fim = asyncio.get_event_loop().time() + tempo
    while asyncio.get_event_loop().time() < fim:
        await pilot.pause(0.05)
        if cond():
            return True
    return cond()


def janela(app) -> str:
    return app.nome_janela(app.focused)


async def pronto(app, pilot) -> None:
    await pilot.pause(0.3)
    assert await esperar(pilot, lambda: app.pronto and app.focused is not None, 4)
    await pilot.pause(0.2)


def env_sub(tmp_path) -> dict:
    """Ambiente de subprocesso apontando para as pastas do teste."""
    from pathlib import Path
    raiz = Path(__file__).parents[1]
    env = dict(os.environ, PYTHONPATH=str(raiz / "src"), TZ=FUSO)
    for k, v in (("XDG_CONFIG_HOME", "cfg"), ("XDG_DATA_HOME", "dados"), ("XDG_RUNTIME_DIR", "run"),
                 ("XDG_STATE_HOME", "state"), ("XDG_CACHE_HOME", "cache")):
        env[k] = str(tmp_path / v)
    return env
