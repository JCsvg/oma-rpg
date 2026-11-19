"""O serviço de ponta a ponta pelo socket, com relógio falso: 25 minutos passam num avancar()."""

import os
import queue
import random
import stat
import time

import pytest

from oma_rpg.cliente import ClienteServico
from oma_rpg.servico import Servico
from tests.conftest import momento


def esperar(cond, tempo=5.0):
    fim = time.monotonic() + tempo
    while time.monotonic() < fim:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


@pytest.fixture
def servico(tmp_path, cfg, relogio):
    from oma_rpg.nucleo.banco import Banco
    from oma_rpg.nucleo.jogo import Jogo
    cfg["conquistas"] = {}
    j = Jogo(Banco(tmp_path / "dados" / "rpg.sqlite3"), cfg, relogio, random.Random(3))
    notas = []
    s = Servico(jogo=j, socket_path=tmp_path / "run" / "oma-rpg" / "servico.sock",
                chave_path=tmp_path / "run" / "oma-rpg" / "jogador.chave", notificar=lambda t, c: notas.append((t, c)))
    s.notas = notas
    s.iniciar()
    yield s
    s.encerrar()


def cliente(s, papel="jogador"):
    c = ClienteServico(socket_path=s.socket_path, chave_path=s.chave_path, papel=papel, iniciar=None)
    c.eventos = queue.Queue()
    c.ao_evento = c.eventos.put
    assert c.conectar()
    return c


def pedir(c, cmd, args=None):
    ok, r = c.pedir_e_esperar(cmd, args)
    return ok, r


def evento(c, nome, tempo=5.0):
    fim = time.monotonic() + tempo
    while time.monotonic() < fim:
        try:
            e = c.eventos.get(timeout=0.1)
        except queue.Empty:
            continue
        if e.get("evento") == nome:
            return e
    raise AssertionError(f"evento {nome} não chegou")


def test_socket_e_chave_so_do_usuario(servico):
    assert stat.S_IMODE(os.stat(servico.socket_path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(servico.chave_path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(servico.socket_path.parent).st_mode) == 0o700


def test_pomodoro_inteiro_pelo_socket_com_relogio_falso(servico):
    c = cliente(servico)
    assert c.papel == "jogador"
    assert pedir(c, "criar_heroi", {"nome": "yahiro", "classe": "programa"})[0]
    ok, q = pedir(c, "nova_quest", {"titulo": "Lista 4 de Compiladores", "materia": "Compiladores", "est": 2, "dif": 2})
    assert ok and q["xp_previsto"] == 41
    assert pedir(c, "iniciar", {"quest": q["id"]})[0]
    ok, st = pedir(c, "status")
    assert st["pomodoro"]["fase"] == "foco" and st["pomodoro"]["restante_s"] == 25 * 60
    servico.jogo.rel.avancar(25 * 60)
    servico.acordar()
    e = evento(c, "pomodoro_fim")
    assert e["xp"] == 24 and e["quest"] == "Lista 4 de Compiladores"
    assert esperar(lambda: servico.notas)
    assert "Pomodoro 1" in servico.notas[0][0]
    servico.jogo.rel.avancar(5 * 60)
    servico.acordar()
    assert evento(c, "pausa_fim")["respeitada"]
    ok, st = pedir(c, "status")
    assert st["heroi"]["xp"] == 24 and st["hoje"]["pomodoros"] == 1 and st["pomodoro"]["fase"] == "parado"
    c.fechar()


def test_mestre_pelo_socket_le_e_cria_rascunho_mas_nao_aprova(servico):
    j = cliente(servico)
    pedir(j, "criar_heroi", {"nome": "yahiro", "classe": "programa"})
    m = cliente(servico, papel="mestre")
    assert m.papel == "mestre"
    ok, r = pedir(m, "rascunho", {"titulo": "Seção 2.1 do TCC", "materia": "TCC", "est": 3, "dif": 3})
    assert ok and r["xp_previsto"] == 77
    assert evento(j, "rascunho")["id"] == r["id"]
    for cmd, a in (("aprovar", {"id": r["id"]}), ("iniciar", {}), ("comprar", {"item": "cafe"}),
                   ("concluir_quest", {"id": r["id"]}), ("aprender", {"skill": "git_stash"})):
        ok, erro = pedir(m, cmd, a)
        assert not ok and "Mestre não pode" in erro
    ok, erro = pedir(m, "rascunho", {"titulo": "x", "est": 1, "dif": 1, "xp": 500})
    assert not ok and "tabela do jogo" in erro
    # chave errada continua Mestre
    ok, r2 = m.pedir_e_esperar("ola", {"chave": "0" * 48})
    assert ok and r2["papel"] == "mestre"
    ok, st = pedir(m, "status")
    assert st["heroi"]["xp"] == 0 and st["heroi"]["bits"] == 0
    j.fechar()
    m.fechar()


def test_virada_do_dia_pelo_servico(servico):
    c = cliente(servico)
    pedir(c, "criar_heroi", {"nome": "yahiro", "classe": "programa"})
    pedir(c, "nova_quest", {"titulo": "Revisar flashcards", "est": 1, "dif": 1, "tipo": "daily"})
    servico.jogo.rel.t = momento("2026-11-19", 0, 1)
    servico.acordar()
    assert evento(c, "dia")["dia"] == "2026-11-19"
    ok, st = pedir(c, "status")
    assert st["heroi"]["hp"] == 100  # -8 da daily, +10 do sono, até o máximo
    c.fechar()


def test_pedido_quebrado_nao_derruba(servico):
    import socket
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(str(servico.socket_path))
    s.sendall(b"isto nao e json\n{\"id\": 1, \"cmd\": 5}\n")
    s.settimeout(2)
    resp = s.recv(4096)
    assert b'"ok": false' in resp
    s.close()
    c = cliente(servico)
    assert pedir(c, "ping")[0]
    c.fechar()
