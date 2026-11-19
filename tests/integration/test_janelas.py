"""A tabela do Ctrl+setas de cada página, linha por linha, com o pilot do Textual (180x48), e o modo estreito.

Cada linha da tabela é uma janela; as colunas são ←, →, ↑ e ↓. "·" (sem vizinha) quer dizer que o foco fica onde está.
O topo fica em cima de todas; a coluna dos painéis fica à esquerda das janelas da primeira coluna.
"""

import importlib

import pytest

from tests.conftest import janela, pronto

GRANDE = (180, 48)
TECLAS = {"esq": "ctrl+left", "dir": "ctrl+right", "cima": "ctrl+up", "baixo": "ctrl+down"}
PAGINAS = ["painel", "foco", "quests", "skills", "classes", "loja", "historico", "taverna", "status"]


def linhas():
    for nome in PAGINAS:
        cls = importlib.import_module(f"oma_rpg.ui.paginas.{nome}").PAGINA
        for w in cls.VIZINHAS:
            yield nome, w
        if not cls.TELA_CHEIA:
            yield nome, "paineis"


def esperado(cls, de: str, direcao: str) -> str:
    if de == "paineis":
        return {"dir": cls.ENTRADA, "cima": "topo"}.get(direcao, de)
    return cls.VIZINHAS[de].get(direcao, de)


@pytest.mark.parametrize("pagina,de", list(linhas()))
async def test_ctrl_setas_seguem_a_tabela(app, pagina, de):
    cls = importlib.import_module(f"oma_rpg.ui.paginas.{pagina}").PAGINA
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.abrir_pagina(pagina, foco=True)
        await pilot.pause(0.3)
        erros = []
        for direcao, tecla in TECLAS.items():
            app.focar_janela(de)
            await pilot.pause(0.05)
            assert janela(app) == de, f"não consegui focar {de}"
            await pilot.press(tecla)
            await pilot.pause(0.05)
            alvo = esperado(cls, de, direcao)
            if janela(app) != alvo:
                erros.append(f"{de} {tecla}: foi para {janela(app)}, a tabela diz {alvo}")
        assert not erros, erros


@pytest.mark.parametrize("pagina", PAGINAS)
async def test_topo_volta_para_a_ultima_janela(app, pagina):
    cls = importlib.import_module(f"oma_rpg.ui.paginas.{pagina}").PAGINA
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.abrir_pagina(pagina, foco=True)
        await pilot.pause(0.3)
        for origem in cls.VIZINHAS:
            app.focar_janela(origem)
            await pilot.pause(0.05)
            await pilot.press("ctrl+up")
            if cls.VIZINHAS[origem].get("cima") != "topo":
                continue
            assert janela(app) == "topo"
            await pilot.press("ctrl+down")
            assert janela(app) == origem


async def test_hjkl_com_ctrl_tambem_trocam(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.abrir_pagina("painel", foco=True)
        await pilot.pause(0.3)
        app.focar_janela("heroi")
        await pilot.pause(0.05)
        for tecla, alvo in (("ctrl+l", "hoje"), ("ctrl+j", "atividade"), ("ctrl+h", "calor"), ("ctrl+k", "heroi")):
            await pilot.press(tecla)
            assert janela(app) == alvo, tecla


async def test_so_a_janela_com_foco_acende(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.abrir_pagina("painel", foco=True)
        await pilot.pause(0.3)
        app.focar_janela("calor")
        await pilot.pause(0.2)
        cal, hoje = app.query_one("#calor"), app.query_one("#hoje")
        acc = app.cor("accent").lower()
        assert str(cal.styles.border_top[1].hex).lower() == acc
        assert str(hoje.styles.border_top[1].hex).lower() != acc
        assert "últimas 24 semanas" in str(cal.border_title) and app.cor("accent") in str(cal.border_title)


async def test_tab_passa_por_todas_as_janelas(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.abrir_pagina("loja", foco=True)
        await pilot.pause(0.3)
        vistas = set()
        for _ in range(7):
            await pilot.press("tab")
            vistas.add(janela(app))
        assert {"topo", "paineis", "categorias", "mochila", "itens", "item"} <= vistas


async def test_alt_numero_vai_direto_ao_painel(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        for n, nome in enumerate(["painel", "foco", "quests", "skills", "loja", "historico", "taverna"], 1):
            await pilot.pause(0.1)
            await pilot.press(f"alt+{n}")
            await pilot.pause(0.25)
            assert app.pagina_nome == nome


@pytest.mark.parametrize("tam", [(90, 30), (110, 34)])
async def test_estreito_mostra_uma_janela_por_vez(app, tam):
    async with app.run_test(size=tam) as pilot:
        await pronto(app, pilot)
        app.abrir_pagina("painel", foco=True)
        await pilot.pause(0.3)
        assert not app.query_one("#paineis").display
        vis = [j.id for j in app.query(".janela") if app._visivel(j)]
        assert vis == ["hoje"]
        assert app.query_one("#hoje").region.width >= tam[0] - 2
        await pilot.press("ctrl+down")
        await pilot.pause(0.2)
        assert janela(app) == "atividade" and [j.id for j in app.query(".janela") if app._visivel(j)] == ["atividade"]
        await pilot.press("ctrl+left", "ctrl+left")
        await pilot.pause(0.2)
        assert janela(app) == "paineis" and app.query_one("#paineis").display
        await pilot.press("ctrl+right")
        await pilot.pause(0.2)
        assert janela(app) == "hoje"


async def test_volta_ao_largo_restaura_o_layout(app):
    async with app.run_test(size=(90, 30)) as pilot:
        await pronto(app, pilot)
        app.abrir_pagina("foco", foco=True)
        await pilot.pause(0.3)
        await pilot.resize_terminal(180, 48)
        await pilot.pause(0.4)
        vis = sorted(j.id for j in app.query(".janela") if app._visivel(j))
        assert vis == ["ativas", "fila", "foco", "neste"]
        assert app.query_one("#paineis").display and app.query_one("#foco").region.width == 90
