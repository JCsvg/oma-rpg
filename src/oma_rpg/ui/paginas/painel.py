"""Tela 2 · painel: herói, hoje (pomodoros e fila), últimas 24 semanas com a estatística por matéria, atividade do dia
e o Mestre. enter abre · f foco · n nova quest · t taverna."""

from __future__ import annotations

from datetime import timedelta

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical

from oma_rpg.nucleo import consultas as C
from oma_rpg.nucleo import regras
from oma_rpg.ui import desenho as D
from oma_rpg.ui.base import Janela, Pagina
from oma_rpg.ui.fonte import grande
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lista import Lista, ajustar
from oma_rpg.ui.widgets import Pintado

ICONE_ORIGEM = {"pomodoro": ("foco", "green"), "commit": ("commit", "blue"), "quest": ("feito", "green"),
                "arco": ("bits", "yellow"), "conquista": ("trofeu", "yellow"), "nivel": ("xp", "green"),
                "daily": ("caveira", "red"), "abandono": ("vida", "red"), "combo": ("combo", "yellow"),
                "inicio_dia": ("foguete", "blue"), "pausa": ("mana", "blue"), "loja": ("loja", "yellow"),
                "skill": ("raio", "blue"), "juros": ("bits", "yellow"), "desmaio": ("coracao_partido", "red"),
                "item": ("mochila", "texto"), "caixa": ("bau", "yellow"), "escudo": ("vida", "blue"),
                "aprovar": ("mestre", "cyan"), "dia": ("vida", "red"), "acordar": ("vida", "red"), "respec": ("raio", "yellow"),
                "streak": ("streak", "orange"), "titulo": ("coroa", "yellow"), "heroi": ("usuario", "texto")}


def mecanica_linha(app, h: dict, w: int) -> Text:
    """A linha da mecânica da classe no quadro do herói (CI verde, carteira, carta...)."""
    a = app
    cid = h["classe_id"]
    hoje = a.hoje()
    if cid == "programa":
        n = int(a.b.escalar("SELECT COUNT(*) FROM commits WHERE dia = ? AND vinculado = 1 AND xp > 0", (hoje,), 0))
        pct = a.cfg["commit"]["ci_verde_pct"] + C.passivos(a.b, a.cfg, hoje)["ci_verde"]
        return Text.assemble((ic("commit") + " ", a.cor("blue")), ("CI verde ", f"bold {a.cor('forte')}"),
                             (f"{n} commit{'s' if n != 1 else ''} hoje, +{pct:.0f}% de XP", a.cor("mudo")))
    if cid == "empreendedor":
        m = a.cfg["mecanicas"]
        return Text.assemble((ic("bits") + " ", a.cor("yellow")), ("carteira ", f"bold {a.cor('forte')}"),
                             (f"rende {m['juros_pct']:.0f}% à meia-noite se cumprir a meta", a.cor("mudo")))
    if cid == "rato":
        return Text.assemble((ic("vida") + " ", a.cor("red")), ("fadiga ", f"bold {a.cor('forte')}"),
                             (f"pausa respeitada cura {a.cfg['mecanicas']['rato_hp_pausa']} HP", a.cor("mudo")))
    if cid == "gamer":
        return Text.assemble((ic("gamer") + " ", a.cor("green")), ("combo ", f"bold {a.cor('forte')}"),
                             ("até x2.0; quebra com 45 min parado", a.cor("mudo")))
    if cid == "otaku":
        lim = a.cfg["mecanicas"]["otaku_virada_pct"]
        return Text.assemble((ic("otaku") + " ", a.cor("cyan")), ("virada ", f"bold {a.cor('forte')}"),
                             (f"abaixo de {lim}% de HP o pomodoro vale x2", a.cor("mudo")))
    cd = C.carta_do_dia(a.b, a.cfg, hoje)
    if cd:
        bf, db = a.cfg["cartas"][cd[0]], a.cfg["cartas"][cd[1]]
        return Text.assemble((ic("mistico") + " ", a.cor("magenta")), (f"{bf['nome']} ", f"bold {a.cor('forte')}"),
                             (f"{bf['curto']} · {db['nome']}: {db['curto']}", a.cor("mudo")))
    return Text("")


class JanelaHeroi(Janela):
    NOME = "heroi"
    FOCAVEL = True
    DEFAULT_CSS = "JanelaHeroi { width: 58; height: 20; }"

    def compose(self) -> ComposeResult:
        yield Pintado(self._desenhar, id="heroi-corpo")

    def pintar(self) -> None:
        self.titulo("herói", "alt+4 skills")
        self.query_one(Pintado).pintar()

    def _desenhar(self, w: int) -> Text:
        a = self.app
        st = a.st.get("heroi")
        if not st:
            return Text("")
        hrow = C.heroi(a.b)
        cls = a.cfg.classe(st["classe_id"])
        cor = cls["cor"]
        sigla = grande(cls["sigla"])
        cor_ini = hrow["cor_retrato"] or cor
        dentro = [Text(""), Text(ic(st["classe_id"]), style=a.cor(cor))]
        dentro += [Text(l, style=a.cor(cor_ini)) for l in sigla]
        dentro += [Text(f"nv {st['nivel']}", style=a.cor("mudo"))]
        ret = D.moldura(a, dentro, 22, hrow["moldura"], cor, fundo="painel")
        direita = [
            Text(st["nome"], style=f"bold {a.cor('forte')}"),
            Text.assemble((ic(st["classe_id"]) + " ", a.cor(cor)), (cls["nome"], a.cor(cor))),
            Text(f"{st['titulo']} · nível {st['nivel']}", style=a.cor("texto")),
            Text(""),
            Text.assemble((ic("streak") + " ", a.cor("orange")), (f"{st['streak']} dias seguidos", a.cor("texto"))),
            Text.assemble((ic("trofeu") + " ", a.cor("yellow")), (f"melhor streak: {st['melhor_streak']}", a.cor("mudo"))),
            Text.assemble((ic("estrela4") + " ", a.cor("yellow")),
                          (f"{st['pontos']} ponto{'s' if st['pontos'] != 1 else ''} de skill", a.cor("yellow"))),
        ]
        linhas = [Text("")]
        for i in range(max(len(ret), len(direita) + 1)):
            esq = ret[i] if i < len(ret) else Text(" " * 22)
            d = direita[i - 1] if 1 <= i <= len(direita) else Text("")
            linhas.append(Text("  ") + esq + Text("   ") + d)
        linhas.append(Text(""))
        larg_barra = max(10, w - 26)
        hp_cor = D.cor_hp(a, st["hp"], st["hp_max"], st["classe_id"] == "otaku")
        for nome, icone, cor_b, v, m in (("vida", "vida", hp_cor, st["hp"], st["hp_max"]), ("mana", "mana", "blue", st["mp"], st["mp_max"]),
                                         ("xp", "xp", "green", st["xp"], st["xp_proximo"])):
            t = Text.assemble((" " + ic(icone) + " ", a.cor({"vida": "red", "mana": "blue", "xp": "green"}[nome])),
                              (f"{nome:<6}", a.cor("mudo")))
            t.append_text(D.barra(a, v, m, larg_barra, cor_b))
            linhas.append(D.linha_lr(t, Text(f"{C.milhar(v)} / {C.milhar(m)}", style=a.cor("texto")), w))
        linhas.append(Text(""))
        hoje_bits = int(a.b.escalar("SELECT SUM(bits) FROM ganhos WHERE dia = ? AND bits > 0", (a.hoje(),), 0))
        linhas.append(Text.assemble((" " + ic("bits") + " ", a.cor("yellow")), (C.milhar(st["bits"]), f"bold {a.cor('forte')}"),
                                    ("  bits", a.cor("mudo")), (f"  +{hoje_bits} hoje" if hoje_bits else "", a.cor("mudo"))))
        prox = regras.combo_max(a.cfg, st["classe_id"] == "gamer")
        sub = f"mais 1 pomodoro sobe para x{min(prox, st['combo'] + 0.1):.1f}" if st["combo"] < prox else "no máximo"
        linhas.append(Text.assemble((" " + ic("combo") + " ", a.cor("yellow")), (f"combo x{st['combo']:.1f}", f"bold {a.cor('forte')}"),
                                    (f"  {sub}", a.cor("mudo"))))
        linhas.append(Text(" ") + mecanica_linha(a, st, w))
        falta = st["xp_proximo"] - st["xp"]
        linhas.append(Text(f" ▲ {C.milhar(st['xp'])} de {C.milhar(st['xp_proximo'])} xp: faltam {C.milhar(falta)} para o nível "
                           f"{st['nivel'] + 1}", style=a.cor("mudo")))
        return D.juntar(linhas)

    def rodape(self):
        return [("enter", "skills", "pagina(4)")]

    def teclas(self):
        return [("enter", "abre a árvore de skills"), ("alt+4", "skills de qualquer lugar")]

    def on_key(self, ev) -> None:
        if ev.key == "enter":
            ev.stop()
            self.app.abrir_pagina("skills", foco=True)


class JanelaHoje(Janela):
    NOME = "hoje"
    DEFAULT_CSS = """
    JanelaHoje { height: 20; }
    JanelaHoje #hoje-status { height: 2; margin-top: 1; }
    JanelaHoje #hoje-mestre { height: 1; margin-bottom: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Pintado(self._status, id="hoje-status")
        yield Lista(self._linha, altura=2, id="hoje-lista", cursor_apagado=True)
        yield Pintado(self._mestre, id="hoje-mestre", ao_clicar=lambda ev: self.app.abrir_pagina("taverna", foco=True))

    def pintar(self) -> None:
        a = self.app
        st = a.st.get("hoje") or {}
        self.titulo("hoje", f"meta {st.get('pomodoros', 0)} de {st.get('meta', 6)} pomodoros")
        itens = C.hoje_lista(a.b, a.cfg, a.hoje())
        self.query_one(Lista).definir(itens)
        for p in self.query(Pintado):
            p.pintar()

    def relogio(self) -> None:
        self.query_one("#hoje-status", Pintado).refresh()

    def _status(self, w: int) -> Text:
        a = self.app
        st = a.st.get("hoje") or {}
        feitos, meta = st.get("pomodoros", 0), st.get("meta", 6)
        t = Text("pomodoros ", style=a.cor("mudo"))
        t.append_text(D.pontos(a, feitos, max(meta, feitos)))
        p = a.st.get("pomodoro") or {}
        fase = p.get("fase")
        msg = {"foco": f"foco: {C.mmss(a.restante())} restantes", "pausa": "pausa curta de 5 min em andamento",
               "longa": "pausa longa de 15 min em andamento", "desmaio": "desmaiado: acorda depois da pausa longa"}.get(fase, "")
        if st.get("overtraining"):
            msg = "teto do dia passou: overtraining (XP pela metade)"
        if msg:
            t.append("   " + msg, style=a.cor("mudo") if fase != "desmaio" else a.cor("red"))
        return t

    def _linha(self, q: dict, i: int, est) -> list[Text]:
        a = self.app
        w = est.largura
        atual = a.st.get("pomodoro", {}).get("quest") == q["titulo"] and a.st.get("pomodoro", {}).get("fase") == "foco"
        fila = C.fila(a.b, a.cfg, a.hoje())
        primeira = bool(fila) and fila[0]["id"] == q["id"]
        feita = q["estado"] == "feita" or q["daily_feita"]
        vencida = q["tipo"] == "daily" and not feita and _perdeu_ontem(a, q)
        if feita:
            icone, cor = ic("feito"), "green"
        elif vencida:
            icone, cor = ic("vencida"), "red"
        elif atual or (primeira and q["feitos"]):
            icone, cor = ic("andamento"), "yellow"
        else:
            icone, cor = ic("pendente"), "texto"
        t = Text(icone + " ", style=a.cor(cor))
        t.append(q["titulo"], style=f"bold {a.cor('forte')}" if (atual or primeira) and not feita else a.cor("texto"))
        l1 = D.linha_lr(t, D.xp_bits(a, q["xp"], q["bits"], mudo=bool(feita)), w)
        l2 = Text("  ")
        mat = Text(ajustar(q["materia"] or "sem matéria", 13).plain, style=f"{a.cor(C.cor_materia(a.b, q['materia']))} on {a.cor('painel')}")
        l2.append_text(mat)
        l2.append(" ")
        l2.append_text(ajustar(D.pontos(a, q["feitos"], q["est"]), 7, "right"))
        l2.append(f" {q['feitos']}/{q['est']}", style=a.cor("mudo"))
        l2.append(" " * max(2, 31 - l2.cell_len))
        if feita:
            com = a.b.um("SELECT hash FROM commits c JOIN pomodoros p ON c.pomodoro_inicio = p.inicio WHERE p.quest_id = ? "
                         "ORDER BY c.ts DESC LIMIT 1", (q["id"],))
            l2.append(f"commit {com[0][:7]}" if com else "feita", style=a.cor("mudo"))
        elif vencida:
            l2.append(f"daily vencida · -{a.cfg['heroi']['daily_hp']} HP às 23:59", style=a.cor("red"))
        elif q["tipo"] == "daily":
            l2.append("daily", style=a.cor("mudo"))
        elif primeira:
            l2.append("agora" if atual else "próximo pomodoro", style=a.cor("mudo"))
        elif q["prazo"]:
            l2.append(f"prazo {C.dia_curto(q['prazo'])}", style=a.cor("mudo"))
        return [l1, l2]

    def _mestre(self, w: int) -> Text:
        a = self.app
        n = int(a.b.escalar("SELECT COUNT(*) FROM quests WHERE estado = 'rascunho'", (), 0))
        if not n:
            return Text("")
        t = Text.assemble((ic("mestre") + " ", a.cor("cyan")), (f"{n} rascunho{'s' if n > 1 else ''} do Mestre "
                                                              f"espera{'m' if n > 1 else ''} aprovação", a.cor("texto")))
        l = D.linha_lr(t, Text("t abre a taverna", style=a.cor("mudo")), w)
        l.stylize(f"on {a.cor('painel')}")
        return l

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.app.abrir_pagina("quests", foco=True, quest=ev.item["id"])

    def rodape(self):
        return [("enter", "abrir", "noop"), ("f", "foco", "noop"), ("n", "nova quest", "noop"), ("t", "taverna", "pagina(7)")]

    def teclas(self):
        return [("↑ ↓", "escolhe a quest"), ("enter", "abre a quest"), ("f", "começa o pomodoro nela"), ("n", "nova quest")]

    def quest_atual(self):
        return self.query_one(Lista).item_atual()


def _perdeu_ontem(a, q: dict) -> bool:
    ontem = C.ontem(a.hoje())
    r = a.b.um("SELECT daily_feita, daily_livre, criada FROM quests WHERE id = ?", (q["id"],))
    return bool(r and r["criada"] < C.inicio_do_dia(ontem) and r["daily_feita"] != ontem and r["daily_livre"] != ontem)


class JanelaCalor(Janela):
    NOME = "calor"
    FOCAVEL = True
    DEFAULT_CSS = "JanelaCalor { width: 58; }"

    def compose(self) -> ComposeResult:
        yield Pintado(self._desenhar)

    def pintar(self) -> None:
        self.titulo("últimas 24 semanas", "pomodoros")
        self.query_one(Pintado).pintar()

    def _desenhar(self, w: int) -> Text:
        a = self.app
        hoje = a.hoje()
        desde = (C.data(hoje) - timedelta(weeks=24)).isoformat()
        valores = C.calor(a.b, "pomodoros", desde)
        h = C.heroi(a.b)
        cor = h["tema_calor"] if h else "green"
        linhas = [Text("")] + [Text("  ") + l for l in D.mapa_calor(a, valores, hoje, 24, cor)]
        linhas += [Text(""), Text("      ") + D.legenda_calor(a, cor), Text("")]
        total = sum(valores.values())
        linhas.append(Text(f"{C.milhar(total)} pomodoros em 24 semanas", style=f"bold {a.cor('forte')}"))
        if valores:
            dia_max = max(valores, key=valores.get)
            d = C.data(dia_max)
            uteis = sum(1 for k in valores if C.data(k).weekday() < 5) or 1
            media = sum(v for k, v in valores.items() if C.data(k).weekday() < 5) / uteis
            linhas.append(Text(f"melhor dia: {d.day}/{d.month} com {valores[dia_max]}  ·  média {media:.1f} por dia útil"
                               .replace(".", ","), style=a.cor("mudo")))
        linhas.append(Text(""))
        linhas.append(D.secao(a, "por matéria", w))
        mats = C.materias(a.b, desde)[:5]
        soma = sum(n for _, n in mats) or 1
        for nome, n in mats:
            t = Text(ajustar(nome, 14).plain, style=a.cor("texto"))
            t.append_text(D.barra(a, n, mats[0][1], max(8, w - 22), C.cor_materia(a.b, nome)))
            t.append(f"{round(100 * n / soma):>5}%", style=a.cor("mudo"))
            linhas.append(t)
        return D.juntar(linhas)

    def rodape(self):
        return [("enter", "histórico", "pagina(6)")]

    def on_key(self, ev) -> None:
        if ev.key == "enter":
            ev.stop()
            self.app.abrir_pagina("historico", foco=True)


class JanelaAtividade(Janela):
    NOME = "atividade"
    DEFAULT_CSS = "JanelaAtividade { width: 55; } JanelaAtividade Lista { margin-top: 1; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, altura=2, id="atividade-lista", cursor_apagado=True)

    def pintar(self) -> None:
        self.titulo("atividade", "hoje")
        rows = [r for r in C.atividade(self.app.b, None, 40) if r["origem"] not in ("pausa", "dia")]
        self.query_one(Lista).definir(rows)

    def _linha(self, r, i: int, est) -> list[Text]:
        a = self.app
        icone, cor = ICONE_ORIGEM.get(r["origem"], ("ponto", "texto"))
        quando = D.quando(r["ts"], a.hoje())
        t = Text(f"{quando:<6} ", style=a.cor("mudo"))
        t.append(ic(icone) + " ", style=a.cor(cor))
        t.append(r["texto"], style=a.cor("texto"))
        d = Text("")
        if r["xp"]:
            d = Text(f"+{r['xp']} xp", style=a.cor("green"))
        elif r["bits"] > 0:
            d = Text(f"+{r['bits']}", style=a.cor("green"))
        elif r["hp"] < 0:
            d = Text(f"{r['hp']} hp", style=a.cor("red"))
        elif r["bits"] < 0:
            d = Text(f"{r['bits']}", style=a.cor("yellow"))
        return [D.linha_lr(t, d, est.largura), Text("")]

    def rodape(self):
        return [("↑ ↓", "rola", "noop")]


class JanelaMestre(Janela):
    NOME = "mestre"
    FOCAVEL = True

    def compose(self) -> ComposeResult:
        yield Pintado(self._desenhar)

    def pintar(self) -> None:
        self.titulo(f"{ic('mestre')} mestre", "claude")
        self.query_one(Pintado).pintar()

    def _desenhar(self, w: int) -> Text:
        a = self.app
        m = a.mestre_estado()
        cor = {"pronto": "cyan", "pensando": "yellow"}.get(m, "mudo")
        linhas = [Text(""), Text.assemble(("● ", a.cor(cor)), (m, a.cor(cor))), Text("")]
        r = a.b.um("SELECT texto FROM taverna WHERE papel = 'mestre' ORDER BY id DESC LIMIT 1")
        if r:
            txt = r["texto"]
            primeira, _, resto = txt.partition(":")
            if resto and len(primeira) < 40:
                linhas.append(Text(primeira + ":", style=f"bold {a.cor('forte')}"))
                linhas += D.quebrar(resto.strip(), w, a.cor("texto"))[:5]
            else:
                linhas += D.quebrar(txt, w, a.cor("texto"))[:6]
        else:
            linhas.append(Text("Converse com o Mestre na taverna para montar as quests da semana.", style=a.cor("mudo")))
        linhas += [Text(""), Text("─" * w, style=a.cor("linha")), Text.assemble(("t", a.cor("accent")), (" abre a taverna", a.cor("mudo"))),
                   Text(""), Text("conquistas", style=f"bold {a.cor('forte')}"), Text("")]
        feitas = C.conquistas_feitas(a.b)
        con = a.cfg["conquistas"]
        recentes = sorted(feitas, key=lambda k: feitas[k], reverse=True)[:2]
        for cid in recentes:
            c = con.get(cid)
            if not c:
                continue
            linhas.append(Text.assemble((ic(c["icone"]) + " ", a.cor("yellow")), (c["nome"], a.cor("texto"))))
            linhas.append(Text(f"  +{c['xp']} xp", style=a.cor("mudo")))
            linhas.append(Text(""))
        faltam = len([k for k in con if k not in feitas])
        linhas.append(Text.assemble((ic("bau") + " ", a.cor("mudo")), (f"{faltam} conquistas a caminho", a.cor("mudo"))))
        return D.juntar(linhas)

    def rodape(self):
        return [("t", "taverna", "pagina(7)")]

    def on_key(self, ev) -> None:
        if ev.key == "enter":
            ev.stop()
            self.app.abrir_pagina("taverna", foco=True)


class PaginaPainel(Pagina):
    NOME = "painel"
    TITULO = "painel"
    ENTRADA = "hoje"
    VIZINHAS = {
        "heroi": {"esq": "paineis", "dir": "hoje", "cima": "topo", "baixo": "calor"},
        "hoje": {"esq": "heroi", "cima": "topo", "baixo": "atividade"},
        "calor": {"esq": "paineis", "dir": "atividade", "cima": "heroi"},
        "atividade": {"esq": "calor", "dir": "mestre", "cima": "hoje"},
        "mestre": {"esq": "atividade", "cima": "hoje"},
    }
    BINDINGS = [Binding("f", "foco", show=False), Binding("n", "nova", show=False), Binding("t", "taverna", show=False)]
    DEFAULT_CSS = "PaginaPainel { layout: vertical; } PaginaPainel .linha { height: auto; } PaginaPainel #baixo { height: 1fr; }"

    def compose(self) -> ComposeResult:
        with Horizontal(classes="linha"):
            yield JanelaHeroi()
            yield JanelaHoje()
        with Horizontal(id="baixo"):
            yield JanelaCalor()
            yield JanelaAtividade()
            yield JanelaMestre()

    def relogio(self) -> None:
        self.query_one(JanelaHoje).relogio()

    def rodape_pagina(self):
        return [("enter", "abrir", "noop"), ("f", "foco", "noop"), ("n", "nova quest", "noop"), ("t", "taverna", "pagina(7)")]

    def action_foco(self) -> None:
        q = self.query_one(JanelaHoje).quest_atual() if self.app.nome_janela(self.app.focused) == "hoje" else None
        a = self.app
        if (a.st.get("pomodoro") or {}).get("fase") in ("parado", "pausa", "longa") and q and q["estado"] == "aberta":
            a.pedir("iniciar", {"quest": q["id"]}, lambda ok, r: ok and a.abrir_pagina("foco", foco=True))
        else:
            a.abrir_pagina("foco", foco=True)

    def action_nova(self) -> None:
        from oma_rpg.ui.dialogos import EditarQuest
        self.app.push_screen(EditarQuest(None))

    def action_taverna(self) -> None:
        self.app.abrir_pagina("taverna", foco=True)


PAGINA = PaginaPainel
