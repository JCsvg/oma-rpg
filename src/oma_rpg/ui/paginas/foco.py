"""Tela 3 · foco: o pomodoro rodando. Timer grande, "pomodoro 4 de 4", XP previsto, skills ativas (1 a 4), commits
feitos dentro do pomodoro, notas rápidas e a fila. espaço pausa · 1-4 usa skill · x abandona · alt+↑↓ fila · n anota."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical

from oma_rpg.nucleo import consultas as C
from oma_rpg.nucleo import regras
from oma_rpg.ui import desenho as D
from oma_rpg.ui.base import Janela, Pagina
from oma_rpg.ui.fonte import pixels
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lista import Lista, ajustar
from oma_rpg.ui.widgets import Botao, Pintado


def _quest_atual(a):
    row = a._atual_row
    if row is None or not row["quest_id"]:
        g = row["guardado_quest"] if row is not None else None
        if g:
            return a.b.um("SELECT * FROM quests WHERE id = ?", (g,))
        f = C.fila(a.b, a.cfg, a.hoje())
        return a.b.um("SELECT * FROM quests WHERE id = ?", (f[0]["id"],)) if f else None
    return a.b.um("SELECT * FROM quests WHERE id = ?", (row["quest_id"],))


class JanelaFoco(Janela):
    NOME = "foco"
    DEFAULT_CSS = """
    JanelaFoco { width: 90; height: 30; }
    JanelaFoco #foco-topo { height: 3; margin-top: 1; }
    JanelaFoco #foco-timer { height: 10; content-align: center top; }
    JanelaFoco #foco-quadros { height: 7; }
    JanelaFoco #foco-botoes { height: 1; margin: 1 0 1 0; }
    JanelaFoco #foco-botoes Botao { margin-right: 2; }
    JanelaFoco #foco-pe { height: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Pintado(self._topo, id="foco-topo")
        yield Pintado(self._timer, id="foco-timer")
        yield Pintado(self._quadros, id="foco-quadros")
        with Horizontal(id="foco-botoes"):
            yield Botao("", id="b-pausar", classes="cheio")
            yield Botao("", id="b-abandonar")
            yield Botao("", id="b-pular")
        yield Pintado(self._pe, id="foco-pe")

    def pintar(self) -> None:
        a = self.app
        p = a.st.get("pomodoro") or {}
        por = a.cfg["pomodoro"]["por_sessao"]
        fase = p.get("fase", "parado")
        n = p.get("n", 0) + (1 if fase in ("foco", "parado") else 0)
        sub = {"pausa": "pausa curta", "longa": "pausa longa", "desmaio": "desmaiado"}.get(fase, f"pomodoro {min(n, por)} de {por}")
        self.titulo("foco", sub)
        self._botoes()
        for w in self.query(Pintado):
            w.pintar()

    def relogio(self) -> None:
        self.query_one("#foco-timer", Pintado).refresh()
        self.query_one("#foco-quadros", Pintado).refresh()
        self.query_one("#foco-topo", Pintado).refresh()

    def _botoes(self) -> None:
        a = self.app
        p = a.st.get("pomodoro") or {}
        fase = p.get("fase", "parado")
        bp, ba, bs = (self.query_one(f"#{i}", Botao) for i in ("b-pausar", "b-abandonar", "b-pular"))
        if fase == "foco":
            bp.label = f"{ic('play')} espaço continuar" if p.get("pausado") else f"{ic('pausa')} espaço pausar"
        elif fase in ("pausa", "longa"):
            bp.label = f"{ic('play')} espaço começar já"
        elif fase == "desmaio":
            bp.label = f"{ic('vida')} espaço acordar"
        else:
            bp.label = f"{ic('play')} espaço " + ("retomar" if p.get("guardado") else "começar")
        ba.label = f"{ic('parar')} x abandonar"
        ba.disabled = fase != "foco"
        bs.label = f"{ic('play')} s pular pausa"
        bs.disabled = fase not in ("pausa", "longa")

    def _topo(self, w: int) -> Text:
        a = self.app
        q = _quest_atual(a)
        if q is None:
            return D.juntar([Text("pomodoro livre", style=f"bold {a.cor('forte')}"),
                             Text("sem quest na fila: n cria uma, ou o XP fica só do pomodoro", style=a.cor("mudo"))])
        t2 = Text()
        t2.append(q["materia"] or "sem matéria", style=f"underline {a.cor(C.cor_materia(a.b, q['materia']))}")
        if q["arco_id"]:
            ids = [r[0] for r in a.b.todos("SELECT id FROM quests WHERE arco_id = ? AND estado IN ('aberta','feita') "
                                           "ORDER BY ordem, id", (q["arco_id"],))]
            t2.append(f"  quest {ids.index(q['id']) + 1 if q['id'] in ids else 1} de {len(ids)} do arco · ", style=a.cor("mudo"))
        else:
            t2.append("  ", style=a.cor("mudo"))
        t2.append(f"est. {q['est']} pomodoro{'s' if q['est'] > 1 else ''} · ", style=a.cor("mudo"))
        t2.append(regras.DIAMANTES[q["dif"]][: q["dif"]], style=a.cor("yellow"))
        t2.append(" dificuldade", style=a.cor("mudo"))
        return D.juntar([Text(q["titulo"], style=f"bold {a.cor('forte')}"), t2])

    def _timer(self, w: int) -> Text:
        a = self.app
        p = a.st.get("pomodoro") or {}
        fase = p.get("fase", "parado")
        pc = a.cfg["pomodoro"]
        if fase in C.FASES_RODANDO:
            rest, dec = a.restante(), a.decorrido()
            total = rest + dec
        else:
            g = a._atual_row["guardado_seg"] if a._atual_row is not None else 0
            total = pc["minutos_foco"] * 60
            dec, rest = g, total - g
        cor = {"foco": "green", "pausa": "blue", "longa": "blue", "desmaio": "red"}.get(fase, "mudo")
        if fase == "foco" and p.get("pausado"):
            cor = "yellow"
        linhas = [Text("")]
        for l in pixels(C.mmss(rest), largura_px=2, espaco=1):
            linhas.append(ajustar(Text(l, style=a.cor(cor)), w, "center"))
        linhas.append(Text(""))
        larg = min(60, w - 4)
        margem = " " * ((w - larg) // 2)
        cor_b = "green" if fase == "foco" else "blue" if fase in ("pausa", "longa") else "red" if fase == "desmaio" else "mudo"
        linhas.append(Text(margem) + D.barra(a, dec, total, larg, cor_b, "▄"))
        rot = "decorridos" if fase != "desmaio" else "desmaiado"
        linhas.append(Text(margem) + D.linha_lr(Text(f"{C.mmss(dec)} {rot}", style=a.cor("mudo")),
                                                Text(f"{C.mmss(rest)} restantes", style=a.cor("texto")), larg))
        linhas.append(Text(""))
        n = p.get("n", 0)
        por = pc["por_sessao"]
        t = Text("sessão ", style=a.cor("mudo"))
        for i in range(por):
            if i:
                t.append(" ─ ", style=a.cor("linha"))
            if i < n:
                t.append("●", style=a.cor("green"))
            elif i == n and fase == "foco":
                t.append("●", style=a.cor("yellow"))
            else:
                t.append("○", style=a.cor("mudo"))
        prox = "pausa longa de 15 min" if n + 1 >= por else "pausa curta de 5 min"
        if fase in ("pausa", "longa"):
            prox = "alongar e beber água"
        t.append(f"   {prox}", style=a.cor("mudo"))
        linhas.append(t)
        return D.juntar(linhas)

    def _quadros(self, w: int) -> Text:
        a = self.app
        h = a.st.get("heroi")
        if not h:
            return Text("")
        hrow = C.heroi(a.b)
        P = C.passivos(a.b, a.cfg, a.hoje(), hrow)
        p = a.st.get("pomodoro") or {}
        fase = p.get("fase", "parado")
        inicio = a._atual_row["inicio"] if fase == "foco" else a.agora()
        cmb = C.combo_de(a.cfg, hrow, P, inicio)
        extra = C.efeito(a.b, "proximo_xp") + C.efeito(a.b, "arriscar")
        ot = C.feitos_dia(a.b, a.hoje()) >= C.teto(a.cfg, P)
        xp = regras.xp_pomodoro(a.cfg, cmb, P["xp_pomodoro"] + extra, ot)
        base = a.cfg["pomodoro"]["xp_base"]
        mp_ganho = a.cfg["pomodoro"]["mp_pausa_longa" if p.get("n", 0) + 1 >= a.cfg["pomodoro"]["por_sessao"] else "mp_pausa_curta"] \
            + int(P["mp_pausa"])
        mp_fim = min(h["mp_max"], h["mp"] + mp_ganho)
        prox = regras.combo(C.seguidos_validos(a.cfg, hrow, inicio) + 1, a.cfg, hrow["classe"] == "gamer", P["combo_max"])
        larg = max(20, (w - 4) // 3)
        quadros = [
            [Text("xp previsto", style=a.cor("mudo")), Text(f"+{xp}", style=f"bold {a.cor('green')}"),
             Text(f"{base} base x combo {cmb:.1f}" + (f" +{extra:.0f}%" if extra else "") + (" · overtraining" if ot else ""),
                  style=a.cor("mudo"))],
            [Text("mana ao fim", style=a.cor("mudo")), Text(f"+{mp_fim - h['mp']}", style=f"bold {a.cor('blue')}"),
             Text(f"{h['mp']} → {mp_fim} de {h['mp_max']}", style=a.cor("mudo"))],
            [Text("combo", style=a.cor("mudo")), Text(f"x{cmb:.1f} → x{prox:.1f}", style=f"bold {a.cor('yellow')}"),
             Text("se terminar sem abandonar", style=a.cor("mudo"))],
        ]
        caixas = [D.caixa(a, q, larg) for q in quadros]
        linhas = []
        for i in range(len(caixas[0])):
            t = Text(" ")
            for n, c in enumerate(caixas):
                if n:
                    t.append("  ")
                t.append_text(c[i])
            linhas.append(t)
        return D.juntar(linhas)

    def _pe(self, w: int) -> Text:
        a = self.app
        pc = a.cfg["pomodoro"]
        return Text(f"abandonar antes de {pc['abandono_livre_min']} min não custa HP; depois custa {pc['abandono_hp']} HP e zera "
                    "o combo", style=a.cor("mudo"))

    def on_botao_apertado(self, ev: Botao.Apertado) -> None:
        ev.stop()
        pg = self.pg
        {"b-pausar": pg.action_espaco, "b-abandonar": pg.action_abandonar, "b-pular": pg.action_pular}[ev.botao.id]()

    def focar_entrada(self) -> None:
        self.query_one("#b-pausar", Botao).focus()

    def rodape(self):
        return [("espaço", "pausar", "noop"), ("1-4", "skills", "noop"), ("x", "abandonar", "noop"), ("alt+↑↓", "fila", "noop"),
                ("n", "nota", "noop")]

    def teclas(self):
        return [("espaço", "começa, pausa ou continua o pomodoro"), ("x", "abandona (pergunta antes)"),
                ("s", "pula a pausa (sem a mana da pausa)"), ("1 a 4", "usa a skill ativa daquele número"),
                ("n", "nota rápida no pomodoro"), ("alt+↑ alt+↓", "move a quest na fila")]


class JanelaNeste(Janela):
    NOME = "neste"
    DEFAULT_CSS = "JanelaNeste Lista { margin-top: 1; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, id="neste-lista", selecionavel=lambda it: it[0] in ("commit", "nota"), cursor_apagado=True)

    def pintar(self) -> None:
        a = self.app
        repos = a.b.todos("SELECT caminho FROM repos")
        onde = _pasta_comum([r[0] for r in repos]) if repos else "nenhum repositório"
        self.titulo("neste pomodoro", f"commits observados em {onde}")
        row = a._atual_row
        itens = []
        ini = row["inicio"] if row is not None and row["fase"] == "foco" else None
        if ini:
            for c in a.b.todos("SELECT * FROM commits WHERE pomodoro_inicio = ? ORDER BY ts", (ini,)):
                itens.append(("commit", c))
        else:
            itens.append(("vazio", "nenhum pomodoro rodando"))
        if not [i for i in itens if i[0] == "commit"] and ini:
            itens.append(("vazio", "nenhum commit neste pomodoro ainda"))
        soltos = a.b.todos("SELECT c.*, r.nome FROM commits c JOIN repos r ON r.id = c.repo_id WHERE c.dia = ? AND c.vinculado = 0",
                           (a.hoje(),))
        itens.append(("branco", ""))
        if soltos:
            n = len(soltos)
            itens.append(("info", f"{n} commit{'s' if n > 1 else ''} fora do pomodoro em {soltos[0]['nome']} "
                                  f"conta{'m' if n > 1 else ''} {int(a.cfg['commit']['fator_solto'] * 100)}%"))
        itens.append(("branco", ""))
        itens.append(("secao", "notas rápidas"))
        itens.append(("branco", ""))
        dia = a.hoje()
        for r in a.b.todos("SELECT * FROM notas WHERE dia = ? ORDER BY ts", (dia,)):
            itens.append(("nota", r))
        itens.append(("branco", ""))
        itens.append(("info", "o Mestre lê as notas na revisão semanal"))
        self.query_one(Lista).definir(itens)

    def _linha(self, it, i: int, est) -> list[Text]:
        a = self.app
        tipo, v = it
        w = est.largura
        if tipo == "commit":
            t = Text(C.hora(v["ts"]) + " ", style=a.cor("mudo"))
            t.append(ic("commit") + " ", style=a.cor("blue"))
            t.append(v["hash"][:7] + " ", style=a.cor("yellow"))
            t.append(v["assunto"], style=a.cor("texto"))
            d = Text(f"+{v['mais']} -{v['menos']}  ", style=a.cor("mudo"))
            d.append("✓" if v["xp"] else "·", style=a.cor("green") if v["xp"] else a.cor("mudo"))
            d.append(f"   +{v['xp']} xp", style=a.cor("green") if v["xp"] else a.cor("mudo"))
            return [D.linha_lr(t, d, w)]
        if tipo == "nota":
            return [Text("• " + v["texto"], style=a.cor("texto"))]
        if tipo == "secao":
            return [D.secao(a, v, w, "n adiciona")]
        if tipo in ("info", "vazio"):
            return [Text(v, style=a.cor("mudo"))]
        return [Text("")]

    def rodape(self):
        return [("n", "nota", "noop")]


def _pasta_comum(caminhos: list[str]) -> str:
    import os
    if len(caminhos) == 1:
        return caminhos[0].replace(os.path.expanduser("~"), "~")
    comum = os.path.commonpath(caminhos) if caminhos else ""
    comum = comum.replace(os.path.expanduser("~"), "~")
    return comum if comum and comum not in ("/", "~") else f"{len(caminhos)} repositórios"


class JanelaAtivas(Janela):
    NOME = "ativas"
    DEFAULT_CSS = "JanelaAtivas { height: 20; } JanelaAtivas #mana-barra { height: 2; margin-top: 1; }"

    def compose(self) -> ComposeResult:
        yield Pintado(self._mana, id="mana-barra")
        yield Lista(self._linha, altura=4, id="ativas-lista", cursor_apagado=True)

    def pintar(self) -> None:
        a = self.app
        h = a.st.get("heroi") or {}
        self.titulo("skills ativas", f"mana {h.get('mp', 0)}/{h.get('mp_max', 0)}")
        hrow = C.heroi(a.b)
        self.query_one(Lista).definir(C.ativas(a.b, a.cfg, hrow) if hrow else [])
        self.query_one(Pintado).pintar()

    def _mana(self, w: int) -> Text:
        a = self.app
        h = a.st.get("heroi") or {}
        return D.barra(a, h.get("mp", 0), h.get("mp_max", 1), w, "blue", "▄")

    def _linha(self, sid: str, i: int, est) -> list[Text]:
        a = self.app
        s = a.cfg.skill(sid)
        hrow = C.heroi(a.b)
        P = C.passivos(a.b, a.cfg, a.hoje(), hrow)
        custo = C.custo_mana(a.cfg, s, P)
        t = Text(f"{i + 1} ", style=a.cor("green"))
        t.append(s["nome"], style=f"bold {a.cor('forte')}")
        l1 = D.linha_lr(t, Text(f"{custo} mp", style=a.cor("blue")), est.largura)
        usada = C.uso_hoje(a.b, sid, a.hoje())
        if usada:
            st = Text(f"  usada hoje às {C.hora(usada)}", style=a.cor("mudo"))
        elif hrow["mp"] < custo:
            st = Text("  mana insuficiente", style=a.cor("red"))
        else:
            st = Text("  pronta", style=a.cor("green"))
        return [l1, Text("  " + s["desc"], style=a.cor("mudo")), st, Text("")]

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.pg.usar(ev.indice + 1)

    def rodape(self):
        return [("enter", "usar", "noop"), ("1-4", "usar", "noop")]


class JanelaFila(Janela):
    NOME = "fila"
    DEFAULT_CSS = "JanelaFila Lista { margin-top: 1; height: auto; max-height: 14; } JanelaFila #fila-pe { height: auto; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, altura=3, id="fila-lista", arrastar=True, cursor_apagado=True)
        yield Pintado(self._pe, id="fila-pe")

    def pintar(self) -> None:
        a = self.app
        self.titulo("próximos pomodoros", "alt+↑↓ reordena")
        self.query_one(Lista).definir(C.fila(a.b, a.cfg, a.hoje()))
        self.query_one(Pintado).pintar()

    def _linha(self, q: dict, i: int, est) -> list[Text]:
        a = self.app
        p = a.st.get("pomodoro") or {}
        atual = p.get("fase") == "foco" and a._atual_row is not None and a._atual_row["quest_id"] == q["id"]
        t = Text(ic("troca") + " ", style=a.cor("mudo"))
        t.append((ic("andamento") if atual else ic("pendente")) + " ", style=a.cor("yellow") if atual else a.cor("texto"))
        t.append(q["titulo"], style=f"bold {a.cor('forte')}" if atual else a.cor("texto"))
        falta = max(0, q["est"] - q["feitos"])
        d = Text("agora", style=a.cor("yellow")) if atual else Text.assemble((str(falta), a.cor("mudo")), (" ●", a.cor("mudo")))
        return [D.linha_lr(t, d, est.largura), Text("    " + (q["materia"] or "sem matéria"), style=a.cor("mudo")), Text("")]

    def _pe(self, w: int) -> Text:
        a = self.app
        st = a.st.get("hoje") or {}
        feitos, meta = st.get("pomodoros", 0), st.get("meta", 6)
        rodando = (a.st.get("pomodoro") or {}).get("fase") == "foco"
        linhas = [Text("")]
        if rodando:
            linhas.append(Text(f"meta de hoje: {feitos} de {meta} feitos, este é o {feitos + 1}º", style=a.cor("texto")))
            linhas.append(Text(f"faltam {max(0, meta - feitos - 1)} depois deste", style=a.cor("mudo")))
        else:
            linhas.append(Text(f"meta de hoje: {feitos} de {meta} feitos", style=a.cor("texto")))
            linhas.append(Text(f"faltam {max(0, meta - feitos)}", style=a.cor("mudo")))
        linhas += [Text(""), Text("─" * w, style=a.cor("linha")),
                   Text("pausa curta (5 min) · alongar e beber água", style=a.cor("mudo")),
                   Text("pausa bem feita restaura HP (Slice of Life, Rato)", style=a.cor("mudo"))]
        return D.juntar(linhas)

    def alt_v(self, passo: int) -> None:
        l = self.query_one(Lista)
        q = l.item_atual()
        if q is None:
            return
        alvo = max(0, min(len(l.itens) - 1, l.cursor + passo))

        def depois(ok, r):
            if ok:
                self.app.atualizar()
                self.call_after_refresh(l.mover_cursor, alvo)
        self.app.pedir("mover_fila", {"id": q["id"], "passo": passo}, depois)

    def on_lista_arrastado(self, ev: Lista.Arrastado) -> None:
        ev.stop()
        ids = [q["id"] for q in self.query_one(Lista).itens]
        ids.insert(ev.destino, ids.pop(ev.indice))
        self.app.pedir("ordenar_fila", {"ids": ids}, lambda ok, r: ok and self.app.atualizar())

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        a = self.app
        if (a.st.get("pomodoro") or {}).get("fase") in ("parado", "pausa", "longa"):
            a.pedir("iniciar", {"quest": ev.item["id"]})

    def rodape(self):
        return [("enter", "começar nesta", "noop"), ("alt+↑↓", "reordena", "noop")]

    def teclas(self):
        return [("alt+↑ alt+↓", "sobe ou desce a quest na fila"), ("arrastar", "o mouse também reordena"),
                ("enter", "começa o pomodoro nesta quest")]


class PaginaFoco(Pagina):
    NOME = "foco"
    TITULO = "foco"
    ENTRADA = "foco"
    VIZINHAS = {
        "foco": {"esq": "paineis", "dir": "ativas", "cima": "topo", "baixo": "neste"},
        "neste": {"esq": "paineis", "dir": "fila", "cima": "foco"},
        "ativas": {"esq": "foco", "cima": "topo", "baixo": "fila"},
        "fila": {"esq": "neste", "cima": "ativas"},
    }
    BINDINGS = [Binding("space", "espaco", show=False), Binding("x", "abandonar", show=False), Binding("s", "pular", show=False),
                Binding("n", "nota", show=False), *[Binding(str(n), f"skill({n})", show=False) for n in range(1, 5)]]
    DEFAULT_CSS = "PaginaFoco #col-esq { width: 90; } PaginaFoco #col-dir { width: 1fr; } PaginaFoco JanelaAtivas { width: 1fr; }"

    def compose(self) -> ComposeResult:
        with Vertical(id="col-esq"):
            yield JanelaFoco()
            yield JanelaNeste()
        with Vertical(id="col-dir"):
            yield JanelaAtivas()
            yield JanelaFila()

    def relogio(self) -> None:
        self.query_one(JanelaFoco).relogio()

    def rodape_pagina(self):
        return [("espaço", "pausar", "espaco"), ("1-4", "skills", "noop"), ("x", "abandonar", "abandonar"),
                ("alt+↑↓", "fila", "noop"), ("n", "nota", "nota")]

    def action_espaco(self) -> None:
        a = self.app
        p = a.st.get("pomodoro") or {}
        fase = p.get("fase", "parado")
        if fase == "foco":
            a.pedir("pausar")
        elif fase == "desmaio":
            a.pedir("acordar")
        else:
            l = self.query_one("#fila-lista", Lista)
            q = l.item_atual() if a.nome_janela(a.focused) == "fila" else None
            a.pedir("iniciar", {"quest": q["id"]} if q else {})

    def action_abandonar(self) -> None:
        a = self.app
        if (a.st.get("pomodoro") or {}).get("fase") != "foco":
            return
        from oma_rpg.ui.dialogos import Abandonar
        a.push_screen(Abandonar())

    def action_pular(self) -> None:
        if (self.app.st.get("pomodoro") or {}).get("fase") in ("pausa", "longa"):
            self.app.pedir("pular_pausa")

    def action_nota(self) -> None:
        from oma_rpg.ui.dialogos import Pedir
        self.app.push_screen(Pedir("nota rápida", "o que não pode esquecer? (uma linha)"),
                             lambda t: t and self.app.pedir("nota", {"texto": t}))

    def action_skill(self, n: int) -> None:
        self.usar(n)

    def usar(self, n: int) -> None:
        a = self.app
        hrow = C.heroi(a.b)
        if hrow is None:
            return
        ativas = C.ativas(a.b, a.cfg, hrow)
        if n - 1 < len(ativas):
            a.pedir("usar_skill", {"skill": ativas[n - 1]})
        else:
            a.avisar("nenhuma skill ativa nesse número: aprenda em skills (alt+4)", alerta=True)


PAGINA = PaginaFoco
