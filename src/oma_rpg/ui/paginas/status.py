"""Tela 8 · status: os 6 atributos (For, Agi, Vig, Int, Con, Pre), perícias independentes com XP e o relatório do perfil."""

from __future__ import annotations

import json

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll

from oma_rpg.nucleo import consultas as C
from oma_rpg.nucleo import regras
from oma_rpg.ui import desenho as D
from oma_rpg.ui.base import Janela, Pagina
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lista import Lista
from oma_rpg.ui.widgets import Botao, Pintado


class JanelaAtributos(Janela):
    NOME = "status-atributos"
    DEFAULT_CSS = "JanelaAtributos { width: 58; } JanelaAtributos #st-heroi { height: 7; margin-top: 1; } " \
                  "JanelaAtributos Lista { margin-top: 1; height: 1fr; }"

    def compose(self) -> ComposeResult:
        yield Pintado(self._heroi, id="st-heroi")
        yield Lista(self._linha, altura=3, id="st-attrs", cursor_sem_foco=True)

    def pintar(self) -> None:
        a = self.app
        h = C.heroi(a.b)
        at = C.atributos(h)
        pts = at["pontos"]
        self.titulo(f"{ic('status')} atributos", f"{pts} ponto{'s' if pts != 1 else ''} livre{'s' if pts != 1 else ''}" if pts else "6 atributos")
        self.query_one("#st-heroi", Pintado).pintar()
        itens = [(k, nome, sig, desc, at[k], at["bonus"]) for k, nome, sig, desc in regras.ATRIBUTOS]
        self.query_one(Lista).definir(itens)

    def _heroi(self, w: int) -> Text:
        a = self.app
        st = a.st.get("heroi")
        if not st:
            return Text("sem herói ainda", style=a.cor("mudo"))
        cls = a.cfg.classe(st["classe_id"])
        linhas = [
            D.linha_lr(Text.assemble((st["nome"], f"bold {a.cor('forte')}"), (" · ", a.cor("mudo")),
                                     (st["classe"], a.cor(cls["cor"]))),
                       Text(f"nível {st['nivel']}", style=f"bold {a.cor('accent')}"), w),
            Text(st["titulo"], style=a.cor("mudo")),
            Text(""),
            D.linha_lr(Text(f"HP {st['hp']}/{st['hp_max']}   MP {st['mp']}/{st['mp_max']}", style=a.cor("texto")),
                       Text(f"XP {st['xp']}/{st['xp_proximo']}", style=a.cor("green")), w),
            D.linha_lr(Text(f"streak {st['streak']}d · combo x{st['combo']:.1f}", style=a.cor("mudo")),
                       Text(f"{st['bits']} bits", style=a.cor("yellow")), w),
        ]
        return D.juntar(linhas)

    def _linha(self, it, i: int, est) -> list[Text]:
        a = self.app
        k, nome, sig, desc, val, _ = it
        w = max(24, est.largura)
        barra = D.barra(a, max(0, min(12, val)), 12, 12, "accent")
        esq = Text.assemble((f"{sig:<4}", f"bold {a.cor('accent')}"), (f"{nome:<13}", f"bold {a.cor('forte')}"), barra)
        st_h = a.st.get("heroi") or {}
        cid = st_h.get("classe_id")
        mod = a.cfg.classe_atributos(cid).get(k, 0) if cid and cid in a.cfg["classes"] else 0
        tag = f" ({mod:+d} cls)" if mod else ""
        dir_ = Text.assemble((f" {val:>2}", f"bold {a.cor('forte')}"), (tag, a.cor("mudo")))
        return [D.linha_lr(esq, dir_, w), Text("    " + desc, style=a.cor("mudo"), no_wrap=True, overflow="ellipsis"), Text("")]

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.pg.action_gastar()

    def atual(self):
        return self.query_one(Lista).item_atual()

    def rodape(self):
        return [("enter / +", "gasta ponto de atributo", "noop")]

    def teclas(self):
        return [("enter ou +", "aumenta o atributo escolhido (1 ponto livre)")]


class JanelaPericias(Janela):
    NOME = "status-pericias"
    DEFAULT_CSS = "JanelaPericias { height: 1fr; } JanelaPericias Lista { margin-top: 1; height: 1fr; }"

    def compose(self) -> ComposeResult:
        yield Lista(self._linha, altura=3, id="st-pericias", cursor_sem_foco=True)

    def pintar(self) -> None:
        a = self.app
        ps = C.pericias(a.b, a.cfg)
        self.titulo("perícias", f"{len(ps)} registradas · n nova · a aprova")
        self.query_one(Lista).definir(ps or [None])

    def _linha(self, p, i: int, est) -> list[Text]:
        a = self.app
        if p is None:
            return [Text("nenhuma perícia ainda (pressione n para criar ou peça ao Mestre)", style=a.cor("mudo")), Text(""), Text("")]
        w = max(24, est.largura)
        sug = p["estado"] != "aprovada"
        t = Text()
        t.append("? " if sug else "✓ ", style=a.cor("yellow") if sug else a.cor("green"))
        t.append(p["nome"], style=f"bold {a.cor('forte')}")
        if sug:
            t.append(" (sugerida pelo Mestre · a aprova)", style=a.cor("yellow"))
        dir_ = Text(f"nv {p['nivel']}", style=f"bold {a.cor('cyan')}")
        l2 = Text("  ")
        l2.append_text(D.barra(a, p["xp"], max(1, p["xp_proximo"]), 16, "cyan"))
        l2.append(f"  {p['xp']}/{p['xp_proximo']} xp", style=a.cor("mudo"))
        return [D.linha_lr(t, dir_, w), l2, Text("")]

    def atual(self):
        return self.query_one(Lista).item_atual()

    def on_lista_escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.pg.action_aprovar_pericia()

    def rodape(self):
        return [("n", "nova perícia", "noop"), ("a", "aprovar", "noop"), ("x", "remover", "noop")]

    def teclas(self):
        return [("n", "cria uma nova perícia"), ("a ou enter", "aprova perícia sugerida"), ("x", "remove perícia")]


class JanelaPerfil(Janela):
    NOME = "status-perfil"
    FOCAVEL = True
    DEFAULT_CSS = ("JanelaPerfil { height: 17; } JanelaPerfil #st-perfil-scroll { height: 1fr; } "
                   "JanelaPerfil #st-perfil-acoes { height: 3; margin-top: 1; } "
                   "JanelaPerfil #st-perfil-acoes Botao { margin-right: 1; }")

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="st-perfil-scroll"):
            yield Pintado(self._desenhar, id="st-perfil-txt")
        with Horizontal(id="st-perfil-acoes"):
            yield Botao("E  questionário 1", id="b-perfil")
            yield Botao("I  2º questionário (Mestre)", id="b-entrevista")
            yield Botao("A  aprovar proposta", id="b-aprovar-prop", classes="cheio")
            yield Botao("X  descartar", id="b-descartar-prop")

    def pintar(self) -> None:
        p = C.perfil(self.app.b)
        tem_prop = bool(p.get("proposta_mestre"))
        self.titulo("sobre você", "proposta do Mestre (a/x)" if tem_prop else "e edita · i 2º questionário")
        self.query_one("#b-aprovar-prop", Botao).display = tem_prop
        self.query_one("#b-descartar-prop", Botao).display = tem_prop
        self.query_one(Pintado).pintar()

    def _desenhar(self, w: int) -> Text:
        a = self.app
        p = C.perfil(a.b)
        rel = (p.get("relatorio") or "").strip()
        mestre_txt = (p.get("perfil_mestre") or "").strip()
        prop_raw = (p.get("proposta_mestre") or "").strip()
        if not rel and not mestre_txt and not prop_raw:
            return Text("\nquestionário ainda não preenchido (e preenche · i 2º questionário)", style=a.cor("mudo"))
        linhas = [Text("")]
        larg = max(20, w - 3)
        if rel:
            for l in rel.splitlines():
                linhas.extend(D.quebrar(l, larg, a.cor("texto")))
        if mestre_txt:
            linhas.append(Text(""))
            linhas.append(Text("2º questionário · estratégia do Mestre:", style=f"bold {a.cor('cyan')}"))
            for l in mestre_txt.splitlines():
                linhas.extend(D.quebrar(l, larg, a.cor("texto")))
        if prop_raw:
            try:
                prop = json.loads(prop_raw)
            except ValueError:
                prop = {}
            if prop:
                linhas.append(Text(""))
                linhas.append(Text("Proposta pendente do Mestre (A aprova · X descarta):", style=f"bold {a.cor('yellow')}"))
                if "atributos" in prop:
                    at = prop["atributos"]
                    txt_at = " · ".join(f"{regras.ATTR_SIGLAS[k]} {at[k]}" for k in regras.ATTR_CHAVES if k in at)
                    linhas.extend(D.quebrar("Personalidade (5 pts): " + txt_at, larg, a.cor("yellow")))
                if "pericias" in prop:
                    linhas.extend(D.quebrar("Perícias (nível 1): " + ", ".join(prop["pericias"]), larg, a.cor("yellow")))
        return D.juntar(linhas)

    def on_botao_apertado(self, ev: Botao.Apertado) -> None:
        ev.stop()
        bid = ev.botao.id
        if bid == "b-perfil":
            self.pg.action_editar_perfil()
        elif bid == "b-entrevista":
            self.pg.action_entrevista()
        elif bid == "b-aprovar-prop":
            self.pg.action_aprovar_proposta()
        elif bid == "b-descartar-prop":
            self.pg.action_descartar_proposta()

    def rodape(self):
        p = C.perfil(self.app.b)
        itens = [("e", "editar Q1", "noop"), ("i", "2º questionário", "noop")]
        if p.get("proposta_mestre"):
            itens += [("a", "aprovar proposta", "noop"), ("x", "descartar", "noop")]
        return itens


class PaginaStatus(Pagina):
    NOME = "status"
    TITULO = "status"
    ENTRADA = "status-atributos"
    VIZINHAS = {
        "status-atributos": {"esq": "paineis", "dir": "status-pericias", "cima": "topo"},
        "status-pericias": {"esq": "status-atributos", "cima": "topo", "baixo": "status-perfil"},
        "status-perfil": {"esq": "status-atributos", "cima": "status-pericias"},
    }
    BINDINGS = [
        Binding("plus,equal", "gastar", show=False),
        Binding("n", "nova_pericia", show=False),
        Binding("a", "aprovar_pericia", show=False),
        Binding("x,delete", "remover_pericia", show=False),
        Binding("e", "editar_perfil", show=False),
        Binding("i", "entrevista", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield JanelaAtributos()
        with Vertical(id="st-dir"):
            yield JanelaPericias()
            yield JanelaPerfil()

    def action_gastar(self) -> None:
        if self.app.nome_janela(self.app.focused) != "status-atributos":
            return
        it = self.query_one(JanelaAtributos).atual()
        if it:
            self.app.pedir("gastar_atributo", {"attr": it[0]})

    def action_nova_pericia(self) -> None:
        from oma_rpg.ui.dialogos import Pedir
        self.app.push_screen(Pedir("nova perícia", "ex.: Programação, Inglês, Atletismo"),
                             lambda nome: nome and self.app.pedir("nova_pericia", {"nome": nome}))

    def action_aprovar_pericia(self) -> None:
        if self.app.nome_janela(self.app.focused) == "status-perfil":
            self.action_aprovar_proposta()
            return
        p = self.query_one(JanelaPericias).atual()
        if p and p["estado"] != "aprovada":
            self.app.pedir("aprovar_pericia", {"id": p["id"]})

    def action_remover_pericia(self) -> None:
        if self.app.nome_janela(self.app.focused) == "status-perfil":
            self.action_descartar_proposta()
            return
        if self.app.nome_janela(self.app.focused) != "status-pericias":
            return
        p = self.query_one(JanelaPericias).atual()
        if p:
            self.app.pedir("remover_pericia", {"id": p["id"]})

    def action_aprovar_proposta(self) -> None:
        if C.perfil(self.app.b).get("proposta_mestre"):
            self.app.pedir("aplicar_proposta_perfil", {})

    def action_descartar_proposta(self) -> None:
        if C.perfil(self.app.b).get("proposta_mestre"):
            self.app.pedir("descartar_proposta_perfil", {})

    def action_entrevista(self) -> None:
        self.app.iniciar_entrevista_perfil()

    def action_editar_perfil(self) -> None:
        from oma_rpg.ui.dialogos import QuestionarioDialogo
        atual = C.perfil(self.app.b)
        cid = (self.app.st.get("heroi") or {}).get("classe_id", "")

        def depois(res) -> None:
            if isinstance(res, dict):
                self.app.pedir("salvar_perfil", res)
        self.app.push_screen(QuestionarioDialogo(atual, editando=True, classe=cid), depois)

    def rodape_pagina(self):
        return [("+", "gastar atributo", "gastar"), ("n", "nova perícia", "nova_pericia"),
                ("a", "aprovar", "aprovar_pericia"), ("e", "editar Q1", "editar_perfil"),
                ("i", "2º questionário", "entrevista")]


PAGINA = PaginaStatus
