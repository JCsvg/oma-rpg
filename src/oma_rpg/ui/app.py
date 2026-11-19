"""Aplicativo Textual do oma-rpg: topo, coluna dos painéis, uma página por vez, rodapé e avisos.

A interface é só cliente: lê o banco (só leitura) e pede tudo ao serviço pelo socket, com o papel de jogador (ou ao
cliente local, no --demo). Fechar a janela não para o pomodoro.
"""

from __future__ import annotations

import importlib
import threading

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal

from oma_rpg import __version__
from oma_rpg.nucleo import consultas as C
from oma_rpg.ui import tema
from oma_rpg.ui.avisos import Aviso, Avisos
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lateral import PAGINAS, Lateral
from oma_rpg.ui.rodape import Rodape
from oma_rpg.ui.topo import Topo

NOMES_PAGINAS = [p for p, _ in PAGINAS]


class Corpo(Horizontal):
    """O meio da tela. O App não recebe o Resize; o corpo recebe e avisa (meia tela e volta)."""

    def on_resize(self, ev) -> None:
        self.app.redimensionou()
ESTREITO = 120  # abaixo disso, uma janela por vez (meia tela)


class OmaRpgApp(App[None]):
    TITLE = "oma-rpg"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen { background: $background; color: $foreground; layers: base avisos; }
    ModalScreen { background: $background 60%; }
    #corpo { height: 1fr; }
    #area { width: 1fr; height: 1fr; }
    Input { border: none; background: $rpg-campo; height: 1; padding: 0 1; }
    Input:focus { border: none; background: $rpg-selecao; }
    Input > .input--placeholder { color: $rpg-mudo; }
    """
    BINDINGS = [
        Binding("ctrl+left,ctrl+h", "janela('esq')", show=False, priority=True),
        Binding("ctrl+right,ctrl+l", "janela('dir')", show=False, priority=True),
        Binding("ctrl+up,ctrl+k", "janela('cima')", show=False, priority=True),
        Binding("ctrl+down,ctrl+j", "janela('baixo')", show=False, priority=True),
        Binding("tab", "ciclo(1)", show=False, priority=True),
        Binding("shift+tab", "ciclo(-1)", show=False, priority=True),
        Binding("alt+left,alt+h", "alt_h(-1)", show=False, priority=True),
        Binding("alt+right,alt+l", "alt_h(1)", show=False, priority=True),
        Binding("alt+up,alt+k", "alt_v(-1)", show=False, priority=True),
        Binding("alt+down,alt+j", "alt_v(1)", show=False, priority=True),
        *[Binding(f"alt+{n}", f"pagina({n})", show=False, priority=True) for n in range(1, 8)],
        Binding("ctrl+@,ctrl+space,ctrl+at,f1", "teclas", show=False, priority=True),
        Binding("slash", "buscar", show=False),
        Binding("question_mark", "ajuda", show=False),
        Binding("escape", "esc", show=False),
        Binding("q", "sair", show=False),
        Binding("left,h", "mover(-1, 0)", show=False),
        Binding("right,l", "mover(1, 0)", show=False),
        Binding("up,k", "mover(0, -1)", show=False),
        Binding("down,j", "mover(0, 1)", show=False),
    ]

    def __init__(self, cliente=None, banco=None, cfg=None, relogio=None, estado=None, demo: bool = False,
                 abertura: bool = True, mestre=None, iniciar_servico: bool = True, **_) -> None:
        super().__init__()
        from oma_rpg.config import Config
        self.demo = demo
        self.cfg = cfg or Config.carregar()
        if banco is None:
            from oma_rpg import caminhos
            from oma_rpg.nucleo.banco import Banco
            banco = Banco(caminhos.arquivo_banco(), leitura=True)
        self.b = banco
        if cliente is None:
            from oma_rpg.cliente import ClienteServico
            cliente = ClienteServico()
        self.cliente = cliente
        if relogio is None:
            from oma_rpg.nucleo.jogo import Relogio
            relogio = Relogio()
        self.relogio = relogio
        if estado is None:
            from oma_rpg.ui.estado import Estado
            estado = Estado()
        self.estado = estado
        if mestre is None and not demo:
            from oma_rpg.mestre import MestreClaude
            mestre = MestreClaude()
        self.mestre = mestre
        self.iniciar_servico = iniciar_servico
        self.com_abertura = abertura
        self.paleta = tema.ler()
        self.pronto = False
        self.st: dict = {}
        self._atual_row = None
        self.pagina = None
        self.pagina_nome = ""
        self.historico: list[str] = []
        self.pos = -1
        self._ultimo_foco: dict[str, object] = {}
        self._ultima_janela = ""
        self._mudou_timer = None
        self._fila_dialogos: list = []
        self._thread_ui = threading.get_ident()
        self._reconectar_timer = None
        self._foco_pendente = ""
        self._estreita = ""
        self._mexidos: list = []

    # ------------------------------------------------------------ montagem
    def compose(self) -> ComposeResult:
        yield Topo(id="topo")
        with Corpo(id="corpo"):
            yield Lateral(id="paineis")
            yield Container(id="area")
        yield Rodape(id="rodape")
        yield Avisos(id="avisos")

    def get_css_variables(self) -> dict[str, str]:
        v = super().get_css_variables()
        paleta = getattr(self, "paleta", None) or tema.ler()
        v.update(tema.tema_textual("omarchy", paleta).variables)
        return v

    def on_mount(self) -> None:
        self.register_theme(tema.tema_textual("omarchy", self.paleta))
        self.theme = "omarchy"
        self.estado.carregar()
        self.cliente.ao_evento = self._evento_thread
        if self.mestre is not None:
            self.mestre.app = self
            self.mestre.ao_mudar = lambda: self._na_ui(self._mestre_mudou)
        self.ler_dados()
        self._seg_timer = self.set_interval(1.0, self._segundo, pause=True)
        self.call_after_refresh(self._iniciar)

    def _iniciar(self) -> None:
        self.pronto = True
        self._conectar()
        if self.com_abertura and not self.estado.ja_abriu():
            from oma_rpg.ui.abertura import Abertura
            self.estado.marcar_abertura()
            self.push_screen(Abertura(__version__), lambda _: self._depois_abertura())
        else:
            self._depois_abertura()

    def _depois_abertura(self) -> None:
        if not self.st.get("heroi"):
            self.criar_heroi()
            return
        salvo = self.estado.obter("pagina")
        self.abrir_pagina(salvo if salvo in NOMES_PAGINAS else "painel", foco=True)
        self._carta_do_dia_se_preciso()

    def criar_heroi(self) -> None:
        from oma_rpg.ui.criar import Criar

        def fim(r):
            if not r:
                self.exit()
                return
            nome, classe = r

            def depois(ok, res):
                if ok:
                    self.ler_dados()
                    self.abrir_pagina("painel", foco=True)
                    self._carta_do_dia_se_preciso()
                else:
                    self.avisar_erro(res)
                    self.criar_heroi()
            self.pedir("criar_heroi", {"nome": nome, "classe": classe}, depois)
        self.push_screen(Criar(), fim)

    # ------------------------------------------------------------ serviço e dados
    def _conectar(self) -> None:
        if self.demo or getattr(self.cliente, "demo", False):
            return
        if self.cliente.conectar():
            return
        if not self.iniciar_servico:
            return

        def trabalho():
            como = self.cliente.garantir_servico()
            self._na_ui(self._conectou, como)
        threading.Thread(target=trabalho, daemon=True).start()

    def _conectou(self, como: str) -> None:
        if como:
            if como in ("systemd", "processo"):
                self.avisar(Text.assemble((ic("ok") + " ", self.cor("green")),
                                          ("serviço iniciado" + (" (systemctl --user)" if como == "systemd" else ""), self.cor("texto"))))
            self.ler_dados()
            self.atualizar()
            if not self.st.get("heroi") and len(self.screen_stack) == 1:
                self.criar_heroi()
        else:
            self.avisar_erro("O serviço do oma-rpg não iniciou. Rode: systemctl --user start oma-rpg.service", 12)

    def _na_ui(self, f, *args) -> None:
        if threading.get_ident() == self._thread_ui:
            f(*args)
        else:
            try:
                self.call_from_thread(f, *args)
            except Exception:
                pass

    def _evento_thread(self, d: dict) -> None:
        self._na_ui(self._evento, d)

    def pedir(self, cmd: str, args: dict | None = None, depois=None, avisar_erro: bool = True) -> None:
        def volta(ok, r):
            def ui():
                if not ok and avisar_erro:
                    self.avisar_erro(r)
                if depois:
                    depois(ok, r)
            self._na_ui(ui)
        self.cliente.pedir(cmd, args or {}, volta)

    def agora(self) -> float:
        return self.relogio.agora()

    def hoje(self) -> str:
        return C.dia_de(self.agora())

    def ler_dados(self) -> None:
        """Foto do estado para o topo, a coluna e as páginas."""
        if getattr(self.b, "memoria", False) and self.b.caminho.exists():
            # o serviço acabou de criar o banco (primeira vez): troca o banco vazio em memória pelo arquivo
            from oma_rpg.nucleo.banco import Banco
            self.b.fechar()
            self.b = Banco(self.b.caminho, leitura=True)
        try:
            self.st = C.status(self.b, self.cfg, self.agora())
            self._atual_row = C.atual(self.b)
        except Exception:
            self.st, self._atual_row = {}, None
        fase = (self.st.get("pomodoro") or {}).get("fase", "parado")
        if hasattr(self, "_seg_timer"):
            (self._seg_timer.resume if fase in C.FASES_RODANDO else self._seg_timer.pause)()

    def restante(self) -> float:
        return C.restante(self._atual_row, self.agora()) if self._atual_row is not None else 0.0

    def decorrido(self) -> float:
        return C.decorrido(self._atual_row, self.agora()) if self._atual_row is not None else 0.0

    def atualizar(self) -> None:
        self._mudou_timer = None
        if not self.pronto:
            return
        self.ler_dados()
        try:
            self.query_one(Lateral).pintar()
            self._pintar_topo()
            if self.pagina is not None and self.pagina.is_mounted:
                self.pagina.pintar()
            self.query_one(Rodape).pintar()
        except Exception:
            pass

    def _agendar_atualizar(self) -> None:
        if self._mudou_timer is not None:
            self._mudou_timer.stop()
        self._mudou_timer = self.set_timer(0.1, self.atualizar)

    def _segundo(self) -> None:
        """A cada segundo, só enquanto há timer rodando: o topo, os ativos e o foco."""
        if getattr(self.cliente, "demo", False):
            self.cliente.tick()
        try:
            self.query_one(Topo).relogio()
            self.query_one(Lateral).relogio()
            if self.pagina is not None:
                self.pagina.relogio()
        except Exception:
            pass

    def _evento(self, d: dict) -> None:
        ev = d.get("evento")
        a = self.cor
        if ev == "mudou":
            self._agendar_atualizar()
        elif ev == "pomodoro_fim":
            t = Text.assemble((ic("feito") + " ", a("green")), (f"+{d['xp']} xp", f"bold {a('green')}"),
                              (f" pomodoro {d['n_dia']} concluído", a("texto")))
            if d.get("overtraining"):
                t.append(" · overtraining", style=a("orange"))
            if d.get("virada"):
                t.append(" · virada x2", style=a("cyan"))
            self.avisar(t, 6)
            if d.get("combo", 1) > d.get("combo_antes", 1):
                prox = round(d["combo"] + 0.1, 1)
                self.avisar(Text.assemble((ic("combo") + " ", a("yellow")), ("combo ", a("texto")),
                                          (f"x{d['combo']:.1f}", f"bold {a('yellow')}"),
                                          (f" · mais 1 e vira x{prox:.1f}" if prox <= 2.0 else "", a("mudo"))), 6)
        elif ev == "pausa_fim" and d.get("respeitada"):
            t = Text.assemble((ic("mana") + " ", a("blue")), ("pausa respeitada ", a("texto")), (f"+{d.get('mp', 0)} mana", a("blue")))
            if d.get("hp"):
                t.append(f" +{d['hp']} HP", style=a("red"))
            self.avisar(t)
        elif ev == "nivel":
            from oma_rpg.ui.dialogos import Nivel
            self.mostrar_dialogo(Nivel(d))
        elif ev == "desmaio":
            from oma_rpg.ui.dialogos import Desmaio
            self.mostrar_dialogo(Desmaio(d))
        elif ev == "conquista":
            self.avisar(Text.assemble((ic("trofeu") + " ", a("yellow")), ("conquista: ", a("texto")), (d["nome"], f"bold {a('yellow')}"),
                                      (f"  +{d['xp']} xp", a("green"))), 8)
        elif ev == "commit":
            t = Text.assemble((ic("commit") + " ", a("blue")), (f"commit {d['hash']} ", a("texto")))
            if d["xp"]:
                t.append(f"+{d['xp']} xp", style=f"bold {a('green')}")
                if d.get("vinculado"):
                    t.append("  (no pomodoro)", style=a("mudo"))
            else:
                t.append(f"0 xp · {d.get('motivo', '')}", style=a("mudo"))
            self.avisar(t)
        elif ev == "quest_feita":
            self.avisar(Text.assemble((ic("feito") + " ", a("green")), ("quest: ", a("texto")), (d["titulo"], f"bold {a('forte')}"),
                                      (f"  +{d['xp']} xp +{d['bits']}", a("green")), (ic("bits"), a("yellow"))))
        elif ev == "chefe":
            self.avisar(Text.assemble((ic("trofeu") + " ", a("yellow")), ("chefe vencido: ", a("texto")), (d["arco"], f"bold {a('yellow')}"),
                                      (f"  +{d['xp']} xp", a("green"))), 8)
        elif ev == "compra":
            self.avisar(Text.assemble((ic("feito") + " ", a("green")), ("comprou ", a("texto")), (d["nome"], f"bold {a('forte')}"),
                                      (f"  -{d['bits']} bits", a("yellow"))))
        elif ev in ("item_usado", "skill_usada"):
            self.avisar(Text.assemble((ic("estrela4") + " ", a("yellow")), (d["nome"] + ": ", f"bold {a('forte')}"), (d["texto"], a("texto"))))
        elif ev == "escudo":
            self.avisar(Text.assemble((ic("vida") + " ", a("red")), ("escudo segurou: ", a("texto")), (d["texto"], a("mudo"))))
        elif ev == "abandono" and not d.get("livre"):
            self.avisar(Text.assemble((ic("vida") + " ", a("red")), (f"-{d['hp']} HP", f"bold {a('red')}"),
                                      (" e combo zerado", a("texto"))), alerta=True)
        elif ev == "guardado":
            self.avisar(Text.assemble((ic("pausa") + " ", a("blue")), (f"pomodoro guardado ({d['minutos']} min)", a("texto")),
                                      (" · espaço retoma no foco", a("mudo"))))
        elif ev == "rascunho":
            self.avisar(Text.assemble((ic("mestre") + " ", a("cyan")), (f"rascunho #{d['id']} do Mestre", a("texto")),
                                      (" · nada vale XP até você aprovar", a("mudo"))))
        elif ev == "pedido_pasta":
            from oma_rpg.ui.dialogos import PedidoPasta
            pid = d.get("id")
            self.mostrar_dialogo(PedidoPasta(str(d.get("caminho", "")), str(d.get("motivo", ""))),
                                 lambda r: self.pedir("responder_pedido", {"id": pid, "resposta": r or "negar"}))
        elif ev == "titulo":
            self.avisar(Text.assemble((ic("coroa") + " ", a("yellow")), ("título destravado: ", a("texto")), (d["titulo"], f"bold {a('yellow')}")), 8)
        elif ev == "desconectado":
            self.avisar_erro("O serviço do oma-rpg parou. Tentando de novo a cada 3 s.")
            if self._reconectar_timer is None:
                self._reconectar_timer = self.set_interval(3.0, self._reconectar)

    def _reconectar(self) -> None:
        if self.cliente.conectar():
            if self._reconectar_timer is not None:
                self._reconectar_timer.stop()
                self._reconectar_timer = None
            self.atualizar()

    def _mestre_mudou(self) -> None:
        try:
            self.query_one(Lateral).relogio()
            if self.pagina_nome == "taverna" and self.pagina is not None:
                self.pagina.pintar()
        except Exception:
            pass

    def _carta_do_dia_se_preciso(self) -> None:
        cd = C.carta_do_dia(self.b, self.cfg, self.hoje())
        if cd and not cd[2]:
            from oma_rpg.ui.dialogos import Carta
            self.mostrar_dialogo(Carta(cd[0], cd[1]))

    # ------------------------------------------------------------ cores e avisos
    def cor(self, nome: str) -> str:
        p = self.paleta
        nome = {"success": "green", "warning": "yellow", "error": "red", "muted": "mudo"}.get(nome, nome)
        return p.get(nome, p["foreground"])

    def avisar(self, texto, segundos: float = 4.0, erro: bool = False, alerta: bool = False, ao_clicar=None) -> None:
        if not isinstance(texto, Text):
            texto = Text(str(texto), style=self.cor("texto"))
        try:
            self.query_one(Avisos).mostrar(Aviso(texto, segundos, "erro" if erro else "alerta" if alerta else "", ao_clicar))
        except Exception:
            pass

    def avisar_erro(self, msg, segundos: float = 8.0) -> None:
        self.avisar(Text.assemble((ic("nao") + " ", self.cor("red")), (str(msg), self.cor("texto"))), segundos, erro=True)

    def notify(self, message, *, title="", severity="information", timeout=None, markup=True):  # noqa: D401
        """Avisos do próprio Textual viram avisos do oma-rpg."""
        self.avisar(str(message), timeout or 4.0, erro=severity == "error", alerta=severity == "warning")

    def mostrar_dialogo(self, tela, depois=None) -> None:
        if len(self.screen_stack) > 1:
            self._fila_dialogos.append((tela, depois))
            return

        def fim(r):
            if depois:
                depois(r)
            if self._fila_dialogos:
                t, d = self._fila_dialogos.pop(0)
                self.call_after_refresh(self.mostrar_dialogo, t, d)
        self.push_screen(tela, fim)

    # ------------------------------------------------------------ dados para a coluna e o topo
    def badge(self, pagina: str) -> Text:
        h = self.st.get("heroi")
        if not h:
            return Text("")
        if pagina == "quests":
            n = len(C.fila(self.b, self.cfg, self.hoje()))
            return Text(str(n), style=self.cor("mudo")) if n else Text("")
        if pagina == "skills" and h["pontos"]:
            return Text(f"+{h['pontos']}", style=self.cor("yellow"))
        if pagina == "taverna":
            n = int(self.b.escalar("SELECT COUNT(*) FROM quests WHERE estado = 'rascunho'", (), 0))
            return Text(str(n), style=self.cor("green")) if n else Text("")
        return Text("")

    def n_repos(self) -> int:
        try:
            return int(self.b.escalar("SELECT COUNT(*) FROM repos", (), 0))
        except Exception:
            return 0

    def mestre_estado(self) -> str:
        return self.mestre.estado if self.mestre is not None else "ausente"

    def mestre_rotulo(self) -> str:
        if self.mestre is None:
            return "ausente"
        return self.mestre.rotulo() if hasattr(self.mestre, "rotulo") else "claude"

    def _pintar_topo(self) -> None:
        trilha = self.pagina.trilha() if self.pagina is not None else [("", "")]
        self.query_one(Topo).pintar(trilha, self.pos > 0, self.pos < len(self.historico) - 1)

    # ------------------------------------------------------------ páginas
    def abrir_pagina(self, nome: str, foco: bool = False, janela: str = "", historico: bool = True, **kw) -> None:
        mod = importlib.import_module(f"oma_rpg.ui.paginas.{nome}")
        cls = mod.PAGINA
        area = self.query_one("#area")
        area.remove_children()
        p = cls(**kw)
        self.pagina, self.pagina_nome = p, nome
        area.mount(p)
        self.query_one(Lateral).display = not cls.TELA_CHEIA
        if historico and (self.pos < 0 or self.historico[self.pos] != nome):
            self.historico = (self.historico[: self.pos + 1] + [nome])[-30:]
            self.pos = len(self.historico) - 1
        if nome in NOMES_PAGINAS:
            self.estado.definir("pagina", nome)
        self._ultimo_foco = {k: v for k, v in self._ultimo_foco.items() if k in ("topo", "paineis")}
        self._foco_pendente = janela or (cls.ENTRADA if foco else "")

    def _depois_de_abrir(self, janela: str) -> None:
        self._foco_pendente = ""
        self._estreita = janela or (self.pagina.ENTRADA if self.pagina is not None else "")
        self.ajustar()
        self.ler_dados()
        if self.pagina is not None:
            self.pagina.pintar()
        self.query_one(Lateral).pintar()
        self._pintar_topo()
        if janela:
            self.focar_janela(janela)
        self.query_one(Rodape).pintar()

    def voltar(self) -> None:
        if self.pos > 0:
            self.pos -= 1
            self.abrir_pagina(self.historico[self.pos], foco=True, historico=False)

    def avancar(self) -> None:
        if self.pos < len(self.historico) - 1:
            self.pos += 1
            self.abrir_pagina(self.historico[self.pos], foco=True, historico=False)

    def action_pagina(self, n: int) -> None:
        if len(self.screen_stack) > 1:
            return
        self.abrir_pagina(NOMES_PAGINAS[n - 1], foco=True)

    # ------------------------------------------------------------ janelas e foco
    def nome_janela(self, w) -> str:
        while w is not None:
            i = getattr(w, "id", None)
            if i == "topo" or i == "paineis":
                return i
            if i and w.has_class("janela"):
                return i
            w = w.parent
        return ""

    def janela_widget(self, nome: str):
        try:
            return self.query_one(f"#{nome}")
        except Exception:
            return None

    def janela_em_foco(self):
        n = self.nome_janela(self.focused)
        return self.janela_widget(n) if n else None

    def on_descendant_focus(self, ev) -> None:
        n = self.nome_janela(ev.widget)
        if n:
            self._ultimo_foco[n] = ev.widget
            if n != "topo":
                self._ultima_janela = n
        self.call_after_refresh(self._depois_do_foco)

    def on_descendant_blur(self, ev) -> None:
        self.call_after_refresh(self._depois_do_foco)

    def _depois_do_foco(self) -> None:
        try:
            self.query_one(Lateral).marcar_foco(self.nome_janela(self.focused) == "paineis")
            self.query_one(Rodape).pintar()
            from oma_rpg.ui.base import Janela
            for j in self.query(Janela):
                j.compor_titulo()
        except Exception:
            pass

    # ------------------------------------------------------------ meia tela
    def estreito(self) -> bool:
        return self.size.width < ESTREITO

    def redimensionou(self) -> None:
        if self.pronto:
            self.ajustar()
            try:
                self.query_one(Topo).ajustar(self.size.width)
            except Exception:
                pass

    def ajustar(self) -> None:
        """Largo: a página do design. Estreito: só a janela atual, na tela toda (a coluna dos painéis vira uma janela)."""
        lat, area = self.query_one(Lateral), self.query_one("#area")
        for w, campo, valor in self._mexidos:
            try:
                if campo == "display":
                    w.display = valor
                else:
                    setattr(w.styles, campo, valor)
            except Exception:
                pass
        self._mexidos = []
        p = self.pagina
        cheia = bool(p is not None and p.TELA_CHEIA)
        if not self.estreito() or p is None:
            lat.display = not cheia
            area.display = True
            return

        def mexer(w, campo, valor):
            antigo = w.display if campo == "display" else getattr(w.styles, campo)
            self._mexidos.append((w, campo, antigo))
            if campo == "display":
                w.display = valor
            else:
                setattr(w.styles, campo, valor)
        alvo_nome = self._estreita or p.ENTRADA
        if alvo_nome == "paineis":
            lat.display = True
            mexer(lat, "width", "1fr")
            area.display = False
            return
        lat.display = False
        area.display = True
        alvo = self.janela_widget(alvo_nome)
        if alvo is None or (alvo is not p and p not in alvo.ancestors):
            return
        from oma_rpg.ui.base import Janela
        estrutura = set()
        for j in p.query(Janela):
            n = j
            while n is not None and n is not p:
                estrutura.add(n)
                n = n.parent
        caminho = {alvo, *[a for a in alvo.ancestors if a in estrutura]}
        for w in estrutura:
            if w in caminho:
                mexer(w, "width", "1fr")
                mexer(w, "height", "1fr")
            elif w.parent is p or w.parent in caminho:
                mexer(w, "display", False)

    def focar_janela(self, nome: str) -> None:
        if self.estreito() and nome not in ("topo",) and nome != self._estreita:
            self._estreita = nome
            self.ajustar()
            self.call_after_refresh(self._focar_janela, nome)
            return
        self._focar_janela(nome)

    def _focar_janela(self, nome: str) -> None:
        w = self.janela_widget(nome)
        if w is None or not w.display:
            return
        ult = self._ultimo_foco.get(nome)
        if ult is not None and getattr(ult, "is_attached", False) and ult.focusable and self._visivel(ult):
            ult.focus()
        elif hasattr(w, "focar_entrada"):
            w.focar_entrada()
        else:
            w.focus()

    def _visivel(self, w) -> bool:
        while w is not None and w is not self.screen:
            if not w.display:
                return False
            w = w.parent
        return True

    def visiveis(self) -> list[str]:
        """As janelas do Tab: no estreito, também as escondidas (o Tab mostra uma de cada vez)."""
        nomes = ["topo"]
        cheia = self.pagina is not None and self.pagina.TELA_CHEIA
        if not cheia:
            nomes.append("paineis")
        if self.pagina is not None:
            from oma_rpg.ui.base import Janela
            nomes += [j.id for j in self.pagina.query(Janela)]
        return nomes

    def vizinha(self, atual: str, direcao: str) -> str:
        """A tabela do Ctrl+setas: a da página, com o topo em cima de todas e os painéis à esquerda."""
        if atual == "topo":
            return (self._ultima_janela or (self.pagina.ENTRADA if self.pagina else "")) if direcao == "baixo" else ""
        tabela = self.pagina.VIZINHAS if self.pagina is not None else {}
        if atual == "paineis":
            return {"dir": self.pagina.ENTRADA if self.pagina else "", "cima": "topo"}.get(direcao, "")
        return tabela.get(atual, {}).get(direcao, "")

    def action_janela(self, direcao: str) -> None:
        if len(self.screen_stack) > 1:
            s = self.screen
            if hasattr(s, "mover_janela"):
                s.mover_janela(direcao)
            return
        atual = self.nome_janela(self.focused) or (self.pagina.ENTRADA if self.pagina else "")
        alvo = self.vizinha(atual, direcao)
        if alvo == "paineis" and self.pagina is not None and self.pagina.TELA_CHEIA:
            alvo = ""
        if alvo:
            self.focar_janela(alvo)

    def action_ciclo(self, passo: int) -> None:
        if len(self.screen_stack) > 1:
            (self.screen.focus_next if passo > 0 else self.screen.focus_previous)()
            return
        vis = self.visiveis()
        atual = self.nome_janela(self.focused)
        i = vis.index(atual) if atual in vis else -1
        self.focar_janela(vis[(i + passo) % len(vis)])

    def action_mover(self, dx: int, dy: int) -> None:
        """Setas fora de uma lista: andam pelos controles vizinhos da janela, pela posição na tela (do oma-mail)."""
        f = self.focused
        if len(self.screen_stack) > 1:
            raiz = self.screen
        else:
            nome = self.nome_janela(f)
            if f is None or not nome:
                if self.pagina is not None:
                    self.focar_janela(self.pagina.ENTRADA)
                return
            if nome == "topo":
                if dy > 0:
                    self.action_janela("baixo")
                return
            raiz = self.janela_widget(nome)
        if f is None or raiz is None:
            return
        cands = [w for w in raiz.query("*") if w is not f and w.focusable and w.can_focus and self._visivel(w)
                 and w.region.area > 0]
        fr = f.region
        cy, fcx = fr.y + fr.height / 2, fr.x + fr.width / 2
        melhor, chave = None, None
        for w in cands:
            r = w.region
            cx, wcy = r.x + r.width / 2, r.y + r.height / 2
            if dx:
                sobrepoe = r.y <= cy < r.bottom or fr.y <= wcy < fr.bottom
                if not sobrepoe or (cx - fcx) * dx <= 0:
                    continue
                k = (abs(cx - fcx), abs(wcy - cy))
            else:
                if dy > 0 and r.y < fr.bottom or dy < 0 and r.bottom > fr.y:
                    continue
                k = (abs(r.y - fr.bottom) if dy > 0 else abs(fr.y - r.bottom), abs(cx - fcx))
            if chave is None or k < chave:
                melhor, chave = w, k
        if melhor is not None:
            melhor.focus()

    def action_alt_h(self, passo: int) -> None:
        if len(self.screen_stack) > 1:
            s = self.screen
            if hasattr(s, "alt_h"):
                s.alt_h(passo)
            return
        j = self.janela_em_foco()
        if j is not None and hasattr(j, "alt_h"):
            j.alt_h(passo)

    def action_alt_v(self, passo: int) -> None:
        if len(self.screen_stack) > 1:
            return
        j = self.janela_em_foco()
        if j is not None and hasattr(j, "alt_v"):
            j.alt_v(passo)

    def _em_texto(self) -> bool:
        f = self.focused
        return f is not None and any(c.__name__ in ("Input", "TextArea") for c in type(f).__mro__)

    def check_action(self, action: str, parameters):
        if action in ("buscar", "ajuda", "sair", "esc", "mover") and (len(self.screen_stack) > 1 or self._em_texto()):
            return False
        return True

    def itens_rodape(self) -> list[tuple[str, str, str]]:
        if hasattr(self.screen, "itens"):
            return self.screen.itens()
        j = self.janela_em_foco()
        itens = list(j.rodape()) if j is not None and hasattr(j, "rodape") else []
        if self.pagina is not None and hasattr(self.pagina, "rodape_pagina"):
            for it in self.pagina.rodape_pagina():
                if len(itens) < 5 and it[0] not in [x[0] for x in itens]:
                    itens.append(it)
        return itens[:5]

    # ------------------------------------------------------------ ações gerais
    def action_noop(self) -> None:
        pass

    def action_esc(self) -> None:
        if self.pagina_nome == "classes":
            self.abrir_pagina("skills", foco=True)

    def action_sair(self) -> None:
        self.exit()

    def action_buscar(self, inicial: str = "") -> None:
        if len(self.screen_stack) > 1:
            return
        from oma_rpg.ui.dialogos import Busca
        self.push_screen(Busca(inicial), self._resultado_busca)

    def _resultado_busca(self, r) -> None:
        if not r:
            return
        tipo, chave = r
        if tipo == "quest":
            self.abrir_pagina("quests", foco=True, quest=chave)
        elif tipo == "skill":
            self.abrir_pagina("skills", foco=True, skill=chave)
        elif tipo == "item":
            self.abrir_pagina("loja", foco=True, item=chave)
        elif tipo == "pagina":
            self.abrir_pagina(chave, foco=True)

    def action_teclas(self) -> None:
        if len(self.screen_stack) > 1:
            from oma_rpg.ui.dialogos import Teclas
            if isinstance(self.screen, Teclas):
                self.screen.dismiss(None)
            return
        from oma_rpg.ui.dialogos import Teclas
        j = self.janela_em_foco()
        nome = self.nome_janela(self.focused)
        self.push_screen(Teclas(nome, j.teclas() if j is not None and hasattr(j, "teclas") else []))

    def action_ajuda(self) -> None:
        from oma_rpg.ui.dialogos import Teclas
        self.push_screen(Teclas("", [], completa=True))

    def abrir_pastas(self) -> None:
        from oma_rpg.ui.dialogos import Pastas
        if len(self.screen_stack) == 1:
            self.push_screen(Pastas())

    def abrir_agente(self) -> None:
        from oma_rpg.ui.dialogos import AgenteDialogo
        if len(self.screen_stack) != 1:
            return

        def depois(res) -> None:
            if not res or self.mestre is None or not hasattr(self.mestre, "definir_agente"):
                return
            ag, mod = res
            self.mestre.definir_agente(ag, mod, salvar=not self.demo)
        self.push_screen(AgenteDialogo(), depois)

    def abrir_repos(self) -> None:
        from oma_rpg.ui.dialogos import Repos
        self.push_screen(Repos())

    async def on_unmount(self) -> None:
        try:
            self.cliente.fechar()
        except Exception:
            pass
        if self.mestre is not None:
            try:
                self.mestre.parar()
            except Exception:
                pass
