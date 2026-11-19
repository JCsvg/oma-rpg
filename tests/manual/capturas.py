"""Gera as capturas de docs/img com o --demo, pelo próprio Textual (SVG) e rsvg-convert. Nenhuma captura da tela real.

    PYTHONPATH=src python tests/manual/capturas.py [pasta] [nomes...]
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parents[2]
sys.path[:0] = [str(RAIZ / "src"), str(RAIZ)]
os.environ["XDG_RUNTIME_DIR"] = tempfile.mkdtemp()
os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp()
os.environ.setdefault("TZ", "America/Sao_Paulo")

from oma_rpg.falso import montar_demo  # noqa: E402
from oma_rpg.ui.app import OmaRpgApp  # noqa: E402
from tests.manual.svg_png import converter  # noqa: E402


def novo(estado: str = "foco", abertura: bool = False) -> OmaRpgApp:
    kw = montar_demo(Path(tempfile.mkdtemp()), fixo=True, estado=estado)
    return OmaRpgApp(**kw, abertura=abertura)


async def capturar(pasta: Path, nome: str, tam, passos, estado: str = "foco", abertura: bool = False) -> None:
    app = novo(estado, abertura)
    async with app.run_test(size=tam) as p:
        await p.pause(0.6)
        if not abertura:
            await passos(app, p)
            await p.pause(0.5)
            for av in list(app.query("Aviso")):
                if nome != "avisos":
                    av.remove()
            await p.pause(0.2)
        converter(app.export_screenshot(title="oma-rpg"), pasta / f"{nome}-{tam[0]}x{tam[1]}.png")
    print("ok", nome, tam)


async def painel(app, p):
    app.abrir_pagina("painel", foco=True)


async def foco(app, p):
    app.abrir_pagina("foco", foco=True)
    await p.pause(0.3)
    app.focar_janela("fila")
    await p.press("down")


async def foco_estreito(app, p):
    app.abrir_pagina("foco", foco=True)


async def quests(app, p):
    app.abrir_pagina("quests", foco=True)


async def skills(app, p):
    app.abrir_pagina("skills", foco=True)


async def classes(app, p):
    app.abrir_pagina("classes", foco=True)


async def loja(app, p):
    app.abrir_pagina("loja", foco=True)


async def historico(app, p):
    app.abrir_pagina("historico", foco=True)


async def taverna(app, p):
    app.abrir_pagina("taverna", foco=True)


async def criar(app, p):
    from oma_rpg.ui.criar import Criar
    app.push_screen(Criar())


async def dialogos(app, p):
    from oma_rpg.ui.dialogos import Vitrine
    app.push_screen(Vitrine())


async def busca(app, p):
    app.abrir_pagina("painel", foco=True)
    await p.pause(0.3)
    await p.press("slash")
    await p.press(*"redes")


async def teclas(app, p):
    app.abrir_pagina("foco", foco=True)
    await p.pause(0.3)
    await p.press("f1")


async def nada(app, p):
    pass


async def principal() -> None:
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].isalpha() else RAIZ / "docs" / "img"
    nomes = [a for a in sys.argv[1:] if a.isalpha()]
    pasta.mkdir(parents=True, exist_ok=True)
    g, m = (180, 48), (90, 30)
    lista = [
        ("painel", g, painel, "pausa"), ("foco", g, foco, "foco"), ("quests", g, quests, "foco"), ("skills", g, skills, "foco"),
        ("classes", g, classes, "foco"), ("loja", g, loja, "foco"), ("historico", g, historico, "foco"),
        ("taverna", g, taverna, "foco"), ("criar", g, criar, "foco"), ("dialogos", g, dialogos, "foco"),
        ("busca", g, busca, "pausa"), ("teclas", g, teclas, "foco"),
        ("painel", m, painel, "pausa"), ("foco", m, foco_estreito, "foco"), ("quests", m, quests, "foco"),
    ]
    for nome, tam, f, estado in lista:
        if nomes and nome not in nomes:
            continue
        await capturar(pasta, nome, tam, f, estado)
    if not nomes or "abertura" in nomes:
        await capturar(pasta, "abertura", g, nada, abertura=True)


if __name__ == "__main__":
    asyncio.run(principal())
