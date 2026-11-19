"""Topo, sem borda: marca, voltar e avançar, a trilha, a caixa de busca (ou o pomodoro rodando) e o herói."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

from oma_rpg.nucleo import consultas as C
from oma_rpg.ui.icones import ic
from oma_rpg.ui.widgets import Botao


class CaixaBusca(Widget, can_focus=True):
    """A caixa do meio. Parado: "/ buscar quests, skills e itens da loja". Em foco: o timer e a quest.
    Enter, clique ou qualquer letra abrem a busca."""

    DEFAULT_CSS = """
    CaixaBusca { width: 56; height: 1; background: $rpg-campo; color: $rpg-mudo; padding: 0 1; }
    CaixaBusca:focus { background: $rpg-selecao; }
    """
    BINDINGS = [Binding("enter", "buscar", show=False), Binding("down,j", "descer", show=False)]

    def render(self) -> Text:
        a = self.app
        st = getattr(a, "st", None) or {}
        p = st.get("pomodoro") or {}
        w = self.size.width - 2
        if p.get("fase") == "foco":
            t = Text(no_wrap=True)
            t.append("● ", style=a.cor("yellow" if p.get("pausado") else "green"))
            t.append(f"foco {C.mmss(a.restante())}", style=f"bold {a.cor('forte')}")
            if p.get("quest"):
                t.append(" · ", style=a.cor("mudo"))
                t.append(p["quest"], style=a.cor("texto"))
            combo = (st.get("heroi") or {}).get("combo", 1.0)
            d = Text(f"combo x{combo:.1f}", style=a.cor("yellow"))
            from oma_rpg.ui.desenho import linha_lr
            return linha_lr(t, d, w)
        return Text("/ buscar quests, skills e itens da loja", style=a.cor("mudo"), no_wrap=True, overflow="ellipsis")

    def action_buscar(self) -> None:
        self.app.action_buscar()

    def action_descer(self) -> None:
        self.app.action_janela("baixo")

    def on_click(self, ev: events.Click) -> None:
        ev.stop()
        self.app.action_buscar()

    def on_key(self, ev: events.Key) -> None:
        if ev.is_printable and ev.character and ev.character not in "jk":
            ev.stop()
            self.app.action_buscar(ev.character if ev.character != "/" else "")


class Trilha(Widget):
    DEFAULT_CSS = "Trilha { height: 1; width: 1fr; }"

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.partes: list[tuple[str, str]] = []
        self._x: list[tuple[int, int, str]] = []

    def definir(self, partes: list[tuple[str, str]]) -> None:
        if partes != self.partes:
            self.partes = partes
            self.refresh()

    def render(self) -> Text:
        a = self.app
        t = Text(no_wrap=True, overflow="ellipsis")
        self._x = []
        for n, (rot, acao) in enumerate(self.partes):
            if n:
                t.append(" / ", style=a.cor("linha"))
            x0 = t.cell_len
            ultimo = n == len(self.partes) - 1
            t.append(rot, style=f"bold {a.cor('forte')}" if ultimo else a.cor("mudo"))
            self._x.append((x0, t.cell_len, acao))
        return t

    async def on_click(self, ev: events.Click) -> None:
        for x0, x1, acao in self._x:
            if x0 <= ev.x < x1 and acao:
                ev.stop()
                await self.app.run_action(acao)
                return


class Topo(Horizontal):
    DEFAULT_CSS = """
    Topo { height: 1; background: $rpg-escuro; }
    Topo #marca { width: auto; padding: 0 1; }
    Topo .nav { padding: 0 0; width: 2; color: $rpg-mudo; background: transparent; }
    Topo .nav:disabled { color: $rpg-linha; }
    Topo #esq { width: 62; height: 1; }
    Topo #trilha { margin: 0 1 0 2; }
    Topo #dir { width: 1fr; height: 1; content-align: right middle; text-align: right; padding: 0 1; color: $rpg-mudo; }
    Topo.-estreito #esq { width: 1fr; }
    Topo.-estreito CaixaBusca { width: 28; }
    Topo.-estreito #dir { width: auto; }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="esq"):
            yield Static("", id="marca")
            yield Botao("‹", id="voltar", classes="nav", tooltip="voltar")
            yield Botao("›", id="avancar", classes="nav", tooltip="avançar")
            yield Trilha(id="trilha")
        yield CaixaBusca(id="busca")
        yield Static("", id="dir")

    def on_mount(self) -> None:
        self.ajustar(self.app.size.width)

    def ajustar(self, largura: int) -> None:
        self.set_class(largura < 120, "-estreito")
        a = self.app
        self.query_one("#marca", Static).update(Text.assemble((ic("marca"), f"bold {a.cor('accent')}"), " ",
                                                              ("oma-rpg", f"bold {a.cor('forte')}")))

    def pintar(self, partes: list[tuple[str, str]], pode_voltar: bool, pode_avancar: bool) -> None:
        self.query_one(Trilha).definir(partes)
        self.query_one("#voltar", Botao).disabled = not pode_voltar
        self.query_one("#avancar", Botao).disabled = not pode_avancar
        self.pintar_estado()

    def pintar_estado(self) -> None:
        a = self.app
        h = (getattr(a, "st", None) or {}).get("heroi")
        t = Text(no_wrap=True)
        if h:
            t.append(ic("usuario") + " ", style=a.cor("mudo"))
            t.append(f"{h['nome']} · nv {h['nivel']}", style=a.cor("mudo"))
        self.query_one("#dir", Static).update(t)
        self.query_one(CaixaBusca).refresh()

    def relogio(self) -> None:
        self.query_one(CaixaBusca).refresh()

    def focar_entrada(self) -> None:
        self.query_one(CaixaBusca).focus()

    def rodape(self) -> list[tuple[str, str, str]]:
        return [("enter", "buscar", "buscar"), ("↓", "volta", "janela('baixo')")]

    def teclas(self) -> list[tuple[str, str]]:
        return [("enter ou letra", "abre a busca de quests, skills e itens"), ("↓ ctrl+↓", "volta para a última janela")]

    def on_click(self, ev: events.Click) -> None:
        pass

    def on_botao_apertado(self, ev: Botao.Apertado) -> None:
        ev.stop()
        {"voltar": self.app.voltar, "avancar": self.app.avancar}.get(ev.botao.id or "", lambda: None)()
