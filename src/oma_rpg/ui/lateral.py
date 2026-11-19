"""Coluna da esquerda, sem borda: os 7 painéis numerados como os workspaces do herdr, o herói e os ativos."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from oma_rpg.nucleo import consultas as C
from oma_rpg.ui import desenho as D
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lista import Lista, ajustar
from oma_rpg.ui.widgets import Pintado

PAGINAS = [("painel", "painel"), ("foco", "foco"), ("quests", "quests"), ("skills", "skills"), ("loja", "loja"),
           ("historico", "histórico"), ("taverna", "taverna"), ("status", "status")]


class Lateral(Vertical):
    DEFAULT_CSS = """
    Lateral { width: 30; height: 1fr; padding: 0 1; }
    Lateral.-foco #cab-paineis { color: $accent; text-style: bold; }
    Lateral #cab-paineis { height: 2; }
    Lateral #lista-paineis { height: 8; }
    Lateral .espaco { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Pintado(self._cab_paineis, id="cab-paineis")
        yield Lista(self._linha_painel, id="lista-paineis", fundo_cursor=True)
        yield Pintado(self._heroi, id="lateral-heroi")
        yield Pintado(self._proximas, id="lateral-proximas")
        yield Static("", classes="espaco")
        yield Pintado(self._ativos, id="lateral-ativos", ao_clicar=self._clique_ativos)

    def on_mount(self) -> None:
        self.query_one("#lista-paineis", Lista).definir([p for p, _ in PAGINAS], cursor=0)

    # ------------------------------------------------------------ desenhos
    def _cab_paineis(self, w: int) -> Text:
        return Text("painéis", style=self.app.cor("accent") if self.has_class("-foco") else self.app.cor("mudo"))

    def _linha_painel(self, item: str, i: int, est) -> list[Text]:
        a = self.app
        atual = a.pagina_nome in (item, "classes" if item == "skills" else "")
        cor_txt = a.cor("forte") if atual else a.cor("texto")
        t = Text(no_wrap=True)
        t.append(str(i + 1), style=a.cor("mudo"))
        t.append(" " + ic(item) + " ", style=a.cor("accent") if atual else a.cor("texto"))
        t.append(dict(PAGINAS)[item], style=f"bold {cor_txt}" if atual else cor_txt)
        badge = a.badge(item)
        w = est.largura
        linha = D.linha_lr(t, badge, w) if badge.cell_len else ajustar(t, w)
        if atual and not (est.cursor and est.foco):
            linha.stylize(f"on {a.cor('selecao')}")
            linha = Text("▌", style=a.cor("accent")) + linha[1:]
        return [linha]

    def _heroi(self, w: int) -> Text:
        a = self.app
        st = a.st.get("heroi")
        linhas = [Text("─" * w, style=a.cor("linha"))]
        if not st:
            linhas.append(Text("sem herói ainda", style=a.cor("mudo")))
            return D.juntar(linhas)
        linhas.append(D.linha_lr(Text("herói", style=a.cor("mudo")), Text(f"nv {st['nivel']}", style=a.cor("mudo")), w))
        linhas.append(Text(""))
        linhas.append(Text(st["nome"], style=f"bold {a.cor('forte')}"))
        cls = a.cfg.classe(st["classe_id"])
        linhas.append(Text.assemble((ic(st["classe_id"]) + " ", a.cor(cls["cor"])), (cls["nome"], a.cor(cls["cor"]))))
        linhas.append(Text(st["titulo"], style=a.cor("mudo")))
        linhas.append(Text(""))
        larg = max(6, w - 13)
        hp_cor = D.cor_hp(a, st["hp"], st["hp_max"], st["classe_id"] == "otaku")
        for icone, cor, v, m in (("vida", hp_cor, st["hp"], st["hp_max"]), ("mana", "blue", st["mp"], st["mp_max"]),
                                 ("xp", "green", st["xp"], st["xp_proximo"])):
            t = Text(ic(icone) + " ", style=a.cor({"vida": "red", "mana": "blue", "xp": "green"}[icone]))
            t.append_text(D.barra(a, v, m, larg, cor))
            num = f"{C.milhar(v)}/{C.milhar(m)}"
            linhas.append(D.linha_lr(t, Text(num, style=a.cor("texto")), w))
        linhas.append(Text(""))
        linhas.append(D.linha_lr(Text.assemble((ic("bits") + " ", a.cor("yellow")), (C.milhar(st["bits"]), f"bold {a.cor('forte')}")),
                                 Text("bits", style=a.cor("mudo")), w))
        linhas.append(Text.assemble((ic("streak") + " ", a.cor("orange")),
                                    (f"{st['streak']} dia{'s' if st['streak'] != 1 else ''} seguidos", a.cor("texto"))))
        linhas.append(Text.assemble((ic("combo") + " ", a.cor("yellow")), (f"combo x{st['combo']:.1f}", a.cor("texto"))))
        if st["pontos"]:
            linhas.append(Text.assemble((ic("estrela4") + " ", a.cor("yellow")),
                                        (f"{st['pontos']} ponto{'s' if st['pontos'] != 1 else ''} de skill", a.cor("yellow"))))
        return D.juntar(linhas)

    def _proximas(self, w: int) -> Text:
        a = self.app
        abertas = [q for q in C.quests(a.b, a.cfg, a.hoje(), "aberta") if not q.get("bloqueada")]
        linhas = [Text("─" * w, style=a.cor("linha")),
                  D.linha_lr(Text("faltam", style=a.cor("mudo")), Text(str(len(abertas)), style=a.cor("mudo")), w)]
        if not abertas:
            linhas.append(Text("nenhuma quest aberta", style=a.cor("mudo")))
            return D.juntar(linhas)
        for q in abertas[:4]:
            p = q.get("prio", 2)
            marca, cor = {3: ("! ", "red"), 2: ("· ", "accent"), 1: ("⌄ ", "mudo")}.get(p, ("· ", "mudo"))
            t = Text(marca, style=f"bold {a.cor(cor)}" if p == 3 else a.cor(cor))
            t.append(q["titulo"], style=a.cor("texto"))
            t.truncate(w, overflow="ellipsis")
            linhas.append(t)
        return D.juntar(linhas)

    def _ativos(self, w: int) -> Text:
        a = self.app
        linhas = [Text("─" * w, style=a.cor("linha")),
                  D.linha_lr(Text("ativos", style=a.cor("mudo")), Text("agora", style=a.cor("mudo")), w)]
        p = a.st.get("pomodoro") or {}
        fase = p.get("fase", "parado")
        if fase == "foco":
            cor = "yellow" if p.get("pausado") else "green"
            linhas.append(Text.assemble(("● ", a.cor(cor)), (f"pomodoro {C.mmss(a.restante())}" + (" pausado" if p.get("pausado") else ""),
                                                            a.cor("texto"))))
        elif fase in ("pausa", "longa"):
            linhas.append(Text.assemble(("● ", a.cor("blue")), (f"pausa {C.mmss(a.restante())}", a.cor("texto"))))
        elif fase == "desmaio":
            linhas.append(Text.assemble(("● ", a.cor("red")), (f"desmaiado {C.mmss(a.restante())}", a.cor("red"))))
        elif p.get("guardado"):
            linhas.append(Text.assemble(("◌ ", a.cor("mudo")), ("pomodoro guardado", a.cor("mudo"))))
        else:
            linhas.append(Text.assemble(("◌ ", a.cor("mudo")), ("pomodoro parado", a.cor("mudo"))))
        n = a.n_repos()
        if n:
            linhas.append(Text.assemble(("✓ ", a.cor("green")), (f"git · {n} repositório{'s' if n != 1 else ''}", a.cor("texto"))))
        else:
            linhas.append(Text.assemble(("◌ ", a.cor("mudo")), ("git · nenhum repositório", a.cor("mudo"))))
        m = a.mestre_estado()
        cor = {"pronto": "cyan", "pensando": "yellow", "ausente": "mudo"}.get(m, "mudo")
        linhas.append(Text.assemble(("● ", a.cor(cor)), (f"Mestre {m}", a.cor("texto") if m != "ausente" else a.cor("mudo"))))
        return D.juntar(linhas)

    def _clique_ativos(self, ev: events.Click) -> None:
        y = ev.y
        if y == 2:
            self.app.abrir_pagina("foco", foco=True)
        elif y == 3:
            self.app.abrir_repos()
        elif y == 4:
            self.app.abrir_pagina("taverna", foco=True)

    # ------------------------------------------------------------ app
    def pintar(self) -> None:
        l = self.query_one("#lista-paineis", Lista)
        l.redesenhar()
        for w in self.query(Pintado):
            w.pintar()

    def relogio(self) -> None:
        self.query_one("#lateral-ativos", Pintado).refresh()

    def marcar_foco(self, foco: bool) -> None:
        if foco != self.has_class("-foco"):
            self.set_class(foco, "-foco")
            self.query_one("#cab-paineis", Pintado).refresh()

    def focar_entrada(self) -> None:
        l = self.query_one("#lista-paineis", Lista)
        nomes = [p for p, _ in PAGINAS]
        alvo = self.app.pagina_nome if self.app.pagina_nome in nomes else "skills"
        l.mover_cursor(nomes.index(alvo), avisar=False)
        l.focus()

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.app.abrir_pagina(ev.item, foco=True)

    def rodape(self) -> list[tuple[str, str, str]]:
        return [("enter", "abrir", "noop"), ("alt+1…7", "painel direto", "noop"), ("→", "janela", "janela('dir')")]

    def teclas(self) -> list[tuple[str, str]]:
        return [("↑ ↓ j k", "escolhe o painel"), ("enter ou clique", "abre"), ("alt+1 … alt+7", "abre direto de qualquer lugar")]
