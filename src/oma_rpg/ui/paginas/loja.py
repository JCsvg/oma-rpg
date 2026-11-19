"""Tela 7 · loja: categorias, a mochila, os itens da categoria e o detalhe com a conta do saldo. Bits são moeda do jogo,
sem valor fora dele. enter compra · u usa da mochila · +/- quantidade · alt+←→ categoria."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical

from oma_rpg.nucleo import consultas as C
from oma_rpg.ui import desenho as D
from oma_rpg.ui.base import Janela, Pagina
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lista import Lista
from oma_rpg.ui.widgets import Botao, Pintado

CATEGORIAS = [("consumivel", "consumíveis", "pocao"), ("cosmetico", "cosméticos", "cabide"), ("utilitario", "utilitários", "chave"),
              ("titulo", "títulos", "coroa"), ("tema", "temas do jogo", "grade")]
ICONE_ITEM = {"pocao": "pocao", "cafe": "cafe", "cadeado": "cadeado", "lampada": "lampada", "bau": "bau", "raio": "raio",
              "cabide": "cabide", "paleta": "paleta", "chave": "chave", "coroa": "coroa", "grade": "grade"}


class JanelaCategorias(Janela):
    NOME = "categorias"
    DEFAULT_CSS = "JanelaCategorias { height: 26; } JanelaCategorias Lista { margin-top: 1; height: 10; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, altura=2, id="cat-lista", cursor_sem_foco=True)
        yield Pintado(self._saldo, id="cat-saldo")

    def pintar(self) -> None:
        self.titulo("categorias")
        p = self.pg
        ks = [k for k, _, _ in CATEGORIAS]
        self.query_one(Lista).definir(ks, cursor=ks.index(p.categoria))
        self.query_one(Pintado).pintar()

    def _linha(self, k: str, i: int, est) -> list[Text]:
        a = self.app
        _, rot, icone = CATEGORIAS[i]
        sel = k == self.pg.categoria
        t = Text()
        t.append(ic(icone) + " ", style=a.cor("texto"))
        t.append(rot, style=f"bold {a.cor('forte')}" if sel else a.cor("texto"))
        n = Text(str(len(a.cfg.itens_da_categoria(k))), style=a.cor("mudo"))
        l = D.linha_lr(t, n, est.largura)
        if sel and not (est.cursor and est.foco):
            l.stylize(f"on {a.cor('selecao')}")
        return [l, Text("")]

    def _saldo(self, w: int) -> Text:
        a = self.app
        h = a.st.get("heroi") or {}
        hoje = int(a.b.escalar("SELECT SUM(bits) FROM ganhos WHERE dia = ? AND bits > 0", (a.hoje(),), 0))
        return D.juntar([Text("─" * w, style=a.cor("linha")), Text(""), Text("seus bits", style=a.cor("mudo")),
                         Text.assemble((ic("bits") + " ", a.cor("yellow")), (C.milhar(h.get("bits", 0)), f"bold {a.cor('forte')}")),
                         Text(""), Text("ganhos de hoje", style=a.cor("mudo")), Text(f"+{hoje} bits", style=a.cor("green")), Text(""),
                         Text("juros e bônus de arco", style=a.cor("mudo")), Text("entram à meia-noite", style=a.cor("mudo"))])

    def on_lista_destacado(self, ev: Lista.Destacado) -> None:
        ev.stop()
        self.pg.mudar_categoria(ev.item)

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.app.focar_janela("itens")

    def rodape(self):
        return [("↑↓", "categoria", "noop"), ("enter", "itens", "noop")]


class JanelaMochila(Janela):
    NOME = "mochila"
    DEFAULT_CSS = "JanelaMochila Lista { margin-top: 1; height: 1fr; } JanelaMochila #mochila-pe { height: 3; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, altura=2, id="mochila-lista", cursor_apagado=True)
        yield Pintado(self._pe, id="mochila-pe")

    def pintar(self) -> None:
        self.titulo("mochila", "u usa")
        a = self.app
        m = C.mochila(a.b)
        itens = sorted(m, key=lambda k: a.cfg.item(k)["ordem"]) if m else []
        self.query_one(Lista).definir([(k, m[k]) for k in itens if k in a.cfg["itens"]])
        self.query_one(Pintado).pintar()

    def _linha(self, it, i, est) -> list[Text]:
        a = self.app
        k, n = it
        d = a.cfg.item(k)
        t = Text()
        t.append(ic(ICONE_ITEM.get(d["icone"], "mochila")) + " ", style=a.cor(d["cor"]) if n else a.cor("mudo"))
        t.append(d["nome"], style=a.cor("texto") if n else a.cor("mudo"))
        return [D.linha_lr(t, Text(f"x{n}", style=a.cor("mudo")), est.largura), Text("")]

    def _pe(self, w: int) -> Text:
        return D.juntar([Text("itens de jogo, sem", style=self.app.cor("mudo")),
                         Text("valor real: só Bits", style=self.app.cor("mudo")), Text("do jogo.", style=self.app.cor("mudo"))])

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.pg.usar(ev.item[0])

    def atual(self):
        it = self.query_one(Lista).item_atual()
        return it[0] if it else None

    def rodape(self):
        return [("u", "usar", "noop"), ("enter", "usar", "noop")]


class JanelaItens(Janela):
    NOME = "itens"
    DEFAULT_CSS = "JanelaItens { width: 74; } JanelaItens Lista { margin-top: 1; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, altura=5, id="itens-lista", cursor_apagado=True)

    def pintar(self) -> None:
        a = self.app
        p = self.pg
        self.titulo(dict((k, r) for k, r, _ in CATEGORIAS)[p.categoria], "alt+←→ categoria")
        l = self.query_one(Lista)
        itens = a.cfg.itens_da_categoria(p.categoria)
        cursor = itens.index(p.item_alvo) if p.item_alvo in itens else None
        p.item_alvo = None
        l.definir(itens, cursor=cursor)
        p.mostrar(l.item_atual())

    def _linha(self, k: str, i: int, est) -> list[Text]:
        a = self.app
        d = a.cfg.item(k)
        w = est.largura
        h = a.st.get("heroi") or {}
        bits = h.get("bits", 0)
        m = C.mochila(a.b)
        posses = C.posses(a.b)
        cor = a.cor(d["cor"])
        icone = ic(ICONE_ITEM.get(d["icone"], "mochila"))
        caixa = ["┌────┐", f"│ {icone}  │" if len(icone) == 1 else f"│ {icone} │", "└────┘"]
        preco = Text(f"{d['preco']}", style=a.cor("texto"))
        preco.append(ic("bits"), style=a.cor("yellow"))
        falta = d["preco"] - bits
        dono = k in posses
        if d["categoria"] != "consumivel" and dono:
            preco = Text("seu" + (" · equipado" if self._equipado(k) else ""), style=a.cor("green"))
        elif falta > 0:
            preco = Text(f"{d['preco']}", style=a.cor("red"))
            preco.append(ic("bits"), style=a.cor("red"))
        tem = m.get(k, 0)
        if d["categoria"] == "consumivel":
            tem_txt = f"você tem {tem}" if tem else "você não tem"
        else:
            tem_txt = "comprado" if dono else "uma vez só"
        dentro = w - 10
        l1 = D.linha_lr(Text(d["nome"], style=f"bold {a.cor('forte')}"), preco, dentro)
        l2 = D.linha_lr(Text(d["desc"], style=a.cor("mudo")), Text(f"faltam {falta}", style=a.cor("red")) if falta > 0 and not dono
                        else Text(""), dentro)
        l3 = Text(tem_txt, style=a.cor("mudo"))
        linhas = []
        for n, (c, txt) in enumerate(zip(caixa, (l1, l2, l3))):
            t = Text("  ")
            t.append(c, style=a.cor("mudo") if n != 1 else cor)
            t.append("  ")
            t.append_text(txt)
            linhas.append(t)
        sel = est.cursor
        if sel:
            linhas = [Text("▌", style=a.cor("accent")) + l[1:] for l in linhas]
        return [Text("")] + linhas + [Text("")]

    def _equipado(self, k: str) -> bool:
        a = self.app
        d = a.cfg.item(k)
        h = C.heroi(a.b)
        col = {"moldura": "moldura", "cor_retrato": "cor_retrato", "titulo": "titulo", "tema_calor": "tema_calor"}.get(d["efeito"])
        return bool(h and col and h[col] == d["valor"])

    def on_lista_destacado(self, ev: Lista.Destacado) -> None:
        ev.stop()
        self.pg.mostrar(ev.item)

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.pg.action_comprar()

    def alt_h(self, passo: int) -> None:
        self.pg.passo_categoria(passo)

    def atual(self):
        return self.query_one(Lista).item_atual()

    def rodape(self):
        return [("enter", "comprar", "noop"), ("u", "usar da mochila", "noop"), ("↑↓", "item", "noop"), ("alt+←→", "categoria", "alt_h(1)")]

    def teclas(self):
        return [("↑ ↓", "escolhe o item"), ("enter", "compra (ou equipa, se já é seu)"), ("+ -", "quantidade"),
                ("u", "usa da mochila"), ("alt+← →", "categoria")]


class JanelaItem(Janela):
    NOME = "item"
    DEFAULT_CSS = """
    JanelaItem #item-corpo { height: auto; }
    JanelaItem #item-botoes { height: auto; margin-top: 1; }
    JanelaItem #item-botoes Botao { margin-bottom: 1; }
    JanelaItem #item-dica { height: auto; margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Pintado(self._desenhar, id="item-corpo")
        with Vertical(id="item-botoes"):
            yield Botao("", id="b-comprar", classes="cheio")
            yield Botao("+/-  quantidade", id="b-qtd")
        yield Pintado(self._dica, id="item-dica")

    def mostrar(self, k: str | None) -> None:
        self.k = k
        self.titulo("item", "enter compra")
        a = self.app
        p = self.pg
        if k:
            d = a.cfg.item(k)
            dono = k in C.posses(a.b)
            b = self.query_one("#b-comprar", Botao)
            if d["categoria"] != "consumivel" and dono:
                b.label = "enter  " + ("tirar" if JanelaItens._equipado(self, k) else "equipar") if d["categoria"] != "utilitario" else "já é seu"
            else:
                b.label = f"enter  comprar {p.qtd}"
            self.query_one("#b-qtd", Botao).display = d["categoria"] == "consumivel"
        for w in self.query(Pintado):
            w.pintar()

    def _desenhar(self, w: int) -> Text:
        a = self.app
        k = getattr(self, "k", None)
        if not k:
            return Text("")
        d = a.cfg.item(k)
        p = self.pg
        h = a.st.get("heroi") or {}
        cor = a.cor(d["cor"])
        icone = ic(ICONE_ITEM.get(d["icone"], "mochila"))
        caixa = ["┌──────────┐", "│          │", f"│    {icone}     │" if len(icone) == 1 else f"│    {icone}    │", "│          │",
                 "└──────────┘"]
        tem = C.mochila(a.b).get(k, 0)
        lado = [Text(d["nome"], style=f"bold {a.cor('forte')}"),
                Text(dict((x, r) for x, r, _ in CATEGORIAS)[d["categoria"]].rstrip("s").replace("consumívei", "consumível"),
                     style=a.cor("mudo")),
                Text(""), Text.assemble((ic("bits") + " ", a.cor("yellow")), (str(d["preco"]), f"bold {a.cor('forte')}")),
                Text(f"você tem {tem}" if d["categoria"] == "consumivel" else ("é seu" if k in C.posses(a.b) else ""), style=a.cor("mudo"))]
        linhas = [Text("")]
        for i in range(5):
            t = Text(" ")
            t.append(caixa[i], style=cor if i == 2 else a.cor("mudo"))
            t.append("  ")
            t.append_text(lado[i])
            linhas.append(t)
        linhas += [Text(""), D.secao(a, "efeito", w), Text("")]
        linhas += D.quebrar(d["detalhe"], w, a.cor("texto"))
        total = d["preco"] * (p.qtd if d["categoria"] == "consumivel" else 1)
        saldo = h.get("bits", 0)
        if not (d["categoria"] != "consumivel" and k in C.posses(a.b)):
            linhas += [Text(""), D.secao(a, "compra", w), Text("")]
            linhas.append(D.linha_lr(Text("saldo agora", style=a.cor("mudo")), Text(C.milhar(saldo), style=a.cor("texto")), w))
            linhas.append(D.linha_lr(Text("preço" + (f" x{p.qtd}" if p.qtd > 1 else ""), style=a.cor("mudo")),
                                     Text(f"-{C.milhar(total)}", style=a.cor("yellow")), w))
            depois = saldo - total
            linhas.append(D.linha_lr(Text("saldo depois", style=a.cor("mudo")),
                                     Text(C.milhar(depois) if depois >= 0 else f"faltam {C.milhar(-depois)}",
                                          style=f"bold {a.cor('forte') if depois >= 0 else a.cor('red')}"), w))
        return D.juntar(linhas)

    def _dica(self, w: int) -> Text:
        a = self.app
        k = getattr(self, "k", None)
        if not k:
            return Text("")
        return D.juntar([D.secao(a, "dica do Mestre", w), Text("")] + D.quebrar(a.cfg.item(k)["dica"], w, a.cor("mudo")))

    def on_botao_apertado(self, ev: Botao.Apertado) -> None:
        ev.stop()
        p = self.pg
        if ev.botao.id == "b-qtd":
            p.action_qtd(1)
        else:
            p.action_comprar()

    def rodape(self):
        return [("enter", "comprar", "noop"), ("+/-", "quantidade", "noop")]


class PaginaLoja(Pagina):
    NOME = "loja"
    TITULO = "loja"
    ENTRADA = "itens"
    VIZINHAS = {
        "categorias": {"esq": "paineis", "dir": "itens", "cima": "topo", "baixo": "mochila"},
        "mochila": {"esq": "paineis", "dir": "itens", "cima": "categorias"},
        "itens": {"esq": "categorias", "dir": "item", "cima": "topo"},
        "item": {"esq": "itens", "cima": "topo"},
    }
    BINDINGS = [Binding("u", "usar", show=False), Binding("plus,equals_sign", "qtd(1)", show=False),
                Binding("minus", "qtd(-1)", show=False)]
    DEFAULT_CSS = "PaginaLoja #l-esq { width: 27; } PaginaLoja JanelaItem { width: 1fr; }"

    def __init__(self, item: str | None = None, **kw) -> None:
        super().__init__()
        self.categoria = "consumivel"
        self.qtd = 1
        self.item_alvo = item

    def compose(self) -> ComposeResult:
        with Vertical(id="l-esq"):
            yield JanelaCategorias()
            yield JanelaMochila()
        yield JanelaItens()
        yield JanelaItem()

    def on_mount(self) -> None:
        if self.item_alvo in self.app.cfg["itens"]:
            self.categoria = self.app.cfg.item(self.item_alvo)["categoria"]

    def mostrar(self, k) -> None:
        try:
            self.query_one(JanelaItem).mostrar(k)
        except Exception:
            pass

    def mudar_categoria(self, k: str) -> None:
        if k != self.categoria:
            self.categoria = k
            self.qtd = 1
            self.query_one(JanelaItens).pintar()
            self.query_one(JanelaCategorias).query_one(Lista).redesenhar()

    def passo_categoria(self, passo: int) -> None:
        ks = [k for k, _, _ in CATEGORIAS]
        self.mudar_categoria(ks[(ks.index(self.categoria) + passo) % len(ks)])
        self.query_one(JanelaCategorias).query_one(Lista).mover_cursor(ks.index(self.categoria), avisar=False)

    def rodape_pagina(self):
        return [("enter", "comprar", "noop"), ("u", "usar da mochila", "usar"), ("↑↓", "item", "noop"), ("alt+←→", "categoria", "noop")]

    def action_comprar(self) -> None:
        a = self.app
        k = self.query_one(JanelaItens).atual()
        if not k:
            return
        d = a.cfg.item(k)
        if d["categoria"] != "consumivel" and k in C.posses(a.b):
            if d["categoria"] != "utilitario":
                a.pedir("equipar", {"item": k})
            return
        a.pedir("comprar", {"item": k, "qtd": self.qtd if d["categoria"] == "consumivel" else 1},
                lambda ok, r: setattr(self, "qtd", 1) if ok else None)

    def action_qtd(self, d: int) -> None:
        self.qtd = max(1, min(20, self.qtd + d))
        self.mostrar(self.query_one(JanelaItens).atual())

    def action_usar(self) -> None:
        a = self.app
        k = self.query_one(JanelaMochila).atual() if a.nome_janela(a.focused) == "mochila" else self.query_one(JanelaItens).atual()
        if k:
            self.usar(k)

    def usar(self, k: str) -> None:
        a = self.app
        if a.cfg.item(k)["categoria"] != "consumivel" or C.mochila(a.b).get(k, 0) <= 0:
            a.avisar("não tem na mochila", alerta=True)
            return
        if a.cfg.item(k)["efeito"] == "respec_total":
            from oma_rpg.ui.dialogos import Confirmar
            a.push_screen(Confirmar("elixir de respec", ["Desaprender todas as skills e receber os pontos de volta?"], "usar"),
                          lambda ok: ok and a.pedir("usar_item", {"item": k}))
            return
        a.pedir("usar_item", {"item": k})


PAGINA = PaginaLoja
