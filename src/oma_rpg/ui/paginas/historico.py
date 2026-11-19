"""Tela 8 · histórico: mapa de calor de 53 semanas estilo GitHub, totais, detalhe do dia escolhido e a divisão por
matéria. ←↓↑→ dia · alt+←→ camada (pomodoros, commits, xp) · [ ] período · enter detalhe."""

from __future__ import annotations

from datetime import timedelta

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widget import Widget

from oma_rpg.nucleo import consultas as C
from oma_rpg.ui import desenho as D
from oma_rpg.ui.base import Janela, Pagina, pagina_de
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lista import Lista, ajustar
from oma_rpg.ui.widgets import Abas, Pintado

CAMADAS = [("pomodoros", "pomodoros"), ("commits", "commits"), ("xp", "xp")]
PERIODOS = [("53", "12 meses"), ("26", "6 meses"), ("13", "3 meses")]
BARRAS = " ▁▂▃▄▅▆▇█"


class Mapa(Widget, can_focus=True):
    pg = property(lambda self: pagina_de(self))
    DEFAULT_CSS = "Mapa { height: 10; width: 1fr; }"
    BINDINGS = [Binding("left,h", "mover(-7)", show=False), Binding("right,l", "mover(7)", show=False),
                Binding("up,k", "mover(-1)", show=False), Binding("down,j", "mover(1)", show=False),
                Binding("enter", "detalhe", show=False)]

    def render(self) -> Text:
        a = self.app
        p = self.pg
        h = C.heroi(a.b)
        cor = h["tema_calor"] if h else "green"
        linhas = D.mapa_calor(a, p.valores(), a.hoje(), p.semanas, cor, cursor=p.dia)
        rodape = Text("    ") + D.legenda_calor(a, cor)
        v = p.valores().get(p.dia, 0)
        unid = {"pomodoros": "pomodoro", "commits": "commit", "xp": "xp"}[p.camada]
        rodape.append(" " * 10)
        rodape.append(f"{D.dia_longo(p.dia)}: {v} {unid}{'s' if v != 1 and unid != 'xp' else ''}", style=f"bold {a.cor('forte')}")
        return D.juntar(linhas + [Text(""), rodape])

    def action_mover(self, d: int) -> None:
        p = self.pg
        novo = C.data(p.dia) + timedelta(days=d)
        hoje = C.data(self.app.hoje())
        inicio = hoje - timedelta(weeks=p.semanas)
        if inicio <= novo <= hoje:
            p.escolher_dia(novo.isoformat())

    def action_detalhe(self) -> None:
        self.app.focar_janela("dia")

    def on_click(self, ev) -> None:
        a = self.app
        p = self.pg
        if ev.y < 1 or ev.y > 7 or ev.x < 4:
            return
        semana = (ev.x - 4) // 2
        hoje = C.data(a.hoje())
        ultima_seg = hoje - timedelta(days=hoje.weekday())
        inicio = ultima_seg - timedelta(weeks=p.semanas - 1)
        d = inicio + timedelta(weeks=semana, days=ev.y - 1)
        if d <= hoje:
            self.focus()
            p.escolher_dia(d.isoformat())


class JanelaMapa(Janela):
    NOME = "mapa"
    DEFAULT_CSS = "JanelaMapa { height: 16; } JanelaMapa Abas { margin: 1 0; }"

    def compose(self) -> ComposeResult:
        yield Abas(CAMADAS, "pomodoros", direita=PERIODOS, valor_dir="53", id="mapa-abas")
        yield Mapa(id="mapa-grade")

    def pintar(self) -> None:
        p = self.pg
        self.titulo("mapa de calor", f"{p.semanas} semanas")
        ab = self.query_one(Abas)
        ab.valor, ab.valor_dir = p.camada, str(p.semanas)
        ab.refresh()
        self.query_one(Mapa).refresh()

    def on_abas_mudou(self, ev: Abas.Mudou) -> None:
        ev.stop()
        p = self.pg
        if ev.valor.startswith("dir:"):
            p.semanas = int(ev.valor[4:])
        else:
            p.camada = ev.valor
        p.pintar()

    def alt_h(self, passo: int) -> None:
        self.query_one(Abas).passo(passo)

    def rodape(self):
        return [("←↓↑→", "dia", "noop"), ("alt+←→", "camada", "alt_h(1)"), ("[ ]", "período", "noop"), ("enter", "detalhe", "noop")]

    def teclas(self):
        return [("← →", "semana anterior e próxima"), ("↑ ↓", "dia anterior e próximo"), ("alt+← →", "camada: pomodoros, commits, xp"),
                ("[ ]", "período: 12, 6 ou 3 meses"), ("enter", "vai para o detalhe do dia"), ("clique", "escolhe o dia")]


class JanelaNumeros(Janela):
    NOME = "numeros"
    FOCAVEL = True
    DEFAULT_CSS = "JanelaNumeros { width: 1fr; height: 16; }"

    def compose(self) -> ComposeResult:
        yield Pintado(self._desenhar)

    def pintar(self) -> None:
        self.titulo("números")
        self.query_one(Pintado).pintar()

    def _desenhar(self, w: int) -> Text:
        a = self.app
        p = self.pg
        desde = (C.data(a.hoje()) - timedelta(weeks=p.semanas)).isoformat()
        pom = C.calor(a.b, "pomodoros", desde)
        total = sum(pom.values())
        ativos = len([v for v in pom.values() if v])
        h = C.heroi(a.b)
        commits = int(a.b.escalar("SELECT COUNT(*) FROM commits WHERE dia >= ? AND xp > 0", (desde,), 0))
        linhas = [Text("")]
        for rot, v in (("pomodoros", C.milhar(total)), ("dias ativos", str(ativos)), ("melhor dia", str(max(pom.values(), default=0))),
                       ("streak atual", str(C.streak_atual(h, a.hoje()) if h else 0)), ("maior streak", str(h["melhor_streak"] if h else 0)),
                       ("por dia ativo", f"{total / ativos:.1f}".replace(".", ",") if ativos else "0")):
            linhas += [D.linha_lr(Text(rot, style=a.cor("mudo")), Text(v, style=f"bold {a.cor('forte')}"), w), Text("")]
        linhas.append(Text(f"commits contados: {commits}", style=a.cor("mudo")))
        return D.juntar(linhas)


class JanelaDia(Janela):
    NOME = "dia"
    DEFAULT_CSS = "JanelaDia #dia-topo { height: 8; margin-top: 1; } JanelaDia Lista { height: 1fr; }"

    def compose(self) -> ComposeResult:
        yield Pintado(self._topo, id="dia-topo")
        yield Lista(self._linha, id="dia-lista", selecionavel=lambda it: it[0] == "quest", cursor_apagado=True)

    def pintar(self) -> None:
        a = self.app
        p = self.pg
        self.titulo(D.dia_longo(p.dia), "enter abre a quest")
        self.query_one(Pintado).pintar()
        itens: list = [("secao", "sessões")]
        poms = a.b.todos("SELECT * FROM pomodoros WHERE dia = ? AND estado = 'feito' ORDER BY inicio", (p.dia,))
        sessoes: list[list] = []
        for r in poms:
            if sessoes and r["inicio"] - sessoes[-1][-1]["fim"] < 30 * 60 and r["materia"] == sessoes[-1][-1]["materia"]:
                sessoes[-1].append(r)
            else:
                sessoes.append([r])
        for s in sessoes:
            itens.append(("sessao", s))
        if not sessoes:
            itens.append(("vazio", "nenhum pomodoro neste dia"))
        itens += [("branco", ""), ("secao", "quests concluídas")]
        ini, fim = C.inicio_do_dia(p.dia), C.fim_do_dia(p.dia)
        qs = a.b.todos("SELECT * FROM quests WHERE estado = 'feita' AND concluida BETWEEN ? AND ? ORDER BY concluida", (ini, fim))
        itens += [("quest", q) for q in qs] or [("vazio", "nenhuma")]
        itens += [("branco", ""), ("secao", "commits")]
        cs = a.b.todos("SELECT * FROM commits WHERE dia = ? ORDER BY ts", (p.dia,))
        itens += [("commit", c) for c in cs] or [("vazio", "nenhum")]
        itens += [("branco", ""), ("vazio", "setas movem o cursor no mapa; a data selecionada aparece aqui")]
        self.query_one(Lista).definir(itens)

    def _topo(self, w: int) -> Text:
        a = self.app
        dia = self.pg.dia
        poms = a.b.todos("SELECT inicio, fim, combo, xp FROM pomodoros WHERE dia = ? AND estado = 'feito'", (dia,))
        xp_q = int(a.b.escalar("SELECT SUM(xp) FROM ganhos WHERE dia = ? AND origem IN ('quest', 'arco')", (dia,), 0))
        cmax = max((r["combo"] for r in poms), default=1.0)
        linhas = [Text(f"{len(poms)} pomodoros · +{sum(r['xp'] for r in poms)} xp de pomodoros · +{xp_q} xp de quests · "
                       f"combo máximo x{cmax:.1f}", style=a.cor("texto")), Text("")]
        h0, h1 = 8, 22
        passo = max(3, (w - 4) // (h1 - h0 + 1))
        cab = Text("")
        for hh in range(h0, h1 + 1):
            cab.append(f"{hh:02d}".ljust(passo), style=a.cor("mudo"))
        linhas.append(cab)
        barra = [" "] * (passo * (h1 - h0 + 1))
        commits = [" "] * len(barra)
        import time as _t
        for r in poms:
            for t in range(int(r["inicio"]), int(r["fim"]), 300):
                lt = _t.localtime(t)
                x = int(((lt.tm_hour - h0) + lt.tm_min / 60) * passo)
                if 0 <= x < len(barra):
                    barra[x] = "█"
        for c in a.b.todos("SELECT ts FROM commits WHERE dia = ?", (dia,)):
            lt = _t.localtime(c["ts"])
            x = int(((lt.tm_hour - h0) + lt.tm_min / 60) * passo)
            if 0 <= x < len(commits):
                commits[x] = "◇"
        linhas.append(Text("".join(barra), style=a.cor("green")))
        linhas.append(Text("".join(commits), style=a.cor("blue")))
        linhas.append(Text.assemble(("pomodoros ", a.cor("mudo")), ("██", a.cor("green")), ("   commits ", a.cor("mudo")), ("◇", a.cor("blue"))))
        return D.juntar(linhas)

    def _linha(self, it, i, est) -> list[Text]:
        a = self.app
        tipo, v = it
        w = est.largura
        if tipo == "secao":
            return [D.secao(a, v, w)]
        if tipo == "sessao":
            t = Text(f"{C.hora(v[0]['inicio'])} a {C.hora(v[-1]['fim'])}   ", style=a.cor("mudo"))
            mat = v[0]["materia"] or "sem matéria"
            t.append(ajustar(Text(mat, style=f"bold {a.cor(C.cor_materia(a.b, mat))}"), 16))
            t.append(f"{len(v)} pomodoro{'s' if len(v) > 1 else ''}", style=a.cor("texto"))
            return [t]
        if tipo == "quest":
            t = Text()
            t.append(ic("feito") + " ", style=a.cor("green"))
            t.append(v["titulo"], style=a.cor("texto"))
            return [D.linha_lr(t, Text(f"+{v['xp_ganho']} xp", style=a.cor("green")), w)]
        if tipo == "commit":
            t = Text()
            t.append(ic("commit") + " ", style=a.cor("blue"))
            t.append(v["hash"][:7] + " ", style=a.cor("yellow"))
            t.append(v["assunto"], style=a.cor("texto"))
            return [t]
        if tipo == "vazio":
            return [Text(v, style=a.cor("mudo"))]
        return [Text("")]

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.app.abrir_pagina("quests", foco=True, quest=ev.item[1]["id"])

    def rodape(self):
        return [("enter", "abre a quest", "noop"), ("↑↓", "quests do dia", "noop")]


class JanelaMaterias(Janela):
    NOME = "materias"
    FOCAVEL = True

    def compose(self) -> ComposeResult:
        yield Pintado(self._desenhar)

    def pintar(self) -> None:
        p = self.pg
        self.titulo("por matéria", dict(PERIODOS)[str(p.semanas)])
        self.query_one(Pintado).pintar()

    def _desenhar(self, w: int) -> Text:
        a = self.app
        p = self.pg
        desde = (C.data(a.hoje()) - timedelta(weeks=p.semanas)).isoformat()
        mats = C.materias(a.b, desde)[:6]
        linhas = [Text("")]
        maximo = mats[0][1] if mats else 1
        for nome, n in mats:
            linhas.append(D.linha_lr(Text(nome, style=a.cor("texto")), Text(f"{n} pomodoros", style=a.cor("mudo")), w))
            linhas.append(D.barra(a, n, maximo, w, C.cor_materia(a.b, nome)))
            linhas.append(Text(""))
        linhas.append(D.secao(a, "últimas 12 semanas", w))
        linhas += [Text(""), Text("")]
        hoje = C.data(a.hoje())
        seg = hoje - timedelta(days=hoje.weekday())
        semanas = []
        for s in range(11, -1, -1):
            ini = seg - timedelta(weeks=s)
            fim = ini + timedelta(days=6)
            n = int(a.b.escalar("SELECT COUNT(*) FROM pomodoros WHERE estado = 'feito' AND dia BETWEEN ? AND ?",
                                (ini.isoformat(), fim.isoformat()), 0))
            semanas.append(n)
        mx = max(semanas) or 1
        t = Text()
        for n in semanas:
            t.append(BARRAS[max(1, round(8 * n / mx)) if n else 0] * 2, style=a.cor("green"))
            t.append("  ")
        linhas.append(t)
        mn = min(semanas)
        linhas.append(Text(f"por semana, de {mn} a {max(semanas)} pomodoros", style=a.cor("mudo")))
        return D.juntar(linhas)


class PaginaHistorico(Pagina):
    NOME = "historico"
    TITULO = "histórico"
    ENTRADA = "mapa"
    VIZINHAS = {
        "mapa": {"esq": "paineis", "dir": "numeros", "cima": "topo", "baixo": "dia"},
        "numeros": {"esq": "mapa", "cima": "topo", "baixo": "materias"},
        "dia": {"esq": "paineis", "dir": "materias", "cima": "mapa"},
        "materias": {"esq": "dia", "cima": "numeros"},
    }
    BINDINGS = [Binding("left_square_bracket", "periodo(-1)", show=False), Binding("right_square_bracket", "periodo(1)", show=False)]
    DEFAULT_CSS = """
    PaginaHistorico { layout: vertical; }
    PaginaHistorico #h-cima { height: 16; }
    PaginaHistorico #h-baixo { height: 1fr; }
    PaginaHistorico JanelaMapa { width: 122; }
    PaginaHistorico JanelaDia { width: 91; }
    """

    def __init__(self, **kw) -> None:
        super().__init__()
        self.camada = "pomodoros"
        self.semanas = 53
        self.dia = ""
        self._cache: tuple | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="h-cima"):
            yield JanelaMapa()
            yield JanelaNumeros()
        with Horizontal(id="h-baixo"):
            yield JanelaDia()
            yield JanelaMaterias()

    def on_mount(self) -> None:
        a = self.app
        self.camada = a.estado.obter("hist_camada", "pomodoros") if a.estado.obter("hist_camada") in dict(CAMADAS) else "pomodoros"
        salvo = a.estado.obter("hist_dia")
        hoje = C.data(a.hoje())
        if isinstance(salvo, str) and len(salvo) == 10 and hoje - timedelta(weeks=53) <= C.data(salvo) <= hoje:
            self.dia = salvo
        else:
            r = a.b.um("SELECT dia FROM pomodoros WHERE estado = 'feito' AND dia < ? ORDER BY dia DESC LIMIT 1", (a.hoje(),))
            self.dia = r[0] if r else a.hoje()

    def valores(self) -> dict[str, int]:
        a = self.app
        chave = (self.camada, self.semanas, a.hoje())
        if self._cache is None or self._cache[0] != chave:
            desde = (C.data(a.hoje()) - timedelta(weeks=self.semanas)).isoformat()
            self._cache = (chave, C.calor(a.b, self.camada, desde))
        return self._cache[1]

    def pintar(self) -> None:
        self._cache = None
        self.app.estado.definir("hist_camada", self.camada)
        super().pintar()

    def escolher_dia(self, dia: str) -> None:
        self.dia = dia
        self.app.estado.definir("hist_dia", dia)
        self.query_one(Mapa).refresh()
        self.query_one(JanelaDia).pintar()

    def action_periodo(self, passo: int) -> None:
        ks = [int(k) for k, _ in PERIODOS]
        i = ks.index(self.semanas)
        self.semanas = ks[max(0, min(len(ks) - 1, i + passo))]
        hoje = C.data(self.app.hoje())
        if C.data(self.dia) < hoje - timedelta(weeks=self.semanas):
            self.dia = hoje.isoformat()
        self.pintar()

    def rodape_pagina(self):
        return [("←↓↑→", "dia", "noop"), ("alt+←→", "camada", "noop"), ("[ ]", "período", "noop"), ("enter", "detalhe", "noop")]


PAGINA = PaginaHistorico
