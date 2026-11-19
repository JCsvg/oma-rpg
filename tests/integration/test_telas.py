"""Cada tela do design com o pilot do Textual, sobre o --demo (motor no mesmo processo, relógio parado)."""

from rich.text import Text

from oma_rpg.nucleo import consultas as C
from tests.conftest import esperar, janela, pronto

G = (180, 48)


def texto(w) -> str:
    r = w.render()
    return r.plain if isinstance(r, Text) else str(r)


def todo_texto(app) -> str:
    from oma_rpg.ui.widgets import Pintado
    return "\n".join(texto(p) for p in app.query(Pintado) if app._visivel(p))


def heroi(app):
    return C.heroi(app.b)


async def abrir(app, pilot, pagina, tam=G):
    await pronto(app, pilot)
    app.abrir_pagina(pagina, foco=True)
    await pilot.pause(0.35)


# ---------------------------------------------------------------- 2 · painel
async def test_painel_mostra_heroi_hoje_calor_atividade_e_mestre(app_pausa):
    app = app_pausa
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "painel")
        t = todo_texto(app)
        for trecho in ("yahiro", "Garoto de Programa", "Dev Júnior · nível 7", "12 dias seguidos", "72 / 100", "34 / 60",
                       "1.240 / 1.800", "combo x1.3", "faltam 560 para o nível 8", "pausa curta de 5 min em andamento",
                       "3 rascunhos do Mestre esperam aprovação", "pomodoros em 24 semanas", "por matéria", "Sua semana está pesada",
                       "10 dias seguidos"):
            assert trecho in t, trecho
        assert "meta 3 de 6 pomodoros" in str(app.query_one("#hoje").border_title)
        hoje = [q["titulo"] for q in app.query_one("#hoje-lista").itens]
        assert hoje[:2] == ["Lista 4 de Compiladores", "Ler: inferência de tipos (Hindley-Milner)"]
        ativ = [r["texto"] for r in app.query_one("#atividade-lista").itens]
        assert "pomodoro 3 concluído" in ativ and "combo subiu para x1.3" in ativ


async def test_painel_f_comeca_o_pomodoro_na_quest_e_abre_o_foco(app_pausa):
    app = app_pausa
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "painel")
        app.focar_janela("hoje")
        await pilot.press("down")
        await pilot.press("f")
        assert await esperar(pilot, lambda: app.pagina_nome == "foco")
        assert C.atual(app.b)["fase"] == "foco"
        q = app.b.um("SELECT titulo FROM quests WHERE id = ?", (C.atual(app.b)["quest_id"],))[0]
        assert q.startswith("Ler: inferência")


async def test_painel_n_abre_nova_quest_e_t_a_taverna(app_pausa):
    app = app_pausa
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "painel")
        await pilot.press("n")
        await pilot.pause(0.2)
        assert type(app.screen).__name__ == "EditarQuest"
        await pilot.press(*"Revisar camada de enlace")
        await pilot.press("tab")
        await pilot.press(*"Redes", "tab", "backspace", "2", "tab", "backspace", "1", "enter")
        assert await esperar(pilot, lambda: len(app.screen_stack) == 1)
        q = app.b.um("SELECT * FROM quests WHERE titulo = 'Revisar camada de enlace'")
        assert q["materia"] == "Redes" and q["est"] == 2 and q["dif"] == 1 and q["origem"] == "jogador"
        await pilot.press("t")
        assert await esperar(pilot, lambda: app.pagina_nome == "taverna")


# ---------------------------------------------------------------- 3 · foco
async def test_foco_mostra_timer_previsao_e_commits(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "foco")
        t = todo_texto(app)
        assert "6:18 decorridos" in t and "18:42 restantes" in t
        assert "+31" in t and "24 base x combo 1.3" in t and "x1.3 → x1.4" in t
        assert "pomodoro 4 de 4" in str(app.query_one("#foco").border_title)
        assert "Ler: inferência de tipos" in t
        commits = [it[1]["hash"][:7] for it in app.query_one("#neste-lista").itens if it[0] == "commit"]
        assert commits == ["e82b7d0", "7c1d4aa"]
        ativas = app.query_one("#ativas-lista").itens
        assert ativas == ["git_stash", "hotfix", "sudo", "dev_null"]
        assert "foco 18:42" in texto(app.query_one("#busca"))


async def test_foco_espaco_pausa_e_continua(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "foco")
        await pilot.press("space")
        assert await esperar(pilot, lambda: C.atual(app.b)["pausado_em"] is not None)
        await pilot.press("space")
        assert await esperar(pilot, lambda: C.atual(app.b)["pausado_em"] is None)


async def test_foco_abandonar_pergunta_e_custa_8_hp(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "foco")
        await pilot.press("x")
        await pilot.pause(0.2)
        assert type(app.screen).__name__ == "Abandonar"
        assert "abandonar custa 8 HP e zera o combo x1.3" in todo_texto(app) or "8 HP" in str(app.screen.query("Static").first().render())
        await pilot.press("x")
        assert await esperar(pilot, lambda: C.atual(app.b)["fase"] == "parado")
        assert heroi(app)["hp"] == 64 and heroi(app)["seguidos"] == 0


async def test_foco_s_no_dialogo_guarda_com_git_stash(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "foco")
        await pilot.press("x")
        await pilot.pause(0.2)
        await pilot.press("s")
        assert await esperar(pilot, lambda: C.atual(app.b)["guardado_seg"] > 0)
        assert heroi(app)["hp"] == 72 and heroi(app)["mp"] == 28 and heroi(app)["seguidos"] == 3


async def test_foco_1_a_4_usam_as_skills(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "foco")
        await pilot.press("2")  # hotfix, 4 mana
        assert await esperar(pilot, lambda: heroi(app)["mp"] == 30)
        await pilot.press("3")  # sudo já usada hoje às 08:52
        await pilot.pause(0.2)
        assert heroi(app)["mp"] == 30
        assert any("já usada hoje" in a.texto.plain for a in app.query("Aviso"))


async def test_foco_o_pomodoro_termina_no_relogio(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "foco")
        app.relogio.avancar(18 * 60 + 43)
        app.cliente.tick()
        assert await esperar(pilot, lambda: C.atual(app.b)["fase"] == "longa")
        assert any("+31 xp" in a.texto.plain for a in app.query("Aviso"))


async def test_foco_alt_seta_reordena_a_fila(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "foco")
        app.focar_janela("fila")
        await pilot.pause(0.1)
        await pilot.press("down")
        antes = [q["titulo"] for q in C.fila(app.b, app.cfg, app.hoje())]
        await pilot.press("alt+down")
        assert await esperar(pilot, lambda: [q["titulo"] for q in C.fila(app.b, app.cfg, app.hoje())] != antes)
        depois = [q["titulo"] for q in C.fila(app.b, app.cfg, app.hoje())]
        assert depois[1] == antes[2] and depois[2] == antes[1]


async def test_foco_n_anota(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "foco")
        await pilot.press("n")
        await pilot.pause(0.2)
        await pilot.press(*"revisar o let", "enter")
        assert await esperar(pilot, lambda: app.b.um("SELECT 1 FROM notas WHERE texto = 'revisar o let'") is not None)


# ---------------------------------------------------------------- 4 · quests
async def test_quests_arcos_tabela_detalhe_e_rascunhos(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "quests")
        arcos = [a["nome"] for a in app.query_one("#arcos-lista").itens]
        assert arcos[:3] == ["Compiladores", "Redes", "TCC"]
        t = todo_texto(app)
        assert "Prova de Compiladores" in t and "bônus:" in t
        assert str(app.query_one("#quests").border_title).find("Compiladores") > 0
        detalhe = "\n".join(it[1].plain if it[0] == "txt" else it[2]["texto"] for it in app.query_one("#quest-detalhe").itens)
        assert "tabela do jogo" in detalhe and "41 xp" in detalhe and "ler o capítulo 4" in detalhe and "a3f9c1e" in detalhe
        assert [q["id"] for q in app.query_one("#r-lista").itens] == [14, 15, 16]


async def test_quests_alt_seta_troca_a_aba(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "quests")
        await pilot.press("alt+right")
        await pilot.pause(0.2)
        assert app.pagina.aba == "rascunhos"
        await pilot.press("alt+right")
        await pilot.pause(0.2)
        assert app.pagina.aba == "feitas"
        assert all(q["estado"] == "feita" for q in app.query_one("#q-lista").itens)


async def test_quests_a_aprova_o_rascunho(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "quests")
        app.focar_janela("rascunhos")
        await pilot.pause(0.1)
        xp = heroi(app)["xp_total"]
        await pilot.press("a")
        assert await esperar(pilot, lambda: app.b.um("SELECT estado FROM quests WHERE id = 14")[0] == "aberta")
        assert heroi(app)["xp_total"] == xp  # aprovar não dá XP


async def test_quests_espaco_abre_o_check_in(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "quests")
        await pilot.press("space")
        await pilot.pause(0.2)
        assert type(app.screen).__name__ == "Concluir"
        await pilot.press(*"li o capítulo 4", "enter")
        assert await esperar(pilot, lambda: app.b.um("SELECT estado FROM quests WHERE titulo LIKE 'Ler: inf%'")[0] == "feita")
        q = app.b.um("SELECT xp_ganho, nota FROM quests WHERE titulo LIKE 'Ler: inf%'")
        assert q["nota"] == "li o capítulo 4" and q["xp_ganho"] == 21  # 1 de 2 pomodoros: metade de 41


async def test_quests_e_abre_aprovacao_com_a_conta_do_jogo(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "quests")
        app.focar_janela("rascunhos")
        await pilot.press("e")
        await pilot.pause(0.3)
        assert type(app.screen).__name__ == "EditarQuest"
        assert "77 · 19" in texto(app.screen.query_one("#conta"))
        app.screen.query_one("#c-est").value = "2"
        await pilot.pause(0.1)
        assert "51 · 13" in texto(app.screen.query_one("#conta"))
        app.screen.query_one("#c-titulo").focus()
        await pilot.press("enter")
        assert await esperar(pilot, lambda: app.b.um("SELECT estado, est FROM quests WHERE id = 14")[:] == ("aberta", 2))


# ---------------------------------------------------------------- 5 e 6 · skills e classes
async def test_skills_arvore_e_aprender(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "skills")
        t = texto(app.query_one("#arvore-grade"))
        for n in ("git stash", "rollback", "fork bomb", "escala horizontal", "root", "Backend", "DevOps", "Hack"):
            assert n in t
        assert "2 pontos livres" in str(app.query_one("#arvore").border_title)
        assert app.query_one("#arvore-grade").sid() == "cache_hit"
        await pilot.press("enter")
        assert await esperar(pilot, lambda: app.b.um("SELECT 1 FROM skills WHERE skill = 'cache_hit'") is not None)
        assert heroi(app)["pontos"] == 1
        await pilot.press("right")
        assert app.query_one("#arvore-grade").sid() == "rollback"
        assert "git revert na própria vida" in texto(app.query_one("#skill-corpo"))


async def test_skills_alt_seta_mostra_outra_classe_sem_aprender(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "skills")
        await pilot.press("alt+left")
        await pilot.pause(0.2)
        assert app.pagina.classe == "mistico" and "O Mago" in texto(app.query_one("#arvore-grade"))
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert heroi(app)["pontos"] == 2


async def test_skills_konami_do_gamer(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "skills")
        app.pagina.ver_classe("gamer")
        await pilot.pause(0.1)
        await pilot.press("up", "up", "down", "down", "left", "right", "left", "right", "b", "a")
        assert await esperar(pilot, lambda: heroi(app)["konami"] == 1)
        assert heroi(app)["titulo"] == "Jogador 1"


async def test_skills_r_respec_custa_bits(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "skills")
        app.query_one("#arvore-grade").ir_para("dev_null")
        await pilot.press("r")
        await pilot.pause(0.2)
        assert type(app.screen).__name__ == "Confirmar"
        await pilot.press("right", "enter")
        assert await esperar(pilot, lambda: heroi(app)["pontos"] == 3)
        assert heroi(app)["bits"] == 1284 - 150


async def test_classes_seis_lado_a_lado_e_trocar(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "skills")
        await pilot.press("c")
        assert await esperar(pilot, lambda: app.pagina_nome == "classes")
        await pilot.pause(0.3)
        assert not app.query_one("#paineis").display
        assert janela(app) == "classe-programa"
        await pilot.press("alt+right")
        assert janela(app) == "classe-empreendedor"
        await pilot.press("enter")
        assert await esperar(pilot, lambda: app.pagina_nome == "skills")
        await pilot.pause(0.2)
        assert app.pagina.classe == "empreendedor"
        await pilot.press("c")
        await pilot.pause(0.4)
        await pilot.press("escape")
        assert await esperar(pilot, lambda: app.pagina_nome == "skills")
        await pilot.press("c")
        await pilot.pause(0.4)
        app.focar_janela("classe-rato")
        await pilot.press("t")
        await pilot.pause(0.2)
        await pilot.press("right", "enter")
        assert await esperar(pilot, lambda: heroi(app)["classe"] == "rato")
        assert app.b.todos("SELECT * FROM skills") == []


# ---------------------------------------------------------------- 7 · loja
async def test_loja_compra_usa_e_categoria(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "loja")
        assert app.query_one("#itens-lista").itens[0] == "pocao_hp"
        await pilot.press("down")
        await pilot.press("plus")
        await pilot.press("enter")
        assert await esperar(pilot, lambda: C.mochila(app.b).get("cafe") == 3)
        assert heroi(app)["bits"] == 1284 - 100
        app.focar_janela("mochila")
        await pilot.pause(0.1)
        await pilot.press("u")
        assert await esperar(pilot, lambda: heroi(app)["hp"] == 100)
        app.focar_janela("itens")
        await pilot.press("alt+right")
        await pilot.pause(0.2)
        assert app.pagina.categoria == "cosmetico"
        assert "Moldura dupla" in str(app.query_one("#itens").border_title) or app.query_one("#itens-lista").itens[0] == "moldura_dupla"


async def test_loja_sem_bits_avisa(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "loja")
        app.query_one("#itens-lista").mover_cursor(6)
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert any("faltam 216 bits" in a.texto.plain for a in app.query("Aviso"))
        assert heroi(app)["bits"] == 1284


# ---------------------------------------------------------------- 8 · histórico
async def test_historico_mapa_dia_camada_e_periodo(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "historico")
        assert app.pagina.dia == "2026-11-10"
        assert "terça 10/11: 8 pomodoros" in texto(app.query_one("#mapa-grade"))
        t = todo_texto(app)
        assert "08:40 a 10:40" in t or "sessões" in str([i for i in app.query_one("#dia-lista").itens])
        itens = app.query_one("#dia-lista").itens
        assert [it[1]["titulo"] for it in itens if it[0] == "quest"] == ["Lista 3 de Compiladores", "Resumo de Redes, cap. 4",
                                                                         "Seção 1 do TCC"]
        await pilot.press("down")
        assert app.pagina.dia == "2026-11-11"
        await pilot.press("left")
        assert app.pagina.dia == "2026-11-04"
        await pilot.press("alt+right")
        await pilot.pause(0.2)
        assert app.pagina.camada == "commits"
        await pilot.press("right_square_bracket")
        await pilot.pause(0.2)
        assert app.pagina.semanas == 26
        assert "por matéria" in str(app.query_one("#materias").border_title)


# ---------------------------------------------------------------- 9 · taverna
async def test_taverna_conversa_e_mestre_so_cria_rascunho(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "taverna")
        conv = app.query_one("#conv-lista").itens
        assert any(t == "cli" for t, _ in conv)
        assert janela(app) == "conversa"
        xp = heroi(app)["xp_total"]
        await pilot.press(*"cria uma revisão de flashcards", "enter")
        assert await esperar(pilot, lambda: app.b.escalar("SELECT COUNT(*) FROM quests WHERE estado = 'rascunho'") == 4, 5)
        await pilot.pause(0.3)
        assert heroi(app)["xp_total"] == xp
        papeis = [r[0] for r in app.b.todos("SELECT papel FROM taverna ORDER BY id DESC LIMIT 3")]
        assert "mestre" in papeis and "cli" in papeis
        app.focar_janela("rascunhos-t")
        await pilot.press("a")
        assert await esperar(pilot, lambda: app.b.escalar("SELECT COUNT(*) FROM quests WHERE estado = 'rascunho'") == 3)


# ---------------------------------------------------------------- 1 · criação de personagem
async def test_criar_heroi(app_vazio):
    app = app_vazio
    async with app.run_test(size=G) as pilot:
        await pilot.pause(0.5)
        assert type(app.screen).__name__ == "Criar"
        await pilot.press("down", "down", "down", "down")
        await pilot.pause(0.1)
        assert app.screen.query_one("Detalhes").classe == "gamer"
        await pilot.press("tab")
        inp = app.screen.query_one("#nome")
        inp.value = "Leo"
        await pilot.press("enter")
        assert await esperar(pilot, lambda: heroi(app) is not None and app.pagina_nome == "painel")
        assert heroi(app)["nome"] == "Leo" and heroi(app)["classe"] == "gamer" and heroi(app)["hp"] == 100


async def test_criar_mistico_tira_a_carta_do_dia(app_vazio):
    app = app_vazio
    async with app.run_test(size=G) as pilot:
        await pilot.pause(0.5)
        await pilot.press("enter")
        assert await esperar(pilot, lambda: type(app.screen).__name__ == "Carta")
        await pilot.press("space")
        await pilot.pause(0.2)
        assert C.carta_do_dia(app.b, app.cfg, app.hoje())[2] is True
        await pilot.press("space")
        assert await esperar(pilot, lambda: len(app.screen_stack) == 1)


# ---------------------------------------------------------------- 10 · diálogos e avisos
async def test_dialogo_de_nivel_e_desmaio(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "painel")
        app.jogo.b.x("UPDATE heroi SET xp = 1790")
        app.relogio.avancar(18 * 60 + 43)
        app.cliente.tick()
        assert await esperar(pilot, lambda: type(app.screen).__name__ == "Nivel")
        assert "Dev Pleno" in str(app.screen.query_one(".linha-texto").render())
        await pilot.press("enter")
        await pilot.pause(0.2)
        app.jogo.b.x("UPDATE heroi SET hp = 5")
        app.pedir("iniciar")
        app.relogio.avancar(6 * 60)
        app.pedir("abandonar")
        assert await esperar(pilot, lambda: type(app.screen).__name__ == "Desmaio")
        assert C.atual(app.b)["fase"] == "desmaio"


async def test_vitrine_dos_dialogos(app):
    from oma_rpg.ui.dialogos import Vitrine
    async with app.run_test(size=G) as pilot:
        await pronto(app, pilot)
        app.push_screen(Vitrine())
        await pilot.pause(0.3)
        titulos = [str(w.border_title) for w in app.screen.query(".quadro")]
        assert titulos == ["nível alcançado", "abandonar o pomodoro?", "você desmaiou", "concluir quest", "aprovar rascunho #14",
                           "carta do dia (Jovem Místico)"]
        await pilot.press("escape")


# ---------------------------------------------------------------- busca, teclas, abertura e mouse
async def test_busca_abre_a_quest(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "painel")
        await pilot.press("slash")
        await pilot.pause(0.2)
        await pilot.press(*"unificador")
        await pilot.pause(0.2)
        await pilot.press("enter")
        assert await esperar(pilot, lambda: app.pagina_nome == "quests")
        await pilot.pause(0.3)
        assert app.query_one("#q-lista").item_atual()["titulo"] == "Implementar o unificador"


async def test_busca_acha_skill_e_item(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "painel")
        await pilot.press("slash")
        await pilot.press(*"café")
        await pilot.pause(0.2)
        await pilot.press("enter")
        assert await esperar(pilot, lambda: app.pagina_nome == "loja")
        await pilot.pause(0.3)
        assert app.query_one("#itens-lista").item_atual() == "cafe"


async def test_ctrl_espaco_mostra_as_teclas_da_janela(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "foco")
        await pilot.press("f1")
        await pilot.pause(0.2)
        assert type(app.screen).__name__ == "Teclas"
        corpo = str(app.screen.query_one("#corpo-teclas").render())
        assert "nesta janela (foco)" in corpo and "pula a pausa" in corpo
        await pilot.press("escape")
        assert len(app.screen_stack) == 1


async def test_rodape_mostra_ate_5_teclas_e_o_lembrete(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "quests")
        r = app.query_one("#rodape").render().plain
        assert r.startswith("enter abrir") and "ctrl+hjkl janelas" in r and "ctrl+espaço ajuda" in r
        assert len(app.itens_rodape()) <= 5


async def test_abertura_uma_vez_por_boot(tmp_path):
    from oma_rpg.falso import montar_demo
    from oma_rpg.ui.app import OmaRpgApp
    kw = montar_demo(pasta=tmp_path / "d", fixo=True)
    app = OmaRpgApp(**kw, abertura=True)
    async with app.run_test(size=G) as pilot:
        await pilot.pause(0.2)
        assert type(app.screen).__name__ == "Abertura"
        await pilot.press("x")
        assert await esperar(pilot, lambda: len(app.screen_stack) == 1)
    app2 = OmaRpgApp(**{**kw, "estado": kw["estado"]}, abertura=True)
    async with app2.run_test(size=G) as pilot:
        await pilot.pause(0.3)
        assert type(app2.screen).__name__ != "Abertura"


async def test_mouse_clique_na_coluna_abre_o_painel(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "painel")
        l = app.query_one("#lista-paineis")
        await pilot.click(l, offset=(4, 4))
        await pilot.click(l, offset=(4, 4))
        assert await esperar(pilot, lambda: app.pagina_nome == "loja")


async def test_mouse_clique_na_aba(app):
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "quests")
        abas = app.query_one("#q-abas")
        x = next(x0 for x0, x1, k, _ in abas._x if k == "feitas")
        await pilot.click(abas, offset=(x + 1, 0))
        await pilot.pause(0.2)
        assert app.pagina.aba == "feitas"


async def test_repositorios_pelo_dialogo(app, tmp_path):
    import subprocess
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "painel")
        app.abrir_repos()
        await pilot.pause(0.2)
        app.screen.query_one("#r-caminho").value = str(repo)
        app.screen.query_one("#r-materia").value = "IC"
        app.screen.query_one("#r-caminho").focus()
        await pilot.press("enter")
        assert await esperar(pilot, lambda: app.b.um("SELECT materia FROM repos WHERE nome = 'r'") is not None)
        app.screen.query_one("#r-caminho").value = str(tmp_path / "nao-existe")
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert any("não existe" in a.texto.plain for a in app.query("Aviso"))


# ---------------------------------------------------------------- pastas que o Mestre pode ler (0.2.0)
async def test_taverna_p_libera_e_remove_pasta(app, tmp_path):
    base = tmp_path / "home-de-teste"
    estudo = base / "Codespace" / "Comp-Deci"
    estudo.mkdir(parents=True)
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "taverna")
        app.focar_janela("rascunhos-t")
        await pilot.press("P")
        await pilot.pause(0.2)
        assert type(app.screen).__name__ == "Pastas"
        await pilot.press("a")
        await pilot.pause(0.2)
        assert type(app.screen).__name__ == "EscolherPasta"
        app.screen.abrir(str(base))
        await pilot.pause(0.1)
        assert app.screen.query_one("#pastas-nav").itens == ["..", "Codespace"]
        app.screen.query_one("#pastas-nav").focus()
        await pilot.press("down", "enter")
        await pilot.pause(0.1)
        assert app.screen.atual == str(base / "Codespace")
        await pilot.press("down", "right")
        await pilot.pause(0.1)
        assert app.screen.atual == str(estudo)
        await pilot.press("space")
        await pilot.pause(0.2)
        assert type(app.screen).__name__ == "Confirmar"
        assert str(estudo) in str(app.screen.query_one(".linha-texto").render())
        await pilot.press("right", "enter")
        assert await esperar(pilot, lambda: C.caminhos_liberados(app.b, app.agora()) == [str(estudo)])
        await pilot.pause(0.3)
        assert type(app.screen).__name__ == "Pastas"
        assert app.screen.query_one("#pastas-lista").itens[0]["caminho"] == str(estudo)
        await pilot.press("x")
        assert await esperar(pilot, lambda: C.caminhos_liberados(app.b, app.agora()) == [])
        await pilot.press("escape")
        await pilot.pause(0.2)
        app.focar_janela("permissoes")
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert type(app.screen).__name__ == "Pastas"


async def test_pasta_sensivel_nao_chega_a_perguntar(app):
    from pathlib import Path
    from oma_rpg.ui.dialogos import confirmar_pasta
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "taverna")
        confirmar_pasta(app, str(Path.home()))
        await pilot.pause(0.2)
        assert len(app.screen_stack) == 1
        assert any("não dá para liberar" in a.texto.plain for a in app.query("Aviso"))


async def test_pedido_do_mestre_abre_o_dialogo(app, tmp_path):
    estudo = tmp_path / "Comp-Deci"
    estudo.mkdir()
    from oma_rpg.comandos import executar
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "taverna")
        executar(app.jogo, "pedir_pasta", {"caminho": str(estudo), "motivo": "montar as quests"}, "mestre")
        for ev in app.jogo.soltar_eventos():
            app.cliente.ao_evento(ev)
        assert await esperar(pilot, lambda: type(app.screen).__name__ == "PedidoPasta")
        assert str(estudo) in str(app.screen.query_one(".linha-texto").render())
        await pilot.press("s")
        assert await esperar(pilot, lambda: C.caminhos_liberados(app.b, app.agora()) == [str(estudo)])
        texto_perm = texto(app.query_one("#permissoes").query_one("Pintado"))
        assert "1 liberada" in texto_perm and "Comp-Deci" in texto_perm


async def test_mensagem_com_pasta_pergunta_antes_de_mandar(app, tmp_path):
    estudo = tmp_path / "Comp-Deci"
    estudo.mkdir()
    async with app.run_test(size=G) as pilot:
        await abrir(app, pilot, "taverna")
        app.query_one("#msg").load_text(f"crie quests a partir de {estudo}")
        app.query_one("#msg").focus()
        await pilot.press("enter")
        assert await esperar(pilot, lambda: type(app.screen).__name__ == "PedidoPasta")
        await pilot.press("u")
        assert await esperar(pilot, lambda: C.caminhos_liberados(app.b, app.agora()) == [str(estudo)])
        assert C.pastas(app.b, app.agora())[0]["modo"] == "uma_vez"
        assert await esperar(pilot, lambda: app.b.um("SELECT 1 FROM taverna WHERE texto LIKE 'crie quests a partir%'") is not None)
