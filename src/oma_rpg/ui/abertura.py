"""Tela 11 · abertura: OMA RPG em letras de pixel, os ícones das 6 classes e o resumo. Uma vez por boot, como no
oma-mail e no oma-docker (marcador em $XDG_RUNTIME_DIR, que some no reboot)."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from oma_rpg.ui.fonte import pixels
from oma_rpg.ui.icones import ic


class Abertura(Screen[None]):
    DEFAULT_CSS = """
    Abertura { align: center middle; background: $background; }
    Abertura #conteudo { width: auto; height: auto; align-horizontal: center; }
    Abertura #logo { color: $accent; width: auto; }
    Abertura #classes { margin-top: 1; width: 100%; text-align: center; }
    Abertura #sub { color: $rpg-mudo; margin-top: 1; width: 100%; text-align: center; }
    """

    def __init__(self, versao: str = "") -> None:
        super().__init__()
        self.versao = versao

    def compose(self) -> ComposeResult:
        a = self.app
        w, _ = a.size
        logo = pixels("OMA RPG") if w >= 44 else ["OMA RPG"]
        icones = Text()
        for n, cid in enumerate(a.cfg.classes_ordem()):
            if n:
                icones.append(" ")
            icones.append(ic(cid), style=a.cor(a.cfg.classe(cid)["cor"]))
        with Vertical(id="conteudo"):
            yield Static(Text("\n".join(logo), style=f"bold {a.cor('accent')}"), id="logo")
            yield Static(icones, id="classes")
            yield Static(Text(f"Estude, ganhe XP e suba de nível. {self.versao}\nQualquer tecla ou clique entra"), id="sub")

    def on_mount(self) -> None:
        self.set_timer(1.5, self._sair)

    def _sair(self) -> None:
        if self.is_current:
            self.dismiss(None)

    def on_key(self, ev: events.Key) -> None:
        ev.stop()
        self._sair()

    def on_click(self, ev: events.Click) -> None:
        self._sair()
