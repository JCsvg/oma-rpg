"""Tela 1 · criação de personagem: as 6 classes à esquerda, detalhes no meio (mecânica, passivas, as cartas do tarô
para o Místico) e os 3 ramos da árvore. Campo de nome embaixo. ↑↓ classe · tab nome · enter cria o herói · esc sai."""

from __future__ import annotations

import getpass

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, Static

from oma_rpg.nucleo.regras import ATTR_SIGLAS
from oma_rpg.ui import desenho as D
from oma_rpg.ui.base import Janela
from oma_rpg.ui.fonte import grande
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lista import Lista, ajustar
from oma_rpg.ui.rodape import Rodape
from oma_rpg.ui.widgets import Botao, Pintado

EXEMPLOS = {
    "programa": ["commit feat dentro do pomodoro: 7 xp", "com CI verde: 9 xp (+25%)", "commit solto: 2 xp (30%)"],
    "empreendedor": ["1.000 bits guardados", "dia com a meta cumprida", "à meia-noite: +10 bits de juros"],
    "rato": ["pausa respeitada: +6 de mana", "e mais +3 de HP (fadiga)", "11º pomodoro do dia: overtraining"],
    "gamer": ["combo x1.0 → x2.0", "11 pomodoros seguidos no dia", "45 min parado: volta a x1.0"],
    "otaku": ["HP abaixo de 30%: virada", "pomodoro de 24 xp vale 48", "chefe do arco: +50%"],
    "polimata": ["perícias sobem +25% mais rápido", "10% chance de crítico (+50% XP)", "fichamento turbina próxima quest"],
    "monge": ["confirmar quest sem pomodoro +30%", "concluir quest cura +3 de HP", "disciplina reduz penalidades"],
}


def _mods_texto(a, cid: str) -> str:
    mods = a.cfg.classe_atributos(cid)
    pos = [f"+1 {ATTR_SIGLAS[k]}" for k, v in mods.items() if v > 0]
    neg = [f"{v} {ATTR_SIGLAS[k]}" for k, v in mods.items() if v < 0]
    return " · ".join(pos + neg)


class ListaClasses(Janela):
    NOME = "criar-classes"
    DEFAULT_CSS = "ListaClasses { width: 47; } ListaClasses Lista { margin-top: 1; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, altura=6, id="criar-lista", cursor_sem_foco=True)

    def on_mount(self) -> None:
        self.titulo("escolha sua classe", "↑↓")
        self.query_one(Lista).definir(self.app.cfg.classes_ordem(), cursor=0)

    def _linha(self, cid: str, i: int, est) -> list[Text]:
        a = self.app
        c = a.cfg.classe(cid)
        sel = est.cursor
        t = Text(f" {i + 1} ", style=a.cor("mudo"))
        t.append(ic(cid) + " ", style=a.cor(c["cor"]))
        t.append(c["nome"], style=f"bold {a.cor('forte')}")
        linhas = [t, Text("     " + c["tema"], style=a.cor("mudo")),
                  Text.assemble(("     poder: ", a.cor(c["cor"])), (c["poder"], a.cor(c["cor"]))),
                  Text(f"     hp {c['hp']} · mana {c['mp']} · {_mods_texto(a, cid)}", style=a.cor("mudo")), Text(""), Text("")]
        if sel:
            linhas = [Text("▌", style=a.cor(c["cor"])) + l[1:] if l.plain else l for l in linhas[:4]] + linhas[4:]
        return linhas

    def on_lista_destacado(self, ev: Lista.Destacado) -> None:
        self.screen.query_one(Detalhes).classe = ev.item
        self.screen.query_one(Detalhes).pintar()

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.screen.query_one("#nome", Input).focus()


class Detalhes(Janela):
    NOME = "criar-detalhes"
    FOCAVEL = True

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.classe = "mistico"

    def compose(self) -> ComposeResult:
        yield Pintado(self._desenhar)

    def pintar(self) -> None:
        ordem = self.app.cfg.classes_ordem()
        self.titulo("detalhes", f"classe {ordem.index(self.classe) + 1} de {len(ordem)}")
        self.query_one(Pintado).pintar()

    def _desenhar(self, w: int) -> Text:
        a = self.app
        cid = self.classe
        c = a.cfg.classe(cid)
        cor = a.cor(c["cor"])
        ret = D.moldura(a, [Text(""), Text(ic(cid), style=cor)] + [Text(l, style=cor) for l in grande(c["sigla"])] + [Text("")],
                        16, "", "texto", fundo="painel")
        direita = [Text(l, style=f"bold {cor}") for l in grande(c["nome"])]
        direita += [Text(""), Text(c["tema"], style=a.cor("texto")),
                    Text(f"atributos da classe: {_mods_texto(a, cid)}", style=a.cor("mudo")), Text(""),
                    Text("poder da classe", style=a.cor("mudo")),
                    Text.assemble((c["poder_titulo"] + ": ", f"bold {cor}"), (c["poder_txt"], a.cor("texto")))]
        linhas = [Text("")]
        for i in range(max(len(ret), len(direita))):
            esq = ret[i] if i < len(ret) else Text(" " * 16)
            d = direita[i] if i < len(direita) else Text("")
            linhas.append(Text(" ") + esq + Text("   ") + d)
        linhas += [Text(""), D.secao(a, "como é um dia", w - 1)]
        for l in c["dia"]:
            linhas.append(Text.assemble(("‣ ", a.cor("mudo")), (l, a.cor("texto"))))
        linhas.append(Text(""))
        if cid == "mistico":
            linhas += self._cartas(w)
        else:
            caixa = D.caixa(a, [Text(x, style=a.cor("texto")) for x in EXEMPLOS.get(cid, [])], 44)
            linhas += [Text("  ") + l for l in caixa]
        linhas.append(Text(""))
        linhas.append(D.secao(a, "árvore de skills", w - 1, f"3 ramos · 15 habilidades · {c['hp']} hp · {c['mp']} mana"))
        linhas.append(Text(""))
        sk = a.cfg.skills_da_classe(cid)
        col = (w - 4) // 3
        cab = Text("")
        for r, nome in enumerate(c["ramos"]):
            cab.append_text(ajustar(Text(nome, style=f"bold {cor}"), col))
            cab.append("  ")
        linhas.append(cab)
        reg = Text("")
        for _ in c["ramos"]:
            reg.append("─" * (col - 2), style=a.cor("linha"))
            reg.append("    ")
        linhas.append(reg)
        for pos in range(5):
            t = Text("")
            for r in range(3):
                sid = next(s for s in sk if a.cfg.skill(s)["ramo"] == r and a.cfg.skill(s)["pos"] == pos)
                s = a.cfg.skill(sid)
                ativa = s["tipo"] == "ativa"
                item = Text.assemble(("◆ " if ativa else "◇ ", cor if ativa else a.cor("mudo")),
                                     (s["nome"], f"bold {a.cor('forte')}" if pos == 4 else a.cor("texto")))
                t.append_text(D.linha_lr(item, Text(s["tipo"], style=a.cor("mudo")), col - 2))
                t.append("    ")
            linhas.append(t)
        linhas += [Text(""), Text("◆ gasta mana · ◇ sempre ligada · a última de cada ramo é o ápice", style=a.cor("mudo"))]
        return D.juntar(linhas)

    def _cartas(self, w: int) -> list[Text]:
        a = self.app
        cor = a.cor("magenta")
        cartas = a.cfg["cartas"]
        trio = [("0", "☼", "O LOUCO"), ("XVII", "✦", "A ESTRELA"), ("XVI", "ϟ", "A TORRE")]
        lado = [Text("carta de hoje", style=a.cor("mudo")), Text(cartas["a_estrela"]["nome"], style=f"bold {cor}"),
                Text.assemble(("buff  ", a.cor("green")), (cartas["a_estrela"]["desc"], a.cor("green"))),
                Text(f"A Torre cobra o dobro de HP das dailies vencidas", style=a.cor("red")), Text(""),
                Text("tire outra carta com a Roda da Fortuna", style=a.cor("mudo"))]
        caixas = []
        for n, (num, sim, nome) in enumerate(trio):
            borda = a.cor("forte") if n == 1 else a.cor("mudo")
            caixas.append([Text("┌──────────┐", style=borda), Text(f"│{num:^10}│", style=borda), Text("│          │", style=borda),
                           Text(f"│{sim:^10}│", style=cor), Text("│          │", style=borda),
                           Text(f"│{nome:^10}│", style=f"bold {a.cor('forte')}" if n == 1 else a.cor("texto")),
                           Text("└──────────┘", style=borda)])
        saida = []
        for i in range(7):
            t = Text(" ")
            for cx in caixas:
                t.append_text(cx[i])
                t.append("  ")
            t.append("   ")
            if 0 <= i - 1 < len(lado):
                t.append_text(lado[i - 1])
            saida.append(t)
        return saida


class CampoNome(Janela):
    NOME = "criar-nome"
    DEFAULT_CSS = "CampoNome { height: 5; } CampoNome Horizontal { height: 1; } CampoNome Input { width: 1fr; }"

    def compose(self) -> ComposeResult:
        yield Static("")
        with Horizontal():
            yield Input(getpass.getuser()[:24], id="nome", placeholder="nome do herói")
            yield Botao("Q  sobre você (questionário)", id="questionario")
            yield Botao("enter  criar herói", id="criar", classes="cheio")

    def on_mount(self) -> None:
        self.titulo("nome do herói", "tab alterna · Q questionário")


class Criar(Screen):
    DEFAULT_CSS = """
    Criar { background: $background; layout: vertical; }
    Criar #criar-topo { height: 1; background: $rpg-escuro; padding: 0 1; }
    Criar #criar-corpo { height: 1fr; }
    Criar Detalhes { width: 1fr; margin-left: 1; }
    """
    BINDINGS = [Binding("escape", "sair", priority=True), Binding("tab", "alternar", priority=True),
                Binding("shift+tab", "alternar", priority=True), Binding("enter", "criar", priority=True),
                Binding("Q,shift+q", "questionario", show=False),
                Binding("ctrl+right,ctrl+l", "janela('dir')", priority=True), Binding("ctrl+left,ctrl+h", "janela('esq')", priority=True),
                Binding("ctrl+down,ctrl+j", "janela('baixo')", priority=True), Binding("ctrl+up,ctrl+k", "janela('cima')", priority=True)]
    VIZINHAS = {"criar-classes": {"dir": "criar-detalhes", "baixo": "criar-nome"},
                "criar-detalhes": {"esq": "criar-classes", "baixo": "criar-nome"},
                "criar-nome": {"cima": "criar-classes"}}

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.perfil: dict = {}

    def compose(self) -> ComposeResult:
        a = self.app
        yield Static(Text.assemble((ic("marca"), f"bold {a.cor('accent')}"), " ", ("oma-rpg", f"bold {a.cor('forte')}"),
                                   ("   ‹ ›   ", a.cor("linha")), ("novo herói", f"bold {a.cor('forte')}")), id="criar-topo")
        with Horizontal(id="criar-corpo"):
            yield ListaClasses()
            yield Detalhes()
        yield CampoNome()
        yield Rodape(id="rodape-criar")

    def on_mount(self) -> None:
        self.query_one(Detalhes).pintar()
        self.query_one("#criar-lista", Lista).focus()

    def itens(self) -> list[tuple[str, str, str]]:
        return [("↑↓", "classe", "noop"), ("tab", "nome", "alternar"),
                ("Q", "sobre você" + (" ✓" if self.perfil else ""), "questionario"),
                ("enter", "criar herói", "criar"), ("esc", "sair", "sair")]

    def action_questionario(self) -> None:
        from oma_rpg.ui.dialogos import QuestionarioDialogo

        def depois(res) -> None:
            if isinstance(res, dict):
                self.perfil = res
                self.query_one("#questionario", Botao).label = "Q  sobre você ✓"
                self.query_one(Rodape).pintar()
        classe = self.query_one(Detalhes).classe
        self.app.push_screen(QuestionarioDialogo(self.perfil, classe=classe), depois)

    def action_alternar(self) -> None:
        i = self.query_one("#nome", Input)
        if i.has_focus:
            self.query_one("#criar-lista", Lista).focus()
        else:
            i.focus()

    def action_janela(self, direcao: str) -> None:
        f = self.focused
        atual = ""
        while f is not None:
            if getattr(f, "id", "") in self.VIZINHAS:
                atual = f.id
                break
            f = f.parent
        alvo = self.VIZINHAS.get(atual, {}).get(direcao)
        if alvo:
            self.query_one(f"#{alvo}").focar_entrada()

    def action_criar(self) -> None:
        nome = self.query_one("#nome", Input).value.strip()
        if not nome:
            self.query_one("#nome", Input).focus()
            return
        classe = self.query_one(Detalhes).classe
        self.dismiss((nome, classe, self.perfil) if self.perfil else (nome, classe))

    def action_sair(self) -> None:
        self.dismiss(None)

    def on_botao_apertado(self, ev: Botao.Apertado) -> None:
        ev.stop()
        if ev.botao.id == "questionario":
            self.action_questionario()
        else:
            self.action_criar()
