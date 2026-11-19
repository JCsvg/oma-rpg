"""Leituras do estado do jogo. Só SELECT: servem a interface (banco só leitura), o CLI e o próprio motor.

Nada aqui muda o banco. A carta do dia, quando ainda não foi gravada, é calculada do mesmo jeito que o motor sorteia
(semente = dia + nome), então a interface e o serviço mostram a mesma carta.
"""

from __future__ import annotations

import json
import random
import time
from collections import defaultdict
from datetime import date, timedelta

from oma_rpg.nucleo import regras

FASES_RODANDO = ("foco", "pausa", "longa", "desmaio")


# ------------------------------------------------------------ datas
def dia_de(t: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(t))


def data(dia: str) -> date:
    return date.fromisoformat(dia)


def ontem(dia: str) -> str:
    return (data(dia) - timedelta(days=1)).isoformat()


def amanha(dia: str) -> str:
    return (data(dia) + timedelta(days=1)).isoformat()


def fim_do_dia(dia: str) -> float:
    d = data(dia)
    return time.mktime((d.year, d.month, d.day, 23, 59, 59, 0, 0, -1))


def inicio_do_dia(dia: str) -> float:
    d = data(dia)
    return time.mktime((d.year, d.month, d.day, 0, 0, 0, 0, 0, -1))


SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
SEMANA_LONGA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def dia_curto(dia: str) -> str:
    """sex 20/11"""
    d = data(dia)
    return f"{SEMANA[d.weekday()]} {d.day:02d}/{d.month:02d}"


def hora(t: float) -> str:
    return time.strftime("%H:%M", time.localtime(t))


def mmss(seg: float) -> str:
    s = max(0, int(seg + 0.999)) if seg > 0 else 0
    return f"{s // 60:d}:{s % 60:02d}"


def milhar(n: int) -> str:
    """1.284"""
    return f"{int(n):,}".replace(",", ".")


# ------------------------------------------------------------ herói e passivos
def heroi(b):
    return b.um("SELECT * FROM heroi WHERE id = 1")


def atual(b):
    return b.um("SELECT * FROM atual WHERE id = 1")


def decorrido(a, agora: float) -> float:
    if a is None or a["fase"] not in FASES_RODANDO:
        return 0.0
    ref = a["pausado_em"] if a["pausado_em"] else agora
    return max(0.0, ref - a["inicio"])


def restante(a, agora: float) -> float:
    if a is None or a["fase"] not in FASES_RODANDO:
        return 0.0
    return max(0.0, a["duracao"] - decorrido(a, agora))


def sortear_carta(cfg, dia: str, nome: str, giro: int = 0) -> tuple[str, str]:
    cartas = cfg["cartas"]
    buffs = sorted(k for k, c in cartas.items() if c["tipo"] == "buff")
    debuffs = sorted(k for k, c in cartas.items() if c["tipo"] == "debuff")
    r = random.Random(f"{dia}|{nome}|{giro}")
    return r.choice(buffs), r.choice(debuffs)


def carta_do_dia(b, cfg, dia: str, h=None) -> tuple[str, str, bool] | None:
    h = h if h is not None else heroi(b)
    if h is None or h["classe"] != "mistico":
        return None
    r = b.um("SELECT buff, debuff, revelada FROM cartas WHERE dia = ?", (dia,))
    if r is not None and r["buff"] in cfg["cartas"] and r["debuff"] in cfg["cartas"]:
        return r["buff"], r["debuff"], bool(r["revelada"])
    buff, debuff = sortear_carta(cfg, dia, h["nome"])
    return buff, debuff, False


def passivos(b, cfg, dia: str, h=None) -> defaultdict:
    """Soma dos efeitos sempre ligados: passivas aprendidas, utilitários comprados e as cartas do dia (Místico)."""
    P: defaultdict = defaultdict(float)
    h = h if h is not None else heroi(b)
    if h is None:
        return P
    sk = cfg["skills"]
    for (sid,) in b.todos("SELECT skill FROM skills"):
        s = sk.get(sid)
        if s and s["classe"] == h["classe"] and s["tipo"] == "passiva":
            P[s["efeito"]] += float(s.get("valor", 0) or 1)
    itens = cfg["itens"]
    for (iid,) in b.todos("SELECT item FROM posses"):
        it = itens.get(iid)
        if it and it["categoria"] == "utilitario" and isinstance(it["valor"], (int, float)):
            P[it["efeito"]] += float(it["valor"])
    cd = carta_do_dia(b, cfg, dia, h)
    if cd:
        for cid in cd[:2]:
            c = cfg["cartas"][cid]
            P[c["efeito"]] += float(c["valor"])
    return P


def hp_max(cfg, h, P) -> int:
    return int(cfg["classes"][h["classe"]]["hp"] + P["hp_max"])


def mp_max(cfg, h, P) -> int:
    return int(cfg["classes"][h["classe"]]["mp"] + P["mp_max"])


def teto(cfg, P) -> int:
    return max(1, int(cfg["pomodoro"]["teto_diario"] + P["teto"]))


def seguidos_validos(cfg, h, inicio: float) -> int:
    """Pomodoros seguidos que ainda contam para o combo de um pomodoro que começa em `inicio`."""
    if h is None or h["seguidos_dia"] != dia_de(inicio):
        return 0
    if h["classe"] == "gamer" and h["ultimo_fim"] and inicio - h["ultimo_fim"] > cfg["combo"]["gamer_intervalo_min"] * 60:
        return 0
    return int(h["seguidos"])


def combo_de(cfg, h, P, inicio: float) -> float:
    return regras.combo(seguidos_validos(cfg, h, inicio), cfg, h["classe"] == "gamer", P["combo_max"])


def titulo_classe(cfg, h) -> str:
    t = cfg["classes"][h["classe"]]["titulos"]
    return t[min(len(t) - 1, regras.indice_titulo(h["nivel"]))]


def titulo(cfg, h) -> str:
    return h["titulo"] or titulo_classe(cfg, h)


def feitos_dia(b, dia: str) -> int:
    return int(b.escalar("SELECT COUNT(*) FROM pomodoros WHERE dia = ? AND estado = 'feito'", (dia,), 0))


def quest_feitos(b, qid: int, dia: str | None = None) -> int:
    if dia:
        return int(b.escalar("SELECT COUNT(*) FROM pomodoros WHERE quest_id = ? AND estado = 'feito' AND dia = ?",
                             (qid, dia), 0))
    return int(b.escalar("SELECT COUNT(*) FROM pomodoros WHERE quest_id = ? AND estado = 'feito'", (qid,), 0))


def efeito(b, tipo: str) -> float:
    return float(b.escalar("SELECT SUM(valor) FROM efeitos WHERE tipo = ?", (tipo,), 0) or 0)


def tem_efeito(b, tipo: str) -> bool:
    return b.um("SELECT 1 FROM efeitos WHERE tipo = ? LIMIT 1", (tipo,)) is not None


# ------------------------------------------------------------ quests
def subtarefas(row) -> list[dict]:
    try:
        v = json.loads(row["subtarefas"] or "[]")
        return [x for x in v if isinstance(x, dict) and isinstance(x.get("texto"), str)][:12]
    except ValueError:
        return []


def quest_dict(b, cfg, q, dia: str | None = None) -> dict:
    daily = q["tipo"] == "daily"
    feitos = quest_feitos(b, q["id"], dia if daily and dia else None)
    xp = regras.xp_quest(q["est"], q["dif"], cfg)
    return {
        "id": q["id"], "titulo": q["titulo"], "materia": q["materia"], "est": q["est"], "dif": q["dif"],
        "arco": q["arco_nome"], "arco_id": q["arco_id"], "prazo": q["prazo"], "tipo": q["tipo"], "estado": q["estado"],
        "origem": q["origem"], "porque": q["porque"], "feitos": feitos, "xp": xp, "bits": regras.bits_de(xp, cfg),
        "hoje": bool(q["hoje"]), "ordem": q["ordem"], "subtarefas": subtarefas(q), "nota": q["nota"],
        "daily_feita": bool(daily and dia and q["daily_feita"] == dia),
        "daily_livre": bool(daily and dia and q["daily_livre"] == dia),
        "xp_ganho": q["xp_ganho"], "concluida": q["concluida"],
    }


def quests(b, cfg, dia: str, estado: str | None = None, arco: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM quests", []
    cond = []
    if estado:
        cond.append("estado = ?")
        args.append(estado)
    else:
        cond.append("estado IN ('aberta', 'rascunho', 'feita')")
    if arco:
        cond.append("lower(arco_nome) = lower(?)")
        args.append(arco)
    sql += " WHERE " + " AND ".join(cond) + " ORDER BY estado = 'feita', ordem, id"
    return [quest_dict(b, cfg, q, dia) for q in b.todos(sql, args)]


def fila(b, cfg, dia: str) -> list[dict]:
    """Quests de hoje ainda abertas: as marcadas para hoje e as dailies pendentes, na ordem da fila."""
    saida = []
    for q in b.todos("SELECT * FROM quests WHERE estado = 'aberta' AND (hoje = 1 OR tipo = 'daily') ORDER BY ordem, id"):
        d = quest_dict(b, cfg, q, dia)
        if d["tipo"] == "daily" and (d["daily_feita"] or d["daily_livre"]):
            continue
        saida.append(d)
    return saida


def hoje_lista(b, cfg, dia: str) -> list[dict]:
    """A janela "hoje" do painel: as de hoje (inclusive as feitas hoje) e as dailies."""
    ini, fim = inicio_do_dia(dia), fim_do_dia(dia)
    saida = []
    for q in b.todos("SELECT * FROM quests WHERE (estado = 'aberta' AND (hoje = 1 OR tipo = 'daily')) "
                     "OR (estado = 'feita' AND concluida BETWEEN ? AND ?) ORDER BY estado != 'feita', ordem, id", (ini, fim)):
        saida.append(quest_dict(b, cfg, q, dia))
    return saida


def arcos(b, cfg) -> list[dict]:
    saida = []
    for a in b.todos("SELECT * FROM arcos ORDER BY id"):
        tot = int(b.escalar("SELECT COUNT(*) FROM quests WHERE arco_id = ? AND estado IN ('aberta','feita')", (a["id"],), 0))
        feitas = int(b.escalar("SELECT COUNT(*) FROM quests WHERE arco_id = ? AND estado = 'feita'", (a["id"],), 0))
        xps = [regras.xp_quest(q["est"], q["dif"], cfg) for q in
               b.todos("SELECT est, dif FROM quests WHERE arco_id = ? AND estado IN ('aberta','feita')", (a["id"],))]
        bonus = regras.chefe_xp(xps, cfg)
        saida.append({"id": a["id"], "nome": a["nome"], "cor": a["cor"], "chefe": a["chefe"], "data": a["data"],
                      "total": tot, "feitas": feitas, "pct": round(100 * feitas / tot) if tot else 0,
                      "bonus_xp": bonus, "bonus_bits": regras.bits_de(bonus, cfg), "vencido": a["bonus_em"] is not None})
    return saida


def cor_materia(b, materia: str) -> str:
    if materia:
        r = b.um("SELECT cor FROM arcos WHERE lower(nome) = lower(?)", (materia,))
        if r:
            return r[0]
    cores = ["blue", "cyan", "magenta", "yellow", "orange", "green"]
    return cores[sum(map(ord, materia or "?")) % len(cores)]


# ------------------------------------------------------------ status (CLI, barra e topo)
def status(b, cfg, agora: float) -> dict:
    h = heroi(b)
    if h is None:
        return {"heroi": None}
    dia = dia_de(agora)
    P = passivos(b, cfg, dia, h)
    a = atual(b)
    feitos = feitos_dia(b, dia)
    qa = b.um("SELECT titulo FROM quests WHERE id = ?", (a["quest_id"],)) if a["quest_id"] else None
    cls = cfg["classes"][h["classe"]]
    return {
        "heroi": {
            "nome": h["nome"], "classe": cls["nome"], "classe_id": h["classe"], "nivel": h["nivel"],
            "titulo": titulo(cfg, h), "xp": h["xp"], "xp_proximo": regras.xp_nivel(h["nivel"], cfg),
            "hp": h["hp"], "hp_max": hp_max(cfg, h, P), "mp": h["mp"], "mp_max": mp_max(cfg, h, P),
            "bits": h["bits"], "pontos": h["pontos"], "combo": combo_de(cfg, h, P, agora),
            "streak": streak_atual(h, dia), "melhor_streak": h["melhor_streak"],
        },
        "hoje": {"dia": dia, "pomodoros": feitos, "meta": cfg["pomodoro"]["meta_diaria"], "teto": teto(cfg, P),
                 "overtraining": feitos >= teto(cfg, P)},
        "pomodoro": {"fase": a["fase"], "restante_s": int(restante(a, agora)), "pausado": bool(a["pausado_em"]),
                     "quest": qa["titulo"] if qa else "", "n": a["n"], "guardado": a["guardado_quest"] is not None},
        "desmaiado": a["fase"] == "desmaio",
    }


def streak_atual(h, dia: str) -> int:
    """O streak continua valendo se o último dia contado foi hoje ou ontem."""
    if h is None or not h["streak_dia"]:
        return 0
    return int(h["streak"]) if h["streak_dia"] in (dia, ontem(dia)) else 0


# ------------------------------------------------------------ histórico
def historico(b, cfg, agora: float, dias: int) -> list[dict]:
    dias = max(1, min(400, int(dias)))
    hoje = dia_de(agora)
    desde = (data(hoje) - timedelta(days=dias - 1)).isoformat()
    pom = defaultdict(lambda: {"pomodoros": 0, "xp": 0, "minutos": 0, "materias": defaultdict(int)})
    for r in b.todos("SELECT dia, materia, xp, minutos FROM pomodoros WHERE estado = 'feito' AND dia >= ?", (desde,)):
        d = pom[r["dia"]]
        d["pomodoros"] += 1
        d["xp"] += r["xp"]
        d["minutos"] += r["minutos"]
        d["materias"][r["materia"] or "sem matéria"] += 1
    com = defaultdict(int)
    for r in b.todos("SELECT dia, COUNT(*) FROM commits WHERE dia >= ? GROUP BY dia", (desde,)):
        com[r[0]] = r[1]
    notas = defaultdict(list)
    for r in b.todos("SELECT dia, texto FROM notas WHERE dia >= ? ORDER BY ts", (desde,)):
        notas[r[0]].append(r[1])
    saida = []
    d = data(desde)
    while d.isoformat() <= hoje:
        k = d.isoformat()
        p = pom.get(k)
        saida.append({"dia": k, "pomodoros": p["pomodoros"] if p else 0, "xp_pomodoros": p["xp"] if p else 0,
                      "commits": com.get(k, 0), "materias": dict(p["materias"]) if p else {}, "notas": notas.get(k, [])})
        d += timedelta(days=1)
    return saida


def calor(b, camada: str, desde: str) -> dict[str, int]:
    if camada == "commits":
        rows = b.todos("SELECT dia, COUNT(*) FROM commits WHERE dia >= ? GROUP BY dia", (desde,))
    elif camada == "xp":
        rows = b.todos("SELECT dia, SUM(xp) FROM ganhos WHERE dia >= ? AND xp > 0 GROUP BY dia", (desde,))
    else:
        rows = b.todos("SELECT dia, COUNT(*) FROM pomodoros WHERE estado = 'feito' AND dia >= ? GROUP BY dia", (desde,))
    return {r[0]: int(r[1] or 0) for r in rows}


def materias(b, desde: str) -> list[tuple[str, int]]:
    rows = b.todos("SELECT materia, COUNT(*) n FROM pomodoros WHERE estado = 'feito' AND dia >= ? GROUP BY materia "
                   "ORDER BY n DESC", (desde,))
    return [(r[0] or "sem matéria", r[1]) for r in rows]


def atividade(b, dia: str | None = None, limite: int = 40) -> list:
    if dia:
        return b.todos("SELECT * FROM ganhos WHERE dia = ? ORDER BY ts DESC, id DESC LIMIT ?", (dia, limite))
    return b.todos("SELECT * FROM ganhos ORDER BY ts DESC, id DESC LIMIT ?", (limite,))


# ------------------------------------------------------------ skills, loja, conquistas
def skills_estado(b, cfg, h, classe: str | None = None) -> dict[str, str]:
    """aprendida, disponivel ou bloqueada, para cada skill da classe."""
    classe = classe or h["classe"]
    aprendidas = {r[0] for r in b.todos("SELECT skill FROM skills")} if h and classe == h["classe"] else set()
    sk = cfg["skills"]
    saida = {}
    for sid in cfg.skills_da_classe(classe):
        s = sk[sid]
        if sid in aprendidas:
            saida[sid] = "aprendida"
            continue
        anterior = [k for k in cfg.skills_da_classe(classe) if sk[k]["ramo"] == s["ramo"] and sk[k]["pos"] == s["pos"] - 1]
        if s["pos"] == 0 or (anterior and anterior[0] in aprendidas):
            saida[sid] = "disponivel"
        else:
            saida[sid] = "bloqueada"
    return saida


def custo_skill(s: dict) -> int:
    return 2 if s["pos"] >= 4 else 1


def custo_mana(cfg, s: dict, P) -> int:
    return max(0, regras.arred(s.get("mp", 0) * (1 - P["custo_mana"] / 100)))


def uso_hoje(b, sid: str, dia: str) -> float | None:
    return b.escalar("SELECT em FROM usos WHERE skill = ? AND dia = ?", (sid, dia))


def ativas(b, cfg, h) -> list[str]:
    """As quatro primeiras ativas aprendidas, na ordem da árvore: as teclas 1 a 4 do foco."""
    aprendidas = {r[0] for r in b.todos("SELECT skill FROM skills")}
    return [sid for sid in cfg.skills_da_classe(h["classe"])
            if sid in aprendidas and cfg["skills"][sid]["tipo"] == "ativa"][:4]


def mochila(b) -> dict[str, int]:
    return {r[0]: r[1] for r in b.todos("SELECT item, qtd FROM mochila")}


def posses(b) -> set[str]:
    return {r[0] for r in b.todos("SELECT item FROM posses")}


def conquistas_feitas(b) -> dict[str, float]:
    return {r[0]: r[1] for r in b.todos("SELECT id, em FROM conquistas")}


def progresso_conquista(b, h, c: dict, dia: str) -> int:
    t = c["tipo"]
    if t == "pomodoros":
        return int(b.escalar("SELECT COUNT(*) FROM pomodoros WHERE estado = 'feito'", (), 0))
    if t == "streak":
        return max(streak_atual(h, dia), int(h["melhor_streak"]) if h else 0)
    if t == "commit_vinculado":
        return int(b.escalar("SELECT COUNT(*) FROM commits WHERE vinculado = 1 AND xp > 0", (), 0))
    if t == "arcos":
        return int(b.escalar("SELECT COUNT(*) FROM arcos WHERE bonus_em IS NOT NULL", (), 0))
    return 0


# ------------------------------------------------------------ pastas liberadas para o Mestre
def pastas(b, agora: float) -> list[dict]:
    """As pastas liberadas agora (as de "uma vez" valem até expirar)."""
    return [{"caminho": r["caminho"], "modo": r["modo"], "expira": r["expira"]} for r in
            b.todos("SELECT * FROM pastas WHERE expira IS NULL OR expira > ? ORDER BY caminho", (agora,))]


def caminhos_liberados(b, agora: float) -> list[str]:
    return [p["caminho"] for p in pastas(b, agora)]


def pedidos_pendentes(b) -> list:
    return b.todos("SELECT * FROM pedidos_pasta WHERE estado = 'pendente' ORDER BY id")
