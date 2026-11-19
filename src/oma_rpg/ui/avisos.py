"""Avisos no canto de baixo à direita (design: "+31 xp pomodoro 4 concluído", "combo x1.4", "commit +9 xp",
"conquista"). Copiado do oma-mail, com o texto já colorido por quem avisa."""

from __future__ import annotations

import time

from rich.text import Text
from textual import events
from textual.containers import Vertical
from textual.widget import Widget


class Aviso(Widget):
    DEFAULT_CSS = """
    Aviso { height: 3; width: auto; min-width: 36; max-width: 76; border: solid $rpg-linha; background: $background;
            padding: 0 1; margin-top: 1; visibility: visible; }
    Aviso.-erro { border: solid $error; }
    Aviso.-alerta { border: solid $warning; }
    """

    def __init__(self, texto: Text, segundos: float, tipo: str = "", ao_clicar=None) -> None:
        super().__init__(classes=f"-{tipo}" if tipo else "")
        self.texto = texto
        self.segundos = segundos
        self.inicio = time.monotonic()
        self.ao_clicar = ao_clicar

    @property
    def restante(self) -> float:
        return max(0.0, self.segundos - (time.monotonic() - self.inicio))

    def get_content_width(self, container, viewport) -> int:
        return min(72, self.texto.cell_len)

    def render(self) -> Text:
        t = self.texto.copy()
        t.no_wrap = True
        t.overflow = "ellipsis"
        return t

    def on_click(self, ev: events.Click) -> None:
        ev.stop()
        if self.ao_clicar is not None:
            self.ao_clicar()
        self.remove()


class Avisos(Vertical):
    DEFAULT_CSS = """
    Avisos { dock: bottom; layer: avisos; height: auto; width: 100%; align: right bottom; margin: 0 1 1 0;
             background: transparent; visibility: hidden; }
    """
    MAX = 4

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.5, self._tick, pause=True)

    def mostrar(self, aviso: Aviso) -> Aviso:
        avisos = list(self.query(Aviso))
        for velho in avisos[: max(0, len(avisos) - self.MAX + 1)]:
            velho.remove()
        self.mount(aviso)
        self._timer.resume()
        return aviso

    def _tick(self) -> None:
        avisos = list(self.query(Aviso))
        if not avisos:
            self._timer.pause()
            return
        for a in avisos:
            if a.restante <= 0:
                a.remove()
