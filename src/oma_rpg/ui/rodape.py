"""Rodapé: até 5 teclas da janela em foco (clicáveis) à esquerda e o lembrete fixo à direita. Vem do oma-mail."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.widget import Widget


class Rodape(Widget):
    DEFAULT_CSS = "Rodape { height: 1; width: 1fr; }"

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self._x: list[tuple[int, int, str]] = []

    def pintar(self) -> None:
        self.refresh()

    def _itens(self) -> list[tuple[str, str, str]]:
        try:
            return list(self.app.itens_rodape())[:5]
        except Exception:
            return []

    def render(self) -> Text:
        a = self.app
        w = self.size.width
        acc, mudo = a.cor("accent"), a.cor("mudo")
        esq = Text(no_wrap=True)
        self._x = []
        for tecla, rot, acao in self._itens():
            if esq.cell_len:
                esq.append("   ")
            x0 = esq.cell_len
            esq.append(tecla, style=acc)
            esq.append(" " + rot, style=mudo)
            self._x.append((x0, esq.cell_len, acao))
        dir_ = [("ctrl+hjkl", "janelas", "janela('dir')"), ("ctrl+espaço", "ajuda", "teclas")]
        d = Text(no_wrap=True)
        xs = []
        for tecla, rot, acao in dir_:
            if d.cell_len:
                d.append("   ")
            x0 = d.cell_len
            d.append(tecla, style=acc)
            d.append(" " + rot, style=mudo)
            xs.append((x0, d.cell_len, acao))
        if esq.cell_len + d.cell_len + 2 > w:
            esq.truncate(max(0, w - d.cell_len - 2), overflow="ellipsis")
        meio = max(1, w - esq.cell_len - d.cell_len)
        self._x += [(a0 + esq.cell_len + meio, b0 + esq.cell_len + meio, acao) for a0, b0, acao in xs]
        return esq + Text(" " * meio) + d

    async def on_click(self, ev: events.Click) -> None:
        for x0, x1, acao in self._x:
            if x0 <= ev.x < x1:
                await self.app.run_action(acao)
                return
