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


# ---------------------------------------------------------------- pastas: ls, ver e pastas
def _liberar(tmp_path, cfg, pasta):
    from oma_rpg import caminhos
    from oma_rpg.nucleo.banco import Banco
    from oma_rpg.nucleo.jogo import Jogo
    b = Banco(caminhos.arquivo_banco())
    Jogo(b, cfg).pasta_adicionar(str(pasta))
    b.fechar()


def test_cli_ls_e_ver_so_nas_pastas_liberadas(com_heroi, cfg, tmp_path):
    estudo = tmp_path / "Comp-Deci"
    (estudo / "aulas").mkdir(parents=True)
    (estudo / "aulas" / "aula1.md").write_text("entropia\n")
    (estudo / "slides.pdf").write_bytes(b"%PDF-1.4\n" + b"\x00" * 4000)
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "x.txt").write_text("não\n")
    (estudo / "link").symlink_to(fora)
    antes = heroi(com_heroi)
    r = json.loads(rodar(com_heroi, "ls", str(estudo), "--json").stdout)
    assert not r["ok"] and "fora das pastas liberadas" in r["erro"] and "tecla P" in r["erro"]
    _liberar(tmp_path, cfg, estudo)
    r = json.loads(rodar(com_heroi, "pastas", "--json").stdout)
    assert [p["caminho"] for p in r["dados"]["pastas"]] == [str(estudo)]
    r = json.loads(rodar(com_heroi, "ls", str(estudo), "-r", "--json").stdout)
    assert r["ok"] and {"aulas", "aulas/aula1.md", "slides.pdf", "link"} <= {i["nome"] for i in r["dados"]["itens"]}
    assert json.loads(rodar(com_heroi, "ver", str(estudo / "aulas" / "aula1.md"), "--json").stdout)["dados"]["conteudo"] == "entropia\n"
    pdf = json.loads(rodar(com_heroi, "ver", str(estudo / "slides.pdf"), "--json").stdout)["dados"]
    assert pdf["conteudo"] is None and pdf["tamanho"] > 4000
    for alvo in (fora / "x.txt", estudo / "link" / "x.txt", f"{estudo}/../fora/x.txt"):
        r = json.loads(rodar(com_heroi, "ver", str(alvo), "--json").stdout)
        assert not r["ok"], alvo
    assert "entropia" in rodar(com_heroi, "ver", str(estudo / "aulas" / "aula1.md")).stdout
    assert heroi(com_heroi) == antes


def test_cli_nao_libera_pasta(com_heroi, tmp_path):
    for sub in (["liberar", str(tmp_path)], ["pasta_adicionar", str(tmp_path)], ["pastas", "--add", str(tmp_path)]):
        assert rodar(com_heroi, *sub).returncode != 0
    assert json.loads(rodar(com_heroi, "pastas", "--json").stdout)["dados"]["pastas"] == []


def test_cli_na_taverna_pede_e_espera_o_jc(com_heroi, cfg, tmp_path):
    """Dentro da taverna (OMA_RPG_MESTRE=1), ls numa pasta nova pede ao JC; quando ele libera, o ls continua."""
    import threading
    import time as _t
    from oma_rpg import caminhos
    from oma_rpg.nucleo.banco import Banco
    from oma_rpg.nucleo.jogo import Jogo
    from oma_rpg.servico import Servico
    estudo = tmp_path / "nova"
    estudo.mkdir()
    (estudo / "a.txt").write_text("ok\n")
    j = Jogo(Banco(caminhos.arquivo_banco()), cfg)
    s = Servico(jogo=j, notificar=lambda t, c: None)
    pedidos = []
    j.ouvintes.append(lambda e: e.get("evento") == "pedido_pasta" and pedidos.append(e))
    s.iniciar()
    try:
        env = dict(env_sub(com_heroi), OMA_RPG_MESTRE="1")
        resultado = {}

        def chamar():
            resultado["r"] = subprocess.run([sys.executable, "-m", "oma_rpg", "ls", str(estudo), "--json"], capture_output=True,
                                            text=True, timeout=60, env=env)
        t = threading.Thread(target=chamar)
        t.start()
        fim = _t.time() + 15
        while not pedidos and _t.time() < fim:
            _t.sleep(0.1)
        assert pedidos and pedidos[0]["caminho"] == str(estudo)
        from oma_rpg.cliente import ClienteServico
        c = ClienteServico(iniciar=None)  # a interface, com a chave de jogador
        assert c.conectar() and c.papel == "jogador"
        assert c.pedir_e_esperar("responder_pedido", {"id": pedidos[0]["id"], "resposta": "sempre"})[0]
        c.fechar()
        t.join(30)
        d = json.loads(resultado["r"].stdout)
        assert d["ok"] and [i["nome"] for i in d["dados"]["itens"]] == ["a.txt"]

        pf = subprocess.run([sys.executable, "-m", "oma_rpg", "perfil",
                             "--estrategia", "Foco em blocos de 25m com revisão ativa.",
                             "--atributos", "for=0,agi=2,vig=2,int=3,con=3,pre=1",
                             "--pericias", "Python,Inglês", "--json"],
                            capture_output=True, text=True, timeout=30, env=env)
        assert pf.returncode == 0, pf.stderr
        dp = json.loads(pf.stdout)
        assert dp["ok"] and dp["dados"]["entrevista_estado"] == "concluida"
        assert dp["dados"]["proposta"]["pericias"] == ["Python", "Inglês"]
    finally:
        s.encerrar()
