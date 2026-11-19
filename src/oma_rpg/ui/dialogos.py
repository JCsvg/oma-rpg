"""Diálogos (tela 10 do design): nível alcançado, abandonar o pomodoro, desmaio, concluir quest (check-in), aprovar
rascunho, carta do dia, editar quest, novo arco, confirmar, busca, teclas e repositórios. enter confirma · esc fecha.

A base (Dialogo com clique fora fechando e Tab entre os campos) vem do oma-mail.
"""

from __future__ import annotations

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.markup import escape
from textual.screen import ModalScreen, Screen
from textual.widgets import Input, Static

from oma_rpg.nucleo import consultas as C
from oma_rpg.nucleo import regras
from oma_rpg.ui import desenho as D
from oma_rpg.ui.fonte import grande
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lista import Lista, ajustar
from oma_rpg.ui.widgets import Botao, Pintado

_CSS = """
{n} { align: center middle; background: $background 60%; }
{n} #caixa { width: 60; max-width: 100%; height: auto; max-height: 92%; background: $background; border: solid $accent;
             border-title-color: $accent; border-title-style: bold; padding: 0 2; }
{n} .linha-texto { height: auto; }
{n} #botoes { height: 1; margin-top: 1; }
{n} #botoes Botao { margin-right: 2; }
{n} .pe { height: 1; margin-top: 1; }
{n} .rot { width: 14; color: $rpg-mudo; }
{n} .campo { height: 1; margin-bottom: 0; }
{n} Input { width: 1fr; }
"""


def css(nome: str, extra: str = "") -> str:
    return _CSS.replace("{n}", nome) + extra


def pe(app, itens: list[tuple[str, str]]) -> Text:
    t = Text(no_wrap=True)
    for n, (k, rot) in enumerate(itens):
        if n:
            t.append("   ")
        t.append(k, style=app.cor("accent"))
        t.append(" " + rot, style=app.cor("mudo"))
    return t


class Dialogo(ModalScreen):
    BINDINGS = [Binding("escape", "cancelar", "fechar", priority=True)]

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def mover_janela(self, direcao: str) -> None:
        (self.focus_next if direcao in ("dir", "baixo") else self.focus_previous)()

    def on_click(self, ev: events.Click) -> None:
        if ev.widget is self:
            self.action_cancelar()

    @on(Botao.Apertado)
    def _botao(self, ev: Botao.Apertado) -> None:
        ev.stop()
        self.apertou(ev.botao.id or "")

    def apertou(self, bid: str) -> None:
        pass


# ---------------------------------------------------------------- corpos (também usados na vitrine das capturas)
def corpo_nivel(app, d: dict) -> list[Text]:
    a = app
    linhas = [Text(""), ajustar(Text(ic("festa"), style=a.cor("yellow")), 52, "center"), Text("")]
    for l in grande(f"NIVEL {d['nivel']}"):
        linhas.append(ajustar(Text(l, style=a.cor("green")), 52, "center"))
    linhas.append(Text(""))
    linhas.append(ajustar(Text(f"+{d.get('pontos', 1)} ponto de skill  ·  +{d.get('hp', 10)} de HP  ·  +{d.get('bits', 25)} bits",
                               style=a.cor("texto")), 52, "center"))
    if d.get("titulo"):
        linhas.append(ajustar(Text(f"novo título: {d['titulo']}", style=a.cor("blue")), 52, "center"))
    return linhas


def corpo_abandonar(app) -> list[Text]:
    a = app
    dec = a.decorrido()
    h = C.heroi(a.b)
    P = C.passivos(a.b, a.cfg, a.hoje(), h)
    pc = a.cfg["pomodoro"]
    livre = dec < pc["abandono_livre_min"] * 60
    mult = (2.0 if C.tem_efeito(a.b, "arriscar") else 1.0) * (P["abandono_mult"] or 1.0)
    custo = regras.arred(pc["abandono_hp"] * max(0.0, 1 - P["abandono_hp"] / 100) * mult)
    cmb = C.combo_de(a.cfg, h, P, a._atual_row["inicio"]) if a._atual_row is not None else 1.0
    linhas = [Text(""), Text(f"Você fez {int(dec // 60)} de {pc['minutos_foco']} minutos.", style=a.cor("texto")), Text("")]
    if livre:
        linhas.append(Text(f"antes de {pc['abandono_livre_min']} min: abandonar não custa HP nem combo", style=a.cor("green")))
    else:
        linhas.append(Text(f"abandonar custa {custo} HP e zera o combo x{cmb:.1f}", style=a.cor("red")))
    g = _skill_guardar(a, h)
    if g:
        s = a.cfg.skill(g)
        linhas += [Text(""), Text(f"{s['nome']} guarda o pomodoro e mantém o combo", style=a.cor("green")),
                   Text(f"({C.custo_mana(a.cfg, s, P)} mana, você tem {h['mp']})", style=a.cor("mudo"))]
    return linhas


def _skill_guardar(a, h) -> str | None:
    for sid in C.ativas(a.b, a.cfg, h):
        if a.cfg.skill(sid)["efeito"] == "guardar" and not C.uso_hoje(a.b, sid, a.hoje()):
            return sid
    return None


def corpo_desmaio(app, d: dict) -> list[Text]:
    a = app
    linhas = [Text(""), Text.assemble((ic("coracao_partido") + " ", a.cor("red")), ("o HP chegou a 0", f"bold {a.cor('forte')}")),
              Text("")]
    linhas.append(Text("• perdeu o streak de hoje" + (" (backup guardou o de ontem)" if d.get("backup") else ""), style=a.cor("texto")))
    linhas.append(Text(f"• perdeu 10% dos bits: -{d.get('bits', 0)}", style=a.cor("texto")))
    linhas.append(Text("• o nível e as skills continuam com você", style=a.cor("texto")))
    linhas += [Text(""), Text("acorda com 50% de HP depois de uma pausa longa", style=a.cor("mudo"))]
    return linhas


def corpo_carta(app, buff: str, debuff: str, revelada: bool = True) -> list[Text]:
    a = app
    b, db = a.cfg["cartas"][buff], a.cfg["cartas"][debuff]
    cor = a.cor("magenta")
    vazio = ["┌───────┐", "│       │", "│   ☆   │", "│       │", "│       │", "└───────┘"]
    meio = ["┌───────┐", f"│{b['numero']:^7}│", f"│{'✦':^7}│", "│       │", f"│{b['nome'].split()[-1].upper()[:7]:^7}│", "└───────┘"]
    lado = [("buff", a.cor("mudo")), (b["curto"], a.cor("green")), ("", ""), ("debuff", a.cor("mudo")), (db["curto"], a.cor("red")), ("", "")]
    linhas = [Text("")]
    for i in range(6):
        t = Text("  ")
        t.append(vazio[i], style=a.cor("mudo"))
        t.append("  ")
        t.append(meio[i] if revelada else vazio[i], style=cor if revelada else a.cor("mudo"))
        t.append("  ")
        t.append(vazio[i], style=a.cor("mudo"))
        t.append("   ")
        t.append(lado[i][0], style=lado[i][1] or a.cor("mudo"))
        linhas.append(t)
    linhas += [Text(""), Text(f"{b['nome']}: {b['desc']}", style=a.cor("texto")), Text(f"{db['nome']}: {db['desc']}", style=a.cor("red"))]
    return linhas


class _Simples(Dialogo):
    """Diálogo de texto com o pé de teclas e um botão principal."""

    BORDA = "accent"
    TITULO = ""
    LARGURA = 60

    def linhas(self) -> list[Text]:
        return []

    def teclas_pe(self) -> list[tuple[str, str]]:
        return [("esc", "fecha")]

    def botoes(self) -> list[tuple[str, str, str]]:
        return []

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = escape(self.TITULO)
            c.styles.width = self.LARGURA
            c.styles.border = ("solid", self.app.cor(self.BORDA))
            c.styles.border_title_color = self.app.cor(self.BORDA)
            yield Static(D.juntar(self.linhas()), classes="linha-texto")
            if self.botoes():
                with Horizontal(id="botoes"):
                    for bid, rot, cls in self.botoes():
                        yield Botao(rot, id=bid, classes=cls)
            yield Static(pe(self.app, self.teclas_pe()), classes="pe")

    def on_mount(self) -> None:
        b = list(self.query(Botao))
        if b:
            b[0].focus()


class Nivel(_Simples):
    DEFAULT_CSS = css("Nivel")
    TITULO = "nível alcançado"

    def __init__(self, d: dict) -> None:
        super().__init__()
        self.d = d

    def linhas(self):
        return corpo_nivel(self.app, self.d)

    def botoes(self):
        return [("ok", "enter  continuar", "cheio")]

    def teclas_pe(self):
        return [("enter", "continuar"), ("alt+4", "gastar o ponto")]

    def apertou(self, bid: str) -> None:
        self.dismiss(True)


class Desmaio(_Simples):
    DEFAULT_CSS = css("Desmaio")
    TITULO = "você desmaiou"
    BORDA = "red"
    LARGURA = 64

    def __init__(self, d: dict) -> None:
        super().__init__()
        self.d = d

    def linhas(self):
        return corpo_desmaio(self.app, self.d)

    def botoes(self):
        return [("ok", "enter  acordar", "cheio")]

    def teclas_pe(self):
        return [("enter", "fecha (acorda sozinho em 15 min)")]

    def apertou(self, bid: str) -> None:
        self.app.pedir("acordar", avisar_erro=False)
        self.dismiss(True)


class Abandonar(_Simples):
    DEFAULT_CSS = css("Abandonar")
    TITULO = "abandonar o pomodoro?"
    BORDA = "yellow"
    BINDINGS = [Binding("escape", "cancelar", priority=True), Binding("s", "guardar"), Binding("x", "abandonar")]

    def linhas(self):
        return corpo_abandonar(self.app)

    def botoes(self):
        b = [("voltar", "esc voltar", "cheio")]
        if _skill_guardar(self.app, C.heroi(self.app.b)):
            b.append(("guardar", "s guardar", ""))
        b.append(("abandonar", "x abandonar", "vermelho"))
        return b

    def teclas_pe(self):
        return [("s", "guardar"), ("x", "abandonar"), ("esc", "voltar")]

    def action_guardar(self) -> None:
        sid = _skill_guardar(self.app, C.heroi(self.app.b))
        if sid:
            self.app.pedir("usar_skill", {"skill": sid})
            self.dismiss(True)

    def action_abandonar(self) -> None:
        self.app.pedir("abandonar")
        self.dismiss(True)

    def apertou(self, bid: str) -> None:
        if bid == "guardar":
            self.action_guardar()
        elif bid == "abandonar":
            self.action_abandonar()
        else:
            self.dismiss(None)


class Carta(_Simples):
    DEFAULT_CSS = css("Carta")
    TITULO = "carta do dia (Jovem Místico)"
    BORDA = "magenta"
    LARGURA = 64
    BINDINGS = [Binding("escape", "cancelar", priority=True), Binding("space", "tirar")]

    def __init__(self, buff: str, debuff: str) -> None:
        super().__init__()
        self.buff, self.debuff = buff, debuff
        self.revelada = False

    def linhas(self):
        return corpo_carta(self.app, self.buff, self.debuff, self.revelada)

    def botoes(self):
        return [("tirar", "espaço  tira a carta", "cheio")]

    def teclas_pe(self):
        return [("espaço", "tira"), ("esc", "depois")]

    def action_tirar(self) -> None:
        if self.revelada:
            self.dismiss(True)
            return
        self.revelada = True
        self.app.pedir("revelar_carta")
        self.query_one(".linha-texto", Static).update(D.juntar(self.linhas()))
        self.query_one("#tirar", Botao).label = "enter  continuar"

    def apertou(self, bid: str) -> None:
        self.action_tirar()


class Confirmar(_Simples):
    DEFAULT_CSS = css("Confirmar")
    BORDA = "yellow"

    def __init__(self, titulo: str, linhas: list[str], rotulo: str = "confirmar") -> None:
        super().__init__()
        self.TITULO = titulo
        self._linhas, self.rotulo = linhas, rotulo

    def linhas(self):
        return [Text("")] + [Text(l, style=self.app.cor("texto" if i == 0 else "mudo")) for i, l in enumerate(self._linhas)]

    def botoes(self):
        return [("nao", "cancelar", "cheio"), ("sim", self.rotulo, "vermelho")]

    def teclas_pe(self):
        return [("← →", "escolhe"), ("enter", "aperta"), ("esc", "cancela")]

    def apertou(self, bid: str) -> None:
        self.dismiss(bid == "sim")

    def on_key(self, ev: events.Key) -> None:
        if ev.key in ("left", "right", "h", "l"):
            ev.stop()
            self.focus_next()


class Pedir(Dialogo):
    DEFAULT_CSS = css("Pedir", "Pedir #campo { margin-top: 1; }")

    def __init__(self, titulo: str, rotulo: str, valor: str = "") -> None:
        super().__init__()
        self.titulo, self.rotulo, self.valor = titulo, rotulo, valor

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = escape(self.titulo)
            yield Static(Text(self.rotulo, style=self.app.cor("mudo")), classes="linha-texto")
            yield Input(self.valor, id="campo")
            yield Static(pe(self.app, [("enter", "salva"), ("esc", "volta")]), classes="pe")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        ev.stop()
        self.dismiss(ev.value.strip() or None)


# ---------------------------------------------------------------- concluir quest (check-in)
def info_conclusao(app, q: dict) -> tuple[Text, Text]:
    a = app
    cheio = q["feitos"] >= regras.xp_cheio_minimo(q["est"], a.cfg)
    if q["feitos"] == 0:
        t1 = Text(f"0 de {q['est']} pomodoros · sem pomodoro, 0 xp", style=a.cor("red"))
    else:
        xp = regras.xp_quest_concluida(q["est"], q["dif"], q["feitos"], a.cfg)
        t1 = Text(f"{q['feitos']} de {q['est']} pomodoros · " + ("XP cheio" if cheio else f"{xp} de {q['xp']} xp (70% para o cheio)"),
                  style=a.cor("green" if cheio else "yellow"))
    com = a.b.todos("SELECT c.xp, r.caminho FROM commits c JOIN repos r ON r.id = c.repo_id JOIN pomodoros p "
                    "ON c.pomodoro_inicio = p.inicio WHERE p.quest_id = ?", (q["id"],))
    if com:
        import os
        onde = com[0]["caminho"].replace(os.path.expanduser("~"), "~")
        t2 = Text.assemble((ic("commit") + " ", a.cor("blue")),
                           (f"{len(com)} commit{'s' if len(com) > 1 else ''} em {onde} detectado{'s' if len(com) > 1 else ''}: "
                            f"+{sum(c['xp'] for c in com)} xp", a.cor("texto")))
    else:
        t2 = Text("nenhum commit nos pomodoros desta quest", style=a.cor("mudo"))
    return t1, t2


class Concluir(Dialogo):
    DEFAULT_CSS = css("Concluir", "Concluir #caixa { border: solid $success; border-title-color: $success; width: 62; } "
                                  "Concluir #nota { margin: 0 0 1 0; }")

    def __init__(self, q: dict) -> None:
        super().__init__()
        self.q = q

    def compose(self) -> ComposeResult:
        a = self.app
        t1, t2 = info_conclusao(a, self.q)
        with Vertical(id="caixa") as c:
            c.border_title = "concluir quest"
            yield Static(D.juntar([Text(""), Text(self.q["titulo"], style=f"bold {a.cor('forte')}"), t1, Text(""),
                                   Text("o que você fez? (uma linha)", style=a.cor("mudo"))]), classes="linha-texto")
            yield Input(placeholder="escrevi a 2.1 com 4 modelos e a tabela", id="nota")
            yield Static(t2, classes="linha-texto")
            yield Static(pe(a, [("enter", "concluir"), ("esc", "volta")]), classes="pe")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        ev.stop()
        self.app.pedir("concluir_quest", {"id": self.q["id"], "nota": ev.value.strip()})
        self.dismiss(True)


# ---------------------------------------------------------------- editar quest e aprovar rascunho
class EditarQuest(Dialogo):
    """Nova quest, editar quest ou aprovar rascunho (os mesmos campos). A recompensa aparece calculada, sem campo."""

    DEFAULT_CSS = css("EditarQuest", """
    EditarQuest #caixa { width: 88; }
    EditarQuest .campo { height: 1; }
    EditarQuest #campo-desc { height: 6; margin-top: 1; }
    EditarQuest #c-porque { height: 5; border: solid $rpg-linha; padding: 0 1; }
    EditarQuest #c-porque:focus { border: solid $accent; }
    EditarQuest #passos { height: auto; max-height: 6; margin-top: 1; }
    EditarQuest #conta { height: 3; margin-top: 1; }
    """)
    CAMPOS = [("titulo", "título"), ("materia", "matéria"), ("est", "pomodoros"), ("dif", "dificuldade"), ("prio", "prioridade"),
              ("pericias", "perícias"), ("arco", "arco"), ("prazo", "prazo")]

    def __init__(self, q: dict | None, aprovar: bool = False) -> None:
        super().__init__()
        self.q = q
        self.aprovar = aprovar

    def compose(self) -> ComposeResult:
        from textual.widgets import TextArea
        a = self.app
        q = self.q or {}
        if self.aprovar:
            titulo = f"aprovar rascunho #{q.get('id')}"
        else:
            titulo = "editar quest" if q else "nova quest"
        with Vertical(id="caixa") as c:
            c.border_title = titulo
            yield Static("")
            for k, rot in self.CAMPOS:
                v = q.get(k, "")
                if k == "dif":
                    v = str(q.get("dif", 2))
                elif k == "prio":
                    v = str(q.get("prio", 2))
                elif k == "est":
                    v = str(q.get("est", 1))
                elif k == "pericias":
                    ps = q.get("pericias") or []
                    v = ", ".join(ps) if isinstance(ps, list) else str(ps)
                with Horizontal(classes="campo"):
                    yield Static(rot, classes="rot")
                    yield Input(str(v or ""), id=f"c-{k}", placeholder={"prazo": "AAAA-MM-DD", "dif": "1 fácil, 2 média, 3 difícil",
                                                                        "prio": "1 baixa, 2 média, 3 alta",
                                                                        "pericias": "ex.: Programação, Inglês",
                                                                        "arco": "grupo, ex. Prova de Compiladores"}.get(k, ""))
            if not q:
                with Horizontal(classes="campo"):
                    yield Static("tipo", classes="rot")
                    yield Input("normal", id="c-tipo", placeholder="normal ou daily")
            with Horizontal(id="campo-desc"):
                yield Static("como fazer", classes="rot")
                yield TextArea(str(q.get("porque") or ""), id="c-porque", soft_wrap=True, show_line_numbers=False, compact=True)
            yield Pintado(self._passos, id="passos")
            yield Pintado(self._conta, id="conta")
            with Horizontal(id="botoes"):
                yield Botao("aprovar" if self.aprovar else "salvar", id="salvar", classes="cheio")
                yield Botao("esc  voltar", id="voltar")
            yield Static(pe(a, [("enter", "aprova" if self.aprovar else "salva"), ("tab", "campo"), ("esc", "volta")]), classes="pe")

    def on_mount(self) -> None:
        self.query_one("#c-titulo", Input).focus()

    def _valores(self) -> dict:
        from textual.widgets import TextArea
        d = {}
        for k, _ in self.CAMPOS:
            d[k] = self.query_one(f"#c-{k}", Input).value.strip()
        d["porque"] = self.query_one("#c-porque", TextArea).text.strip()
        if not self.q:
            d["tipo"] = self.query_one("#c-tipo", Input).value.strip() or "normal"
        return d

    def _passos(self, w: int) -> Text:
        from oma_rpg.nucleo.jogo import Jogo
        a = self.app
        desc = self.query_one("#c-porque").text if self.is_mounted and self.query("#c-porque") else str((self.q or {}).get("porque") or "")
        subs = Jogo._passos_de(desc)
        if not subs and self.q and self.q.get("subtarefas"):
            subs = self.q["subtarefas"]
        if not subs:
            return Text("")
        linhas = [Text("passos (checklist visual, opcional)", style=f"bold {a.cor('forte')}")]
        for s in subs[:5]:
            t = Text()
            t.append((ic("feito") if s.get("feita") else ic("pendente")) + " ", style=a.cor("green") if s.get("feita") else a.cor("cyan"))
            t.append(s["texto"], style=a.cor("mudo") if s.get("feita") else a.cor("texto"))
            t.truncate(max(20, w), overflow="ellipsis")
            linhas.append(t)
        if len(subs) > 5:
            linhas.append(Text(f"  e mais {len(subs) - 5} passos", style=a.cor("mudo")))
        return D.juntar(linhas)

    def _conta(self, w: int) -> Text:
        a = self.app
        d = self._valores() if self.is_mounted and self.query("#c-est") else {"est": "1", "dif": "2"}
        try:
            from oma_rpg.nucleo.jogo import dificuldade
            est, dif = int(d["est"]), dificuldade(d["dif"])
            xp = regras.xp_quest(est, dif, a.cfg)
            t = Text.assemble(("XP e Bits: ", a.cor("yellow")), (f"{xp} · {regras.bits_de(xp, a.cfg)}", f"bold {a.cor('yellow')}"),
                              (" (tabela do jogo)", a.cor("yellow")))
            conta = Text(f"{a.cfg['quest']['xp_por_pomodoro']} × {est} × {regras.mult_dif(dif, a.cfg)}".replace(".", ","),
                         style=a.cor("mudo"))
        except Exception:
            t, conta = Text("XP e Bits: preencha pomodoros (1 a 8) e dificuldade (1 a 3)", style=a.cor("mudo")), Text("")
        nota = "o Mestre não escolhe esses valores" if self.aprovar else "o jogo calcula; não existe campo de recompensa"
        return D.juntar([t, conta, Text(nota, style=a.cor("mudo"))])

    def on_input_changed(self, ev: Input.Changed) -> None:
        if ev.input.id in ("c-est", "c-dif"):
            self.query_one("#conta", Pintado).pintar()

    def on_text_area_changed(self, ev) -> None:
        if ev.text_area.id == "c-porque":
            self.query_one("#passos", Pintado).pintar()

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        ev.stop()
        self._salvar()

    def apertou(self, bid: str) -> None:
        if bid == "salvar":
            self._salvar()
        else:
            self.action_cancelar()

    def _salvar(self) -> None:
        d = self._valores()
        a = self.app
        if self.q:
            args = {"id": self.q["id"], **{k: v for k, v in d.items()}}
            if self.q.get("estado") == "rascunho":
                def depois(ok, r):
                    if ok and self.aprovar:
                        a.pedir("aprovar", {"id": self.q["id"]})
                    if ok:
                        self.dismiss(True)
                a.pedir("editar_quest", args, depois)
            else:
                a.pedir("editar_quest", args, lambda ok, r: ok and self.dismiss(True))
        else:
            a.pedir("nova_quest", d, lambda ok, r: ok and self.dismiss(True))


class NovoArco(Dialogo):
    DEFAULT_CSS = css("NovoArco")

    def __init__(self, arco: dict | None = None) -> None:
        super().__init__()
        self.arco = arco

    def compose(self) -> ComposeResult:
        ar = self.arco or {}
        with Vertical(id="caixa") as c:
            c.border_title = "editar arco" if self.arco else "novo arco"
            yield Static("")
            for k, rot, ph in (("nome", "nome", "ex. Compiladores"), ("chefe", "chefe", "ex. Prova de Compiladores"),
                               ("data", "data do chefe", "AAAA-MM-DD")):
                with Horizontal(classes="campo"):
                    yield Static(rot, classes="rot")
                    yield Input(str(ar.get(k, "") or ""), id=f"a-{k}", placeholder=ph)
            yield Static(Text("vencer todas as quests do arco até a data dá o bônus do chefe", style=self.app.cor("mudo")),
                         classes="linha-texto")
            yield Static(pe(self.app, [("enter", "salva"), ("tab", "campo"), ("esc", "volta")]), classes="pe")

    def on_mount(self) -> None:
        self.query_one("#a-nome", Input).focus()

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        ev.stop()
        d = {k: self.query_one(f"#a-{k}", Input).value.strip() for k in ("nome", "chefe", "data")}
        if self.arco:
            self.app.pedir("editar_arco", {"id": self.arco["id"], **d}, lambda ok, r: ok and self.dismiss(True))
        else:
            self.app.pedir("novo_arco", d, lambda ok, r: ok and self.dismiss(True))


# ---------------------------------------------------------------- busca
class Busca(Dialogo):
    DEFAULT_CSS = css("Busca", """
    Busca { align: center top; }
    Busca #caixa { width: 64; margin-top: 1; height: auto; max-height: 30; }
    Busca Lista { height: auto; max-height: 22; margin-top: 1; }
    """)
    BINDINGS = [Binding("escape", "cancelar", priority=True), Binding("down", "descer", priority=True),
                Binding("up", "subir", priority=True)]

    def __init__(self, inicial: str = "") -> None:
        super().__init__()
        self.inicial = inicial

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = "buscar quests, skills e itens da loja"
            yield Input(self.inicial, id="busca-campo", placeholder="digite para buscar")
            yield Lista(self._linha, id="busca-lista", cursor_sem_foco=True, selecionavel=lambda it: it[0] != "cab")
            yield Static(pe(self.app, [("↑ ↓", "escolhe"), ("enter", "abre"), ("esc", "fecha")]), classes="pe")

    def on_mount(self) -> None:
        i = self.query_one(Input)
        i.focus()
        i.cursor_position = len(i.value)
        self._buscar(self.inicial)

    def _buscar(self, q: str) -> None:
        a = self.app
        q = q.strip().lower()
        res: list = []
        import unicodedata

        def norm(s: str) -> str:
            return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))
        nq = norm(q)
        if not nq:
            for p, rot in (("painel", "painel"), ("foco", "foco"), ("quests", "quests"), ("skills", "skills"), ("loja", "loja"),
                           ("historico", "histórico"), ("taverna", "taverna")):
                res.append(("pagina", p, rot))
        else:
            qs = [q_ for q_ in C.quests(a.b, a.cfg, a.hoje()) if nq in norm(q_["titulo"] + " " + q_["materia"])][:8]
            if qs:
                res.append(("cab", "", "quests"))
                res += [("quest", x["id"], x["titulo"]) for x in qs]
            h = C.heroi(a.b)
            sk = [s for s in a.cfg["skills"] if nq in norm(a.cfg.skill(s)["nome"] + " " + a.cfg.skill(s)["desc"])]
            if h:
                sk.sort(key=lambda s: a.cfg.skill(s)["classe"] != h["classe"])
            if sk:
                res.append(("cab", "", "skills"))
                res += [("skill", s, f"{a.cfg.skill(s)['nome']} · {a.cfg.classe(a.cfg.skill(s)['classe'])['nome']}") for s in sk[:6]]
            its = [i for i in a.cfg["itens"] if nq in norm(a.cfg.item(i)["nome"] + " " + a.cfg.item(i)["desc"])][:6]
            if its:
                res.append(("cab", "", "loja"))
                res += [("item", i, a.cfg.item(i)["nome"]) for i in its]
        self.query_one(Lista).definir(res, cursor=0)

    def _linha(self, it, i, est) -> list[Text]:
        a = self.app
        tipo, _, rot = it
        if tipo == "cab":
            return [Text(rot, style=f"bold {a.cor('mudo')}")]
        icone = {"quest": "quests", "skill": "skills", "item": "loja", "pagina": it[1]}.get(tipo, "ponto")
        return [Text.assemble(("  " + ic(icone) + " ", a.cor("accent")), (rot, a.cor("texto")))]

    def on_input_changed(self, ev: Input.Changed) -> None:
        self._buscar(ev.value)

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        ev.stop()
        it = self.query_one(Lista).item_atual()
        if it and it[0] != "cab":
            self.dismiss((it[0], it[1]))

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.dismiss((ev.item[0], ev.item[1]))

    def action_descer(self) -> None:
        self.query_one(Lista).action_cursor(1)

    def action_subir(self) -> None:
        l = self.query_one(Lista)
        if l._proximo(l.cursor, -1) >= 0:
            l.action_cursor(-1)


# ---------------------------------------------------------------- teclas e ajuda
GLOBAIS = [("ctrl+← ↓ ↑ → ou ctrl+hjkl", "muda de janela"), ("← ↓ ↑ → ou hjkl", "anda dentro da janela"),
           ("alt+← →", "troca de aba, camada ou categoria"), ("alt+↑ ↓", "move ou reordena o item (fila, quests)"),
           ("alt+1 … alt+7", "vai direto para o painel"), ("tab / shift+tab", "próxima janela"), ("/", "busca"),
           ("ctrl+espaço ou F1", "estas teclas"), ("?", "ajuda completa"), ("q", "sai (o serviço e o pomodoro continuam)")]
POR_TELA = [
    ("painel", [("enter", "abre"), ("f", "foco"), ("n", "nova quest"), ("t", "taverna")]),
    ("foco", [("espaço", "pausa ou começa"), ("1-4", "usa skill"), ("x", "abandona"), ("s", "pula a pausa"),
              ("alt+↑↓", "reordena a fila"), ("n", "anota")]),
    ("quests", [("enter", "abre"), ("n", "nova"), ("espaço", "conclui"), ("a", "aprova rascunho"), ("e", "edita"),
                ("d", "descarta"), ("+", "põe ou tira de hoje"), ("f", "foco nesta"), ("alt+← →", "aba")]),
    ("skills", [("enter", "aprende"), ("← →", "ramo"), ("c", "classes"), ("r", "respec (bits)"), ("alt+← →", "outra classe")]),
    ("classes", [("alt+← →", "troca"), ("enter", "vê a árvore"), ("t", "vira esta classe"), ("esc", "volta")]),
    ("loja", [("enter", "compra"), ("u", "usa da mochila"), ("+ -", "quantidade"), ("alt+← →", "categoria")]),
    ("histórico", [("← ↓ ↑ →", "dia"), ("alt+← →", "camada"), ("[ ]", "período"), ("enter", "detalhe")]),
    ("taverna", [("enter", "envia"), ("shift+enter", "quebra a linha"), ("a", "aprova"), ("e", "edita"), ("d", "descarta")]),
]


class Teclas(Dialogo):
    DEFAULT_CSS = css("Teclas", "Teclas #caixa { width: 86; } Teclas #corpo-teclas { height: auto; max-height: 40; overflow-y: auto; }")
    BINDINGS = [Binding("escape,q,f1", "cancelar", priority=True)]

    def __init__(self, nome: str, itens: list[tuple[str, str]], completa: bool = False) -> None:
        super().__init__()
        self.nome, self.itens, self.completa = nome, itens, completa

    def compose(self) -> ComposeResult:
        a = self.app
        linhas = []
        if self.itens and not self.completa:
            linhas.append(Text(f"nesta janela ({self.nome})", style=f"bold {a.cor('accent')}"))
            for k, d in self.itens:
                linhas.append(Text.assemble((f"  {k:<24}", a.cor("accent")), (d, a.cor("texto"))))
            linhas.append(Text(""))
        linhas.append(Text("em qualquer janela", style=f"bold {a.cor('accent')}"))
        for k, d in GLOBAIS:
            linhas.append(Text.assemble((f"  {k:<24}", a.cor("accent")), (d, a.cor("texto"))))
        if self.completa:
            for tela, ts in POR_TELA:
                linhas += [Text(""), Text(tela, style=f"bold {a.cor('accent')}")]
                linhas.append(Text("  " + "  ·  ".join(f"{k} {d}" for k, d in ts), style=a.cor("texto")))
            linhas += [Text(""), Text("mouse: clique escolhe e dá foco, roda rola, clique duplo abre, arrastar reordena a fila",
                                      style=a.cor("mudo")),
                       Text("dentro do herdr, ctrl+espaço é dele: use F1", style=a.cor("mudo"))]
        with Vertical(id="caixa") as c:
            c.border_title = "teclas" if not self.completa else "ajuda"
            yield Static(D.juntar(linhas), id="corpo-teclas")
            yield Static(pe(a, [("esc", "fecha")]), classes="pe")


# ---------------------------------------------------------------- repositórios
class Repos(Dialogo):
    """Os repositórios que o serviço observa. Só metadados locais, por `git log`."""

    DEFAULT_CSS = css("Repos", "Repos #caixa { width: 80; } Repos Lista { height: auto; max-height: 12; margin: 1 0; }")
    BINDINGS = [Binding("escape", "cancelar", priority=True), Binding("delete,x", "remover"), Binding("n", "novo")]

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = "repositórios observados"
            yield Static(Text("commit dentro de pomodoro vinculado vale 100%; solto vale 30%. Só o autor configurado em "
                              "user.email conta.", style=self.app.cor("mudo")), classes="linha-texto")
            yield Lista(self._linha, id="repos-lista", cursor_sem_foco=True)
            with Horizontal(classes="campo"):
                yield Static("pasta", classes="rot")
                yield Input(id="r-caminho", placeholder="~/Work/compiladores")
            with Horizontal(classes="campo"):
                yield Static("matéria", classes="rot")
                yield Input(id="r-materia", placeholder="vazio: vale para qualquer quest")
            yield Static(pe(self.app, [("enter", "adiciona"), ("x", "remove o escolhido"), ("esc", "fecha")]), classes="pe")

    def on_mount(self) -> None:
        self._recarregar()
        self.query_one("#r-caminho", Input).focus()

    def _recarregar(self) -> None:
        self.query_one(Lista).definir(list(self.app.b.todos("SELECT * FROM repos ORDER BY id")))

    def _linha(self, r, i, est) -> list[Text]:
        import os
        a = self.app
        cam = r["caminho"].replace(os.path.expanduser("~"), "~")
        return [D.linha_lr(Text.assemble((ic("git") + " ", a.cor("green")), (cam, a.cor("texto"))),
                           Text(r["materia"] or "qualquer matéria", style=a.cor("mudo")), est.largura)]

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        ev.stop()
        cam = self.query_one("#r-caminho", Input).value.strip()
        if not cam:
            return
        mat = self.query_one("#r-materia", Input).value.strip()

        def depois(ok, r):
            if ok:
                self.query_one("#r-caminho", Input).value = ""
                self.query_one("#r-materia", Input).value = ""
                self.set_timer(0.2, self._recarregar)
        self.app.pedir("repo_adicionar", {"caminho": cam, "materia": mat}, depois)

    def action_remover(self) -> None:
        if isinstance(self.focused, Input):
            return
        r = self.query_one(Lista).item_atual()
        if r is not None:
            self.app.pedir("repo_remover", {"id": r["id"]}, lambda ok, _: ok and self.set_timer(0.2, self._recarregar))

    def action_novo(self) -> None:
        self.query_one("#r-caminho", Input).focus()


# ---------------------------------------------------------------- vitrine (as capturas mostram todos de uma vez)
class Vitrine(Screen):
    """A tela 10 do design: os diálogos lado a lado, os avisos, os estados da barra de HP e a legenda."""

    DEFAULT_CSS = """
    Vitrine { background: $background; layout: vertical; }
    Vitrine .fila { height: 15; margin: 1 1 0 1; }
    Vitrine .quadro { width: 1fr; height: 14; border: solid $rpg-linha; border-title-color: $accent; border-title-style: bold;
                      padding: 0 1; margin: 0 1; }
    Vitrine .baixo { height: 1fr; margin: 1 1 0 1; }
    Vitrine .col { width: 1fr; margin: 0 1; }
    """
    BINDINGS = [Binding("escape", "fechar", priority=True)]

    def compose(self) -> ComposeResult:
        a = self.app
        d_nivel = {"nivel": 8, "titulo": "Dev Pleno", "pontos": 1, "hp": 10, "bits": 25}
        q = {"id": 14, "titulo": "Seção 2.1 do TCC", "est": 3, "dif": 3, "feitos": 3, "xp": 77}
        quadros = [
            [("nível alcançado", corpo_nivel(a, d_nivel) + [Text(""), pe(a, [("enter", "continuar")])], "accent"),
             ("abandonar o pomodoro?", self._abandonar(), "yellow"),
             ("você desmaiou", corpo_desmaio(a, {"bits": 128, "backup": True}) + [Text(""), pe(a, [("enter", "acordar")])], "red")],
            [("concluir quest", self._concluir(q), "green"),
             ("aprovar rascunho #14", self._aprovar(), "cyan"),
             ("carta do dia (Jovem Místico)", corpo_carta(a, "a_estrela", "a_torre") + [Text(""), pe(a, [("espaço", "tira")])], "magenta")],
        ]
        for fila in quadros:
            with Horizontal(classes="fila"):
                for titulo, linhas, cor in fila:
                    w = Static(D.juntar(linhas), classes="quadro")
                    w.border_title = titulo
                    w.styles.border_title_color = a.cor(cor)
                    yield w
        with Horizontal(classes="baixo"):
            yield Static(D.juntar(self._avisos()), classes="col")
            yield Static(D.juntar(self._barras()), classes="col")
            yield Static(D.juntar(self._legenda()), classes="col")

    def _abandonar(self) -> list[Text]:
        a = self.app
        return [Text(""), Text("Você fez 6 de 25 minutos.", style=a.cor("texto")), Text(""),
                Text("abandonar custa 8 HP e zera o combo x1.3", style=a.cor("red")), Text(""),
                Text("git stash guarda o pomodoro e mantém o combo", style=a.cor("green")),
                Text("(6 mana, você tem 34)", style=a.cor("mudo")), Text(""), Text(""),
                pe(a, [("s", "guardar"), ("x", "abandonar"), ("esc", "voltar")])]

    def _concluir(self, q) -> list[Text]:
        a = self.app
        return [Text(""), Text(q["titulo"], style=f"bold {a.cor('forte')}"), Text("3 de 3 pomodoros · XP cheio", style=a.cor("green")),
                Text(""), Text("o que você fez? (uma linha)", style=a.cor("mudo")),
                Text(" escrevi a 2.1 com 4 modelos e a tabela", style=f"{a.cor('texto')} on {a.cor('campo')}"), Text(""),
                Text.assemble((ic("commit") + " ", a.cor("blue")), ("2 commits em ~/Work/tcc detectados: +14 xp", a.cor("texto"))),
                Text(""), pe(a, [("enter", "concluir"), ("esc", "volta")])]

    def _aprovar(self) -> list[Text]:
        a = self.app
        linhas = [Text("")]
        for k, v in (("título", "Seção 2.1 do TCC: modelos de GAN em IDS"), ("matéria", "TCC"), ("pomodoros", "3"),
                     ("dificuldade", "◆◆◆"), ("prazo", "sex 20/11")):
            linhas.append(Text.assemble((f"{k:<13}", a.cor("mudo")), (v, a.cor("texto"))))
        linhas += [Text(""), Text("XP e Bits: 77 · 19 (tabela do jogo)", style=a.cor("yellow")),
                   Text("o Mestre não escolhe esses valores", style=a.cor("mudo")), Text(""),
                   pe(a, [("enter", "aprova"), ("tab", "campo"), ("esc", "volta")])]
        return linhas

    def _avisos(self) -> list[Text]:
        a = self.app
        avisos = [Text.assemble((ic("feito") + " ", a.cor("green")), ("+31 xp", f"bold {a.cor('green')}"), (" pomodoro 4 concluído", a.cor("texto"))),
                  Text.assemble((ic("combo") + " ", a.cor("yellow")), ("combo ", a.cor("texto")), ("x1.4", f"bold {a.cor('yellow')}"),
                                (" · mais 1 e vira x1.5", a.cor("mudo"))),
                  Text.assemble((ic("commit") + " ", a.cor("blue")), ("commit a3f9c1e ", a.cor("texto")), ("+9 xp", f"bold {a.cor('green')}"),
                                (" (CI verde)", a.cor("mudo"))),
                  Text.assemble((ic("trofeu") + " ", a.cor("yellow")), ("conquista: ", a.cor("texto")),
                                ("10 dias seguidos", f"bold {a.cor('yellow')}"))]
        linhas = [Text("avisos (canto inferior direito)", style=a.cor("mudo"))]
        for t in avisos:
            linhas += D.caixa(a, [t], 52)
        return linhas

    def _barras(self) -> list[Text]:
        a = self.app
        linhas = [Text("estados da barra de HP", style=a.cor("mudo")), Text("")]
        for nome, v, cor, nota in (("cheio", 100, "red", ""), ("normal", 72, "red", ""), ("baixo", 25, "orange", "<30%: laranja"),
                                   ("crítico", 8, "red", "<10%: pisca"), ("virada", 18, "cyan", "Otaku: x2")):
            t = Text(f"{nome:<9}", style=a.cor("texto"))
            t.append_text(D.barra(a, v, 100, 24, cor))
            t.append(f"   {nota}", style=a.cor("mudo"))
            linhas += [t, Text("")]
        return linhas

    def _legenda(self) -> list[Text]:
        a = self.app
        pares = [(("feito", "green", "feito"), ("andamento", "yellow", "em andamento")),
                 (("pendente", "texto", "pendente"), ("vencida", "red", "vencida")),
                 (("xp", "green", "xp"), ("bits", "yellow", "bits")), (("vida", "red", "hp"), ("mana", "blue", "mana")),
                 (("streak", "orange", "streak"), ("commit", "blue", "commit"))]
        linhas = [Text("legenda", style=a.cor("mudo")), Text("")]
        for (i1, c1, r1), (i2, c2, r2) in pares:
            t = Text.assemble((ic(i1) + " ", a.cor(c1)), (f"{r1:<26}", a.cor("texto")), (ic(i2) + " ", a.cor(c2)), (r2, a.cor("texto")))
            linhas += [t, Text("")]
        linhas.append(Text.assemble(("◆ ", a.cor("blue")), ("ativa  ", a.cor("mudo")), ("◇ ", a.cor("mudo")), ("passiva  ", a.cor("mudo")),
                                    ("● ", a.cor("mudo")), ("feito  ", a.cor("mudo")), ("◌ ", a.cor("mudo")), ("pendente", a.cor("mudo"))))
        return linhas

    def action_fechar(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------- pastas que o Mestre pode ler
def _curto(caminho: str) -> str:
    import os
    h = os.path.expanduser("~")
    return "~" + caminho[len(h):] if caminho == h or caminho.startswith(h + "/") else caminho


class Pastas(Dialogo):
    """As pastas liberadas para o Mestre ler (só leitura, com as subpastas). a adiciona, x remove."""

    DEFAULT_CSS = css("Pastas", "Pastas #caixa { width: 84; } Pastas Lista { height: auto; max-height: 14; margin: 1 0; }")
    BINDINGS = [Binding("escape", "cancelar", priority=True), Binding("a,n", "adicionar"), Binding("x,delete", "remover")]

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = "pastas que o Mestre pode ler"
            yield Static(Text("Só leitura, com as subpastas. O Mestre lê pelo oma-rpg ls e ver, e pelo Read, Glob e Grep "
                              "do Claude Code, só aqui dentro. Ele não consegue mudar esta lista.", style=self.app.cor("mudo")),
                         classes="linha-texto")
            yield Lista(self._linha, id="pastas-lista", cursor_sem_foco=True)
            with Horizontal(id="botoes"):
                yield Botao("a  adicionar pasta", id="adicionar", classes="cheio")
                yield Botao("x  remover", id="remover")
                yield Botao("esc  fechar", id="fechar")
            yield Static(pe(self.app, [("↑ ↓", "escolhe"), ("a", "adiciona"), ("x", "remove"), ("esc", "fecha")]), classes="pe")

    def on_mount(self) -> None:
        self.recarregar()
        self.query_one(Lista).focus()

    def recarregar(self) -> None:
        a = self.app
        ps = C.pastas(a.b, a.agora())
        self.query_one(Lista).definir(ps or [None])

    def _linha(self, p, i, est) -> list[Text]:
        a = self.app
        if p is None:
            return [Text("nenhuma pasta liberada ainda", style=a.cor("mudo"))]
        t = Text()
        t.append(ic("ok") + " ", style=a.cor("green"))
        t.append(_curto(p["caminho"]), style=a.cor("texto"))
        dir_ = Text("sempre", style=a.cor("mudo")) if p["modo"] == "sempre" else \
            Text(f"uma vez, até {C.hora(p['expira'])}", style=a.cor("yellow"))
        return [D.linha_lr(t, dir_, est.largura)]

    def action_adicionar(self) -> None:
        def escolhida(caminho):
            if caminho:
                confirmar_pasta(self.app, caminho, lambda: self.set_timer(0.2, self.recarregar))
        self.app.push_screen(EscolherPasta(), escolhida)

    def action_remover(self) -> None:
        p = self.query_one(Lista).item_atual()
        if p:
            self.app.pedir("pasta_remover", {"caminho": p["caminho"]}, lambda ok, r: ok and self.set_timer(0.2, self.recarregar))

    def apertou(self, bid: str) -> None:
        {"adicionar": self.action_adicionar, "remover": self.action_remover, "fechar": self.action_cancelar}.get(bid, lambda: None)()


def confirmar_pasta(app, caminho: str, depois=None, modo: str = "sempre") -> None:
    """Mostra o caminho absoluto resolvido e libera só depois do sim. Pasta sensível nem chega a perguntar."""
    from oma_rpg.nucleo import pastas
    from oma_rpg.nucleo.jogo import ErroJogo
    try:
        real = pastas.validar_raiz(caminho)
    except ErroJogo as e:
        app.avisar_erro(f"não dá para liberar: {e}")
        return

    def fim(ok):
        if ok:
            app.pedir("pasta_adicionar", {"caminho": real, "modo": modo}, lambda ok2, r: ok2 and depois and depois())
    app.push_screen(Confirmar("liberar pasta para o Mestre?", [real, "só leitura, com as subpastas; dá para remover depois (tecla P)"],
                              "liberar"), fim)


class EscolherPasta(Dialogo):
    """Navegador de pastas dentro do app (sem zenity). enter ou → entra, ← sobe, espaço escolhe a pasta aberta."""

    DEFAULT_CSS = css("EscolherPasta", """
    EscolherPasta #caixa { width: 90; }
    EscolherPasta Lista { height: 18; margin: 1 0; }
    """)
    BINDINGS = [Binding("escape", "cancelar", priority=True), Binding("left,h,backspace", "subir"),
                Binding("right,l", "entrar"), Binding("space,s", "escolher")]

    def __init__(self, inicio: str | None = None) -> None:
        super().__init__()
        import os
        h = os.path.expanduser("~")
        self.atual = inicio or (os.path.join(h, "Projects") if os.path.isdir(os.path.join(h, "Projects")) else h)

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = "escolher pasta"
            yield Input(self.atual, id="caminho-pasta", placeholder="digite o caminho e enter")
            yield Lista(self._linha, id="pastas-nav", cursor_sem_foco=True)
            with Horizontal(id="botoes"):
                yield Botao("espaço  escolher esta pasta", id="escolher", classes="cheio")
                yield Botao("esc  cancelar", id="cancelar")
            yield Static(pe(self.app, [("enter →", "entra"), ("←", "sobe"), ("espaço", "escolhe a aberta"), ("esc", "cancela")]),
                         classes="pe")

    def on_mount(self) -> None:
        self.abrir(self.atual)
        self.query_one(Lista).focus()

    def abrir(self, caminho: str) -> None:
        import os
        caminho = os.path.realpath(os.path.expanduser(caminho))
        if not os.path.isdir(caminho):
            self.app.avisar_erro("não é uma pasta")
            return
        self.atual = caminho
        try:
            filhos = sorted((e.name for e in os.scandir(caminho) if e.is_dir() and not e.name.startswith(".")), key=str.lower)
        except OSError:
            filhos = []
        itens = ([".."] if caminho != "/" else []) + filhos[:500]
        self.query_one(Lista).definir(itens, cursor=0)
        i = self.query_one(Input)
        with i.prevent(Input.Changed):
            i.value = _curto(caminho)

    def _linha(self, nome, i, est) -> list[Text]:
        a = self.app
        if nome == "..":
            return [Text("  ..  (sobe)", style=a.cor("mudo"))]
        return [Text.assemble(("  ▸ ", a.cor("accent")), (nome + "/", a.cor("texto")))]

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self._entrar(ev.item)

    def _entrar(self, nome) -> None:
        import os
        if nome is None:
            return
        self.abrir(os.path.dirname(self.atual) if nome == ".." else os.path.join(self.atual, nome))

    def action_entrar(self) -> None:
        if isinstance(self.focused, Input):
            return
        self._entrar(self.query_one(Lista).item_atual())

    def action_subir(self) -> None:
        if isinstance(self.focused, Input):
            return
        import os
        self.abrir(os.path.dirname(self.atual))

    def action_escolher(self) -> None:
        if isinstance(self.focused, Input):
            return
        self.dismiss(self.atual)

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        ev.stop()
        self.abrir(ev.value.strip() or "~")
        self.query_one(Lista).focus()

    def apertou(self, bid: str) -> None:
        if bid == "escolher":
            self.dismiss(self.atual)
        else:
            self.dismiss(None)


class PedidoPasta(_Simples):
    """O Mestre quer ler uma pasta que não está liberada: liberar uma vez, liberar sempre ou negar."""

    DEFAULT_CSS = css("PedidoPasta")
    TITULO = "o Mestre quer ler uma pasta"
    BORDA = "yellow"
    LARGURA = 80
    BINDINGS = [Binding("escape,n", "negar", priority=True), Binding("u", "uma_vez"), Binding("s", "sempre")]

    def __init__(self, caminho: str, motivo: str = "") -> None:
        super().__init__()
        self.caminho, self.motivo = caminho, motivo

    def linhas(self):
        a = self.app
        l = [Text(""), Text("O Mestre quer ler", style=a.cor("texto")), Text(self.caminho, style=f"bold {a.cor('forte')}"),
             Text("liberar? (só leitura, com as subpastas)", style=a.cor("texto"))]
        if self.motivo:
            l += [Text(""), Text("por quê: " + self.motivo, style=a.cor("mudo"))]
        l += [Text(""), Text("uma vez vale por 60 minutos; sempre fica na lista (tecla P na taverna)", style=a.cor("mudo"))]
        return l

    def botoes(self):
        return [("uma_vez", "u  liberar uma vez", ""), ("sempre", "s  liberar sempre", "cheio"), ("negar", "n  negar", "vermelho")]

    def teclas_pe(self):
        return [("u", "uma vez"), ("s", "sempre"), ("n esc", "negar")]

    def on_mount(self) -> None:
        self.query_one("#sempre", Botao).focus()

    def action_uma_vez(self) -> None:
        self.dismiss("uma_vez")

    def action_sempre(self) -> None:
        self.dismiss("sempre")

    def action_negar(self) -> None:
        self.dismiss("negar")

    def apertou(self, bid: str) -> None:
        self.dismiss(bid)


class AgenteDialogo(Dialogo):
    """Escolhe o agente CLI da taverna e o modelo (padrão ou específico)."""

    DEFAULT_CSS = css(
        "AgenteDialogo",
        "AgenteDialogo #caixa { width: 82; } AgenteDialogo #agentes-lista { height: auto; max-height: 6; margin: 1 0 0 0; } "
        "AgenteDialogo #modelos-lista { height: auto; max-height: 7; margin: 1 0; } "
        "AgenteDialogo #rot-mod { color: $rpg-mudo; margin-top: 1; }",
    )
    BINDINGS = [Binding("escape", "cancelar", priority=True)]

    def __init__(self, agentes: list[dict] | None = None) -> None:
        super().__init__()
        from oma_rpg import mestre
        self._agentes = agentes if agentes is not None else mestre.detectar_agentes()
        self._escolhido = self._agentes[0] if self._agentes else {"id": "claude", "rotulo": "Claude Code", "comando": "claude",
                                                                  "disponivel": False, "modelos": [""]}

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = "agente e modelo do Mestre"
            yield Static(Text("Escolha qual CLI responde na taverna. Opcionalmente escolha ou digite um modelo.",
                              style=self.app.cor("mudo")), classes="linha-texto")
            yield Lista(self._linha_agente, id="agentes-lista", cursor_sem_foco=True)
            yield Static("modelo", id="rot-mod")
            yield Lista(self._linha_modelo, id="modelos-lista", cursor_sem_foco=True)
            yield Input(placeholder="ou digite outro modelo (opcional)…", id="modelo-custom")
            with Horizontal(id="botoes"):
                yield Botao("enter  usar este", id="usar", classes="cheio")
                yield Botao("esc  fechar", id="fechar")
            yield Static(pe(self.app, [("↑ ↓", "escolhe"), ("tab", "troca campo"), ("enter", "confirma"), ("esc", "fecha")]),
                         classes="pe")

    def on_mount(self) -> None:
        m = self.app.mestre
        ag_atual = getattr(m, "agente", "claude") if m is not None else "claude"
        mod_atual = getattr(m, "modelo", "") if m is not None else ""
        la = self.query_one("#agentes-lista", Lista)
        idx = next((i for i, a in enumerate(self._agentes) if a["id"] == ag_atual), 0)
        la.definir(self._agentes, cursor=idx)
        self._escolhido = self._agentes[idx]
        self._carregar_modelos(mod_atual)
        la.focus()

    def _carregar_modelos(self, mod_atual: str = "") -> None:
        mods = list(self._escolhido.get("modelos") or [""])
        lm = self.query_one("#modelos-lista", Lista)
        c = mods.index(mod_atual) if mod_atual and mod_atual in mods else 0
        lm.definir(mods, cursor=c)
        if mod_atual and mod_atual not in mods:
            self.query_one("#modelo-custom", Input).value = mod_atual

    def _sincronizar_agente(self) -> None:
        it = self.query_one("#agentes-lista", Lista).item_atual()
        if it and it["id"] != self._escolhido["id"]:
            self._escolhido = it
            self._carregar_modelos("")

    def on_key(self, ev) -> None:
        if self.focused and self.focused.id == "agentes-lista":
            self.call_after_refresh(self._sincronizar_agente)

    def _linha_agente(self, ag: dict, i: int, est) -> list[Text]:
        a = self.app
        m = a.mestre
        ativo = m is not None and getattr(m, "agente", "") == ag["id"]
        ok = ag["disponivel"] or a.demo
        t = Text()
        t.append("✓ " if ativo else ("● " if ok else "○ "), style=a.cor("green") if ok else a.cor("mudo"))
        t.append(ag["rotulo"], style=f"bold {a.cor('forte')}" if ok else a.cor("mudo"))
        dir_ = Text("instalado" if ag["disponivel"] else "não encontrado", style=a.cor("mudo"))
        return [D.linha_lr(t, dir_, est.largura)]

    def _linha_modelo(self, mod: str, i: int, est) -> list[Text]:
        a = self.app
        m = a.mestre
        ativo = m is not None and getattr(m, "agente", "") == self._escolhido["id"] and getattr(m, "modelo", "") == mod
        rot = "padrão (do agente)" if not mod else mod
        t = Text()
        t.append("✓ " if ativo else "  ", style=a.cor("cyan"))
        t.append(rot, style=a.cor("texto") if mod else a.cor("mudo"))
        return [t]

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        if ev.lista.id == "agentes-lista":
            self._escolhido = ev.item
            self._carregar_modelos("")
            self.query_one("#modelos-lista", Lista).focus()
        elif ev.lista.id == "modelos-lista":
            self._confirmar()

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        ev.stop()
        self._confirmar()

    def _confirmar(self) -> None:
        ag = self._escolhido
        if not ag["disponivel"] and not self.app.demo:
            self.app.avisar_erro(f"o comando {ag['comando']} não está instalado")
            return
        custom = self.query_one("#modelo-custom", Input).value.strip()
        mod = custom if custom else (self.query_one("#modelos-lista", Lista).item_atual() or "")
        self.dismiss((ag["id"], mod))

    def apertou(self, bid: str) -> None:
        if bid == "usar":
            self._confirmar()
        else:
            self.action_cancelar()


class QuestionarioDialogo(Dialogo):
    """Questionário abrangente sobre o jogador para mapear atributos, perícias e contexto do Mestre."""

    DEFAULT_CSS = css(
        "QuestionarioDialogo",
        "QuestionarioDialogo #caixa { width: 94; } QuestionarioDialogo #q-scroll { height: auto; max-height: 22; } "
        "QuestionarioDialogo .campo { height: 1; } QuestionarioDialogo .rot { width: 22; } "
        "QuestionarioDialogo #previa { height: 4; margin-top: 1; }",
    )
    BINDINGS = [Binding("escape", "cancelar", priority=True)]
    PERGUNTAS = [
        ("ocupacao", "o que você faz", "ex.: Ciência da Computação, estágio, dev"),
        ("objetivos", "principais objetivos", "ex.: passar em Comp-Deci, fechar TCC, treinar"),
        ("estilo_vida", "estilo de vida", "sedentário, moderado, ativo, muito ativo"),
        ("altura_cm", "altura (cm)", "ex.: 175"),
        ("peso_kg", "peso (kg)", "ex.: 72"),
        ("sono", "horas de sono/noite", "ex.: 7h, 6h irregular"),
        ("treina", "treina? (s/n)", "s ou n"),
        ("treino_tipo", "qual atividade", "ex.: musculação, corrida, natação"),
        ("treino_freq", "quantas vezes", "ex.: 5x/semana, 1x/dia, 2x/dia"),
        ("tempo_estudo", "estudo por dia", "ex.: 3h/dia, 2h/dia"),
        ("atencao", "atenção e foco", "ex.: TDAH / dificuldade de foco, média, alta"),
        ("estilo_estudo", "como gosta estudar", "ex.: prática, exercícios, resumos, projetos"),
        ("tamanho_bloco", "blocos preferidos", "ex.: 1 pomodoro (25m), 2+ pomodoros, sem timer"),
        ("obstaculos", "o que mais te trava", "ex.: começar tarefas grandes, cansaço à noite"),
        ("rotina", "rotina / horários", "ex.: manhã estágio, tarde estudo, noite treino"),
        ("pericias_iniciais", "perícias iniciais", "ex.: Programação, Inglês, Atletismo"),
    ]

    def __init__(self, inicial: dict | None = None, editando: bool = False) -> None:
        super().__init__()
        self._inicial = inicial or {}
        self._editando = editando

    def compose(self) -> ComposeResult:
        from textual.containers import VerticalScroll
        p = self._inicial
        with Vertical(id="caixa") as c:
            c.border_title = "sobre você · questionário completo"
            yield Static(Text("Mapeia seus atributos iniciais, perícias e dá contexto ao Mestre para criar quests sob medida.",
                              style=self.app.cor("mudo")), classes="linha-texto")
            with VerticalScroll(id="q-scroll"):
                for k, rot, ph in self.PERGUNTAS:
                    v = p.get(k, "")
                    if k == "treina" and isinstance(v, (int, bool)):
                        v = "s" if v else ("n" if "treina" in p else "")
                    with Horizontal(classes="campo"):
                        yield Static(rot, classes="rot")
                        yield Input(str(v or ""), id=f"q-{k}", placeholder=ph)
            yield Pintado(self._previa, id="previa")
            with Horizontal(id="botoes"):
                yield Botao("enter  salvar perfil", id="salvar", classes="cheio")
                yield Botao("esc  fechar", id="fechar")
            yield Static(pe(self.app, [("tab", "próxima"), ("enter", "salva"), ("esc", "cancela")]), classes="pe")

    def on_mount(self) -> None:
        self.query_one("#q-ocupacao", Input).focus()

    def _coletar(self) -> dict:
        d: dict = {}
        for k, _, _ in self.PERGUNTAS:
            v = self.query_one(f"#q-{k}", Input).value.strip()
            if k == "altura_cm":
                try:
                    d[k] = int(v)
                except ValueError:
                    d[k] = 0
            elif k == "peso_kg":
                try:
                    d[k] = float(v.replace(",", "."))
                except ValueError:
                    d[k] = 0.0
            elif k == "treina":
                d[k] = v.lower().startswith("s") or v == "1"
            else:
                d[k] = v
        return d

    def _previa(self, w: int) -> Text:
        from oma_rpg.nucleo.jogo import Jogo
        from oma_rpg.nucleo.regras import ATRIBUTOS
        a = self.app
        d = self._coletar() if self.is_mounted and self.query("#q-ocupacao") else self._inicial
        attrs, pers, _ = Jogo.calcular_iniciais_perfil(d)
        t_attr = Text()
        for k, _, sig, _ in ATRIBUTOS:
            t_attr.append(f"{sig} ", style=a.cor("mudo"))
            t_attr.append(f"{attrs[k]}   ", style=f"bold {a.cor('accent')}")
        t_per = Text("perícias iniciais: " + (", ".join(pers) if pers else "nenhuma ainda"), style=a.cor("texto"))
        nota = Text("ao editar depois, altera apenas o relatório de contexto (atributos sobem por nível)", style=a.cor("mudo")) \
            if self._editando else Text("atributos e perícias iniciais calculados a partir das suas respostas", style=a.cor("mudo"))
        return D.juntar([t_attr, t_per, nota])

    def on_input_changed(self, ev: Input.Changed) -> None:
        if ev.input.id.startswith("q-"):
            self.query_one("#previa", Pintado).pintar()

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        ev.stop()
        self.dismiss(self._coletar())

    def apertou(self, bid: str) -> None:
        if bid == "salvar":
            self.dismiss(self._coletar())
        else:
            self.action_cancelar()
