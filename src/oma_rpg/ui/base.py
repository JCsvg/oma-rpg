"""Base das janelas e das páginas.

Janela: borda fina; só a janela com o foco usa a cor de destaque (título e borda), as outras ficam em cinza. O título
leva um texto à direita na própria borda ("alt+4 skills", "meta 3 de 6"): o Textual só põe o subtítulo embaixo, então o
título é montado com o texto da esquerda, uma régua de ─ na cor da borda e o da direita (técnica do oma-mail).

Pagina: um dos sete painéis (ou a vista das classes). Só uma fica montada por vez. `VIZINHAS` é a tabela do Ctrl+setas
daquela página; "paineis" é a coluna da esquerda e "topo" a linha de cima.
"""

from __future__ import annotations

from rich.text import Text
from textual.containers import Vertical
from textual.markup import escape
from textual.widget import Widget


def pagina_de(w):
    """A página dona do widget (não a página aberta agora: na troca, a antiga ainda pinta uma última vez)."""
    for anc in (w, *w.ancestors):
        if isinstance(anc, Pagina):
            return anc
    return w.app.pagina


class Janela(Vertical):
    DEFAULT_CSS = """
    Janela { border: solid $rpg-linha; border-title-color: $rpg-mudo; border-title-align: left; padding: 0 1;
             height: 1fr; width: 1fr; background: $background; }
    Janela:focus, Janela:focus-within { border: solid $accent; border-title-color: $accent; border-title-style: bold; }
    """
    NOME = ""
    FOCAVEL = False
    pg = property(lambda self: pagina_de(self))

    def __init__(self, **kw) -> None:
        kw.setdefault("id", self.NOME)
        kw.setdefault("classes", "janela")
        super().__init__(**kw)
        if self.FOCAVEL:
            self.can_focus = True
        self._t_raw: tuple[str, Text | str] | None = None

    # ------------------------------------------------------------ título
    def titulo(self, esq: str, dir_: Text | str = "") -> None:
        if self._t_raw != (esq, dir_):
            self._t_raw = (esq, dir_)
            self.compor_titulo()

    def compor_titulo(self) -> None:
        if self._t_raw is None or not self.is_mounted:
            return
        a = self.app
        esq, dir_ = self._t_raw
        f = a.focused
        foco = f is not None and (f is self or self in f.ancestors)
        cor_linha = a.cor("accent") if foco else a.cor("linha")
        if isinstance(dir_, Text):
            dir_m = "".join(f"[{s.style}]{escape(t)}[/]" if s.style else escape(t)
                            for t, s in ((dir_.plain[sp.start:sp.end], sp) for sp in _spans(dir_)))
            dir_len = dir_.cell_len
        else:
            dir_m, dir_len = escape(str(dir_)), Text(str(dir_)).cell_len
        k = self.size.width - 6 - Text(esq).cell_len - dir_len - 2
        if not dir_len or k < 2:
            comp = escape(esq)
        else:
            comp = f"{escape(esq)} [not bold {cor_linha}]{'─' * k}[/] [not bold {a.cor('mudo')}]{dir_m}[/]"
        if self.border_title != comp:
            self.border_title = comp

    def on_resize(self) -> None:
        self.compor_titulo()

    # ------------------------------------------------------------ o que cada janela conta para o app
    def pintar(self) -> None:
        """Relê os dados e redesenha."""

    def rodape(self) -> list[tuple[str, str, str]]:
        """(tecla, rótulo, ação) para o rodapé: no máximo 5."""
        return []

    def teclas(self) -> list[tuple[str, str]]:
        """(tecla, o que faz) para o Ctrl+Espaço."""
        return []

    def focar_entrada(self) -> None:
        for w in self.query("*"):
            if w.focusable and w.display:
                w.focus()
                return
        if self.can_focus:
            self.focus()

    def alt_h(self, passo: int) -> None:
        pass

    def alt_v(self, passo: int) -> None:
        pass


def _spans(t: Text):
    """Pedaços de um Text com o estilo de cada um (inclusive o texto sem estilo)."""
    from rich.text import Span
    pos = 0
    saida = []
    for sp in sorted(t.spans, key=lambda s: s.start):
        if sp.start > pos:
            saida.append(Span(pos, sp.start, ""))
        saida.append(Span(sp.start, sp.end, str(sp.style)))
        pos = sp.end
    if pos < len(t.plain):
        saida.append(Span(pos, len(t.plain), ""))
    return saida


class Pagina(Widget):
    DEFAULT_CSS = "Pagina { width: 1fr; height: 1fr; layout: horizontal; }"
    NOME = ""
    TITULO = ""
    ENTRADA = ""
    VIZINHAS: dict[str, dict[str, str]] = {}
    TELA_CHEIA = False  # sem a coluna dos painéis (classes)
    pg = property(lambda self: self)

    def __init__(self, **kw) -> None:
        super().__init__(classes=f"pagina-{self.NOME}")

    def on_mount(self) -> None:
        self.call_after_refresh(self.app._depois_de_abrir, getattr(self.app, "_foco_pendente", ""))

    def pintar(self) -> None:
        for j in self.query(Janela):
            try:
                j.pintar()
            except Exception:  # uma janela com dado estranho não derruba a página
                import logging
                logging.getLogger("oma-rpg").exception("falha ao pintar %s", j.id)

    def janelas(self) -> list[str]:
        return [j.id for j in self.query(Janela)]

    def trilha(self) -> list[tuple[str, str]]:
        return [(self.TITULO, "")]

    def relogio(self) -> None:
        """Chamado a cada segundo enquanto há timer rodando (só a página do foco usa)."""
