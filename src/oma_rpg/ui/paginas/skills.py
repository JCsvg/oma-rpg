"""Tela 5 · skills: a árvore da classe, 3 ramos de 5 skills, com tipo, efeito, custo e requisito.
enter aprende · ←→ ramo · c vê as classes · r respec (custa Bits) · alt+←→ olha a árvore de outra classe.
O Gamer tem um easter egg: ↑↑↓↓←→←→BA aqui destrava um título."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget

from oma_rpg.nucleo import consultas as C
from oma_rpg.ui import desenho as D
from oma_rpg.ui.base import Janela, Pagina, pagina_de
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lista import ajustar
from oma_rpg.ui.widgets import Botao, Pintado

KONAMI = ["up", "up", "down", "down", "left", "right", "left", "right", "b", "a"]
ESTADO_TXT = {"aprendida": ("aprendida", "green", "✓"), "disponivel": ("disponível", "yellow", "●"),
              "bloqueada": ("bloqueada", "mudo", "◌"), "previa": ("outra classe", "mudo", "◇")}


class Arvore(Widget, can_focus=True):
    pg = property(lambda self: pagina_de(self))
    DEFAULT_CSS = "Arvore { height: 1fr; width: 1fr; }"
    BINDINGS = [Binding("up,k", "mover(0, -1)", show=False), Binding("down,j", "mover(0, 1)", show=False),
                Binding("left,h", "mover(-1, 0)", show=False), Binding("right,l", "mover(1, 0)", show=False),
                Binding("b", "tecla('b')", show=False), Binding("a", "tecla('a')", show=False)]

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.ramo, self.pos = 1, 2
        self._caixas: list[tuple[int, int, int, int, str]] = []
        self._abas: list[tuple[int, int, str]] = []
        self._seq: list[str] = []

    def sid(self) -> str | None:
        a = self.app
        for s in a.cfg.skills_da_classe(self.pg.classe):
            d = a.cfg.skill(s)
            if d["ramo"] == self.ramo and d["pos"] == self.pos:
                return s
        return None

    def ir_para(self, sid: str) -> None:
        d = self.app.cfg.skill(sid)
        self.ramo, self.pos = d["ramo"], d["pos"]
        self.refresh()

    def estados(self) -> dict[str, str]:
        a = self.app
        h = C.heroi(a.b)
        cid = self.pg.classe
        if h is None or cid != h["classe"]:
            return {s: "previa" for s in a.cfg.skills_da_classe(cid)}
        return C.skills_estado(a.b, a.cfg, h)

    def render(self) -> Text:
        a = self.app
        w = self.size.width
        cid = self.pg.classe
        cls = a.cfg.classe(cid)
        h = C.heroi(a.b)
        est = self.estados()
        linhas: list[Text] = []
        self._caixas, self._abas = [], []
        # abas das classes
        t = Text(no_wrap=True)
        for n, c in enumerate(a.cfg.classes_ordem()):
            if n:
                t.append(" ")
            x0 = t.cell_len
            nome = f" {ic(c)} {a.cfg.classe(c)['nome']} "
            if c == cid:
                t.append(nome, style=f"bold {a.cor('fundo')} on {a.cor('accent')}")
            else:
                t.append(nome, style=f"{a.cor('texto')} on {a.cor('campo')}")
            self._abas.append((x0, t.cell_len, c))
        linhas += [Text(""), t, Text("")]
        mec = f"{cls['poder_titulo']}: {cls['poder_txt'][0].lower()}{cls['poder_txt'][1:]}"
        if h and cid != h["classe"]:
            mec += "  (prévia: a sua classe é " + a.cfg.classe(h["classe"])["nome"] + ")"
        linhas.append(Text(mec, style=a.cor("mudo")))
        linhas.append(Text(""))
        cw = max(20, (w - 2) // 3)
        bw = min(32, cw - 4)
        cab, reg = Text(" "), Text(" ")
        for r, nome in enumerate(cls["ramos"]):
            cab.append_text(ajustar(Text(nome, style=f"bold {a.cor(cls['cor'])}"), cw))
            reg.append("─" * (cw - 3), style=a.cor("linha"))
            reg.append("   ")
        linhas += [cab, reg, Text("")]
        sk = a.cfg.skills_da_classe(cid)
        por = {(a.cfg.skill(s)["ramo"], a.cfg.skill(s)["pos"]): s for s in sk}
        P = C.passivos(a.b, a.cfg, a.hoje(), h) if h else None
        for pos in range(5):
            y0 = len(linhas)
            caixas = []
            for r in range(3):
                sid = por[(r, pos)]
                s = a.cfg.skill(sid)
                e = est.get(sid, "bloqueada")
                rot, cor, marca = ESTADO_TXT[e]
                cursor = r == self.ramo and pos == self.pos
                borda = a.cor("accent") if cursor and self.has_focus else a.cor("forte") if cursor else \
                    a.cor("linha") if e in ("bloqueada", "previa") else a.cor("texto")
                fundo = f" on {a.cor('selecao')}" if cursor else ""
                nome = Text()
                nome.append(marca + " ", style=a.cor(cor) + fundo)
                nome.append(s["nome"], style=(f"bold {a.cor('forte')}" if e != "bloqueada" else a.cor("mudo")) + fundo)
                custo = f"{C.custo_mana(a.cfg, s, P) if P else s.get('mp', 0)} mp" if s["tipo"] == "ativa" else \
                    ("2 pts" if s["pos"] == 4 else "")
                l2 = D.linha_lr(Text(s["tipo"], style=a.cor("mudo") + fundo), Text(custo, style=a.cor("blue") + fundo), bw - 6)
                l3 = Text(rot, style=a.cor(cor) + fundo)
                caixa = [Text("┌" + "─" * (bw - 2) + "┐", style=borda)]
                for conteudo in (nome, l2, l3):
                    c = Text("│ ", style=borda)
                    corpo = ajustar(conteudo, bw - 4)
                    if cursor:
                        corpo.stylize(f"on {a.cor('selecao')}")
                    c.append_text(corpo)
                    c.append(" │", style=borda)
                    caixa.append(c)
                caixa.append(Text("└" + "─" * (bw - 2) + "┘", style=borda))
                caixas.append(caixa)
                x0 = 1 + r * cw + 1
                self._caixas.append((x0, y0, x0 + bw, y0 + 5, sid))
            for i in range(5):
                t = Text(" ")
                for r in range(3):
                    t.append(" ")
                    t.append_text(caixas[r][i])
                    t.append(" " * (cw - bw - 1))
                linhas.append(t)
            if pos < 4:
                t = Text(" ")
                for r in range(3):
                    t.append(" " * (1 + bw // 2) + "│" + " " * (cw - bw // 2 - 2), style=a.cor("linha"))
                linhas.append(t)
        linhas += [Text(""), Text(f" ◆ gasta mana · ◇ sempre ligada · a última de cada ramo custa 2 pontos", style=a.cor("mudo"))]
        return D.juntar(linhas)

    def action_mover(self, dx: int, dy: int) -> None:
        self._registrar({(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}[(dx, dy)])
        self.ramo = max(0, min(2, self.ramo + dx))
        self.pos = max(0, min(4, self.pos + dy))
        self.refresh()
        self.pg.mostrar()

    def action_tecla(self, k: str) -> None:
        self._registrar(k)

    def _registrar(self, k: str) -> None:
        self._seq = (self._seq + [k])[-len(KONAMI):]
        if self._seq == KONAMI:
            self._seq = []
            a = self.app
            h = C.heroi(a.b)
            if self.pg.classe == "gamer" or (h and h["classe"] == "gamer"):
                a.pedir("konami")

    def on_click(self, ev: events.Click) -> None:
        ev.stop()
        self.focus()
        for x0, x1, c in self._abas:
            if ev.y == 1 and x0 <= ev.x < x1:
                self.pg.ver_classe(c)
                return
        for x0, y0, x1, y1, sid in self._caixas:
            if x0 <= ev.x < x1 and y0 <= ev.y < y1:
                self.ir_para(sid)
                self.pg.mostrar()
                if ev.chain >= 2:
                    self.pg.action_aprender()
                return

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()


class JanelaArvore(Janela):
    NOME = "arvore"

    def compose(self) -> ComposeResult:
        yield Arvore(id="arvore-grade")

    def pintar(self) -> None:
        a = self.app
        h = a.st.get("heroi") or {}
        self.titulo("árvore de skills", f"{h.get('pontos', 0)} pontos livres · respec {a.cfg['loja']['respec_skill_bits']} bits")
        self.query_one(Arvore).refresh()

    def alt_h(self, passo: int) -> None:
        a = self.app
        ordem = a.cfg.classes_ordem()
        self.pg.ver_classe(ordem[(ordem.index(self.pg.classe) + passo) % len(ordem)])

    def rodape(self):
        return [("enter", "aprender", "noop"), ("←→", "ramo", "noop"), ("c", "classes", "noop"), ("r", "respec", "noop")]

    def teclas(self):
        return [("← → ↑ ↓", "anda pela árvore"), ("enter ou clique duplo", "aprende"), ("r", "respec da skill (bits)"),
                ("c", "todas as classes"), ("alt+← →", "olha a árvore de outra classe")]


class JanelaSkill(Janela):
    NOME = "skill"
    DEFAULT_CSS = """
    JanelaSkill { width: 41; }
    JanelaSkill #skill-corpo { height: 1fr; }
    JanelaSkill #skill-botao { margin: 1 0 0 0; }
    JanelaSkill #skill-pe { height: 2; }
    """

    def compose(self) -> ComposeResult:
        yield Pintado(self._desenhar, id="skill-corpo")
        yield Botao("enter  aprender", id="skill-botao", classes="cheio")
        yield Pintado(self._pe, id="skill-pe")

    def pintar(self) -> None:
        self.titulo("skill", "c classes")
        a = self.app
        sid = self.pg.query_one(Arvore).sid()
        est = self.pg.query_one(Arvore).estados().get(sid, "bloqueada")
        b = self.query_one(Botao)
        b.display = est == "disponivel"
        for p in self.query(Pintado):
            p.pintar()

    def _desenhar(self, w: int) -> Text:
        a = self.app
        arv = self.pg.query_one(Arvore)
        sid = arv.sid()
        if not sid:
            return Text("")
        s = a.cfg.skill(sid)
        cls = a.cfg.classe(s["classe"])
        est = arv.estados().get(sid, "bloqueada")
        rot, cor, marca = ESTADO_TXT[est]
        h = C.heroi(a.b)
        P = C.passivos(a.b, a.cfg, a.hoje(), h) if h else None
        custo_mp = C.custo_mana(a.cfg, s, P) if P else s.get("mp", 0)
        linhas = [Text(""), Text.assemble((ic("desfazer" if s["efeito"] == "desfazer_hp" else "raio") + " ", a.cor("yellow")),
                                          (s["nome"], f"bold {a.cor('yellow' if est == 'disponivel' else 'forte')}")),
                  Text(f"{cls['ramos'][s['ramo']]} · {s['tipo']}" + (f" · {custo_mp} mp" if s["tipo"] == "ativa" else ""),
                       style=a.cor("mudo")), Text(""),
                  Text.assemble((marca + " ", a.cor(cor)), (rot, a.cor(cor))), Text(""),
                  D.secao(a, "efeito", w), Text("")]
        linhas += D.quebrar(s["desc"][0].upper() + s["desc"][1:] + ("" if s["desc"].endswith(".") else "."), w, a.cor("texto"))
        linhas += [Text(""), D.secao(a, "requisito", w), Text("")]
        if s["pos"] == 0:
            linhas.append(Text("nenhum: é a primeira do ramo", style=a.cor("mudo")))
        else:
            ant = next(k for k in a.cfg.skills_da_classe(s["classe"]) if a.cfg.skill(k)["ramo"] == s["ramo"]
                       and a.cfg.skill(k)["pos"] == s["pos"] - 1)
            ok = arv.estados().get(ant) == "aprendida"
            linhas.append(Text.assemble(("✓ " if ok else "◌ ", a.cor("green") if ok else a.cor("mudo")),
                                        (f"{a.cfg.skill(ant)['nome']} ({'aprendida' if ok else 'ainda não'})", a.cor("texto"))))
        linhas += [Text(""), D.secao(a, "custo", w), Text("")]
        pts = C.custo_skill(s)
        linhas.append(Text(f"{pts} ponto{'s' if pts > 1 else ''} de skill", style=a.cor("texto")))
        if h:
            linhas.append(Text(f"você tem {h['pontos']}", style=a.cor("mudo")))
        linhas.append(Text(""))
        if s.get("uso"):
            linhas += D.quebrar(s["uso"], w, a.cor("mudo"))
        elif s["tipo"] == "ativa":
            linhas += D.quebrar(f"uso: {custo_mp} mana, uma vez por dia; tecla de 1 a 4 no foco", w, a.cor("mudo"))
        else:
            linhas.append(Text("sempre ligada depois de aprendida", style=a.cor("mudo")))
        if s.get("frase"):
            linhas += [Text("")] + D.quebrar(f"“{s['frase']}”", w, a.cor("mudo"))
        return D.juntar(linhas)

    def _pe(self, w: int) -> Text:
        a = self.app
        return D.juntar([Text(""), Text.assemble(("r", a.cor("accent")), (" respec · ", a.cor("mudo")), ("c", a.cor("accent")),
                                                 (" todas as classes", a.cor("mudo")))])

    def on_botao_apertado(self, ev: Botao.Apertado) -> None:
        ev.stop()
        self.pg.action_aprender()

    def rodape(self):
        return [("enter", "aprender", "noop"), ("r", "respec", "noop"), ("c", "classes", "noop")]


class PaginaSkills(Pagina):
    NOME = "skills"
    TITULO = "skills"
    ENTRADA = "arvore"
    VIZINHAS = {
        "arvore": {"esq": "paineis", "dir": "skill", "cima": "topo"},
        "skill": {"esq": "arvore", "cima": "topo"},
    }
    BINDINGS = [Binding("enter", "aprender", show=False), Binding("c", "classes", show=False), Binding("r", "respec", show=False)]

    def __init__(self, skill: str | None = None, classe: str | None = None, **kw) -> None:
        super().__init__()
        self._skill = skill
        self._classe = classe
        self.classe = "programa"

    def compose(self) -> ComposeResult:
        yield JanelaArvore()
        yield JanelaSkill()

    def on_mount(self) -> None:
        a = self.app
        h = C.heroi(a.b)
        self.classe = h["classe"] if h else "programa"
        if self._classe in a.cfg["classes"]:
            self.classe = self._classe
        if self._skill in a.cfg["skills"]:
            self.classe = a.cfg.skill(self._skill)["classe"]
            self.query_one(Arvore).ir_para(self._skill)
        elif self.classe == (h["classe"] if h else ""):
            est = C.skills_estado(a.b, a.cfg, h)
            disp = [s for s in a.cfg.skills_da_classe(self.classe) if est[s] == "disponivel"]
            if disp:
                self.query_one(Arvore).ir_para(disp[0])

    def trilha(self):
        return [("skills", "")]

    def mostrar(self) -> None:
        self.query_one(JanelaSkill).pintar()

    def ver_classe(self, cid: str) -> None:
        self.classe = cid
        self.query_one(Arvore).refresh()
        self.mostrar()

    def rodape_pagina(self):
        return [("enter", "aprender", "aprender"), ("←→", "ramo", "noop"), ("c", "classes", "classes"), ("r", "respec", "respec")]

    def action_aprender(self) -> None:
        a = self.app
        h = C.heroi(a.b)
        if h is None or self.classe != h["classe"]:
            a.avisar("é a árvore de outra classe: troque em classes (c) para aprender", alerta=True)
            return
        sid = self.query_one(Arvore).sid()
        if sid:
            a.pedir("aprender", {"skill": sid})

    def action_respec(self) -> None:
        from oma_rpg.ui.dialogos import Confirmar
        a = self.app
        sid = self.query_one(Arvore).sid()
        if not sid or self.query_one(Arvore).estados().get(sid) != "aprendida":
            a.avisar("respec vale para uma skill aprendida (a última do ramo)", alerta=True)
            return
        custo = a.cfg["loja"]["respec_skill_bits"]
        a.push_screen(Confirmar("respec", [f"Desaprender {a.cfg.skill(sid)['nome']} e receber os pontos de volta?",
                                           f"custa {custo} bits"], "respec"),
                      lambda ok: ok and a.pedir("respec", {"skill": sid}))

    def action_classes(self) -> None:
        self.app.abrir_pagina("classes", foco=True, historico=True)


PAGINA = PaginaSkills
