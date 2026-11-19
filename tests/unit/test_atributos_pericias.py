"""Testes de atributos, perícias independentes, questionário de perfil, classes novas e conclusão sem pomodoro."""

from __future__ import annotations

from oma_rpg.nucleo import consultas as C


def test_questionario_calcula_atributos_pericias_e_mantem_quests(jogo):
    # Simula quests já existentes antes de criar um herói novo
    jogo.b.x("INSERT INTO arcos (nome, cor, criado) VALUES ('P2 Comp-Deci', 'blue', 1.0)")
    jogo.b.x("INSERT INTO quests (titulo, est, dif, estado, origem, criada) VALUES ('MT 1', 2, 2, 'aberta', 'jogador', 1.0)")

    res = jogo.criar_heroi("JC", "polimata", perfil={
        "ocupacao": "Ciência da Computação e estágio em Python",
        "objetivos": "Passar em Comp-Deci e treinar",
        "altura_cm": 175,
        "peso_kg": 72,
        "treina": True,
        "treino_tipo": "musculação",
        "treino_freq": "5x/semana",
        "tempo_estudo": "3h/dia",
        "atencao": "TDAH / distração fácil",
        "estilo_estudo": "prática e exercícios",
        "rotina": "manhã estágio, tarde estudo, noite treino",
        "pericias_iniciais": "Inglês",
    })
    assert res["atributos"]["for"] >= 3
    assert res["atributos"]["vig"] >= 3
    assert res["atributos"]["int"] >= 3
    assert "Inglês" in res["pericias"]
    assert "Programação" in res["pericias"]
    # Quests salvas continuam lá
    assert len(C.quests(jogo.b, jogo.cfg, jogo.hoje(), "aberta")) == 1
    assert C.perfil(jogo.b)["ocupacao"].startswith("Ciência")


def test_nivel_da_pontos_de_atributo_e_gastar_aumenta(heroi):
    j = heroi
    j._ganho("pomodoro", "xp", xp=300)
    h = C.heroi(j.b)
    assert h["nivel"] == 2
    assert h["pontos_attr"] == 2
    r = j.gastar_atributo("vig")
    assert r["valor"] == 2
    st = C.status(j.b, j.cfg, j.agora())
    assert st["atributos"]["vig"] == 2
    assert st["atributos"]["pontos"] == 1
    assert st["heroi"]["hp_max"] == 104  # 100 + 4 de Vigor


def test_pericias_sugeridas_pelo_mestre_e_xp_ao_concluir(heroi):
    j = heroi
    r = j.rascunho(titulo="Treino A", est=1, dif=1, pericias=["Atletismo"])
    ps = {p["nome"]: p for p in C.pericias(j.b, j.cfg)}
    assert ps["Atletismo"]["estado"] == "sugerida"
    j.aprovar(r["id"])
    ps = {p["nome"]: p for p in C.pericias(j.b, j.cfg)}
    assert ps["Atletismo"]["estado"] == "aprovada"
    res = j.concluir_quest(r["id"])
    assert res["xp"] > 0  # sem pomodoro dá 35%
    ps = {p["nome"]: p for p in C.pericias(j.b, j.cfg)}
    assert ps["Atletismo"]["xp"] >= 10


def test_classes_novas_polimata_e_monge(jogo):
    jogo.criar_heroi("JC", "monge")
    q = jogo.nova_quest(titulo="Treino de perna", est=2, dif=2, pericias=["Musculação"])
    res = jogo.concluir_quest(q["id"])
    # Monge dá +30% XP em quest só confirmada (41 * 0.35 * 1.30 = 18.655 -> 19)
    assert res["xp"] == 19
