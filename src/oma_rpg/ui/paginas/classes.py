"""Tela 6 · classes: as 6 lado a lado, na tela toda. alt+←→ troca · enter vê a árvore · t vira esta classe · esc volta.
Dá para trocar de classe depois, perdendo os pontos gastos."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll

from oma_rpg.nucleo import consultas as C
from oma_rpg.ui import desenho as D
from oma_rpg.ui.base import Janela, Pagina
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lista import ajustar
from oma_rpg.ui.widgets import Pintado

GRADE = ["mistico", "programa", "empreendedor", "rato", "gamer", "otaku", "polimata", "monge"]


class CaixaClasse(Janela):
    FOCAVEL = True
    DEFAULT_CSS = "CaixaClasse { height: 1fr; width: 1fr; }"

    def __init__(self, cid: str) -> None:
        super().__init__(id=f"classe-{cid}")
        self.cid = cid

    def compose(self) -> ComposeResult:
        yield Pintado(self._desenhar)

    def pintar(self) -> None:
        c = self.app.cfg.classe(self.cid)
        self.titulo(f"{ic(self.cid)} {c['nome']}", f"hp {c['hp']} · mana {c['mp']}")
        self.styles.border_title_color = self.app.cor(c["cor"])
        self.query_one(Pintado).pintar()

    def _desenhar(self, w: int) -> Text:
        a = self.app
        c = a.cfg.classe(self.cid)
        cor = a.cor(c["cor"])
        linhas = [Text(""), Text.assemble((c["poder_titulo"] + ": ", f"bold {cor}"), (c["poder_txt"], a.cor("texto"))), Text("")]
        cw = (w - 2) // 3
        cab, reg = Text(), Text()
        for nome in c["ramos"]:
            cab.append_text(ajustar(Text(nome, style=f"bold {cor}"), cw))
            reg.append("─" * (cw - 2), style=a.cor("linha"))
            reg.append("  ")
        linhas += [cab, reg, Text("")]
        sk = a.cfg.skills_da_classe(self.cid)
        for pos in range(5):
            t = Text()
            for r in range(3):
                sid = next(s for s in sk if a.cfg.skill(s)["ramo"] == r and a.cfg.skill(s)["pos"] == pos)
                s = a.cfg.skill(sid)
                ativa = s["tipo"] == "ativa"
                item = Text()
                item.append("◆ " if ativa else "◇ ", style=cor if ativa else a.cor("mudo"))
                item.append(s["nome"], style=f"bold {a.cor('forte')}" if pos == 4 else a.cor("texto"))
                t.append_text(ajustar(item, cw))
            linhas.append(t)
        h = C.heroi(a.b)
        atual = Text("sua classe atual", style=a.cor("green")) if h and h["classe"] == self.cid else Text("")
        linhas += [Text(""), D.linha_lr(Text(c["tema"], style=a.cor("mudo")), atual, w)]
        return D.juntar(linhas)

    def rodape(self):
        return [("alt+←→", "trocar de classe", "alt_h(1)"), ("enter", "ver árvore", "noop"), ("esc", "voltar", "esc"),
                ("t", "virar esta", "noop")]

    def teclas(self):
        return [("alt+← →", "a classe ao lado"), ("enter", "abre a árvore desta classe"), ("t", "troca para esta classe (perde os pontos gastos)"),
                ("esc", "volta para as skills")]

    def alt_h(self, passo: int) -> None:
        i = GRADE.index(self.cid)
        self.app.focar_janela(f"classe-{GRADE[(i + passo) % len(GRADE)]}")


class PaginaClasses(Pagina):
    NOME = "classes"
    TITULO = "todas as classes"
    ENTRADA = "classe-programa"
    TELA_CHEIA = True
    VIZINHAS = {
        "classe-mistico": {"dir": "classe-programa", "cima": "topo", "baixo": "classe-empreendedor"},
        "classe-programa": {"esq": "classe-mistico", "cima": "topo", "baixo": "classe-rato"},
        "classe-empreendedor": {"dir": "classe-rato", "cima": "classe-mistico", "baixo": "classe-gamer"},
        "classe-rato": {"esq": "classe-empreendedor", "cima": "classe-programa", "baixo": "classe-otaku"},
        "classe-gamer": {"dir": "classe-otaku", "cima": "classe-empreendedor", "baixo": "classe-polimata"},
        "classe-otaku": {"esq": "classe-gamer", "cima": "classe-rato", "baixo": "classe-monge"},
        "classe-polimata": {"dir": "classe-monge", "cima": "classe-gamer"},
        "classe-monge": {"esq": "classe-polimata", "cima": "classe-otaku"},
    }
    BINDINGS = [Binding("enter", "arvore", show=False), Binding("t", "trocar", show=False)]
    DEFAULT_CSS = "PaginaClasses { layout: vertical; } PaginaClasses #cl-scroll { height: 1fr; } PaginaClasses .fila { height: 15; }"

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="cl-scroll"):
            for i in range(0, len(GRADE), 2):
                with Horizontal(classes="fila"):
                    yield CaixaClasse(GRADE[i])
                    if i + 1 < len(GRADE):
                        yield CaixaClasse(GRADE[i + 1])

    def on_mount(self) -> None:
        h = C.heroi(self.app.b)
        if h:
            self.ENTRADA = f"classe-{h['classe']}"
            self.app._foco_pendente = self.ENTRADA if self.app._foco_pendente else ""

    def trilha(self):
        return [("skills", "pagina(4)"), ("todas as classes", "")]

    def _atual(self) -> str | None:
        n = self.app.nome_janela(self.app.focused)
        return n.removeprefix("classe-") if n.startswith("classe-") else None

    def action_arvore(self) -> None:
        cid = self._atual()
        if cid:
            self.app.abrir_pagina("skills", foco=True, classe=cid)

    def action_trocar(self) -> None:
        from oma_rpg.ui.dialogos import Confirmar
        a = self.app
        cid = self._atual()
        h = C.heroi(a.b)
        if not cid or not h or cid == h["classe"]:
            return
        gastos = int(a.b.escalar("SELECT SUM(custo) FROM skills", (), 0))
        a.push_screen(Confirmar(f"virar {a.cfg.classe(cid)['nome']}?",
                                [f"Você perde os {gastos} pontos gastos na árvore de {a.cfg.classe(h['classe'])['nome']}.",
                                 "nível, XP, Bits e streak continuam"], "trocar de classe"),
                      lambda ok: ok and a.pedir("trocar_classe", {"classe": cid}, lambda ok2, r: ok2 and a.atualizar()))


PAGINA = PaginaClasses
