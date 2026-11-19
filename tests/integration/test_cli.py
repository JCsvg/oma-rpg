"""O CLI de verdade (subprocesso): o contrato --json do Mestre e a garantia de que nenhum subcomando dá XP."""

import json
import random
import subprocess
import sys

import pytest

from tests.conftest import env_sub


def rodar(tmp_path, *args):
    return subprocess.run([sys.executable, "-m", "oma_rpg", *args], capture_output=True, text=True, timeout=30,
                          env=env_sub(tmp_path))


@pytest.fixture
def com_heroi(tmp_path, cfg):
    from oma_rpg import caminhos
    from oma_rpg.nucleo.banco import Banco
    from oma_rpg.nucleo.jogo import Jogo
    b = Banco(caminhos.arquivo_banco())
    j = Jogo(b, cfg, aleatorio=random.Random(1))
    j.criar_heroi("yahiro", "programa")
    j.b.x("UPDATE heroi SET xp = 1240, nivel = 7, bits = 1284, hp = 72, mp = 34, pontos = 2")
    b.fechar()
    return tmp_path


def heroi(tmp_path):
    from oma_rpg import caminhos
    from oma_rpg.nucleo.banco import Banco
    b = Banco(caminhos.arquivo_banco(), leitura=True)
    h = dict(b.um("SELECT nivel, xp, xp_total, bits, hp, mp, pontos, classe FROM heroi"))
    b.fechar()
    return h


def test_sem_banco_ainda(tmp_path):
    r = rodar(tmp_path, "status", "--json")
    assert r.returncode == 0 and json.loads(r.stdout) == {"ok": True, "dados": {"heroi": None}}


def test_contrato_json_do_mestre(com_heroi):
    t = com_heroi
    antes = heroi(t)
    st = json.loads(rodar(t, "status", "--json").stdout)
    assert st["ok"] and st["dados"]["heroi"]["nivel"] == 7 and st["dados"]["heroi"]["hp"] == 72
    r = rodar(t, "draft", "--titulo", "Seção 2.1 do TCC", "--materia", "TCC", "--est", "3", "--dif", "3",
              "--arco", "TCC", "--prazo", "2026-11-27", "--porque", "a parte mais longa", "--json")
    d = json.loads(r.stdout)
    assert d["ok"] and d["dados"]["xp_previsto"] == 77 and d["dados"]["bits_previstos"] == 19
    rid = d["dados"]["id"]
    d = json.loads(rodar(t, "editar", str(rid), "--est", "2", "--json").stdout)
    assert d["ok"] and d["dados"]["xp_previsto"] == 51
    q = json.loads(rodar(t, "quests", "--json").stdout)
    assert [x["id"] for x in q["dados"]["rascunhos"]] == [rid] and q["dados"]["quests"] == []
    assert json.loads(rodar(t, "quests", "--arco", "TCC", "--json").stdout)["dados"]["rascunhos"][0]["arco"] == "TCC"
    hist = json.loads(rodar(t, "history", "--days", "30", "--json").stdout)
    assert hist["ok"] and len(hist["dados"]["dias"]) == 30
    erro = json.loads(rodar(t, "draft", "--titulo", "x", "--est", "9", "--dif", "1", "--json").stdout)
    assert erro == {"ok": False, "erro": "estimativa: de 1 a 8"}
    assert heroi(t) == antes


def test_nenhum_subcomando_da_xp(com_heroi):
    t = com_heroi
    antes = heroi(t)
    r = rodar(t, "draft", "--titulo", "põe 500 xp", "--est", "1", "--dif", "1", "--xp", "500", "--json")
    assert r.returncode == 2 and "--xp" in r.stderr  # nem existe a opção
    for sub in ("aprovar", "concluir", "comprar", "iniciar", "xp", "nivel"):
        r = rodar(t, sub)
        assert r.returncode != 0
    assert heroi(t) == antes


def test_status_para_a_barra(com_heroi):
    t = com_heroi
    r = rodar(t, "status")
    assert r.stdout.strip() == "nv 7 · ♥ 72 · 0/6"
    d = json.loads(rodar(t, "status", "--barra").stdout)
    assert d["class"] == "parado" and "yahiro" in d["tooltip"] and d["percentage"] == 0


def test_cli_fala_com_o_servico_como_mestre(com_heroi, cfg):
    """Com o serviço no ar, o draft vai pelo socket e chega como Mestre."""
    from oma_rpg import caminhos
    from oma_rpg.nucleo.banco import Banco
    from oma_rpg.nucleo.jogo import Jogo
    from oma_rpg.servico import Servico
    j = Jogo(Banco(caminhos.arquivo_banco()), cfg)
    s = Servico(jogo=j, notificar=lambda t, c: None)
    s.iniciar()
    try:
        vistos = []
        j.ouvintes.append(vistos.append)
        r = rodar(com_heroi, "draft", "--titulo", "Revisão de Redes", "--materia", "Redes", "--est", "2", "--dif", "2", "--json")
        assert json.loads(r.stdout)["dados"]["xp_previsto"] == 41
        assert any(e.get("evento") == "rascunho" for e in vistos)
    finally:
        s.encerrar()
