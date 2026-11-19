"""Letras grandes. Duas fontes: a de 3 linhas com traço de caixa (NÍVEL 8, nome da classe, iniciais do retrato),
copiada do oma-mail, e a de pixels 5x5 (o timer do foco e o OMA RPG da abertura).

Acentos somem (É vira E). Letra fora do dicionário vira espaço.
"""

from __future__ import annotations

import unicodedata

_L1 = "┏━┓ ┳━┓ ┏━╸ ┳━┓ ┏━╸ ┏━╸ ┏━╸ ╻ ╻ ╻   ╻ ╻ ╻ ╻   ┏┳┓"
_L2 = "┣━┫ ┣━┫ ┃   ┃ ┃ ┣━  ┣━  ┃╺┓ ┣━┫ ┃   ┃ ┣┳┛ ┃   ┃┃┃"
_L3 = "╹ ╹ ┻━┛ ┗━╸ ┻━┛ ┗━╸ ╹   ┗━┛ ╹ ╹ ╹ ┗━┛ ╹┗╸ ┗━╸ ╹╹╹"
_M1 = "┏┓╻ ┏━┓ ┏━┓ ┏━┓ ┏━┓ ┏━╸ ╺┳╸ ╻ ╻ ╻ ╻ ╻╻╻ ┓ ┏ ╻ ╻ ╺━┓"
_M2 = "┃┗┫ ┃ ┃ ┣━┛ ┃ ┃ ┣┳┛ ┗━┓  ┃  ┃ ┃ ┃┏┛ ┃┃┃  ╋  ┗┳┛ ┏━┛"
_M3 = "╹ ╹ ┗━┛ ╹   ┗━╋ ╹┗╸ ╺━┛  ╹  ┗━┛ ┗┛  ┗┻┛ ┛ ┗  ╹  ┗━╸"
_N1 = "┏━┓ ╺┓ ╺━┓ ╺━┓ ╻ ╻ ┏━╸ ┏━╸ ╺━┓ ┏━┓ ┏━┓        ╻ ╺━┓"
_N2 = "┃ ┃  ┃ ┏━┛  ━┫ ┗━┫ ┗━┓ ┣━┓   ┃ ┣━┫ ┗━┫   ╺╸   ┃  ┏┛"
_N3 = "┗━┛ ╺┻ ┗━╸ ╺━┛   ╹ ╺━┛ ┗━┛   ╹ ┗━┛ ╺━┛      · ·  ·"


def _cortar(linhas: tuple[str, str, str], larguras: list[int]) -> list[tuple[str, str, str]]:
    saida, x = [], 0
    for w in larguras:
        saida.append(tuple(l[x:x + w].ljust(w) for l in linhas))
        x += w + 1
    return saida


# Larguras de cada glifo nas linhas acima (I tem 1 coluna, J e os sinais variam).
_A_M = _cortar((_L1, _L2, _L3), [3, 3, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 3])
_N_Z = _cortar((_M1, _M2, _M3), [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3])
_DIG = _cortar((_N1, _N2, _N3), [3, 2, 3, 3, 3, 3, 3, 3, 3, 3, 1, 2, 1, 1, 3])

GLIFOS: dict[str, tuple[str, str, str]] = {}
for _c, _g in zip("ABCDEFGHIJKLM", _A_M):
    GLIFOS[_c] = _g
for _c, _g in zip("NOPQRSTUVWXYZ", _N_Z):
    GLIFOS[_c] = _g
for _c, _g in zip("0123456789", _DIG[:10]):
    GLIFOS[_c] = _g
GLIFOS[" "] = ("  ", "  ", "  ")
GLIFOS["-"] = (" ", "╺╸", " ")
GLIFOS["!"] = ("╻", "┃", "·")
GLIFOS["."] = (" ", " ", "·")
GLIFOS["?"] = ("╺━┓", " ┏┛", " · ")
GLIFOS["-"] = ("  ", "╺╸", "  ")


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def grande(texto: str) -> list[str]:
    """Três linhas do título em letras grandes."""
    t = _sem_acento(texto).upper()
    linhas = ["", "", ""]
    for c in t:
        g = GLIFOS.get(c, GLIFOS[" "])
        for i in range(3):
            linhas[i] += g[i] + " "
    return [l.rstrip() for l in linhas]


def largura_grande(texto: str) -> int:
    return max((len(l) for l in grande(texto)), default=0)


# ------------------------------------------------------------ pixels 5x5
PIXELS: dict[str, list[str]] = {
    "0": ["#####", "#...#", "#...#", "#...#", "#####"],
    "1": ["..#..", ".##..", "..#..", "..#..", ".###."],
    "2": ["#####", "....#", "#####", "#....", "#####"],
    "3": ["#####", "....#", ".####", "....#", "#####"],
    "4": ["#...#", "#...#", "#####", "....#", "....#"],
    "5": ["#####", "#....", "#####", "....#", "#####"],
    "6": ["#####", "#....", "#####", "#...#", "#####"],
    "7": ["#####", "....#", "...#.", "..#..", "..#.."],
    "8": ["#####", "#...#", "#####", "#...#", "#####"],
    "9": ["#####", "#...#", "#####", "....#", "#####"],
    ":": [".", "#", ".", "#", "."],
    "O": [".###.", "#...#", "#...#", "#...#", ".###."],
    "M": ["#...#", "##.##", "#.#.#", "#...#", "#...#"],
    "A": [".###.", "#...#", "#####", "#...#", "#...#"],
    "R": ["####.", "#...#", "####.", "#..#.", "#...#"],
    "P": ["####.", "#...#", "####.", "#....", "#...."],
    "G": [".####", "#....", "#.###", "#...#", ".###."],
    " ": ["...", "...", "...", "...", "..."],
}


def pixels(texto: str, largura_px: int = 1, espaco: int = 1) -> list[str]:
    """Cinco linhas de █. `largura_px` colunas por pixel (2 no timer, para o pixel ficar quadrado)."""
    linhas = ["", "", "", "", ""]
    for n, c in enumerate(texto.upper()):
        g = PIXELS.get(c, PIXELS[" "])
        for i in range(5):
            if n:
                linhas[i] += " " * espaco * largura_px
            linhas[i] += "".join(("█" if p == "#" else " ") * largura_px for p in g[i])
    return linhas
