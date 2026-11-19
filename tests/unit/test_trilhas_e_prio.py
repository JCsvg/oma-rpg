"""Testes de prioridade, descrição longa e campanhas com trilhas e ramos (depende_de)."""

from __future__ import annotations

import pytest

from oma_rpg.nucleo import consultas as C
from oma_rpg.nucleo.jogo import ErroJogo


def test_prioridade_ordena_quests_e_valida_faixa(heroi):
    jogo = heroi
    q1 = jogo.nova_quest(titulo="Baixa", est=1, dif=1, prio=1)
    q2 = jogo.nova_quest(titulo="Alta", est=1, dif=1, prio=3)
    q3 = jogo.nova_quest(titulo="Media", est=1, dif=1)
    qs = C.quests(jogo.b, jogo.cfg, jogo.hoje(), "aberta")
    assert [q["id"] for q in qs] == [q2["id"], q3["id"], q1["id"]]
    assert qs[0]["prio"] == 3
    with pytest.raises(ErroJogo):
        jogo.nova_quest(titulo="Errada", est=1, dif=1, prio=4)


def test_trilha_com_ramos_exige_multiplos_prerequisitos(heroi):
    jogo = heroi
    r1 = jogo.nova_quest(titulo="Ramo A", est=1, dif=1, arco="Campanha")
    r2 = jogo.nova_quest(titulo="Ramo B", est=1, dif=1, arco="Campanha")
    chefe = jogo.nova_quest(titulo="Chefe Final", est=2, dif=3, arco="Campanha", depende_de=[r1["id"], r2["id"]],
                            descricao="1. Revisar Ramo A e B. 2. Resolver simulado sem consulta.")

    qs = {q["id"]: q for q in C.quests(jogo.b, jogo.cfg, jogo.hoje(), "aberta")}
    assert qs[chefe["id"]]["bloqueada"] is True
    assert qs[chefe["id"]]["faltam_deps"] == [r1["id"], r2["id"]]
    assert "simulado sem consulta" in qs[chefe["id"]]["porque"]

    with pytest.raises(ErroJogo, match="bloqueada"):
        jogo.iniciar(chefe["id"])
    with pytest.raises(ErroJogo, match="bloqueada"):
        jogo.concluir_quest(chefe["id"])

    jogo.concluir_quest(r1["id"])
    qs = {q["id"]: q for q in C.quests(jogo.b, jogo.cfg, jogo.hoje(), "aberta")}
    assert qs[chefe["id"]]["bloqueada"] is True
    assert qs[chefe["id"]]["faltam_deps"] == [r2["id"]]

    jogo.concluir_quest(r2["id"])
    qs = {q["id"]: q for q in C.quests(jogo.b, jogo.cfg, jogo.hoje(), "aberta")}
    assert qs[chefe["id"]]["bloqueada"] is False
    jogo.iniciar(chefe["id"])
