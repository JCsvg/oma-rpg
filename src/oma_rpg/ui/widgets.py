"""Peças pequenas: botão de uma linha (do oma-mail), abas clicáveis, texto pintado por função e régua."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget


class Botao(Widget, can_focus=True):
    """Botão de uma linha: clique ou Enter apertam. `cheio` é a ação principal."""

    DEFAULT_CSS = """
    Botao { width: auto; height: 1; padding: 0 1; color: $foreground; background: $rpg-painel; }
    Botao:hover { background: $rpg-hover; }
    Botao:focus { background: $rpg-selecao; text-style: bold; }
    Botao.cheio { background: $accent; color: $background; text-style: bold; }
    Botao.cheio:hover { background: $accent 85%; }
    Botao.cheio:focus { background: $accent; color: $background; text-style: bold underline; }
    Botao.mudo { color: $rpg-mudo; background: transparent; }
    Botao.liso { background: transparent; }
    Botao.vermelho { color: $error; background: $rpg-painel; }
    Botao:disabled { color: $rpg-linha; }
    """
    BINDINGS = [Binding("enter", "apertar", show=False)]

    class Apertado(Message):
        def __init__(self, botao: "Botao") -> None:
            super().__init__()
            self.botao = botao

        @property
        def control(self) -> "Botao":
            return self.botao

    def __init__(self, rotulo="", id: str | None = None, classes: str = "", tooltip: str | None = None,
                 desativado: bool = False, valor=None) -> None:
        super().__init__(id=id, classes=classes, disabled=desativado)
        self._rotulo = rotulo
        self.valor = valor
        if tooltip:
            self.tooltip = tooltip

    @property
    def label(self):
        return self._rotulo

    @label.setter
    def label(self, v) -> None:
        if v != self._rotulo:
            self._rotulo = v
            self.refresh(layout=True)

    def get_content_width(self, container, viewport) -> int:
        return (self._rotulo if isinstance(self._rotulo, Text) else Text(str(self._rotulo))).cell_len

    def render(self) -> Text:
        if isinstance(self._rotulo, Text):
            return self._rotulo
        return Text(str(self._rotulo), no_wrap=True, overflow="ellipsis")

    def press(self) -> None:
        if not self.disabled:
            self.post_message(self.Apertado(self))

    def action_apertar(self) -> None:
        self.press()

    def on_click(self, ev: events.Click) -> None:
        ev.stop()
        if ev.button == 1:
            self.press()


class Abas(Widget):
    """Abas de uma linha: [hoje] [semana] [arco]. Clique troca; Alt+← → vêm da janela (`passo`)."""

    DEFAULT_CSS = "Abas { height: 1; width: 1fr; }"

    class Mudou(Message):
        def __init__(self, abas: "Abas", valor: str) -> None:
            super().__init__()
            self.abas, self.valor = abas, valor

        @property
        def control(self) -> "Abas":
            return self.abas

    def __init__(self, opcoes: list[tuple[str, str]], valor: str = "", direita: list[tuple[str, str]] | None = None,
                 valor_dir: str = "", **kw) -> None:
        super().__init__(**kw)
        self.opcoes = opcoes
        self.valor = valor or (opcoes[0][0] if opcoes else "")
        self.direita = direita or []
        self.valor_dir = valor_dir or (self.direita[0][0] if self.direita else "")
        self._x: list[tuple[int, int, str, bool]] = []

    def definir(self, opcoes: list[tuple[str, str]] | None = None, valor: str | None = None) -> None:
        if opcoes is not None:
            self.opcoes = opcoes
        if valor is not None:
            self.valor = valor
        self.refresh()

    def passo(self, d: int) -> str:
        ks = [k for k, _ in self.opcoes]
        if not ks:
            return ""
        i = ks.index(self.valor) if self.valor in ks else 0
        self.valor = ks[(i + d) % len(ks)]
        self.refresh()
        self.post_message(self.Mudou(self, self.valor))
        return self.valor

    def passo_dir(self, d: int) -> str:
        ks = [k for k, _ in self.direita]
        if not ks:
            return ""
        i = ks.index(self.valor_dir) if self.valor_dir in ks else 0
        self.valor_dir = ks[max(0, min(len(ks) - 1, i + d))]
        self.refresh()
        self.post_message(self.Mudou(self, "dir:" + self.valor_dir))
        return self.valor_dir

    def _pedaco(self, t: Text, rot: str, ativo: bool) -> None:
        a = self.app
        if ativo:
            t.append(f" {rot} ", style=f"bold {a.cor('fundo')} on {a.cor('accent')}")
        else:
            t.append(f" {rot} ", style=f"{a.cor('texto')} on {a.cor('campo')}")

    def render(self) -> Text:
        t = Text(no_wrap=True)
        self._x = []
        for n, (k, rot) in enumerate(self.opcoes):
            if n:
                t.append(" ")
            x0 = t.cell_len
            self._pedaco(t, rot, k == self.valor)
            self._x.append((x0, t.cell_len, k, False))
        if self.direita:
            d = Text(no_wrap=True)
            xs = []
            for n, (k, rot) in enumerate(self.direita):
                if n:
                    d.append(" ")
                x0 = d.cell_len
                self._pedaco(d, rot, k == self.valor_dir)
                xs.append((x0, d.cell_len, k))
            meio = max(1, self.size.width - t.cell_len - d.cell_len)
            base = t.cell_len + meio
            t.append(" " * meio)
            t.append_text(d)
            self._x += [(base + a0, base + b0, k, True) for a0, b0, k in xs]
        return t

    def on_click(self, ev: events.Click) -> None:
        for x0, x1, k, dir_ in self._x:
            if x0 <= ev.x < x1:
                ev.stop()
                if dir_:
                    self.valor_dir = k
                    self.post_message(self.Mudou(self, "dir:" + k))
                else:
                    self.valor = k
                    self.post_message(self.Mudou(self, k))
                self.refresh()
                return


class Pintado(Widget):
    """Texto calculado por uma função (`desenhar(largura) -> Text`). `pintar()` redesenha.

    Com `focavel=True` vira uma janela de leitura que aceita foco (herói, números, permissões)."""

    DEFAULT_CSS = "Pintado { height: auto; width: 1fr; } Pintado.-alto { height: 1fr; }"

    def __init__(self, desenhar, focavel: bool = False, ao_clicar=None, **kw) -> None:
        super().__init__(**kw)
        self.desenhar = desenhar
        self.can_focus = focavel
        self.ao_clicar = ao_clicar

    def pintar(self) -> None:
        self.refresh(layout=True)

    def get_content_height(self, container, viewport, width: int) -> int:
        try:
            return max(1, len(self.desenhar(width).split()))
        except Exception:
            return 1

    def render(self) -> Text:
        try:
            return self.desenhar(self.size.width)
        except Exception as e:  # um desenho com dado estranho não derruba a tela
            return Text(f"({type(e).__name__})", style=self.app.cor("mudo"))

    def on_click(self, ev: events.Click) -> None:
        if self.ao_clicar is not None:
            ev.stop()
            self.ao_clicar(ev)


class Regua(Widget):
    DEFAULT_CSS = "Regua { height: 1; width: 1fr; }"

    def render(self) -> Text:
        return Text("─" * self.size.width, style=self.app.cor("linha"))
