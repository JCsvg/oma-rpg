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
        "hobbies": "jogos, leitura, corrida",
        "estilo_vida": "ativo",
        "altura_cm": 175,
        "peso_kg": 72,
        "sono": "7h regular",
        "treina": True,
        "treino_tipo": "musculação",
        "treino_freq": "5x/semana",
        "tempo_estudo": "3h/dia",
        "dificuldade_estudo": "manter atenção em teoria pesada",
        "dificuldade_metas": "procrastino ao começar tarefas grandes",
        "atencao": "TDAH / distração fácil",
        "estilo_estudo": "prática e exercícios",
        "rotina": "manhã estágio, tarde estudo, noite treino",
        "pericias_iniciais": "Inglês",
    })
    pers = res["personalidade"]
    assert sum(pers.values()) == 11  # base 6 + 5 pts distribuídos
    assert all(0 <= v <= 3 for v in pers.values())  # teto 3 sem classe
    assert sum(res["atributos"].values()) == 12  # +1 +1 -1 da classe
    assert res["atributos"]["int"] >= 3
    assert res["atributos"]["vig"] >= 2
    assert len(res["pericias"]) <= 5
    assert "Inglês" in res["pericias"]
    assert "Programação" in res["pericias"]
    # Quests salvas continuam lá
    assert len(C.quests(jogo.b, jogo.cfg, jogo.hoje(), "aberta")) == 1
    assert C.perfil(jogo.b)["ocupacao"].startswith("Ciência")
    assert C.perfil(jogo.b)["entrevista_estado"] == "pendente"


def test_personalidade_sedentario_tira_menos_um_e_classe_aplica_penalidade(jogo):
    res = jogo.criar_heroi("Ana", "empreendedor", perfil={
        "ocupacao": "Pesquisa em algoritmos e matemática",
        "estilo_vida": "sedentário",
        "sono": "5h irregular",
        "treina": False,
        "tempo_estudo": "5h/dia",
        "atencao": "alta",
        "estilo_estudo": "leitura e resumos",
    })
    pers = res["personalidade"]
    assert sum(pers.values()) == 11
    assert any(v == 0 for v in pers.values())  # tirou -1 de atributo fraco para reforçar forte
    assert pers["int"] == 3
    assert pers["vig"] == 0
    # empreendedor dá -1 Vig: 0 - 1 = -1 -> -8 HP máx (simétrico)
    assert res["atributos"]["vig"] == -1
    assert C.status(jogo.b, jogo.cfg, jogo.agora())["atributos"]["bonus"]["hp_max"] == -8


def test_entrevista_mestre_salva_estrategia_e_proposta_aprovada_pelo_jogador(jogo):
    from oma_rpg.comandos import executar
    from oma_rpg.mestre import montar_prompt_entrevista

    jogo.criar_heroi("JC", "programa", perfil={
        "ocupacao": "Ciência da Computação",
        "hobbies": "RPG e leitura",
        "tempo_estudo": "3h/dia",
        "dificuldade_estudo": "teoria abstrata",
        "dificuldade_metas": "subestimo prazos",
        "pericias_iniciais": "Python, Inglês",
    })
    st = C.status(jogo.b, jogo.cfg, jogo.agora())
    prompt = montar_prompt_entrevista(st)
    assert "2º questionário" in prompt and "RPG e leitura" in prompt

    r = executar(jogo, "salvar_entrevista", {
        "estrategia": "Usar método Feynman em blocos de 25m e revisar erros ao final.",
        "atributos": {"for": 0, "agi": 2, "vig": 2, "int": 3, "con": 3, "pre": 1},
        "pericias": ["Python", "Inglês", "Teoria da Computação", "Escrita", "Atletismo"],
    }, "mestre")
    assert r["entrevista_estado"] == "concluida"
    # Ainda não mudou herói antes do jogador aprovar
    assert jogo.heroi()["attr_con"] != 3

    ap = executar(jogo, "aplicar_proposta_perfil", {}, "jogador")
    # programa dá +1 Int, +1 Agi, -1 Pre
    assert ap["atributos"] == {"for": 0, "agi": 3, "vig": 2, "int": 4, "con": 3, "pre": 0}
    assert len(ap["pericias"]) == 5
    assert C.perfil(jogo.b)["proposta_mestre"] == ""
    assert "Feynman" in C.perfil(jogo.b)["perfil_mestre"]


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
    # Monge dá +30% XP em quest só confirmada + 3% de For (+1 da classe) -> 19
    assert res["xp"] == 19
    # Todas as 8 classes têm +1 em 2 atributos e -1 em 1 atributo (soma líquida = +1)
    for cid in jogo.cfg.classes_ordem():
        mods = list(jogo.cfg.classe_atributos(cid).values())
        assert sorted(mods) == [-1, 0, 0, 0, 1, 1], cid
