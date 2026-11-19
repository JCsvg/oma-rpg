"""Dados inventados para o --demo, os testes da interface e as capturas: o herói yahiro (Garoto de Programa, nível 7),
os arcos, as quests e os rascunhos do design, 53 semanas de histórico e a conversa da taverna.

Escreve direto num banco temporário (nunca no real) e devolve os argumentos do OmaRpgApp com um ClienteLocal: o motor
roda no mesmo processo, sem serviço, sem socket e sem git. O relógio começa em 18/11/2026 às 10:36:18 (quarta) e anda.
"""

from __future__ import annotations

import json
import random
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

DIA = "2026-11-18"
MATERIAS = [("Compiladores", 34), ("Redes", 22), ("TCC", 18), ("Inglês", 14), ("IC", 9), ("Projetos pessoais", 3)]


def ts(dia: str, h: int, m: int = 0, s: int = 0) -> float:
    a, me, d = (int(x) for x in dia.split("-"))
    return time.mktime((a, me, d, h, m, s, 0, 0, -1))


class RelogioDemo:
    """Começa num instante fixo e anda junto com o relógio de verdade (ou fica parado, nas capturas)."""

    def __init__(self, inicio: float, fixo: bool = False) -> None:
        self.inicio = inicio
        self.fixo = fixo
        self.t0 = time.monotonic()
        self.t = inicio

    def agora(self) -> float:
        return self.t if self.fixo else self.inicio + (time.monotonic() - self.t0)

    def avancar(self, seg: float) -> None:
        if self.fixo:
            self.t += seg
        else:
            self.inicio += seg


def popular(b, cfg, estado: str = "foco") -> float:
    """Preenche o banco. Devolve o instante "agora" do demo."""
    x = b.x
    r = random.Random(7)
    agora = ts(DIA, 10, 36, 18) if estado == "foco" else ts(DIA, 10, 14, 0)
    with b.transacao():
        x("INSERT INTO heroi (id, nome, classe, nivel, xp, xp_total, bits, hp, mp, pontos, seguidos, seguidos_dia, ultimo_fim, "
          "streak, streak_dia, streak_antes, melhor_streak, criado) VALUES (1, 'yahiro', 'programa', 7, 1240, 0, 1284, 72, 34, 2, "
          "3, ?, ?, 12, ?, 11, 31, ?)", (DIA, ts(DIA, 10, 12), DIA, ts("2025-11-10", 9)))
        b.definir_meta("dia", DIA)
        for s in ("git_stash", "hotfix", "sudo", "backup", "dev_null"):
            x("INSERT INTO skills (skill, em, custo) VALUES (?, ?, 1)", (s, ts("2026-10-01", 9)))
        x("INSERT INTO usos (skill, dia, em) VALUES ('sudo', ?, ?)", (DIA, ts(DIA, 8, 52)))
        # arcos, na ordem das cores do design
        arcos = [("Compiladores", "blue", "Prova de Compiladores", "2026-11-26"), ("Redes", "cyan", "Prova de Redes", "2026-11-19"),
                 ("TCC", "magenta", "Entrega do capítulo 2", "2026-11-27"), ("Inglês", "yellow", "", ""),
                 ("IC", "orange", "Relatório parcial", "2026-12-04"), ("Projetos pessoais", "green", "", "")]
        for i, (n, c, ch, dt) in enumerate(arcos, 1):
            x("INSERT INTO arcos (id, nome, cor, chefe, data, criado) VALUES (?,?,?,?,?,?)", (i, n, c, ch, dt, ts("2026-08-01", 9)))
        aid = {n: i for i, (n, *_) in enumerate(arcos, 1)}
        qid = [0]

        def quest(titulo, materia, est, dif, estado_q="aberta", hoje=0, prazo="", tipo="normal", origem="jogador",
                  subtarefas=(), qid_fixo=None, porque="", concluida=None, xp_ganho=0, daily_feita="", criada=None):
            if qid_fixo:
                i = qid_fixo
            else:
                qid[0] += 1
                while qid[0] in (14, 15, 16):
                    qid[0] += 1
                i = qid[0]
            arco = materia if materia in aid else ""
            x("INSERT INTO quests (id, titulo, materia, est, dif, arco_id, arco_nome, prazo, tipo, estado, origem, porque, ordem, "
              "hoje, subtarefas, criada, aprovada, concluida, xp_ganho, daily_feita) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (i, titulo, materia, est, dif, aid.get(arco) if estado_q != "rascunho" else None, arco, prazo, tipo, estado_q, origem,
               porque, i, hoje, json.dumps([{"texto": t, "feita": f} for t, f in subtarefas], ensure_ascii=False),
               criada or ts("2026-11-10", 9), ts("2026-11-10", 9) if estado_q != "rascunho" else None, concluida, xp_ganho,
               daily_feita))
            return i
        # hoje (painel e foco)
        q_lista4 = quest("Lista 4 de Compiladores", "Compiladores", 2, 2, "feita", 1, concluida=ts(DIA, 9, 41), xp_ganho=41)
        q_ler = quest("Ler: inferência de tipos (Hindley-Milner)", "Compiladores", 2, 2, hoje=1, origem="mestre",
                      subtarefas=[("ler o capítulo 4", True), ("refazer o exemplo do let", False), ("resumir em 5 linhas", False)])
        q_redes = quest("Resumo de Redes, cap. 5", "Redes", 2, 1, hoje=1)
        q_tcc = quest("Seção 2 do TCC: trabalhos relacionados", "TCC", 3, 3, hoje=1, prazo="2026-11-20")
        q_ing = quest("Inglês: 20 min de listening", "Inglês", 1, 1, tipo="daily", daily_feita="2026-11-17")
        quest("Revisar flashcards", "Redes", 1, 1, tipo="daily", daily_feita="2026-11-16")
        # o resto do arco de Compiladores
        for t, e, d in (("Implementar o unificador", 3, 3), ("Lista 5 de Compiladores", 2, 2),
                        ("Revisar anotações de análise sintática", 1, 1), ("Simulado da prova", 3, 3)):
            quest(t, "Compiladores", e, d)
        for t, e, d, dia in (("Capítulo 3 do livro", 2, 1, "2026-11-13"), ("Lista 3 de Compiladores", 3, 2, "2026-11-10"),
                             ("Lista 2 de Compiladores", 2, 2, "2026-11-03"), ("Lista 1 de Compiladores", 2, 2, "2026-10-27")):
            quest(t, "Compiladores", e, d, "feita", concluida=ts(dia, 15), xp_ganho=0)
        # rascunhos do Mestre (#14 a #16)
        quest("Seção 2.1 do TCC: modelos de GAN em IDS", "TCC", 3, 3, "rascunho", prazo="2026-11-20", origem="mestre", qid_fixo=14,
              porque="você falou em fechar o capítulo 2 até sexta; esta é a parte mais longa.", criada=ts(DIA, 9, 5))
        quest("Seção 2.2 do TCC: SMOTE e variantes", "TCC", 2, 2, "rascunho", prazo="2026-11-20", origem="mestre", qid_fixo=15,
              porque="reaproveita as notas da semana passada.", criada=ts(DIA, 9, 5))
        quest("Revisão de Redes: camada de transporte", "Redes", 2, 2, "rascunho", prazo="2026-11-19", origem="mestre", qid_fixo=16,
              porque="há prova na quinta; o assunto aparece em 3 listas.", criada=ts(DIA, 9, 5))
        # outros arcos (para o progresso)
        for materia, feitas, total in (("Redes", 3, 10), ("TCC", 2, 11), ("Inglês", 10, 14), ("IC", 4, 9), ("Projetos pessoais", 1, 10)):
            ja = int(b.escalar("SELECT COUNT(*) FROM quests WHERE materia = ? AND tipo = 'normal' AND estado != 'rascunho'", (materia,), 0))
            for k in range(total - ja):
                feita = k < feitas
                quest(f"{materia}: parte {k + 1}", materia, r.choice([1, 2, 2, 3]), r.choice([1, 2, 2, 3]),
                      "feita" if feita else "aberta", concluida=ts("2026-11-0" + str(1 + k % 9), 16) if feita else None)
        # repositórios (de mentira: o demo não roda o vigia)
        for i, (cam, mat) in enumerate((("~/Work/compiladores", "Compiladores"), ("~/Work/tcc", "TCC"), ("~/Projects/oma-rpg", "")), 1):
            x("INSERT INTO repos (id, caminho, nome, materia, registrado) VALUES (?,?,?,?,?)",
              (i, str(Path(cam).expanduser()), Path(cam).name, mat, ts("2026-09-01", 9)))
        # histórico de 53 semanas (pomodoros, commits e o XP de cada dia no livro)
        inicio = date.fromisoformat(DIA) - timedelta(weeks=53)
        pesos = [m for m, p in MATERIAS for _ in range(p)]
        d = inicio
        n_com = 0
        while d.isoformat() < DIA:
            k = d.isoformat()
            util = d.weekday() < 5
            if r.random() < (0.86 if util else 0.45):
                n = max(1, min(11, int(r.gauss(4.6 if util else 2.2, 2.0))))
                hora = 8.5
                xp_dia = 0
                for p in range(n):
                    ini = ts(k, int(hora), int((hora % 1) * 60))
                    cmb = min(1.5, 1 + 0.1 * p)
                    xp = round(24 * cmb)
                    x("INSERT INTO pomodoros (quest_id, materia, inicio, fim, dia, estado, minutos, combo, xp) VALUES "
                      "(NULL, ?, ?, ?, ?, 'feito', 25, ?, ?)", (r.choice(pesos), ini, ini + 1500, k, cmb, xp))
                    xp_dia += xp
                    hora += 0.5 if p % 4 != 3 else 0.75
                    if p == 3:
                        hora += 3.5
                x("INSERT INTO ganhos (ts, dia, origem, texto, xp, bits) VALUES (?, ?, 'pomodoro', 'pomodoros do dia', ?, ?)",
                  (ts(k, 20), k, xp_dia, round(xp_dia / 4)))
                for _ in range(r.choice([0, 0, 1, 1, 2, 3]) if util else 0):
                    n_com += 1
                    hc = ts(k, r.randint(9, 21), r.randint(0, 59))
                    x("INSERT INTO commits (repo_id, hash, ts, dia, assunto, tipo, mais, menos, vinculado, xp) VALUES "
                      "(?,?,?,?,?,?,?,?,?,?)", (r.randint(1, 3), "%040x" % r.getrandbits(160), hc, k,
                                                r.choice(["feat(parser): gramática de let", "fix(redes): checksum do segmento",
                                                          "docs(tcc): seção 1 revisada", "test: casos do lexer"]),
                                                "feat", r.randint(1, 40), r.randint(0, 10), 1, 9))
            d += timedelta(days=1)
        # terça 10/11 do histórico do design: 8 pomodoros, 3 quests e 3 commits
        x("DELETE FROM pomodoros WHERE dia = '2026-11-10'")
        x("DELETE FROM commits WHERE dia = '2026-11-10'")
        for hh, mm, mat in ((8, 40, "Compiladores"), (9, 10, "Compiladores"), (9, 40, "Compiladores"), (10, 15, "Compiladores"),
                            (14, 0, "Redes"), (14, 30, "Redes"), (15, 5, "Redes"), (20, 0, "TCC")):
            ini = ts("2026-11-10", hh, mm)
            x("INSERT INTO pomodoros (quest_id, materia, inicio, fim, dia, estado, minutos, combo, xp) VALUES "
              "(NULL, ?, ?, ?, '2026-11-10', 'feito', 25, 1.3, 27)", (mat, ini, ini + 1500))
        for i, (hh, mm, hsh, msg) in enumerate(((9, 22, "b72e9c1", "feat(parser): gramática de let"),
                                                (10, 31, "2d4f7a8", "fix(redes): checksum do segmento"),
                                                (15, 20, "90ac3e5", "docs(tcc): seção 1 revisada"))):
            x("INSERT INTO commits (repo_id, hash, ts, dia, assunto, tipo, mais, menos, vinculado, xp) VALUES "
              "(?,?,?,'2026-11-10',?,'feat',12,3,1,9)", (1 + i % 3, hsh + "0" * 33, ts("2026-11-10", hh, mm), msg))
        x("UPDATE quests SET concluida = ?, xp_ganho = 61 WHERE titulo = 'Lista 3 de Compiladores'", (ts("2026-11-10", 10, 50),))
        for hh, t_q, xp_q in ((10, "Lista 3 de Compiladores", 61), (15, "Resumo de Redes, cap. 4", 27), (20, "Seção 1 do TCC", 77)):
            x("INSERT INTO ganhos (ts, dia, origem, texto, xp, bits) VALUES (?, '2026-11-10', 'quest', ?, ?, ?)",
              (ts("2026-11-10", hh, 50), f"quest: {t_q}", xp_q, round(xp_q / 4)))
        for t_q, xp_q in (("Resumo de Redes, cap. 4", 27), ("Seção 1 do TCC", 77)):
            x("INSERT INTO quests (titulo, materia, est, dif, arco_id, arco_nome, tipo, estado, origem, criada, concluida, xp_ganho) "
              "VALUES (?,?,2,?,?,?,'normal','feita','jogador',?,?,?)",
              (t_q, t_q.split()[-1] if "Redes" not in t_q else "Redes", 1 if xp_q == 27 else 3,
               aid["Redes" if "Redes" in t_q else "TCC"], "Redes" if "Redes" in t_q else "TCC", ts("2026-11-01", 9),
               ts("2026-11-10", 15 if "Redes" in t_q else 20, 40), xp_q))
        # hoje: pomodoros 1 a 3, a quest, o bônus de arco, o commit e o combo
        x("DELETE FROM pomodoros WHERE dia = ?", (DIA,))
        x("DELETE FROM ganhos WHERE dia = ?", (DIA,))
        x("DELETE FROM commits WHERE dia = ?", (DIA,))
        hoje = [(8, 21, 24, 1.0, q_lista4), (8, 50, 26, 1.1, q_lista4), (9, 47, 29, 1.2, q_ler)]
        for n, (hh, mm, xp, cmb, q) in enumerate(hoje, 1):
            ini = ts(DIA, hh, mm)
            pid = x("INSERT INTO pomodoros (quest_id, materia, inicio, fim, dia, estado, minutos, combo, xp) VALUES "
                    "(?, 'Compiladores', ?, ?, ?, 'feito', 25, ?, ?)", (q, ini, ini + 1500, DIA, cmb, xp)).lastrowid
            x("INSERT INTO ganhos (ts, dia, origem, ref, texto, xp, bits) VALUES (?,?,?,?,?,?,?)",
              (ini + 1500, DIA, "pomodoro", pid, f"pomodoro {n} concluído", xp, round(xp / 4)))
        livro = [(ts(DIA, 8, 40), "inicio_dia", "dia começou: meta de 6", 0, 0, 0),
                 (ts(DIA, 9, 40), "arco", "bônus de arco", 0, 15, 0),
                 (ts(DIA, 9, 41), "quest", "quest: Lista 4 de Compiladores", 41, 10, 0),
                 (ts(DIA, 10, 12, 1), "combo", "combo subiu para x1.3", 0, 0, 0),
                 (ts("2026-11-16", 21), "conquista", "conquista: 10 dias seguidos", 100, 25, 0),
                 (ts("2026-11-17", 23, 59, 59), "daily", "daily vencida: Inglês", 0, 0, -8),
                 (ts("2026-11-17", 16, 20), "nivel", "nível 7 alcançado", 0, 25, 10)]
        for t_, o, txt, xp, bits, hp in livro:
            x("INSERT INTO ganhos (ts, dia, origem, texto, xp, bits, hp) VALUES (?,?,?,?,?,?,?)",
              (t_, time.strftime("%Y-%m-%d", time.localtime(t_)), o, txt, xp, bits, hp))
        commits_hoje = [(ts(DIA, 9, 20), 3, "5d1e0b2", "feat: atalho de debug no foco", 4, 0, 0, 1),
                        (ts(DIA, 10, 9), 1, "a3f9c1e", "feat(tipos): unificação de variáveis livres", 4, 1, 1, 9)]
        if estado == "foco":
            ini4 = ts(DIA, 10, 30)
            commits_hoje += [(ini4 + 60, 1, "e82b7d0", "test: casos de let-polimorfismo", 2, 0, 1, 6),
                             (ini4 + 200, 1, "7c1d4aa", "chore: formata o módulo de tipos", 1, 1, 1, 0)]
        for t_, repo, hsh, msg, mais, menos, vinc, xp in commits_hoje:
            x("INSERT INTO commits (repo_id, hash, ts, dia, assunto, tipo, mais, menos, vinculado, pomodoro_inicio, xp, motivo) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              (repo, hsh.ljust(40, "0"), t_, DIA, msg, "chore" if msg.startswith("chore") else "feat", mais, menos, vinc,
               (ts(DIA, 10, 30) if t_ > ts(DIA, 10, 30) else ts(DIA, 9, 47)) if vinc else None, xp,
               "" if xp else "tipo chore não conta"))
            if xp:
                x("INSERT INTO ganhos (ts, dia, origem, texto, xp, bits) VALUES (?,?,?,?,?,?)",
                  (t_, DIA, "commit", f"{hsh[:7]} {msg.split(':')[0]}", xp, round(xp / 4)))
        x("INSERT INTO notas (ts, dia, quest_id, texto) VALUES (?,?,?,?)",
          (ts(DIA, 10, 33), DIA, q_ler, "conferir a regra de generalização no let"))
        x("INSERT INTO notas (ts, dia, quest_id, texto) VALUES (?,?,?,?)",
          (ts(DIA, 10, 35), DIA, q_ler, "exemplo do capítulo 3 não fecha com a prova do slide"))
        # o relógio: pausa curta depois do 3º pomodoro, ou o 4º pomodoro rodando há 6:18
        if estado == "foco":
            x("UPDATE atual SET fase = 'foco', quest_id = ?, inicio = ?, duracao = 1500, n = 3 WHERE id = 1", (q_ler, ts(DIA, 10, 30)))
        else:
            x("UPDATE atual SET fase = 'pausa', quest_id = ?, inicio = ?, duracao = 300, n = 3 WHERE id = 1", (q_ler, ts(DIA, 10, 12)))
        x("UPDATE quests SET ordem = CASE id WHEN ? THEN 1 WHEN ? THEN 2 WHEN ? THEN 3 WHEN ? THEN 4 ELSE ordem + 10 END",
          (q_ler, q_redes, q_tcc, q_ing))
        # mochila, posses e conquistas
        for item, qtd in (("pocao_hp", 2), ("cafe", 1), ("congelar", 0), ("bilhete", 1)):
            x("INSERT INTO mochila (item, qtd) VALUES (?, ?)", (item, qtd))
        for item in ("tema_verde", "titulo_cafe"):
            x("INSERT INTO posses (item, em) VALUES (?, ?)", (item, ts("2026-10-01", 9)))
        for cid, dia in (("primeiro_pomodoro", "2025-11-12"), ("streak_3", "2025-11-14"), ("streak_7", "2025-11-20"),
                         ("pomodoros_100", "2026-01-10"), ("pomodoros_500", "2026-05-02"), ("pomodoros_1000", "2026-10-20"),
                         ("commit_ci", "2026-11-12"), ("streak_10", "2026-11-16")):
            x("INSERT INTO conquistas (id, em) VALUES (?, ?)", (cid, ts(dia, 21)))
        # taverna
        conversa = [
            ("voce", "preciso fechar a seção 2 do TCC até sexta e estudar Redes para a prova de quinta", ""),
            ("mestre", "Entendido. Hoje é quarta: sobram 3 pomodoros hoje e 6 amanhã. Vou olhar o seu estado e montar um backlog enxuto.", ""),
            ("cli", "oma-rpg status --json", "hp 72/100 · 3 pomodoros restantes hoje · prova de Redes em qui 19/11"),
            ("cli", "oma-rpg quests --arco TCC --json", "2 quests feitas, 9 abertas, seção 2 sem estimativa"),
            ("cli", 'oma-rpg draft --titulo "Seção 2.1 do TCC" --est 3 --dif 3 --json', "rascunho #14 criado"),
            ("cli", 'oma-rpg draft --titulo "Seção 2.2 do TCC" --est 2 --dif 2 --json', "rascunho #15 criado"),
            ("cli", 'oma-rpg draft --titulo "Revisão de Redes: transporte" --est 2 --dif 2 --json', "rascunho #16 criado"),
            ("mestre", "Criei 3 rascunhos. O XP deles vem da tabela do jogo, não de mim. A seção 2.1 é a mais longa: sugiro o "
                       "primeiro bloco de amanhã. Quer que eu mexa em alguma estimativa?", ""),
            ("voce", "deixa a 2.2 para sábado e adiciona uma revisão de flashcards de Redes de manhã", ""),
        ]
        for n, (papel, txt, extra) in enumerate(conversa):
            x("INSERT INTO taverna (ts, papel, texto, extra) VALUES (?,?,?,?)",
              (ts(DIA, 9, 0, n), papel, txt, json.dumps({"resultado": extra}, ensure_ascii=False) if extra else ""))
        x("INSERT INTO taverna (ts, papel, texto) VALUES (?, 'mestre', ?)",
          (ts("2026-11-18", 9, 1), "Sua semana está pesada: prova de Redes na quinta e o prazo da seção 2 do TCC na sexta. "
                                   "Sugeri quebrar o TCC em 3 sessões."))
        x("UPDATE taverna SET id = id")  # (ordem por id)
    # o último texto do Mestre na conversa fica por último
    ultimo = b.um("SELECT id FROM taverna WHERE texto LIKE 'Sua semana%'")[0]
    b.x("UPDATE taverna SET ts = ? WHERE id = ?", (ts(DIA, 8, 59), ultimo))
    b.x("UPDATE heroi SET xp_total = (SELECT SUM(xp) FROM ganhos) WHERE id = 1")
    return agora


def montar_demo(pasta: Path | None = None, fixo: bool = False, estado: str = "foco") -> dict:
    """Banco temporário com os dados do design e os argumentos do OmaRpgApp (cliente local, sem serviço)."""
    from oma_rpg.cliente import ClienteLocal
    from oma_rpg.config import Config
    from oma_rpg.mestre import MestreFalso
    from oma_rpg.nucleo.banco import Banco
    from oma_rpg.nucleo.jogo import Jogo
    from oma_rpg.ui.estado import Estado
    pasta = Path(pasta) if pasta else Path(tempfile.mkdtemp(prefix="oma-rpg-demo-"))
    pasta.mkdir(parents=True, exist_ok=True)
    cfg = Config.carregar(usar_usuario=False)
    escrita = Banco(pasta / "rpg.sqlite3")
    agora = popular(escrita, cfg, estado)
    rel = RelogioDemo(agora, fixo=fixo)
    jogo = Jogo(escrita, cfg, rel, random.Random(5))
    cliente = ClienteLocal(jogo)
    leitura = Banco(pasta / "rpg.sqlite3", leitura=True)
    estado_ui = Estado(pasta / "estado")
    estado_ui.dados = {"hist_dia": "2026-11-10"}  # a terça do design
    estado_ui.salvar()
    return {"cliente": cliente, "banco": leitura, "cfg": cfg, "relogio": rel, "estado": estado_ui,
            "demo": True, "mestre": MestreFalso(cliente)}
