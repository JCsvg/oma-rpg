"""O motor com relógio falso: pomodoro, pausa, combo, HP, MP, desmaio, overtraining, dia, quests, skills, loja e
persistência. Nenhum teste espera 25 minutos de verdade."""

import pytest

from oma_rpg.nucleo import consultas as C
from oma_rpg.nucleo.jogo import ORIGENS_XP, ErroJogo
from tests.conftest import momento, pomodoro


def h(j):
    return j.heroi()


def test_pomodoro_conclui_no_relogio_e_pausa_da_mana(heroi):
    j = heroi
    j.b.x("UPDATE heroi SET mp = 30")
    j.iniciar()
    j.rel.avancar(24 * 60 + 59)
    j.tick()
    assert j.atual()["fase"] == "foco"
    j.rel.avancar(1)
    j.tick()
    assert j.atual()["fase"] == "pausa"
    assert h(j)["xp"] == 24 and h(j)["bits"] == 6
    evs = j.soltar_eventos()
    assert any(e["evento"] == "pomodoro_fim" and e["xp"] == 24 for e in evs)
    assert j.notas and "Pomodoro 1" in j.notas[-1][0]
    j.rel.avancar(5 * 60)
    j.tick()
    assert j.atual()["fase"] == "parado"
    assert h(j)["mp"] == 36  # +6 da pausa respeitada


def test_pular_pausa_nao_da_mana(heroi):
    j = heroi
    j.b.x("UPDATE heroi SET mp = 30")
    pomodoro(j, pausa=False)
    j.pular_pausa()
    assert h(j)["mp"] == 30 and j.atual()["fase"] == "parado"


def test_combo_sobe_a_cada_pomodoro_e_pausa_longa_no_quarto(heroi):
    j = heroi
    xps = []
    for _ in range(4):
        antes = h(j)["xp_total"]
        pomodoro(j, pausa=False)
        xps.append(h(j)["xp_total"] - antes)
        if _ < 3:
            assert j.atual()["fase"] == "pausa"
            j.rel.avancar(5 * 60)
            j.tick()
    assert xps == [24, 26, 29, 31]
    assert j.atual()["fase"] == "longa" and j.atual()["duracao"] == 15 * 60
    assert C.combo_de(j.cfg, h(j), j.P(), j.agora()) == 1.4


def test_combo_zera_no_outro_dia(heroi):
    j = heroi
    pomodoro(j)
    pomodoro(j)
    j.rel.t = momento("2026-11-19", 9, 0)
    j.tick()
    antes = h(j)["xp_total"]
    pomodoro(j)
    assert h(j)["xp_total"] - antes == 24


def test_abandonar_antes_de_5_min_nao_custa_nada(heroi):
    j = heroi
    pomodoro(j)
    j.iniciar()
    j.rel.avancar(4 * 60)
    r = j.abandonar()
    assert r["livre"] and r["hp"] == 0
    assert h(j)["hp"] == 100 and h(j)["seguidos"] == 1


def test_abandonar_depois_custa_8_hp_e_zera_o_combo(heroi):
    j = heroi
    pomodoro(j)
    j.iniciar()
    j.rel.avancar(6 * 60)
    r = j.abandonar()
    assert r["hp"] == 8 and h(j)["hp"] == 92 and h(j)["seguidos"] == 0
    p = j.b.um("SELECT * FROM pomodoros WHERE estado = 'abandonado'")
    assert p["minutos"] == 6


def test_pausar_congela_o_timer(heroi):
    j = heroi
    j.iniciar()
    j.rel.avancar(10 * 60)
    j.pausar()
    j.rel.avancar(20 * 60)
    j.tick()
    assert j.atual()["fase"] == "foco"
    assert C.restante(j.atual(), j.agora()) == 15 * 60
    j.pausar()
    j.rel.avancar(15 * 60)
    j.tick()
    assert j.atual()["fase"] == "pausa"


def test_pausado_demais_guarda_sozinho(heroi):
    j = heroi
    j.iniciar()
    j.rel.avancar(7 * 60)
    j.pausar()
    j.rel.avancar(31 * 60)
    j.tick()
    a = j.atual()
    assert a["fase"] == "parado" and a["guardado_seg"] == 7 * 60
    j.iniciar()
    assert C.restante(j.atual(), j.agora()) == 18 * 60  # retoma de onde parou


def test_desmaio_perde_bits_e_streak_e_acorda_com_metade(heroi):
    j = heroi
    pomodoro(j)
    j.b.x("UPDATE heroi SET hp = 8, bits = 1284")
    j.iniciar()
    j.rel.avancar(6 * 60)
    j.abandonar()
    a = j.atual()
    assert a["fase"] == "desmaio"
    assert h(j)["hp"] == 0 and h(j)["bits"] == 1284 - 128 and h(j)["streak"] == 0
    evs = j.soltar_eventos()
    assert any(e["evento"] == "desmaio" and e["bits"] == 128 for e in evs)
    with pytest.raises(ErroJogo):
        j.iniciar()
    with pytest.raises(ErroJogo):
        j.acordar()
    j.rel.avancar(15 * 60)
    j.tick()
    assert j.atual()["fase"] == "parado" and h(j)["hp"] == 50


def test_desmaio_com_backup_guarda_o_streak_de_ontem(heroi):
    j = heroi
    j.b.x("UPDATE heroi SET pontos = 5")
    j.aprender("sudo")
    j.aprender("backup")
    for dia in ("2026-11-16", "2026-11-17", "2026-11-18"):
        j.rel.t = momento(dia, 9, 0)
        j.tick()
        pomodoro(j)
    assert C.streak_atual(h(j), "2026-11-18") == 3
    j.b.x("UPDATE heroi SET hp = 5")
    j.iniciar()
    j.rel.avancar(6 * 60)
    j.abandonar()
    assert j.atual()["fase"] == "desmaio" and h(j)["streak"] == 2
    j.rel.t = momento("2026-11-19", 9, 0)
    j.tick()
    pomodoro(j)
    assert C.streak_atual(h(j), "2026-11-19") == 3


def test_overtraining_depois_do_teto(heroi):
    j = heroi
    j.b.x("UPDATE heroi SET hp = 100")
    for _ in range(10):
        pomodoro(j)
    j.b.x("UPDATE heroi SET seguidos = 0")
    antes = h(j)["xp_total"]
    pomodoro(j)
    assert h(j)["xp_total"] - antes == 12
    assert "overtraining" in j.b.um("SELECT texto FROM ganhos WHERE origem = 'pomodoro' ORDER BY id DESC")[0]


def test_daily_vencida_custa_8_hp_na_virada(heroi):
    j = heroi
    j.nova_quest(titulo="Revisar flashcards", materia="Redes", est=1, dif=1, tipo="daily")
    j.b.x("UPDATE heroi SET hp = 50")
    j.rel.t = momento("2026-11-19", 0, 0, 5)
    j.tick()
    assert h(j)["hp"] == 50 - 8 + 10  # a noite de sono cura 10 depois
    assert j.b.um("SELECT * FROM ganhos WHERE origem = 'daily'")["hp"] == -8


def test_daily_feita_nao_custa_e_sudo_segura(heroi):
    j = heroi
    q = j.nova_quest(titulo="Inglês", materia="Inglês", est=1, dif=1, tipo="daily")
    pomodoro(j, quest=q["id"])
    r = j.concluir_quest(q["id"], "ouvi o podcast")
    assert r["xp"] == 14
    j.b.x("UPDATE heroi SET hp = 50, pontos = 1, mp = 60")
    j.aprender("sudo")
    j.rel.t = momento("2026-11-19", 8, 0)
    j.tick()
    assert h(j)["hp"] == 60  # feita ontem: só a cura do sono
    j.usar_skill("sudo")
    j.rel.t = momento("2026-11-20", 8, 0)
    j.tick()
    assert h(j)["hp"] == 70  # não fez hoje, mas o sudo segurou
    assert j.b.um("SELECT 1 FROM ganhos WHERE origem = 'escudo'") is not None


def test_sobe_de_nivel_com_ponto_hp_e_bits(heroi):
    j = heroi
    j.b.x("UPDATE heroi SET xp = 290, hp = 50")
    pomodoro(j, pausa=False)
    x = h(j)
    assert x["nivel"] == 2 and x["xp"] == 290 + 24 - 300 and x["pontos"] == 1
    assert x["hp"] == 60 and x["bits"] == 6 + 25
    assert any(e["evento"] == "nivel" and e["nivel"] == 2 for e in j.soltar_eventos())


def test_quest_so_vale_com_pomodoro(heroi):
    j = heroi
    q = j.nova_quest(titulo="Lista 4", materia="Compiladores", est=2, dif=2, arco="Compiladores")
    assert q["xp_previsto"] == 41 and q["bits_previstos"] == 10
    r = j.concluir_quest(q["id"])
    assert r["xp"] == 0 and h(j)["xp_total"] == 0
    q2 = j.nova_quest(titulo="Lista 5", materia="Compiladores", est=2, dif=2)
    pomodoro(j, quest=q2["id"])
    pomodoro(j, quest=q2["id"])
    antes = h(j)["xp_total"]
    r = j.concluir_quest(q2["id"])
    assert r["xp"] == 41 and r["cheio"] and h(j)["xp_total"] - antes == 41


def test_chefe_do_arco_quando_todas_feitas(heroi):
    j = heroi
    j.novo_arco("Redes", "Prova de Redes", "2026-11-26")
    a = j.nova_quest(titulo="A", materia="Redes", est=1, dif=1, arco="Redes")
    b = j.nova_quest(titulo="B", materia="Redes", est=1, dif=1, arco="Redes")
    pomodoro(j, quest=a["id"])
    j.concluir_quest(a["id"])
    assert j.b.um("SELECT bonus_em FROM arcos")[0] is None
    pomodoro(j, quest=b["id"])
    j.concluir_quest(b["id"])
    assert j.b.um("SELECT bonus_em FROM arcos")[0] is not None
    g = j.b.um("SELECT * FROM ganhos WHERE origem = 'arco'")
    assert g["xp"] == 14 and "Prova de Redes" in g["texto"]


def test_rascunho_aprovado_e_editado(heroi):
    j = heroi
    r = j.rascunho(titulo="Seção 2.1 do TCC", materia="TCC", est=3, dif=3, arco="TCC", prazo="2026-11-20",
                   porque="a parte mais longa")
    assert r["xp_previsto"] == 77 and r["bits_previstos"] == 19 and r["estado"] == "rascunho"
    assert C.fila(j.b, j.cfg, j.hoje()) == []
    r = j.editar_rascunho(id=r["id"], est=2)
    assert r["xp_previsto"] == 51  # 17 × 2 × 1,5
    j.aprovar(r["id"])
    assert [q["titulo"] for q in C.fila(j.b, j.cfg, j.hoje())] == ["Seção 2.1 do TCC"]
    assert j.b.um("SELECT nome FROM arcos")[0] == "TCC"
    with pytest.raises(ErroJogo):
        j.editar_rascunho(id=r["id"], est=1)  # aprovado: o Mestre não mexe mais


def test_reestimar_quest_comecada_custa_bits(heroi):
    j = heroi
    q = j.nova_quest(titulo="X", est=2, dif=2)
    pomodoro(j, quest=q["id"])
    j.b.x("UPDATE heroi SET bits = 100")
    j.editar_quest(id=q["id"], est=3)
    assert h(j)["bits"] == 80
    j.b.x("INSERT INTO mochila (item, qtd) VALUES ('pergaminho', 1)")
    j.usar_item("pergaminho")
    j.editar_quest(id=q["id"], est=4)
    assert h(j)["bits"] == 80


def test_fila_reordena(heroi):
    j = heroi
    ids = [j.nova_quest(titulo=t, est=1, dif=1)["id"] for t in "ABC"]
    j.mover_fila(ids[2], -2)
    assert [q["titulo"] for q in C.fila(j.b, j.cfg, j.hoje())] == ["C", "A", "B"]
    j.ordenar_fila([ids[1], ids[0], ids[2]])
    assert [q["titulo"] for q in C.fila(j.b, j.cfg, j.hoje())] == ["B", "A", "C"]
    r = j.iniciar()
    assert r["quest_id"] == ids[1]  # sem quest, começa pela primeira da fila


def test_skills_requisito_custo_e_respec(heroi):
    j = heroi
    j.b.x("UPDATE heroi SET pontos = 2, bits = 200")
    with pytest.raises(ErroJogo):
        j.aprender("hotfix")  # precisa do git stash antes
    j.aprender("git_stash")
    j.aprender("hotfix")
    assert h(j)["pontos"] == 0
    with pytest.raises(ErroJogo):
        j.aprender("sudo")
    with pytest.raises(ErroJogo):
        j.respec("git_stash")  # o hotfix depende dele
    j.respec("hotfix")
    assert h(j)["pontos"] == 1 and h(j)["bits"] == 50
    with pytest.raises(ErroJogo):
        j.aprender("o_mago")  # outra classe


def test_ultima_do_ramo_custa_2_pontos(heroi):
    j = heroi
    j.b.x("UPDATE heroi SET pontos = 6")
    for s in ("sudo", "backup", "rollback", "ci_verde"):
        j.aprender(s)
    j.b.x("UPDATE heroi SET pontos = 1")
    with pytest.raises(ErroJogo):
        j.aprender("alta_disponibilidade")
    j.b.x("UPDATE heroi SET pontos = 2")
    j.aprender("alta_disponibilidade")
    assert C.hp_max(j.cfg, h(j), j.P()) == 120


def test_hotfix_vale_40_por_cento_e_uma_vez_por_dia(heroi):
    j = heroi
    j.b.x("UPDATE heroi SET pontos = 2, mp = 60")
    j.aprender("git_stash")
    j.aprender("hotfix")
    j.usar_skill("hotfix")
    assert h(j)["mp"] == 56
    with pytest.raises(ErroJogo):
        j.usar_skill("hotfix")
    antes = h(j)["xp_total"]
    pomodoro(j)
    assert h(j)["xp_total"] - antes == round(24 * 1.4)


def test_git_stash_guarda_sem_perder_combo(heroi):
    j = heroi
    j.b.x("UPDATE heroi SET pontos = 1, mp = 60")
    j.aprender("git_stash")
    pomodoro(j)
    pomodoro(j)
    j.iniciar()
    j.rel.avancar(10 * 60)
    j.usar_skill("git_stash")
    assert h(j)["seguidos"] == 2 and h(j)["hp"] == 100 and j.atual()["guardado_seg"] == 600
    j.iniciar()
    j.rel.avancar(15 * 60)
    j.tick()
    assert j.b.um("SELECT combo FROM pomodoros ORDER BY id DESC")[0] == 1.2


def test_rollback_devolve_a_ultima_perda(heroi):
    j = heroi
    j.b.x("UPDATE heroi SET pontos = 3, mp = 60")
    for s in ("sudo", "backup", "rollback"):
        j.aprender(s)
    j.iniciar()
    j.rel.avancar(6 * 60)
    j.abandonar()
    assert h(j)["hp"] == 92
    j.usar_skill("rollback")
    assert h(j)["hp"] == 100 and h(j)["mp"] == 50


def test_loja_compra_usa_e_equipa(heroi):
    j = heroi
    j.b.x("UPDATE heroi SET bits = 300, hp = 50, mp = 10")
    with pytest.raises(ErroJogo):
        j.comprar("elixir")
    j.comprar("pocao_hp", 2)
    assert h(j)["bits"] == 140 and C.mochila(j.b)["pocao_hp"] == 2
    j.usar_item("pocao_hp")
    assert h(j)["hp"] == 80
    j.comprar("titulo_cafe")
    with pytest.raises(ErroJogo):
        j.comprar("titulo_cafe")
    j.equipar("titulo_cafe")
    assert C.titulo(j.cfg, h(j)) == "Café com Leite"
    j.equipar("titulo_cafe")
    assert C.titulo(j.cfg, h(j)) == "Estagiário"


def test_bilhete_de_caixa_da_bits_ou_cosmetico(heroi):
    j = heroi
    j.b.x("INSERT INTO mochila (item, qtd) VALUES ('bilhete', 5)")
    for _ in range(5):
        j.usar_item("bilhete")
    cosmeticos = [i for i in C.posses(j.b) if j.cfg.item(i)["categoria"] == "cosmetico"]
    assert h(j)["bits"] > 0 or cosmeticos


def test_juros_do_empreendedor_na_meta(jogo):
    j = jogo
    j.criar_heroi("ana", "empreendedor")
    j.b.x("UPDATE heroi SET bits = 1000")
    for _ in range(6):
        pomodoro(j)
    antes = h(j)["bits"]
    j.rel.t = momento("2026-11-19", 8, 0)
    j.tick()
    assert h(j)["bits"] - antes == 10  # 1% de ~1000, até 50


def test_gamer_combo_vai_a_2_e_quebra_com_intervalo(jogo):
    j = jogo
    j.criar_heroi("leo", "gamer")
    j.b.x("UPDATE heroi SET seguidos = 9, seguidos_dia = ?, ultimo_fim = ?", (j.hoje(), j.agora()))
    assert C.combo_de(j.cfg, h(j), j.P(), j.agora()) == 1.9
    j.b.x("UPDATE heroi SET seguidos = 12")
    assert C.combo_de(j.cfg, h(j), j.P(), j.agora()) == 2.0
    assert C.combo_de(j.cfg, h(j), j.P(), j.agora() + 46 * 60) == 1.0


def test_otaku_virada_com_hp_baixo(jogo):
    j = jogo
    j.criar_heroi("mika", "otaku")
    j.b.x("UPDATE heroi SET hp = 20")
    pomodoro(j)
    assert j.b.um("SELECT xp FROM pomodoros")[0] == 48


def test_mistico_carta_do_dia_muda_os_bits(jogo):
    j = jogo
    j.criar_heroi("luz", "mistico")
    buff, debuff, _ = C.carta_do_dia(j.b, j.cfg, j.hoje())
    assert j.cfg["cartas"][buff]["tipo"] == "buff" and j.cfg["cartas"][debuff]["tipo"] == "debuff"
    j.revelar_carta()
    assert C.carta_do_dia(j.b, j.cfg, j.hoje())[2] is True


def test_trocar_de_classe_perde_os_pontos_gastos(heroi):
    j = heroi
    j.b.x("UPDATE heroi SET pontos = 3")
    j.aprender("git_stash")
    j.aprender("sudo")
    r = j.trocar_classe("rato")
    assert r["pontos_perdidos"] == 2 and h(j)["pontos"] == 1 and h(j)["classe"] == "rato"
    assert j.b.todos("SELECT * FROM skills") == []


def test_streak_e_congelar(heroi):
    j = heroi
    for dia in ("2026-11-16", "2026-11-17"):
        j.rel.t = momento(dia, 9, 0)
        j.tick()
        pomodoro(j)
    j.b.x("INSERT INTO mochila (item, qtd) VALUES ('congelar', 1)")
    j.usar_item("congelar")
    j.rel.t = momento("2026-11-19", 9, 0)  # 18 sem pomodoro
    j.tick()
    pomodoro(j)
    assert C.streak_atual(h(j), "2026-11-19") == 3
    j.rel.t = momento("2026-11-21", 9, 0)  # 20 sem pomodoro e sem congelar
    j.tick()
    assert C.streak_atual(h(j), "2026-11-21") == 0


def test_persistencia_retoma_o_pomodoro_depois_de_reabrir(tmp_path, cfg, relogio):
    from oma_rpg.nucleo.banco import Banco
    from oma_rpg.nucleo.jogo import Jogo
    arq = tmp_path / "rpg.sqlite3"
    cfg["conquistas"] = {}
    j = Jogo(Banco(arq), cfg, relogio)
    j.criar_heroi("yahiro", "programa")
    q = j.nova_quest(titulo="Ler: inferência de tipos", materia="Compiladores", est=2, dif=2)
    j.iniciar(q["id"])
    relogio.avancar(10 * 60)
    j.b.fechar()
    # o serviço caiu; volta 17 minutos depois (o pomodoro acabou no meio, a pausa ainda corre)
    relogio.avancar(17 * 60)
    j2 = Jogo(Banco(arq), cfg, relogio)
    assert j2.atual()["fase"] == "foco" and j2.atual()["quest_id"] == q["id"]
    j2.tick()
    assert j2.heroi()["xp"] == 24 and j2.atual()["fase"] == "pausa"
    assert C.quest_feitos(j2.b, q["id"]) == 1
    j2.b.fechar()
    leitor = Banco(arq, leitura=True)
    assert C.heroi(leitor)["xp"] == 24
    with pytest.raises(Exception):
        leitor.x("UPDATE heroi SET xp = 9999")
    leitor.fechar()


def test_pomodoro_de_ontem_conta_para_ontem(heroi):
    """Serviço parado durante a meia-noite: o pomodoro que acabou às 23:50 entra no dia certo."""
    j = heroi
    j.rel.t = momento("2026-11-18", 23, 25)
    j.iniciar()
    j.rel.t = momento("2026-11-19", 7, 0)
    j.tick()
    assert j.b.um("SELECT dia FROM pomodoros")[0] == "2026-11-18"
    assert h(j)["streak_dia"] == "2026-11-18"


def test_livro_bate_com_o_heroi_e_so_tem_origens_de_xp(heroi):
    """Invariante: todo XP do herói está no livro, com origem pomodoro, commit, quest, arco ou conquista."""
    j = heroi
    q = j.nova_quest(titulo="Q", est=2, dif=3, arco="Arco")
    for _ in range(3):
        pomodoro(j, quest=q["id"])
    j.concluir_quest(q["id"])
    j.b.x("UPDATE heroi SET bits = bits + 500")  # (teste) dinheiro para a loja
    j.comprar("cafe")
    j.usar_item("cafe")
    x = h(j)
    assert x["xp_total"] == j.b.escalar("SELECT SUM(xp) FROM ganhos")
    origens = {r[0] for r in j.b.todos("SELECT DISTINCT origem FROM ganhos WHERE xp > 0")}
    assert origens and origens <= ORIGENS_XP


def test_ganho_recusa_xp_de_origem_errada(heroi):
    with pytest.raises(PermissionError):
        heroi._ganho("loja", "trapaça", xp=500)
    with pytest.raises(PermissionError):
        heroi._ganho("skill", "trapaça", bits=500)


def test_conquistas_dao_xp_de_pomodoro_e_streak(banco, relogio):
    from oma_rpg.config import Config
    from oma_rpg.nucleo.jogo import Jogo
    j = Jogo(banco, Config.carregar(usar_usuario=False), relogio)
    j.criar_heroi("yahiro", "programa")
    pomodoro(j)
    assert set(C.conquistas_feitas(j.b)) == {"primeiro_pomodoro"}
    assert j.heroi()["xp_total"] == 24 + 10
    assert j.b.um("SELECT origem FROM ganhos WHERE texto LIKE 'conquista%'")[0] == "conquista"
