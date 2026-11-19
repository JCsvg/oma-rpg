"""Ícones (Nerd Font, conjunto md, conferidos renderizando a JetBrainsMono Nerd Font) e a versão simples.

`OMA_RPG_ICONES=simples` troca tudo por caracteres comuns, para terminal sem Nerd Font.
"""

from __future__ import annotations

import os

ICONES: dict[str, tuple[str, str]] = {
    "marca": ("\U000F03EB", "✎"), "painel": ("\U000F02DC", "⌂"), "foco": ("\U000F051B", "◷"),
    "quests": ("\U000F0756", "☰"), "skills": ("\U000F0241", "ϟ"), "loja": ("\U000F04DC", "▤"),
    "historico": ("\U000F02C1", "▦"), "taverna": ("\U000F167A", "☺"), "mestre": ("\U000F167A", "☺"),
    "status": ("\U000F0004", "@"), "polimata": ("\U000F0335", "✦"), "monge": ("\U000F02D1", "☸"),
    "mistico": ("\U000F18A1", "♠"), "programa": ("\U000F018D", "▸"), "empreendedor": ("\U000F012A", "↗"),
    "rato": ("\U000F01E5", "↔"), "gamer": ("\U000F0297", "◎"), "otaku": ("\U000F05DA", "▯"),
    "vida": ("\U000F02D1", "♥"), "mana": ("\U000F0241", "ϟ"), "xp": ("\U000F04CF", "✪"), "bits": ("\U000F0813", "₿"),
    "streak": ("\U000F0238", "▲"), "combo": ("\U000F0535", "↗"), "commit": ("\U000F0718", "◇"),
    "feito": ("\U000F05E1", "✓"), "pendente": ("\U000F0766", "○"), "vencida": ("\U000F05D6", "!"),
    "andamento": ("\U000F0150", "◷"), "trofeu": ("\U000F0538", "♛"), "medalha": ("\U000F0A08", "✪"),
    "usuario": ("\U000F0004", "@"), "arco": ("\U000F023B", "⚑"), "foguete": ("\U000F0463", "^"),
    "caveira": ("\U000F068C", "x"), "pocao": ("\U000F112F", "δ"), "cafe": ("\U000F0176", "c"), "cadeado": ("\U000F033E", "#"),
    "bilhete": ("\U000F0507", "$"), "coroa": ("\U000F01A5", "♛"), "paleta": ("\U000F03D8", "*"), "chave": ("\U000F05B7", "/"),
    "cabide": ("\U000F0A7B", "T"), "mochila": ("\U000F0E10", "□"), "lampada": ("\U000F0335", "i"), "play": ("\U000F040A", "▶"),
    "pausa": ("\U000F03E4", "‖"), "parar": ("\U000F04DB", "■"), "desfazer": ("\U000F054C", "↶"), "buscar": ("\U000F0349", "/"),
    "bau": ("\U000F0726", "▣"), "coracao_partido": ("\U000F02D3", "♡"), "festa": ("\U000F0E8D", "★"),
    "estrela4": ("\U000F0AE2", "✦"), "grade": ("\U000F02C1", "▦"), "raio": ("\U000F0241", "ϟ"), "nota": ("\U000F039E", "≡"),
    "calendario": ("\U000F00ED", "▤"), "subir": ("\U000F0737", "▲"), "git": ("\U000F02A2", "±"), "rascunhos": ("\U000F0756", "≡"),
}
FIXOS = {"ok": "✓", "nao": "✗", "aviso": "!", "ponto": "●", "vazio": "◌", "circulo": "○", "seta": "→", "ativa": "◆",
         "passiva": "◇", "troca": "⇅", "bloqueada": "◌", "disponivel": "●", "aprendida": "✓"}
GIRO = "⣾⣽⣻⢿⡿⣟⣯⣷"

_modo = "simples" if os.environ.get("OMA_RPG_ICONES", "").lower() == "simples" else "nerd"


def definir_modo(modo: str) -> None:
    global _modo
    _modo = "simples" if modo == "simples" else "nerd"


def ic(nome: str) -> str:
    if nome in FIXOS:
        return FIXOS[nome]
    par = ICONES.get(nome)
    if par is None:
        return ""
    return par[1] if _modo == "simples" else par[0]
