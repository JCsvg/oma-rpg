"""Fórmulas do jogo, sem estado. Tudo aqui é função pura sobre números e a Config.

xp   = round(17 × est × mult_dif)        mult_dif: fácil 0,8 · média 1,2 · difícil 1,5
bits = round(xp / 4)
xp do pomodoro = xp base × combo × bônus das skills ativas

`round` do design é o arredondamento escolar (0,5 sobe). O `round` do Python arredonda 76,5 para 76 (para o par),
e o design mostra 77 xp numa quest difícil de 3 pomodoros, então aqui é `arred`.
"""

from __future__ import annotations

import math
import re

DIFS = {1: "fácil", 2: "média", 3: "difícil"}
DIAMANTES = {1: "◆◇◇", 2: "◆◆◇", 3: "◆◆◆"}
ATRIBUTOS = (
    ("for", "Força", "For", "+3% XP em quests só confirmadas e +1 de cura por ponto acima de 1"),
    ("agi", "Agilidade", "Agi", "+2% XP de commit e +0,02 no combo máximo por ponto acima de 1"),
    ("vig", "Vigor", "Vig", "+4 de HP máximo por ponto acima de 1"),
    ("int", "Intelecto", "Int", "+3% XP de perícia e +2% XP de quest com foco por ponto acima de 1"),
    ("con", "Consciência", "Con", "+2% XP de pomodoro e +2 de mana máxima por ponto acima de 1"),
    ("pre", "Presença", "Pre", "+3% de Bits ganhos e +1% de desconto na loja por ponto acima de 1"),
)
ATTR_SIGLAS = {k: sig for k, _, sig, _ in ATRIBUTOS}


def bonus_atributos(attrs: dict) -> dict:
    """Converte os 6 atributos do herói em bônus numéricos concretos."""
    ex = {k: max(0, int(attrs.get(f"attr_{k}", attrs.get(k, 1))) - 1) for k, *_ in ATRIBUTOS}
    return {
        "xp_confirmacao": ex["for"] * 3.0,
        "cura_extra": ex["for"],
        "xp_commit": ex["agi"] * 2.0,
        "combo_max": round(ex["agi"] * 0.02, 2),
        "hp_max": ex["vig"] * 4,
        "xp_pericia": ex["int"] * 3.0,
        "xp_quest_foco": ex["int"] * 2.0,
        "xp_pomodoro": ex["con"] * 2.0,
        "mp_max": ex["con"] * 2,
        "bits": ex["pre"] * 3.0,
        "desconto_loja": min(25, ex["pre"]),
    }


def xp_pericia_nivel(nivel: int, cfg) -> int:
    p = cfg["pericia"]
    return p["xp_base"] + p["xp_passo"] * max(0, int(nivel) - 1)


def arred(x: float) -> int:
    """Arredondamento escolar: 0,5 sobe (para números negativos, desce em módulo)."""
    if x < 0:
        return -arred(-x)
    return int(math.floor(x + 0.5 + 1e-9))


def mult_dif(dif: int, cfg) -> float:
    q = cfg["quest"]
    return {1: q["mult_facil"], 2: q["mult_media"], 3: q["mult_dificil"]}[int(dif)]


def xp_quest(est: int, dif: int, cfg) -> int:
    return arred(cfg["quest"]["xp_por_pomodoro"] * int(est) * mult_dif(dif, cfg))


def bits_de(xp: int, cfg, pct: float = 0.0) -> int:
    if xp <= 0:
        return 0
    return arred(xp / cfg["quest"]["bits_divisor"] * (1 + pct / 100))


def xp_cheio_minimo(est: int, cfg) -> int:
    """Pomodoros feitos para a quest valer o XP cheio (70% do estimado, para cima)."""
    return max(1, math.ceil(int(est) * cfg["quest"]["xp_cheio_fracao"] - 1e-9))


def xp_quest_concluida(est: int, dif: int, feitos: int, cfg, bonus_pct: float = 0.0,
                       sem_pomodoro_pct: float = 0.0) -> int:
    """Sem pomodoro vale a fração reduzida (35%); com 70% dos estimados vale 100%; entre eles, proporcional."""
    cheio = xp_quest(est, dif, cfg)
    frac_sem = float(cfg["quest"].get("sem_pomodoro_fracao", 0.35))
    if feitos <= 0:
        return max(1, arred(cheio * frac_sem * (1 + (bonus_pct + sem_pomodoro_pct) / 100)))
    precisa = xp_cheio_minimo(est, cfg)
    base = cheio if feitos >= precisa else max(cheio * frac_sem, cheio * feitos / precisa)
    return max(1, arred(base * (1 + bonus_pct / 100)))


def combo_max(cfg, gamer: bool, extra: float = 0.0) -> float:
    c = cfg["combo"]
    return round((c["max_gamer"] if gamer else c["max"]) + extra, 2)


def combo(seguidos: int, cfg, gamer: bool = False, extra_max: float = 0.0) -> float:
    """Combo usado no próximo pomodoro: x1.0 + 0.1 por pomodoro seguido no dia, até x1.5 (x2.0 no Gamer)."""
    c = cfg["combo"]
    return round(min(combo_max(cfg, gamer, extra_max), 1 + c["passo"] * max(0, seguidos)), 2)


def xp_pomodoro(cfg, combo_: float, bonus_pct: float = 0.0, overtraining: bool = False, mult: float = 1.0) -> int:
    p = cfg["pomodoro"]
    x = p["xp_base"] * combo_ * (1 + bonus_pct / 100) * mult
    if overtraining:
        x *= p["overtraining_mult"]
    return max(0, arred(x))


def xp_nivel(nivel: int, cfg) -> int:
    """XP para passar do nível n para o n+1."""
    h = cfg["heroi"]
    return h["xp_nivel_base"] + h["xp_nivel_passo"] * max(1, nivel)


def indice_titulo(nivel: int) -> int:
    """Faixas de título: 1-3, 4-7, 8-11, 12-15, 16-19, 20+."""
    if nivel <= 3:
        return 0
    return min(5, 1 + (nivel - 4) // 4)


_TIPO = re.compile(r"^\s*([A-Za-z]+)(\([^)]*\))?!?:")


def tipo_commit(assunto: str) -> str:
    if assunto.lower().startswith(("merge ", "revert ")):
        return "chore"
    m = _TIPO.match(assunto or "")
    if not m:
        return "outro"
    t = m.group(1).lower()
    if t in ("feat", "fix", "perf"):
        return "feat"
    if t in ("test", "tests", "docs", "doc", "refactor"):
        return "test"
    if t in ("chore", "style", "ci", "build", "merge", "revert", "wip"):
        return "chore"
    return "outro"


def xp_commit(tipo: str, linhas: int, vinculado: bool, cfg, ci_pct: float = 0.0, bonus_pct: float = 0.0,
              solto_extra_pct: float = 0.0) -> int:
    c = cfg["commit"]
    base = {"feat": c["xp_feat"], "test": c["xp_test"], "chore": c["xp_chore"]}.get(tipo, c["xp_outro"])
    if linhas <= 0 or base <= 0:
        return 0
    fator = 1.0 if vinculado else min(1.0, c["fator_solto"] + solto_extra_pct / 100)
    x = base * fator * (1 + bonus_pct / 100)
    if vinculado:
        x *= 1 + ci_pct / 100
    return max(0, arred(x))


def chefe_xp(xps_quests: list[int], cfg, extra_pct: float = 0.0) -> int:
    return arred(sum(xps_quests) * (cfg["quest"]["chefe_pct"] + extra_pct) / 100)
