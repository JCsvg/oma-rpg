"""Tela 9 · taverna: a conversa com o Mestre (o Claude Code do usuário), as chamadas que ele fez ao CLI, os rascunhos
criados e o que ele pode e não pode fazer. enter envia · shift+enter quebra a linha · a aprova · e edita · d descarta.

O TextArea só é importado quando a taverna abre (memória)."""

from __future__ import annotations

import json
import re

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, TextArea

from oma_rpg.nucleo import consultas as C
from oma_rpg.ui import desenho as D
from oma_rpg.ui.base import Janela, Pagina, pagina_de
from oma_rpg.ui.icones import GIRO, ic
from oma_rpg.ui.lista import Lista
from oma_rpg.ui.dialogos import _curto
from oma_rpg.ui.widgets import Botao, Pintado


class Mensagem(TextArea):
    BINDINGS = [Binding("enter", "enviar", priority=True), Binding("shift+enter,alt+enter", "quebrar", priority=True)]

    def action_enviar(self) -> None:
        t = self.text.strip()
        if t:
            pagina_de(self).enviar(t)
            self.load_text("")

    def action_quebrar(self) -> None:
        self.insert("\n")


class JanelaConversa(Janela):
    NOME = "conversa"
    DEFAULT_CSS = """
    JanelaConversa #conv-topo { height: 2; margin-top: 1; }
    JanelaConversa Lista { height: 1fr; }
    JanelaConversa #caixa-msg { height: 6; border: solid $rpg-linha; border-title-color: $rpg-mudo; padding: 0 1;
                                border-subtitle-color: $rpg-mudo; border-title-align: left; }
    JanelaConversa #caixa-msg:focus-within { border: solid $accent; }
    JanelaConversa Mensagem { height: 3; border: none; padding: 0; background: transparent; }
    JanelaConversa Mensagem:focus { border: none; }
    JanelaConversa #dica-msg { height: 1; color: $rpg-mudo; }
    """

    def compose(self) -> ComposeResult:
        yield Pintado(self._topo, id="conv-topo")
        yield Lista(self._linha, alturas=self._altura, id="conv-lista", selecionavel=lambda it: False)
        with Vertical(id="caixa-msg") as c:
            c.border_title = "mensagem"
            c.border_subtitle = "enter envia"
            yield Mensagem(id="msg", soft_wrap=True, show_line_numbers=False, compact=True, placeholder="escreva aqui…")
            yield Static("shift+enter quebra a linha  ·  /revisão  /rascunhos  /meta", id="dica-msg")

    def on_mount(self) -> None:
        self._cache: dict = {}

    def pintar(self) -> None:
        a = self.app
        self.titulo(f"{ic('mestre')} taverna", f"Mestre · {a.mestre_rotulo()} · P pastas · M agente")
        rows = a.b.todos("SELECT * FROM taverna ORDER BY ts, id")
        itens: list = []
        for r in rows[-200:]:
            if r["papel"] == "cli" and itens and itens[-1][0] == "cli":
                itens[-1][1].append(r)
            elif r["papel"] == "cli":
                itens.append(("cli", [r]))
            else:
                itens.append(("msg", r))
        if a.mestre_estado() == "pensando":
            itens.append(("pensando", None))
        self._cache = {}
        l = self.query_one(Lista)
        l.definir(itens)
        l.scroll_end(animate=False)
        self.query_one(Pintado).pintar()
        c = self.query_one("#caixa-msg")
        c.border_subtitle = "enter envia" if a.mestre_estado() != "ausente" else "M escolhe agente"

    def relogio(self) -> None:
        pass

    def _topo(self, w: int) -> Text:
        a = self.app
        h = C.heroi(a.b)
        classe = a.cfg.classe(h["classe"]) if h else None
        m = a.mestre_estado()
        if m == "ausente":
            t = Text.assemble(("● ", a.cor("mudo")), ("agente não encontrado: pressione M para escolher outro CLI", a.cor("mudo")))
        else:
            rot = a.mestre_rotulo()
            t = Text.assemble(("● ", a.cor("cyan")), (f"Mestre conectado via {rot}. Fala em {classe['tema'].split(',')[0]} "
                                                      f"(sua classe)." if classe else f"Mestre conectado via {rot}.",
                                                      a.cor("mudo")))
        return D.juntar([t, Text("─" * w, style=a.cor("linha"))])

    def _linhas_item(self, it, w: int) -> list[Text]:
        a = self.app
        tipo, v = it
        if tipo == "pensando":
            return [Text(""), Text.assemble(("mestre ", f"bold {a.cor('cyan')}"), ("digitando ", a.cor("mudo")),
                                            (GIRO[int(a.agora() * 4) % 8], a.cor("accent")))]
        if tipo == "cli":
            linhas = [Text("")]
            for r in v:
                extra = {}
                try:
                    extra = json.loads(r["extra"]) if r["extra"] else {}
                except ValueError:
                    pass
                t = Text("  ")
                t.append("● ", style=a.cor("blue"))
                t.append(r["texto"][: w - 6], style=a.cor("texto"))
                linhas.append(t)
                if extra.get("resultado"):
                    linhas.append(Text("    └ " + str(extra["resultado"])[: w - 8], style=a.cor("mudo")))
            linhas.append(Text(""))
            for l in linhas[1:-1]:
                l.pad_right(max(0, w - l.cell_len))
                l.stylize(f"on {a.cor('painel')}")
            return linhas
        papel = v["papel"]
        rot = {"voce": ("você", "forte"), "mestre": ("mestre", "cyan"), "sistema": ("aviso", "yellow")}.get(papel, (papel, "mudo"))
        corpo = D.quebrar(v["texto"], max(10, w - 8), a.cor("texto") if papel != "sistema" else a.cor("mudo"))
        linhas = [Text("")]
        for n, l in enumerate(corpo):
            t = Text(f"{rot[0]:<7}" if n == 0 else " " * 7, style=f"bold {a.cor(rot[1])}")
            t.append_text(l)
            linhas.append(t)
        return linhas

    def _altura(self, it) -> int:
        w = max(20, self.query_one(Lista).size.width or 80)
        chave = (id(it), w)
        if chave not in self._cache:
            self._cache[chave] = self._linhas_item(it, w)
        return len(self._cache[chave])

    def _linha(self, it, i, est) -> list[Text]:
        chave = (id(it), est.largura)
        if chave not in self._cache:
            self._cache[chave] = self._linhas_item(it, est.largura)
        return self._cache[chave]

    def focar_entrada(self) -> None:
        self.query_one(Mensagem).focus()

    def rodape(self):
        return [("enter", "enviar", "noop"), ("shift+enter", "nova linha", "noop"), ("/meta", "atalhos", "noop")]

    def teclas(self):
        return [("enter", "envia para o Mestre"), ("shift+enter ou alt+enter", "quebra a linha"),
                ("/revisão /rascunhos /meta", "atalhos de pedido"), ("ctrl+→", "rascunhos")]


class JanelaRascunhosT(Janela):
    NOME = "rascunhos-t"
    DEFAULT_CSS = "JanelaRascunhosT { height: 18; } JanelaRascunhosT Lista { margin-top: 1; height: 1fr; } " \
                  "JanelaRascunhosT #rt-pe { height: 3; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, altura=4, id="rt-lista", cursor_apagado=True)
        yield Pintado(self._pe, id="rt-pe")

    def pintar(self) -> None:
        a = self.app
        rs = C.quests(a.b, a.cfg, a.hoje(), "rascunho")
        self.titulo(f"{ic('rascunhos')} rascunhos", f"{len(rs)} aguardando")
        self.query_one(Lista).definir(rs)
        self.query_one(Pintado).pintar()

    def _linha(self, q: dict, i: int, est) -> list[Text]:
        a = self.app
        w = max(20, est.largura)
        p = q.get("prio", 2)
        marca, cor = {3: ("! ", "red"), 2: ("· ", "accent"), 1: ("⌄ ", "mudo")}.get(p, ("· ", "mudo"))
        t = Text(no_wrap=True, overflow="ellipsis")
        t.append(f"#{q['id']:<3} ", style=a.cor("mudo"))
        t.append(marca, style=f"bold {a.cor(cor)}" if p == 3 else a.cor(cor))
        t.append(q["titulo"], style=f"bold {a.cor('forte')}")
        t.truncate(w, overflow="ellipsis")

        l2 = Text("     ")
        l2.append(f"{q['est']}p ", style=a.cor("texto"))
        l2.append_text(D.diamantes(a, q["dif"]))
        l2.append(f" · {q['xp']} xp · {q['bits']}", style=a.cor("yellow"))
        l2.append(ic("bits"), style=a.cor("yellow"))
        if q.get("depende_de"):
            l2.append(" · após " + ",".join(f"#{d}" for d in q["depende_de"]), style=a.cor("mudo"))
        elif q["prazo"]:
            l2.append(f" · {C.dia_curto(q['prazo'])}", style=a.cor("mudo"))
        l2.truncate(w, overflow="ellipsis")

        if est.cursor and est.foco:
            l3 = Text.assemble(("     a", a.cor("accent")), (" aprovar   ", a.cor("texto")),
                               ("e", a.cor("accent")), (" editar   ", a.cor("texto")),
                               ("d", a.cor("accent")), (" descartar", a.cor("texto")))
        elif q["porque"]:
            l3 = Text("     " + q["porque"].replace("\n", " "), style=a.cor("mudo"), no_wrap=True, overflow="ellipsis")
            l3.truncate(w, overflow="ellipsis")
        else:
            l3 = Text("")
        return [t, l2, l3, Text("")]

    def _pe(self, w: int) -> Text:
        a = self.app
        return D.juntar([Text.assemble(("shift+a", a.cor("accent")), (" aprova todos  ·  ", a.cor("mudo")),
                                       ("nada vale XP até aprovar", a.cor("mudo")))])

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.pg.action_editar()

    def atual(self):
        return self.query_one(Lista).item_atual()

    def rodape(self):
        return [("a", "aprovar", "noop"), ("e", "editar", "noop"), ("d", "descartar", "noop")]

    def teclas(self):
        return [("a", "aprova o rascunho"), ("e ou enter", "edita e aprova"), ("d", "descarta"), ("shift+a", "aprova todos")]


class JanelaQuestsT(Janela):
    NOME = "quests-t"
    DEFAULT_CSS = "JanelaQuestsT { height: 1fr; } JanelaQuestsT Lista { margin-top: 1; height: 1fr; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, altura=3, id="qt-lista", cursor_sem_foco=True)

    def pintar(self) -> None:
        a = self.app
        qs = C.quests(a.b, a.cfg, a.hoje(), "aberta")
        self.titulo(f"{ic('quests')} quests", f"{len(qs)} abertas")
        self.query_one(Lista).definir(qs)

    def _linha(self, q: dict, i: int, est) -> list[Text]:
        a = self.app
        w = max(20, est.largura)
        p = q.get("prio", 2)
        marca, cor = {3: ("! ", "red"), 2: ("· ", "accent"), 1: ("⌄ ", "mudo")}.get(p, ("· ", "mudo"))
        t = Text(no_wrap=True, overflow="ellipsis")
        t.append(f"#{q['id']:<3} ", style=a.cor("mudo"))
        if q.get("bloqueada"):
            t.append("🔒 ", style=a.cor("yellow"))
        else:
            t.append(marca, style=f"bold {a.cor(cor)}" if p == 3 else a.cor(cor))
        t.append(q["titulo"], style=a.cor("mudo") if q.get("bloqueada") else f"bold {a.cor('forte')}")
        dir_ = Text(f"{q['feitos']}/{q['est']}", style=a.cor("mudo"))
        l1 = D.linha_lr(t, dir_, w)
        if q.get("bloqueada"):
            sub = Text(f"     depende de {', '.join('#' + str(d) for d in q['faltam_deps'])}", style=a.cor("yellow"))
        elif q["porque"]:
            sub = Text(f"     {q['porque'].replace(chr(10), ' ')}", style=a.cor("mudo"), no_wrap=True, overflow="ellipsis")
            sub.truncate(w, overflow="ellipsis")
        else:
            sub = Text(f"     {q['xp']} xp · {q['arco'] or q['materia'] or 'geral'}", style=a.cor("mudo"))
        return [l1, sub, Text("")]

    def atual(self):
        return self.query_one(Lista).item_atual()

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        q = self.atual()
        if q:
            from oma_rpg.ui.dialogos import EditarQuest
            self.app.push_screen(EditarQuest(q))

    def rodape(self):
        return [("f", "focar", "noop"), ("espaço", "concluir", "noop"), ("enter", "editar", "noop")]

    def teclas(self):
        return [("f", "começa pomodoro na quest"), ("espaço", "conclui a quest"), ("enter", "edita")]


class PaginaTaverna(Pagina):
    NOME = "taverna"
    TITULO = "taverna"
    ENTRADA = "conversa"
    VIZINHAS = {
        "conversa": {"esq": "paineis", "dir": "rascunhos-t", "cima": "topo"},
        "rascunhos-t": {"esq": "conversa", "cima": "topo", "baixo": "quests-t"},
        "quests-t": {"esq": "conversa", "cima": "rascunhos-t"},
    }
    BINDINGS = [Binding("a", "aprovar", show=False), Binding("e", "editar", show=False), Binding("d", "descartar", show=False),
                Binding("A,shift+a", "aprovar_todos", show=False), Binding("P,shift+p", "pastas", show=False),
                Binding("M,shift+m", "agente", show=False), Binding("f", "focar_quest", show=False),
                Binding("space", "concluir_quest", show=False)]
    DEFAULT_CSS = "PaginaTaverna JanelaConversa { width: 1fr; } PaginaTaverna #t-dir { width: 52; }"

    def compose(self) -> ComposeResult:
        yield JanelaConversa()
        with Vertical(id="t-dir"):
            yield JanelaRascunhosT()
            yield JanelaQuestsT()

    def on_mount(self) -> None:
        self._giro = self.set_interval(0.25, self._girar, pause=True)

    def _girar(self) -> None:
        if self.app.mestre_estado() != "pensando":
            self._giro.pause()
            return
        try:
            self.query_one(JanelaConversa).pintar()
        except Exception:
            pass

    def pintar(self) -> None:
        super().pintar()
        if self.app.mestre_estado() == "pensando":
            self._giro.resume()

    def enviar(self, texto: str) -> None:
        m = self.app.mestre
        if m is None or self.app.mestre_estado() == "ausente":
            self.app.avisar_erro("Agente não encontrado: pressione M na taverna para escolher outro.")
            return
        nova = pasta_na_mensagem(self.app, texto)
        if nova:
            from oma_rpg.ui.dialogos import PedidoPasta

            def resposta(r):
                if r in ("sempre", "uma_vez"):
                    self.app.pedir("pasta_adicionar", {"caminho": nova, "modo": r}, lambda ok, _: self._mandar(texto))
                else:
                    self._mandar(texto)
            self.app.push_screen(PedidoPasta(nova, "a mensagem cita esta pasta"), resposta)
            return
        self._mandar(texto)

    def _mandar(self, texto: str) -> None:
        self.app.mestre.enviar(texto)
        self._giro.resume()

    def action_pastas(self) -> None:
        self.app.abrir_pastas()

    def action_agente(self) -> None:
        self.app.abrir_agente()

    def rodape_pagina(self):
        return [("P", "pastas", "pastas"), ("M", "agente", "agente"), ("a", "aprovar", "aprovar"), ("e", "editar", "editar")]

    def _rascunho(self):
        return self.query_one(JanelaRascunhosT).atual() if self.app.nome_janela(self.app.focused) == "rascunhos-t" else None

    def _quest(self):
        return self.query_one(JanelaQuestsT).atual() if self.app.nome_janela(self.app.focused) == "quests-t" else None

    def action_focar_quest(self) -> None:
        q = self._quest()
        if q:
            self.app.pedir("iniciar", {"quest_id": q["id"]}, lambda ok, r: ok and self.app.abrir_pagina("foco", foco=True))

    def action_concluir_quest(self) -> None:
        q = self._quest()
        if q:
            from oma_rpg.ui.dialogos import Concluir
            self.app.push_screen(Concluir(q))

    def action_aprovar(self) -> None:
        q = self._rascunho()
        if q:
            self.app.pedir("aprovar", {"id": q["id"]})

    def action_aprovar_todos(self) -> None:
        if self.app.nome_janela(self.app.focused) != "conversa":
            self.app.pedir("aprovar_todos")

    def action_editar(self) -> None:
        from oma_rpg.ui.dialogos import EditarQuest
        q = self._rascunho()
        if q:
            self.app.push_screen(EditarQuest(q, aprovar=True))

    def action_descartar(self) -> None:
        q = self._rascunho()
        if q:
            self.app.pedir("descartar_rascunho", {"id": q["id"]})


CAMINHO = re.compile(r"(?:(?<=\s)|^)(~/[^\s,;:\"'()<>]+|/[^\s,;:\"'()<>]+)")


def pasta_na_mensagem(app, texto: str) -> str:
    """A primeira pasta que a mensagem cita, existe, pode ser liberada e ainda não está liberada (senão, vazio)."""
    from oma_rpg.nucleo import pastas
    from oma_rpg.nucleo.jogo import ErroJogo
    liberadas = C.caminhos_liberados(app.b, app.agora())
    for m in CAMINHO.finditer(texto):
        bruto = m.group(1).rstrip(".!?")
        try:
            alvo = pastas.pasta_pedida(bruto)
            pastas.validar_raiz(alvo)
        except (ErroJogo, OSError):
            continue
        try:
            pastas.resolver(alvo, liberadas)
        except ErroJogo:
            return alvo
    return ""


PAGINA = PaginaTaverna
