"""Desenhos em texto: barras, bolinhas de pomodoro, diamantes de dificuldade, mapa de calor, seções e caixas."""

from __future__ import annotations

from rich.text import Text

from oma_rpg.nucleo import consultas as C
from oma_rpg.nucleo import regras
from oma_rpg.ui.icones import ic
from oma_rpg.ui.lista import ajustar

BLOCO = "▆"


def barra(app, valor: float, maximo: float, largura: int, cor: str, ch: str = BLOCO) -> Text:
    largura = max(1, largura)
    cheio = 0 if maximo <= 0 else max(0, min(largura, round(largura * valor / maximo)))
    t = Text(no_wrap=True)
    t.append(ch * cheio, style=app.cor(cor))
    t.append(ch * (largura - cheio), style=app.cor("vazio"))
    return t


def cor_hp(app, hp: int, hp_max: int, otaku: bool = False) -> str:
    """cheio e normal: vermelho; <30%: laranja; <10%: pisca (vermelho forte); Otaku na virada: ciano."""
    f = hp / hp_max if hp_max else 0
    if otaku and f < 0.3:
        return "cyan"
    if f < 0.3:
        return "orange"
    return "red"


def pontos(app, feitos: int, est: int, cor: str = "green", sep: str = " ") -> Text:
    t = Text(no_wrap=True)
    for i in range(max(est, feitos)):
        if i:
            t.append(sep)
        if i < feitos:
            t.append("●", style=app.cor(cor))
        else:
            t.append("◌", style=app.cor("mudo"))
    return t


def diamantes(app, dif: int) -> Text:
    return Text(regras.DIAMANTES.get(int(dif), "◆◇◇"), style=app.cor("yellow"))


def xp_bits(app, xp: int, bits: int, mais: bool = True, mudo: bool = False) -> Text:
    s = "+" if mais else ""
    t = Text(no_wrap=True)
    t.append(f"{s}{xp} xp", style=app.cor("mudo" if mudo else "texto"))
    t.append("  ")
    t.append(f"{s}{bits}", style=app.cor("mudo" if mudo else "texto"))
    t.append(ic("bits"), style=app.cor("yellow"))
    return t


def secao(app, titulo: str, largura: int, direita: str = "") -> Text:
    t = Text(no_wrap=True)
    t.append(titulo, style=f"bold {app.cor('forte')}")
    resto = largura - t.cell_len - 1 - (len(direita) + 1 if direita else 0)
    if resto > 0:
        t.append(" " + "─" * resto, style=app.cor("linha"))
    if direita:
        t.append(" " + direita, style=app.cor("mudo"))
    return t


def linha_lr(esq: Text | str, dir_: Text | str, largura: int) -> Text:
    """Texto à esquerda e à direita na mesma linha."""
    e = esq if isinstance(esq, Text) else Text(str(esq))
    d = dir_ if isinstance(dir_, Text) else Text(str(dir_))
    e = e.copy()
    e.no_wrap = True
    if e.cell_len + d.cell_len + 1 > largura:
        e.truncate(max(0, largura - d.cell_len - 1), overflow="ellipsis")
    meio = max(1, largura - e.cell_len - d.cell_len)
    return e + Text(" " * meio) + d


def juntar(linhas: list[Text]) -> Text:
    t = Text(no_wrap=True)
    for n, l in enumerate(linhas):
        if n:
            t.append("\n")
        t.append_text(l if isinstance(l, Text) else Text(str(l)))
    return t


def quebrar(texto: str, largura: int, estilo: str = "") -> list[Text]:
    """Quebra em palavras, sem cortar no meio."""
    linhas, atual = [], ""
    for palavra in texto.split():
        if not atual:
            atual = palavra
        elif len(atual) + 1 + len(palavra) <= largura:
            atual += " " + palavra
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return [Text(ajustar(Text(l), largura).plain.rstrip(), style=estilo) for l in linhas] or [Text("")]


def caixa(app, linhas: list[Text], largura: int, cor: str = "linha", fundo: str | None = None) -> list[Text]:
    """Uma caixa de borda fina em volta das linhas (as três do foco, a moldura do retrato)."""
    c = app.cor(cor)
    dentro = largura - 2
    saida = [Text("┌" + "─" * dentro + "┐", style=c)]
    for l in linhas:
        t = Text("│", style=c)
        corpo = ajustar(l, dentro)
        if fundo:
            corpo.stylize(f"on {app.cor(fundo)}")
        t.append_text(corpo)
        t.append("│", style=c)
        saida.append(t)
    saida.append(Text("└" + "─" * dentro + "┘", style=c))
    return saida


MOLDURAS = {"": "┌─┐│└┘", "dupla": "╔═╗║╚╝", "redonda": "╭─╮│╰╯", "grossa": "┏━┓┃┗┛", "tracejada": "┌┄┐┆└┘"}


def moldura(app, linhas: list[Text], largura: int, estilo: str, cor: str, fundo: str | None = None) -> list[Text]:
    m = MOLDURAS.get(estilo, MOLDURAS[""])
    c = app.cor(cor)
    dentro = largura - 2
    saida = [Text(m[0] + m[1] * dentro + m[2], style=c)]
    for l in linhas:
        t = Text(m[3], style=c)
        corpo = ajustar(l, dentro, "center")
        if fundo:
            corpo.stylize(f"on {app.cor(fundo)}")
        t.append_text(corpo)
        t.append(m[3], style=c)
        saida.append(t)
    saida.append(Text(m[4] + m[1] * dentro + m[5], style=c))
    return saida


# ------------------------------------------------------------ mapa de calor
def niveis_calor(app, cor: str) -> list[str]:
    from oma_rpg.ui.tema import misturar
    base, fundo = app.cor(cor), app.cor("fundo")
    return [app.cor("vazio"), misturar(base, fundo, 0.35), misturar(base, fundo, 0.55), misturar(base, fundo, 0.78), base]


def nivel_de(v: int, maximo: int) -> int:
    if v <= 0 or maximo <= 0:
        return 0
    return max(1, min(4, 1 + int(4 * v / (maximo + 1))))


def mapa_calor(app, valores: dict[str, int], fim_dia: str, semanas: int, cor: str, cursor: str = "",
               rotulos: bool = True) -> list[Text]:
    """Colunas = semanas (seg a dom), da mais antiga à de `fim_dia`. Rótulos dos meses em cima e seg/qua/sex."""
    from datetime import timedelta
    fim = C.data(fim_dia)
    ultima_seg = fim - timedelta(days=fim.weekday())
    inicio = ultima_seg - timedelta(weeks=semanas - 1)
    niveis = niveis_calor(app, cor)
    maximo = max(valores.values(), default=0)
    meses = [" "] * (semanas * 2)
    ultimo_mes = -1
    for s in range(semanas):
        d = inicio + timedelta(weeks=s)
        if d.month != ultimo_mes:
            if s == 0 and d.day > 7:
                ultimo_mes = d.month
                continue
            nome = C.MESES[d.month - 1]
            for i, ch in enumerate(nome):
                if s * 2 + i < len(meses):
                    meses[s * 2 + i] = ch
            ultimo_mes = d.month
    margem = "    " if rotulos else ""
    linhas = [Text(margem + "".join(meses).rstrip(), style=app.cor("mudo"))]
    for wd in range(7):
        t = Text(no_wrap=True)
        if rotulos:
            t.append({0: "seg ", 2: "qua ", 4: "sex "}.get(wd, "    "), style=app.cor("mudo"))
        for s in range(semanas):
            d = inicio + timedelta(weeks=s, days=wd)
            k = d.isoformat()
            if d > fim:
                t.append("  ")
                continue
            v = valores.get(k, 0)
            estilo = niveis[nivel_de(v, maximo)]
            if k == cursor:
                t.append("■", style=f"bold {app.cor('forte')} on {app.cor('selecao')}")
                t.append("▏", style=app.cor("accent"))
            else:
                t.append("■ ", style=estilo)
        linhas.append(t)
    return linhas


def legenda_calor(app, cor: str) -> Text:
    t = Text("menos ", style=app.cor("mudo"))
    for c in niveis_calor(app, cor):
        t.append("■ ", style=c)
    t.append("mais", style=app.cor("mudo"))
    return t


def dia_longo(dia: str) -> str:
    d = C.data(dia)
    return f"{C.SEMANA_LONGA[d.weekday()]} {d.day:02d}/{d.month:02d}"


def quando(ts: float, hoje: str) -> str:
    d = C.dia_de(ts)
    if d == hoje:
        return C.hora(ts)
    if d == C.ontem(hoje):
        return "ontem"
    return C.SEMANA[C.data(d).weekday()]
