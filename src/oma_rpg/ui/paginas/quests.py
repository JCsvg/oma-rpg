"""Tela 4 · quests: arcos (grupos, com o chefe), a tabela com matéria, estimativa, dificuldade e recompensa, o detalhe
com a conta do XP e, embaixo, os rascunhos do Mestre com a recompensa que o jogo calculou.
enter abre · n nova · espaço conclui · a aprova rascunho · alt+←→ aba (hoje, semana, arco, rascunhos, feitas)."""

from __future__ import annotations

from datetime import timedelta

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget

from oma_rpg.nucleo import consultas as C
from oma_rpg.nucleo import regras
from oma_rpg.ui import desenho as D
from oma_rpg.ui.base import Janela, Pagina
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lista import Lista, ajustar
from oma_rpg.ui.widgets import Abas, Pintado


class JanelaArcos(Janela):
    NOME = "arcos"
    DEFAULT_CSS = "JanelaArcos { width: 34; } JanelaArcos Lista { margin-top: 1; height: auto; max-height: 30; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, altura=5, id="arcos-lista", cursor_sem_foco=True)
        yield Pintado(self._chefe, id="arcos-chefe")

    def pintar(self) -> None:
        self.titulo("arcos", "n novo")
        l = self.query_one(Lista)
        atual = self.pg.arco_id
        arcos = C.arcos(self.app.b, self.app.cfg)
        cursor = next((i for i, x in enumerate(arcos) if x["id"] == atual), 0)
        l.definir(arcos, cursor=cursor)
        self.query_one(Pintado).pintar()

    def _linha(self, ar: dict, i: int, est) -> list[Text]:
        a = self.app
        w = est.largura
        sel = ar["id"] == self.pg.arco_id
        t = Text(" ")
        t.append(ic("arco") + " ", style=a.cor(ar["cor"]))
        t.append(ar["nome"], style=f"bold {a.cor('forte')}" if sel else a.cor("texto"))
        if ar["vencido"]:
            t.append("  " + ic("trofeu"), style=a.cor("yellow"))
        barra = Text(" ") + D.barra(a, ar["feitas"], max(1, ar["total"]), w - 7, ar["cor"], "▆")
        linhas = [t, D.linha_lr(barra, Text(f"{ar['pct']}%", style=a.cor("mudo")), w),
                  Text(f" {ar['feitas']} de {ar['total']} quests", style=a.cor("mudo")), Text(""), Text("")]
        if sel:
            linhas = [Text("▌", style=a.cor("accent")) + l[1:] if l.plain else l for l in linhas[:3]] + linhas[3:]
        return linhas

    def _chefe(self, w: int) -> Text:
        a = self.app
        ar = next((x for x in C.arcos(a.b, a.cfg) if x["id"] == self.pg.arco_id), None)
        if not ar or not ar["chefe"]:
            return Text("")
        faltam = ar["total"] - ar["feitas"]
        quando = D.dia_longo(ar["data"]) if ar["data"] else "sem data"
        linhas = [Text("─" * w, style=a.cor("linha")), Text("chefe do arco", style=a.cor("mudo")),
                  Text(ar["chefe"], style=f"bold {a.cor('forte')}"),
                  Text(f"{quando} · {faltam} quest{'s' if faltam != 1 else ''} falta{'m' if faltam != 1 else ''}", style=a.cor("mudo")),
                  Text.assemble((f"bônus: +{ar['bonus_xp']} xp  +{ar['bonus_bits']}", a.cor("yellow")), (ic("bits"), a.cor("yellow")))]
        if ar["vencido"]:
            linhas[-1] = Text("chefe vencido", style=a.cor("green"))
        return D.juntar(linhas)

    def on_lista_destacado(self, ev: Lista.Destacado) -> None:
        ev.stop()
        p = self.pg
        p.arco_id = ev.item["id"]
        self.query_one(Lista).redesenhar()
        self.query_one(Pintado).pintar()
        if p.aba == "arco":
            p.query_one(JanelaQuests).pintar()

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        p = self.pg
        p.aba = "arco"
        p.query_one(JanelaQuests).pintar()
        self.app.focar_janela("quests")

    def rodape(self):
        return [("enter", "quests do arco", "noop"), ("n", "novo arco", "noop"), ("e", "edita", "noop")]

    def teclas(self):
        return [("↑ ↓", "escolhe o arco"), ("enter", "mostra as quests do arco"), ("n", "novo arco"), ("e", "edita o arco e o chefe")]


ABAS = [("hoje", "hoje"), ("semana", "semana"), ("arco", "arco"), ("rascunhos", "rascunhos"), ("feitas", "feitas"),
        ("arvore", "árvore")]


def _montar_arvore(qs: list[dict]) -> list[dict]:
    """Ordena quests de um arco em árvore por dependências (suporta múltiplos pré-requisitos)."""
    por_id = {q["id"]: q for q in qs}
    filhos: dict[int, list[dict]] = {q["id"]: [] for q in qs}
    raizes: list[dict] = []
    for q in qs:
        deps = [d for d in q.get("depende_de") or [] if d in por_id]
        if not deps:
            raizes.append(q)
        else:
            filhos[deps[0]].append(q)
    saida: list[dict] = []
    vistos: set[int] = set()

    def visitar(q: dict, prefixo: str, ultimo: bool, raiz: bool) -> None:
        if q["id"] in vistos:
            return
        vistos.add(q["id"])
        deps = [d for d in q.get("depende_de") or [] if d in por_id]
        galho = "" if raiz else ("└─ " if ultimo else "├─ ")
        extra = f" [+{','.join('#' + str(d) for d in deps[1:])}]" if len(deps) > 1 else ""
        saida.append({**q, "_arvore": prefixo + galho, "_converge": extra})
        prox_pref = prefixo + ("" if raiz else ("   " if ultimo else "│  "))
        sub = filhos.get(q["id"], [])
        for i, f in enumerate(sub):
            visitar(f, prox_pref, i == len(sub) - 1, False)

    for r in raizes:
        visitar(r, "", True, True)
    for q in qs:
        if q["id"] not in vistos:
            visitar(q, "", True, True)
    return saida


def _niveis_arvore(qs: list[dict]) -> list[list[dict]]:
    """Agrupa quests do arco por nível topológico (0 = raízes, 1+ = dependentes)."""
    por_id = {q["id"]: q for q in qs}
    memo: dict[int, int] = {}

    def niv(qid: int, pilha: set[int]) -> int:
        if qid in memo:
            return memo[qid]
        if qid in pilha:
            return 0
        q = por_id.get(qid)
        if not q:
            return 0
        deps = [d for d in q.get("depende_de") or [] if d in por_id]
        n = 1 + max(niv(d, pilha | {qid}) for d in deps) if deps else 0
        memo[qid] = n
        return n

    grupos: dict[int, list[dict]] = {}
    for q in qs:
        grupos.setdefault(niv(q["id"], set()), []).append(q)
    linhas: list[list[dict]] = []
    for k in sorted(grupos):
        bloco = grupos[k]
        for i in range(0, len(bloco), 3):
            linhas.append(bloco[i : i + 3])
    return linhas


class ArvoreQuests(Widget, can_focus=True):
    DEFAULT_CSS = "ArvoreQuests { height: auto; width: 1fr; }"
    BINDINGS = [Binding("up,k", "mover(0, -1)", show=False), Binding("down,j", "mover(0, 1)", show=False),
                Binding("left,h", "mover(-1, 0)", show=False), Binding("right,l", "mover(1, 0)", show=False),
                Binding("enter", "escolher", show=False)]

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self._grade: list[list[dict]] = []
        self._caixas: list[tuple[int, int, int, int, dict]] = []
        self.qid: int | None = None

    def definir(self, qs: list[dict]) -> dict | None:
        self._grade = _niveis_arvore(qs)
        todos = [q for linha in self._grade for q in linha]
        if not todos:
            self.qid = None
        elif self.qid is None or not any(q["id"] == self.qid for q in todos):
            self.qid = todos[0]["id"]
        self.refresh(layout=True)
        return self.atual()

    def atual(self) -> dict | None:
        for linha in self._grade:
            for q in linha:
                if q["id"] == self.qid:
                    return q
        return self._grade[0][0] if self._grade else None

    def _pos(self) -> tuple[int, int]:
        for r, linha in enumerate(self._grade):
            for c, q in enumerate(linha):
                if q["id"] == self.qid:
                    return r, c
        return 0, 0

    def action_mover(self, dx: int, dy: int) -> None:
        if not self._grade:
            return
        r, c = self._pos()
        nr = max(0, min(len(self._grade) - 1, r + dy))
        nc = max(0, min(len(self._grade[nr]) - 1, c + dx))
        self.qid = self._grade[nr][nc]["id"]
        self.refresh()
        pg = self.ancestors_with_self
        for anc in pg:
            if hasattr(anc, "mostrar"):
                anc.mostrar(self.atual())
                break

    def action_escolher(self) -> None:
        q = self.atual()
        if q:
            for anc in self.ancestors_with_self:
                if hasattr(anc, "action_editar"):
                    anc.action_editar()
                    break

    def on_mouse_down(self, ev: events.MouseDown) -> None:
        self.focus()
        for x0, y0, x1, y1, q in self._caixas:
            if x0 <= ev.x < x1 and y0 <= ev.y < y1:
                self.qid = q["id"]
                self.refresh()
                for anc in self.ancestors_with_self:
                    if hasattr(anc, "mostrar"):
                        anc.mostrar(q)
                        break
                break

    def get_content_height(self, container, viewport, width: int) -> int:
        if not self._grade:
            return 3
        return max(3, len(self._grade) * 6)

    def render(self) -> Text:
        a = self.app
        w = max(40, self.size.width)
        self._caixas = []
        if not self._grade:
            return Text("\n  nenhuma quest neste arco", style=a.cor("mudo"))
        linhas: list[Text] = []
        for idx_l, grupo in enumerate(self._grade):
            cols = max(1, len(grupo))
            cw = max(16, (w - 2) // cols)
            bw = min(28, cw - 2)
            y0 = len(linhas)
            caixas = []
            for idx_c, q in enumerate(grupo):
                feita = q["estado"] == "feita" or q["daily_feita"]
                bloq = bool(q.get("bloqueada")) and not feita
                cursor = q["id"] == self.qid
                borda = a.cor("accent") if cursor and self.has_focus else a.cor("forte") if cursor else \
                    a.cor("linha") if bloq else (a.cor("green") if feita else a.cor("texto"))
                fundo = f" on {a.cor('selecao')}" if cursor else ""
                marca, cor = ("✓", "green") if feita else ("🔒", "yellow") if bloq else \
                    (("!", "red") if q.get("prio", 2) == 3 else ("●", "cyan"))
                l1 = Text()
                l1.append(f"{marca} ", style=a.cor(cor) + fundo)
                l1.append(q["titulo"], style=(a.cor("mudo") if (feita or bloq) else f"bold {a.cor('forte')}") + fundo)
                l2 = D.linha_lr(Text(f"#{q['id']} · {q['feitos']}/{q['est']}p", style=a.cor("mudo") + fundo),
                                Text(f"+{q['xp']}xp", style=a.cor("yellow") + fundo), bw - 4)
                deps = q.get("depende_de") or []
                l3_txt = "após " + ",".join(f"#{d}" for d in deps) if deps else (q["materia"] or "raiz")
                l3 = Text(l3_txt, style=(a.cor("yellow") if bloq else a.cor("mudo")) + fundo)
                caixa = [Text("┌" + "─" * (bw - 2) + "┐", style=borda)]
                for cont in (l1, l2, l3):
                    c = Text("│ ", style=borda)
                    corpo = ajustar(cont, bw - 4)
                    if cursor:
                        corpo.stylize(f"on {a.cor('selecao')}")
                    c.append_text(corpo)
                    c.append(" │", style=borda)
                    caixa.append(c)
                caixa.append(Text("└" + "─" * (bw - 2) + "┘", style=borda))
                caixas.append(caixa)
                x0 = 1 + idx_c * cw
                self._caixas.append((x0, y0, x0 + bw, y0 + 5, q))
            for row_i in range(5):
                t = Text(" ")
                for idx_c in range(cols):
                    t.append_text(caixas[idx_c][row_i])
                    t.append(" " * max(1, cw - bw))
                linhas.append(t)
            if idx_l < len(self._grade) - 1:
                con = Text(" ")
                for idx_c in range(cols):
                    con.append(" " * (bw // 2) + "│" + " " * (cw - bw // 2 - 1), style=a.cor("linha"))
                linhas.append(con)
        return D.juntar(linhas)


class JanelaQuests(Janela):
    NOME = "quests"
    DEFAULT_CSS = """
    JanelaQuests { height: 1fr; }
    JanelaQuests Abas { margin-top: 1; }
    JanelaQuests #q-cab { height: 2; margin-top: 1; }
    JanelaQuests Lista { height: 1fr; }
    JanelaQuests #q-arvore-scroll { height: 1fr; display: none; margin-top: 1; }
    JanelaQuests #q-pe { height: 3; }
    """

    def compose(self) -> ComposeResult:
        yield Abas(ABAS, "arco", id="q-abas")
        yield Pintado(self._cab, id="q-cab")
        yield Lista(self._linha, altura=2, id="q-lista", arrastar=True, cursor_apagado=True)
        with VerticalScroll(id="q-arvore-scroll"):
            yield ArvoreQuests(id="q-arvore")
        yield Pintado(self._pe, id="q-pe")

    def itens(self) -> list[dict]:
        a = self.app
        p = self.pg
        dia = a.hoje()
        if p.aba == "hoje":
            return C.hoje_lista(a.b, a.cfg, dia)
        if p.aba == "semana":
            fim = (C.data(dia) + timedelta(days=7)).isoformat()
            return [q for q in C.quests(a.b, a.cfg, dia, "aberta") if q["hoje"] or (q["prazo"] and q["prazo"] <= fim)]
        if p.aba == "rascunhos":
            return C.quests(a.b, a.cfg, dia, "rascunho")
        if p.aba == "feitas":
            fs = C.quests(a.b, a.cfg, dia, "feita")
            return sorted(fs, key=lambda q: -(q["concluida"] or 0))[:60]
        ar = a.b.um("SELECT nome FROM arcos WHERE id = ?", (p.arco_id,))
        if not ar:
            qs = C.quests(a.b, a.cfg, dia, "aberta")
            return _montar_arvore(qs) if p.aba == "arvore" else qs
        qs = [q for q in C.quests(a.b, a.cfg, dia, arco=ar[0]) if q["estado"] != "rascunho"]
        return _montar_arvore(qs) if p.aba == "arvore" else qs

    def pintar(self) -> None:
        a = self.app
        p = self.pg
        n = int(a.b.escalar("SELECT COUNT(*) FROM quests WHERE estado = 'rascunho'", (), 0))
        self.query_one(Abas).definir([(k, f"{r} {n}" if k == "rascunhos" and n else r) for k, r in ABAS], p.aba)
        ar = a.b.um("SELECT nome FROM arcos WHERE id = ?", (p.arco_id,))
        self.titulo("quests", ar[0] if p.aba == "arco" and ar else dict(ABAS)[p.aba])
        l = self.query_one(Lista)
        arv_scroll = self.query_one("#q-arvore-scroll")
        cab = self.query_one("#q-cab")
        itens = self.itens()
        if p.aba == "arvore":
            l.display = False
            cab.display = False
            arv_scroll.display = True
            atual = self.query_one(ArvoreQuests).definir(itens)
            for w in self.query(Pintado):
                w.pintar()
            p.mostrar(atual)
            return
        l.display = True
        cab.display = True
        arv_scroll.display = False
        cursor = None
        if p.quest_alvo is not None:
            cursor = next((i for i, q in enumerate(itens) if q["id"] == p.quest_alvo), None)
            p.quest_alvo = None
        l.definir(itens, cursor=cursor)
        for w in self.query(Pintado):
            w.pintar()
        p.mostrar(l.item_atual())

    def _cols(self, w: int) -> tuple[int, int, int, int]:
        return max(10, w - 36), 12, 5, 16

    def _cab(self, w: int) -> Text:
        a = self.app
        c1, c2, c3, c4 = self._cols(w)
        t = Text(no_wrap=True)
        for rot, larg, al in (("quest", c1, "left"), ("pomodoros", c2, "left"), ("dif.", c3, "left"), ("recompensa", c4, "right")):
            t.append_text(ajustar(Text(rot, style=a.cor("mudo")), larg, al))
            t.append(" ")
        return D.juntar([t, Text("─" * w, style=a.cor("linha"))])

    def _linha(self, q: dict, i: int, est) -> list[Text]:
        a = self.app
        c1, c2, c3, c4 = self._cols(est.largura)
        feita = q["estado"] == "feita" or q["daily_feita"]
        rasc = q["estado"] == "rascunho"
        p = a.st.get("pomodoro") or {}
        rodando = p.get("fase") == "foco" and a._atual_row is not None and a._atual_row["quest_id"] == q["id"]
        if feita:
            icone, cor = ic("feito"), "green"
        elif rasc:
            icone, cor = ic("mestre"), "cyan"
        elif rodando or (0 < q["feitos"] < q["est"]):
            icone, cor = ic("andamento"), "yellow"
        else:
            icone, cor = ic("pendente"), "texto"
        if self.pg.aba == "arvore" and q.get("_arvore"):
            tit = Text()
            tit.append(q["_arvore"], style=a.cor("accent"))
            tit.append(icone + " ", style=a.cor(cor))
            if q.get("bloqueada") and not feita:
                tit.append("🔒 ", style=a.cor("yellow"))
            tit.append(q["titulo"], style=a.cor("mudo") if (feita or q.get("bloqueada")) else a.cor("texto"))
            if q.get("_converge"):
                tit.append(q["_converge"], style=a.cor("yellow"))
            pom = D.pontos(a, q["feitos"], q["est"])
            pom.append(f"  {q['feitos']}/{q['est']}", style=a.cor("mudo"))
            rec = D.xp_bits(a, q["xp"], q["bits"], mudo=bool(feita))
            t = Text(no_wrap=True)
            t.append_text(ajustar(tit, c1))
            t.append(" ")
            t.append_text(ajustar(pom, c2))
            t.append(" ")
            t.append_text(ajustar(D.diamantes(a, q["dif"]), c3))
            t.append(" ")
            t.append_text(ajustar(rec, c4, "right"))
            return [t, Text("")]
        tit = Text()
        tit.append(icone + " ", style=a.cor(cor))
        if q.get("bloqueada") and not feita:
            tit.append("🔒 ", style=a.cor("yellow"))
        elif q.get("prio", 2) == 3 and not feita:
            tit.append("! ", style=f"bold {a.cor('red')}")
        elif q.get("prio", 2) == 1 and not feita:
            tit.append("⌄ ", style=a.cor("mudo"))
        tit.append(q["titulo"], style=a.cor("mudo") if (feita or q.get("bloqueada")) else (f"bold {a.cor('forte')}" if rodando else a.cor("texto")))
        pom = D.pontos(a, q["feitos"], q["est"])
        pom.append(f"  {q['feitos']}/{q['est']}", style=a.cor("mudo"))
        rec = D.xp_bits(a, q["xp"], q["bits"], mudo=bool(feita))
        t = Text(no_wrap=True)
        t.append_text(ajustar(tit, c1))
        t.append(" ")
        t.append_text(ajustar(pom, c2))
        t.append(" ")
        t.append_text(ajustar(D.diamantes(a, q["dif"]), c3))
        t.append(" ")
        t.append_text(ajustar(rec, c4, "right"))
        return [t, Text("")]

    def _pe(self, w: int) -> Text:
        a = self.app
        return D.juntar([Text(""), Text("alt+↑↓ move na fila · espaço conclui (vale só com pomodoro)", style=a.cor("mudo")), Text(""),
                         Text(f"XP cheio exige {int(a.cfg['quest']['xp_cheio_fracao'] * 100)}% dos pomodoros estimados",
                              style=a.cor("mudo"))])

    def on_lista_destacado(self, ev: Lista.Destacado) -> None:
        ev.stop()
        self.pg.mostrar(ev.item)

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.pg.action_editar()

    def on_lista_arrastado(self, ev: Lista.Arrastado) -> None:
        ev.stop()
        l = self.query_one(Lista)
        ids = [q["id"] for q in l.itens if q["estado"] == "aberta"]
        x, y = l.itens[ev.indice], l.itens[ev.destino]
        if x["id"] in ids and y["id"] in ids:
            ids.insert(ids.index(y["id"]), ids.pop(ids.index(x["id"])))
            self.app.pedir("ordenar_fila", {"ids": ids})

    def on_abas_mudou(self, ev: Abas.Mudou) -> None:
        ev.stop()
        self.pg.aba = ev.valor
        self.pintar()

    def alt_h(self, passo: int) -> None:
        self.query_one(Abas).passo(passo)

    def alt_v(self, passo: int) -> None:
        q = self.query_one(Lista).item_atual()
        if not q or q["estado"] != "aberta":
            return
        a = self.app

        def mover(ok, r):
            if ok:
                a.pedir("mover_fila", {"id": q["id"], "passo": passo})
        if not q["hoje"] and q["tipo"] != "daily":
            a.pedir("marcar_hoje", {"id": q["id"], "valor": True}, mover)
        else:
            mover(True, None)

    def atual(self):
        if self.pg.aba == "arvore":
            return self.query_one(ArvoreQuests).atual()
        return self.query_one(Lista).item_atual()

    def focar_entrada(self) -> None:
        if self.pg.aba == "arvore":
            self.query_one(ArvoreQuests).focus()
        else:
            self.query_one(Lista).focus()

    def rodape(self):
        return [("enter", "abrir", "noop"), ("n", "nova", "noop"), ("espaço", "concluir", "noop"), ("a", "aprovar rascunho", "noop"),
                ("alt+←→", "aba", "alt_h(1)")]

    def teclas(self):
        return [("↑ ↓", "escolhe a quest"), ("enter", "edita"), ("n", "nova quest"), ("espaço", "conclui (check-in)"),
                ("a", "aprova o rascunho"), ("d", "descarta"), ("+", "põe ou tira da fila de hoje"), ("f", "começa um pomodoro nela"),
                ("alt+← →", "aba"), ("alt+↑ ↓", "move na fila"), ("arrastar", "também reordena")]


class JanelaQuest(Janela):
    NOME = "quest"
    DEFAULT_CSS = "JanelaQuest { width: 1fr; height: 1fr; } JanelaQuest Lista { margin-top: 1; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, id="quest-detalhe", selecionavel=lambda it: it[0] == "sub", cursor_apagado=True)

    def mostrar(self, q: dict | None) -> None:
        self.q = q
        self.titulo("quest", "enter edita" if q and q["estado"] != "feita" else "")
        a = self.app
        if q is None:
            self.query_one(Lista).definir([("txt", Text("nenhuma quest aqui", style=a.cor("mudo")))])
            return
        w = max(20, self.size.width - 4)
        itens = [("txt", l) for l in D.quebrar(q["titulo"], w, f"bold {a.cor('forte')}")]
        orig = Text()
        orig.append(q["materia"] or "sem matéria", style=a.cor(C.cor_materia(a.b, q["materia"])))
        orig.append(" criada pelo Mestre" if q["origem"] == "mestre" else " criada por você", style=a.cor("mudo"))
        prio_txt = {3: ("alta", "red"), 2: ("média", "mudo"), 1: ("baixa", "mudo")}.get(q.get("prio", 2), ("média", "mudo"))
        orig.append(" · prio ", style=a.cor("mudo"))
        orig.append(prio_txt[0], style=a.cor(prio_txt[1]))
        itens.append(("txt", orig))
        if q.get("depende_de"):
            deps = ", ".join(f"#{d}" for d in q["depende_de"])
            msg = f"🔒 bloqueada (falta {', '.join('#' + str(d) for d in q['faltam_deps'])})" if q.get("bloqueada") else f"trilha: após {deps}"
            itens.append(("txt", Text(msg, style=a.cor("yellow") if q.get("bloqueada") else a.cor("mudo"))))
        if q["tipo"] == "daily":
            itens.append(("txt", Text("daily: vale uma vez por dia; vencida custa HP", style=a.cor("mudo"))))
        if q["porque"]:
            itens.append(("txt", Text("")))
            itens.append(("txt", Text("como resolver", style=f"bold {a.cor('forte')}")))
            itens += [("txt", l) for l in D.quebrar(q["porque"], w, a.cor("texto"))]
        itens.append(("txt", Text("")))
        if q["subtarefas"]:
            itens.append(("txt", Text("subtarefas", style=f"bold {a.cor('forte')}")))
            for i, s in enumerate(q["subtarefas"]):
                itens.append(("sub", i, s))
            itens.append(("txt", Text("")))
        itens.append(("txt", Text("recompensa", style=f"bold {a.cor('forte')}")))
        base = a.cfg["quest"]["xp_por_pomodoro"] * q["est"]
        itens.append(("txt", D.linha_lr(Text(f"base: {q['est']} pomodoro{'s' if q['est'] > 1 else ''} x {a.cfg['quest']['xp_por_pomodoro']}",
                                             style=a.cor("mudo")), Text(str(base), style=a.cor("texto")), w)))
        dif = Text()
        dif.append("dificuldade ", style=a.cor("mudo"))
        dif.append(regras.DIAMANTES[q["dif"]][: q["dif"]], style=a.cor("yellow"))
        itens.append(("txt", D.linha_lr(dif, Text(f"x{regras.mult_dif(q['dif'], a.cfg)}".replace(".", ","), style=a.cor("texto")), w)))
        itens.append(("txt", D.linha_lr(Text("tabela do jogo", style=f"bold {a.cor('forte')}"),
                                        Text(f"{q['xp']} xp", style=f"bold {a.cor('green')}"), w)))
        itens.append(("txt", Text("combo e CI verde somam nos pomodoros", style=a.cor("mudo"))))
        itens.append(("txt", Text("o Mestre sugere; o jogo calcula", style=a.cor("mudo"))))
        coms = list(a.b.todos("SELECT c.hash, c.assunto, c.xp FROM commits c JOIN pomodoros p ON c.pomodoro_inicio = p.inicio "
                              "WHERE p.quest_id = ? ORDER BY c.ts", (q["id"],)))
        row = a._atual_row
        if row is not None and row["quest_id"] == q["id"] and row["fase"] == "foco":
            coms += list(a.b.todos("SELECT hash, assunto, xp FROM commits WHERE pomodoro_inicio = ? ORDER BY ts", (row["inicio"],)))
        itens.append(("txt", Text("")))
        itens.append(("txt", Text("commits vinculados", style=f"bold {a.cor('forte')}")))
        itens.append(("txt", Text("")))
        for c in coms[:5]:
            t = Text()
            t.append(ic("commit") + " ", style=a.cor("blue"))
            t.append(c["hash"][:7] + " ", style=a.cor("yellow"))
            t.append(c["assunto"].split(":")[0], style=a.cor("texto"))
            itens.append(("txt", D.linha_lr(t, Text(f"+{c['xp']} xp", style=a.cor("green")), w)))
        if not coms:
            itens.append(("txt", Text("nenhum ainda", style=a.cor("mudo"))))
        itens.append(("txt", Text("")))
        itens += [("txt", l) for l in D.quebrar(f"dica: closes quest-{q['id']} na mensagem do commit conclui a quest sozinha.", w,
                                                a.cor("mudo"))]
        if q["nota"]:
            itens += [("txt", Text("")), ("txt", Text("check-in: " + q["nota"], style=a.cor("texto")))]
        self.query_one(Lista).definir(itens)

    def _linha(self, it, i, est) -> list[Text]:
        a = self.app
        if it[0] == "sub":
            s = it[2]
            t = Text()
            t.append(ic("feito") if s.get("feita") else ic("pendente"), style=a.cor("green") if s.get("feita") else a.cor("texto"))
            t.append(" " + s["texto"], style=a.cor("mudo") if s.get("feita") else a.cor("texto"))
            return [t]
        return [it[1]]

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self._alternar()

    def _alternar(self) -> None:
        it = self.query_one(Lista).item_atual()
        if it and it[0] == "sub" and getattr(self, "q", None):
            self.app.pedir("subtarefa", {"id": self.q["id"], "indice": it[1]})

    def on_key(self, ev) -> None:
        if ev.key == "space":
            ev.stop()
            self._alternar()

    def rodape(self):
        return [("espaço", "marca subtarefa", "noop"), ("s", "nova subtarefa", "noop"), ("e", "edita", "noop")]


class JanelaRascunhos(Janela):
    NOME = "rascunhos"
    DEFAULT_CSS = "JanelaRascunhos { height: 10; } JanelaRascunhos Lista { margin-top: 1; height: 1fr; } JanelaRascunhos #r-pe { height: 1; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, altura=3, id="r-lista", cursor_apagado=True)
        yield Pintado(self._pe, id="r-pe")

    def pintar(self) -> None:
        a = self.app
        rs = C.quests(a.b, a.cfg, a.hoje(), "rascunho")
        self.titulo(f"{ic('mestre')} rascunhos do Mestre", f"{len(rs)} aguardando · nada vale XP até você aprovar")
        self.query_one(Lista).definir(rs)
        self.query_one(Pintado).pintar()

    def _linha(self, q: dict, i: int, est) -> list[Text]:
        a = self.app
        w = est.largura
        t = Text()
        t.append(ic("mestre") + " ", style=a.cor("cyan"))
        t.append(q["titulo"], style=f"bold {a.cor('forte')}")
        d = Text.assemble((f"{q['xp']} xp  ", a.cor("mudo")), (f"{q['bits']}", a.cor("mudo")), (ic("bits"), a.cor("yellow")))
        l2 = Text()
        l2.append(f"  {q['materia'] or 'sem matéria'} · {q['est']} pomodoro{'s' if q['est'] > 1 else ''} · ", style=a.cor("mudo"))
        l2.append_text(D.diamantes(a, q["dif"]))
        if q["prazo"]:
            l2.append(f" · prazo {C.dia_curto(q['prazo'])}", style=a.cor("mudo"))
        linhas = [D.linha_lr(t, d, w), l2,
                  Text("  " + ((q["porque"] or "sem descrição").replace("\n", " "))[:max(20, w - 4)], style=a.cor("mudo"))]
        return linhas

    def _pe(self, w: int) -> Text:
        return Text("XP e Bits mostrados são a tabela do jogo, não o que o Mestre quiser", style=self.app.cor("mudo"))

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.pg.action_editar()

    def atual(self):
        if self.pg.aba == "arvore":
            return self.query_one(ArvoreQuests).atual()
        return self.query_one(Lista).item_atual()

    def focar_entrada(self) -> None:
        if self.pg.aba == "arvore":
            self.query_one(ArvoreQuests).focus()
        else:
            self.query_one(Lista).focus()

    def rodape(self):
        return [("a", "aprovar", "noop"), ("e", "editar", "noop"), ("d", "descartar", "noop"), ("shift+a", "aprova todos", "noop")]

    def teclas(self):
        return [("a", "aprova (vira quest aberta, na fila de hoje)"), ("e ou enter", "edita antes de aprovar"),
                ("d", "descarta"), ("shift+a", "aprova todos")]


class PaginaQuests(Pagina):
    NOME = "quests"
    TITULO = "quests"
    ENTRADA = "quests"
    VIZINHAS = {
        "arcos": {"esq": "paineis", "dir": "quests", "cima": "topo"},
        "quests": {"esq": "arcos", "dir": "quest", "cima": "topo", "baixo": "rascunhos"},
        "quest": {"esq": "quests", "cima": "topo", "baixo": "rascunhos"},
        "rascunhos": {"esq": "arcos", "cima": "quests"},
    }
    BINDINGS = [Binding("n", "nova", show=False), Binding("space", "concluir", show=False), Binding("a", "aprovar", show=False),
                Binding("A,shift+a", "aprovar_todos", show=False), Binding("D,shift+d", "descartar_todos", show=False),
                Binding("e", "editar", show=False), Binding("d", "descartar", show=False),
                Binding("plus", "hoje", show=False), Binding("f", "foco", show=False), Binding("s", "subtarefa", show=False)]
    DEFAULT_CSS = "PaginaQuests #q-dir { width: 1fr; } PaginaQuests #q-cima { height: 1fr; } PaginaQuests JanelaQuests { width: 58; }"

    def __init__(self, quest: int | None = None, **kw) -> None:
        super().__init__()
        self.aba = "arco"
        self.arco_id = None
        self.quest_alvo = quest

    def compose(self) -> ComposeResult:
        yield JanelaArcos()
        with Vertical(id="q-dir"):
            with Horizontal(id="q-cima"):
                yield JanelaQuests()
                yield JanelaQuest()
            yield JanelaRascunhos()

    def pintar(self) -> None:
        a = self.app
        if self.arco_id is None:
            r = a.b.um("SELECT id FROM arcos ORDER BY id LIMIT 1")
            self.arco_id = r[0] if r else None
        if self.quest_alvo is not None:
            q = a.b.um("SELECT estado, arco_id FROM quests WHERE id = ?", (self.quest_alvo,))
            if q is not None:
                if q["estado"] == "rascunho":
                    self.aba = "rascunhos"
                elif q["arco_id"]:
                    self.aba, self.arco_id = "arco", q["arco_id"]
                elif q["estado"] == "feita":
                    self.aba = "feitas"
                else:
                    self.aba = "hoje"
        super().pintar()

    def mostrar(self, q) -> None:
        try:
            self.query_one(JanelaQuest).mostrar(q)
        except Exception:
            pass

    def _selecionada(self):
        a = self.app
        nome = a.nome_janela(a.focused)
        if nome == "rascunhos":
            return self.query_one(JanelaRascunhos).atual()
        if nome in ("quests", "quest"):
            return self.query_one(JanelaQuests).atual()
        return None

    def rodape_pagina(self):
        return [("enter", "abrir", "noop"), ("n", "nova", "nova"), ("espaço", "concluir", "concluir"),
                ("a", "aprovar rascunho", "aprovar"), ("alt+←→", "aba", "alt_h(1)")]

    def action_nova(self) -> None:
        from oma_rpg.ui.dialogos import EditarQuest, NovoArco
        if self.app.nome_janela(self.app.focused) == "arcos":
            self.app.push_screen(NovoArco())
        else:
            self.app.push_screen(EditarQuest(None))

    def action_editar(self) -> None:
        from oma_rpg.ui.dialogos import EditarQuest, NovoArco
        a = self.app
        if a.nome_janela(a.focused) == "arcos":
            ar = a.b.um("SELECT * FROM arcos WHERE id = ?", (self.arco_id,))
            if ar:
                a.push_screen(NovoArco(dict(ar)))
            return
        q = self._selecionada()
        if q and q["estado"] in ("aberta", "rascunho"):
            a.push_screen(EditarQuest(q, aprovar=q["estado"] == "rascunho"))

    def action_concluir(self) -> None:
        from oma_rpg.ui.dialogos import Concluir
        q = self._selecionada()
        if q and q["estado"] == "aberta" and not q["daily_feita"]:
            self.app.push_screen(Concluir(q))

    def action_aprovar(self) -> None:
        q = self._selecionada()
        if q and q["estado"] == "rascunho":
            self.app.pedir("aprovar", {"id": q["id"]})

    def action_aprovar_todos(self) -> None:
        self.app.pedir("aprovar_todos")

    def action_descartar_todos(self) -> None:
        self.app.pedir("descartar_todos_rascunhos")

    def action_descartar(self) -> None:
        from oma_rpg.ui.dialogos import Confirmar
        q = self._selecionada()
        if not q or q["estado"] not in ("aberta", "rascunho"):
            return
        cmd = "descartar_rascunho" if q["estado"] == "rascunho" else "descartar_quest"
        self.app.push_screen(Confirmar("descartar?", [q["titulo"], "sai das listas; nada de XP nem de HP"], "descartar"),
                             lambda ok: ok and self.app.pedir(cmd, {"id": q["id"]}))

    def action_hoje(self) -> None:
        q = self._selecionada()
        if q and q["estado"] == "aberta":
            self.app.pedir("marcar_hoje", {"id": q["id"], "valor": not q["hoje"]})

    def action_foco(self) -> None:
        q = self._selecionada()
        a = self.app
        if q and q["estado"] == "aberta":
            a.pedir("iniciar", {"quest": q["id"]}, lambda ok, r: ok and a.abrir_pagina("foco", foco=True))

    def action_subtarefa(self) -> None:
        from oma_rpg.ui.dialogos import Pedir
        q = self.query_one(JanelaQuests).atual()
        if q and q["estado"] in ("aberta", "rascunho"):
            self.app.push_screen(Pedir("nova subtarefa", q["titulo"]),
                                 lambda t: t and self.app.pedir("subtarefa", {"id": q["id"], "texto": t}))


PAGINA = PaginaQuests
