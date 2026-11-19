"""O motor do jogo: regras com estado, em cima do banco. Roda dentro do serviço (ou do --demo e dos testes).

Toda mudança de XP, Bits, HP e MP passa por `_ganho`, que grava uma linha no livro `ganhos` com a origem. XP positivo
só aceita as origens de ORIGENS_XP, e todas elas nascem de um pomodoro concluído no relógio do motor ou de um commit
visto no git: a quest só libera XP proporcional aos pomodoros feitos nela, o chefe do arco soma o XP dessas quests e
a conquista conta pomodoros, streak e commits. Nenhum método público recebe valor de XP, Bits, HP, nível ou pontos.

Quem pode chamar cada método é decidido em `comandos.py` (papéis Mestre e jogador). `tick` e `observar_commit` não
são comandos: só o laço do serviço chama.
"""

from __future__ import annotations

import json
import random
import re
import time
from datetime import date, timedelta

from oma_rpg.nucleo import consultas as C
from oma_rpg.nucleo import regras

ORIGENS_XP = frozenset({"pomodoro", "commit", "quest", "arco", "conquista"})
ORIGENS_BITS_POSITIVOS = ORIGENS_XP | {"nivel", "juros", "caixa"}
FECHA_QUEST = re.compile(r"\b(?:closes?|fecha|conclui)\s+quest-(\d+)\b", re.I)
CORES_ARCO = ["blue", "cyan", "magenta", "yellow", "orange", "green", "red"]
_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")


class ErroJogo(Exception):
    """Erro que vai para a tela como está (texto curto, em português)."""


class Relogio:
    def agora(self) -> float:
        return time.time()


class RelogioFalso:
    """Relógio dos testes e das capturas: anda só quando mandam."""

    def __init__(self, t: float) -> None:
        self.t = float(t)

    def agora(self) -> float:
        return self.t

    def avancar(self, seg: float) -> None:
        self.t += seg


def texto(v, nome: str, maximo: int, obrigatorio: bool = False) -> str:
    if v is None:
        v = ""
    if not isinstance(v, str):
        raise ErroJogo(f"{nome}: precisa ser texto")
    v = _CONTROLE.sub(" ", v).strip()
    if obrigatorio and not v:
        raise ErroJogo(f"{nome}: não pode ficar vazio")
    if len(v) > maximo:
        raise ErroJogo(f"{nome}: no máximo {maximo} caracteres")
    return v


def inteiro(v, nome: str, mini: int, maxi: int) -> int:
    if isinstance(v, bool):
        raise ErroJogo(f"{nome}: precisa ser número")
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ErroJogo(f"{nome}: precisa ser número") from None
    if isinstance(v, float) and not v.is_integer():
        raise ErroJogo(f"{nome}: precisa ser número inteiro")
    if not mini <= n <= maxi:
        raise ErroJogo(f"{nome}: de {mini} a {maxi}")
    return n


def data_valida(v, nome: str = "prazo") -> str:
    v = texto(v, nome, 10)
    if not v:
        return ""
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        raise ErroJogo(f"{nome}: use AAAA-MM-DD") from None


DIF_NOMES = {"1": 1, "2": 2, "3": 3, "facil": 1, "fácil": 1, "media": 2, "média": 2, "dificil": 3, "difícil": 3}


def dificuldade(v) -> int:
    if isinstance(v, str) and v.strip().lower() in DIF_NOMES:
        return DIF_NOMES[v.strip().lower()]
    return inteiro(v, "dificuldade", 1, 3)


class Jogo:
    def __init__(self, banco, cfg, relogio=None, aleatorio: random.Random | None = None) -> None:
        self.b = banco
        self.cfg = cfg
        self.rel = relogio or Relogio()
        self.rng = aleatorio or random.Random()
        self.ouvintes: list = []
        self.notificar = lambda titulo, corpo: None
        self._eventos: list[dict] = []

    # ------------------------------------------------------------ básico
    def agora(self) -> float:
        return self.rel.agora()

    def hoje(self) -> str:
        return C.dia_de(self.agora())

    def emitir(self, ev: dict) -> None:
        self._eventos.append(ev)

    def soltar_eventos(self) -> list[dict]:
        """O serviço chama depois de cada comando ou tick e repassa para os clientes."""
        evs, self._eventos = self._eventos, []
        if evs:
            evs.append({"evento": "mudou"})
        for ev in evs:
            for f in list(self.ouvintes):
                try:
                    f(ev)
                except Exception:
                    pass
        return evs

    def heroi(self):
        return C.heroi(self.b)

    def _h(self):
        h = C.heroi(self.b)
        if h is None:
            raise ErroJogo("crie o herói primeiro")
        return h

    def atual(self):
        return C.atual(self.b)

    def P(self, h=None):
        return C.passivos(self.b, self.cfg, self.hoje(), h)

    def _cfg(self, secao: str, chave: str):
        return self.cfg[secao][chave]

    # ------------------------------------------------------------ o livro (única mudança de recursos)
    def _ganho(self, origem: str, texto_: str, xp: int = 0, bits: int = 0, hp: int = 0, mp: int = 0,
               ref: int | None = None, ts: float | None = None) -> dict:
        if xp < 0:
            raise ValueError("xp não diminui")
        if xp > 0 and origem not in ORIGENS_XP:
            raise PermissionError(f"origem sem direito a XP: {origem}")
        if bits > 0 and origem not in ORIGENS_BITS_POSITIVOS:
            raise PermissionError(f"origem sem direito a Bits: {origem}")
        ts = self.agora() if ts is None else ts
        h = self._h()
        P = C.passivos(self.b, self.cfg, C.dia_de(ts), h)
        hpm, mpm = C.hp_max(self.cfg, h, P), C.mp_max(self.cfg, h, P)
        novo_hp = max(0, min(hpm, h["hp"] + hp))
        novo_mp = max(0, min(mpm, h["mp"] + mp))
        novo_bits = max(0, h["bits"] + bits)
        dh, dm, db = novo_hp - h["hp"], novo_mp - h["mp"], novo_bits - h["bits"]
        with self.b.transacao():
            self.b.x("UPDATE heroi SET xp = xp + ?, xp_total = xp_total + ?, bits = ?, hp = ?, mp = ? WHERE id = 1",
                     (xp, xp, novo_bits, novo_hp, novo_mp))
            self.b.x("INSERT INTO ganhos (ts, dia, origem, ref, texto, xp, bits, hp, mp) VALUES (?,?,?,?,?,?,?,?,?)",
                     (ts, C.dia_de(ts), origem, ref, texto_[:200], xp, db, dh, dm))
        if xp > 0:
            self._verificar_nivel(ts)
        if dh < 0 and novo_hp == 0 and self.atual()["fase"] != "desmaio":
            self._desmaiar(ts)
        return {"xp": xp, "bits": db, "hp": dh, "mp": dm}

    def _registro(self, origem: str, texto_: str, ts: float | None = None) -> None:
        """Linha só de atividade, sem mexer em nada (combo subiu, dia começou)."""
        ts = self.agora() if ts is None else ts
        self.b.x("INSERT INTO ganhos (ts, dia, origem, texto) VALUES (?,?,?,?)", (ts, C.dia_de(ts), origem, texto_[:200]))

    def _consumir(self, tipo: str) -> float:
        v = C.efeito(self.b, tipo)
        self.b.x("DELETE FROM efeitos WHERE tipo = ?", (tipo,))
        return v

    def _efeito(self, tipo: str, valor: float, origem: str) -> None:
        self.b.x("INSERT INTO efeitos (tipo, valor, origem, criado) VALUES (?,?,?,?)", (tipo, valor, origem, self.agora()))

    # ------------------------------------------------------------ herói
    def criar_heroi(self, nome, classe) -> dict:
        nome = texto(nome, "nome", 24, obrigatorio=True)
        if classe not in self.cfg["classes"]:
            raise ErroJogo("classe desconhecida")
        if self.heroi() is not None:
            raise ErroJogo("o herói já existe")
        cls = self.cfg["classes"][classe]
        agora = self.agora()
        with self.b.transacao():
            self.b.x("INSERT INTO heroi (id, nome, classe, hp, mp, criado) VALUES (1, ?, ?, ?, ?, ?)",
                     (nome, classe, cls["hp"], cls["mp"], agora))
            self.b.x("INSERT OR IGNORE INTO posses (item, em) VALUES ('tema_verde', ?)", (agora,))
            self.b.definir_meta("dia", self.hoje())
        self._registro("heroi", f"{nome} entrou como {cls['nome']}")
        self.emitir({"evento": "heroi"})
        return {"nome": nome, "classe": classe}

    def trocar_classe(self, classe) -> dict:
        h = self._h()
        if classe not in self.cfg["classes"]:
            raise ErroJogo("classe desconhecida")
        if classe == h["classe"]:
            raise ErroJogo("essa já é a sua classe")
        custo = self._cfg("loja", "trocar_classe_bits")
        if h["bits"] < custo:
            raise ErroJogo(f"faltam {custo - h['bits']} bits")
        perdidos = int(self.b.escalar("SELECT SUM(custo) FROM skills", (), 0))
        with self.b.transacao():
            self.b.x("DELETE FROM skills")
            self.b.x("DELETE FROM efeitos")
            self.b.x("UPDATE heroi SET classe = ? WHERE id = 1", (classe,))
            if custo:
                self._ganho("classe", "troca de classe", bits=-custo)
            self._ganho("classe", f"agora {self.cfg['classes'][classe]['nome']}")  # reajusta HP e MP ao máximo novo
        self.emitir({"evento": "classe", "classe": classe, "pontos_perdidos": perdidos})
        return {"classe": classe, "pontos_perdidos": perdidos}

    def konami(self) -> dict:
        h = self._h()
        if h["konami"]:
            return {"novo": False}
        self.b.x("UPDATE heroi SET konami = 1, titulo = 'Jogador 1' WHERE id = 1")
        self._registro("titulo", "título destravado: Jogador 1")
        self.emitir({"evento": "titulo", "titulo": "Jogador 1"})
        return {"novo": True, "titulo": "Jogador 1"}

    # ------------------------------------------------------------ nível, desmaio, streak, conquistas
    def _verificar_nivel(self, ts: float) -> None:
        while True:
            h = self._h()
            precisa = regras.xp_nivel(h["nivel"], self.cfg)
            if h["xp"] < precisa:
                return
            antes = C.titulo_classe(self.cfg, h)
            novo = h["nivel"] + 1
            self.b.x("UPDATE heroi SET nivel = ?, xp = xp - ?, pontos = pontos + ? WHERE id = 1",
                     (novo, precisa, self._cfg("heroi", "pontos_nivel")))
            hd = self.cfg["heroi"]
            self._ganho("nivel", f"nível {novo} alcançado", bits=hd["bits_nivel"], hp=hd["hp_nivel"], ts=ts)
            depois = C.titulo_classe(self.cfg, self._h())
            self.emitir({"evento": "nivel", "nivel": novo, "titulo": depois if depois != antes else "",
                         "pontos": hd["pontos_nivel"], "hp": hd["hp_nivel"], "bits": hd["bits_nivel"]})
            self.notificar(f"Nível {novo}", f"+1 ponto de skill · +{hd['hp_nivel']} de HP · +{hd['bits_nivel']} bits")

    def _perder_hp(self, valor: int, origem: str, texto_: str, ts: float | None = None) -> int:
        valor = int(valor)
        if valor <= 0:
            return 0
        if C.tem_efeito(self.b, "escudo"):
            self._consumir("escudo")
            self._registro("escudo", f"escudo segurou: {texto_}", ts)
            self.emitir({"evento": "escudo", "texto": texto_})
            return 0
        r = self._ganho(origem, texto_, hp=-valor, ts=ts)
        if r["hp"] < 0:
            self.b.x("UPDATE heroi SET ultima_perda = ? WHERE id = 1", (-r["hp"],))
        return -r["hp"]

    def _desmaiar(self, ts: float) -> None:
        h = self._h()
        a = self.atual()
        if a["fase"] == "foco":
            self._registrar_pomodoro(a, ts, "abandonado")
        perda = regras.arred(h["bits"] * self._cfg("heroi", "desmaio_bits_pct") / 100)
        dia = C.dia_de(ts)
        P = C.passivos(self.b, self.cfg, dia, h)
        guardou = P["backup"] > 0
        streak = (h["streak_antes"] if h["streak_dia"] == dia else C.streak_atual(h, dia)) if guardou else 0
        longa = self._cfg("pomodoro", "minutos_pausa_longa") * 60
        with self.b.transacao():
            self.b.x("UPDATE atual SET fase = 'desmaio', inicio = ?, duracao = ?, pausado_em = NULL WHERE id = 1", (ts, longa))
            self.b.x("UPDATE heroi SET streak = ?, streak_dia = ?, seguidos = 0 WHERE id = 1", (streak, dia))
            self.b.x("DELETE FROM efeitos WHERE tipo IN ('proximo_xp', 'arriscar', 'commit_mais')")
        if perda:
            self._ganho("desmaio", "desmaio: 10% dos bits", bits=-perda, ts=ts)
        self.emitir({"evento": "desmaio", "bits": perda, "backup": guardou, "streak": streak})
        self.notificar("Você desmaiou", "o HP chegou a 0; acorda com 50% depois de uma pausa longa")

    def acordar(self) -> dict:
        a = self.atual()
        if a["fase"] != "desmaio":
            raise ErroJogo("você não está desmaiado")
        falta = C.restante(a, self.agora())
        if falta > 0:
            raise ErroJogo(f"ainda falta {C.mmss(falta)} da pausa longa")
        self._acordar(self.agora())
        return {}

    def _acordar(self, ts: float) -> None:
        h = self._h()
        P = self.P(h)
        alvo = regras.arred(C.hp_max(self.cfg, h, P) * self._cfg("heroi", "desmaio_volta_pct") / 100)
        self.b.x("UPDATE atual SET fase = 'parado', inicio = 0, duracao = 0, n = 0 WHERE id = 1")
        self._ganho("acordar", "acordou depois da pausa longa", hp=max(0, alvo - h["hp"]), ts=ts)
        self.emitir({"evento": "acordou"})

    def _contar_streak(self, dia: str) -> None:
        h = self._h()
        if C.feitos_dia(self.b, dia) < self._cfg("heroi", "streak_minimo") or h["streak_dia"] == dia:
            return
        antes = h["streak"] if h["streak_dia"] == C.ontem(dia) else 0
        novo = antes + 1
        self.b.x("UPDATE heroi SET streak = ?, streak_antes = ?, streak_dia = ?, melhor_streak = MAX(melhor_streak, ?) "
                 "WHERE id = 1", (novo, antes, dia, novo))

    def _verificar_conquistas(self, ts: float) -> None:
        h = self._h()
        feitas = C.conquistas_feitas(self.b)
        dia = C.dia_de(ts)
        for cid, c in sorted(self.cfg["conquistas"].items(), key=lambda x: x[1]["ordem"]):
            if cid in feitas or C.progresso_conquista(self.b, h, c, dia) < c["alvo"]:
                continue
            self.b.x("INSERT OR IGNORE INTO conquistas (id, em) VALUES (?, ?)", (cid, ts))
            xp = int(c["xp"])
            self._ganho("conquista", f"conquista: {c['nome']}", xp=xp, bits=regras.bits_de(xp, self.cfg), ts=ts)
            self.emitir({"evento": "conquista", "nome": c["nome"], "xp": xp})

    # ------------------------------------------------------------ dia
    def _fim_do_dia(self, dia: str) -> None:
        ts = C.fim_do_dia(dia)
        h = self._h()
        P = C.passivos(self.b, self.cfg, dia, h)
        hd = self.cfg["heroi"]
        # dailies vencidas
        mult = P["daily_mult"] or 1.0
        custo = regras.arred(hd["daily_hp"] * max(0.0, 1 - P["daily_hp"] / 100) * mult)
        for q in self.b.todos("SELECT * FROM quests WHERE tipo = 'daily' AND estado = 'aberta' AND criada <= ?", (ts,)):
            if q["daily_feita"] == dia or q["daily_livre"] == dia:
                continue
            self._perder_hp(custo, "daily", f"daily vencida: {q['titulo']}", ts=ts)
            if self.atual()["fase"] == "desmaio":
                break
        # juros do Empreendedor
        h = self._h()
        if h["classe"] == "empreendedor" and C.feitos_dia(self.b, dia) >= self._cfg("pomodoro", "meta_diaria"):
            cl = self.cfg["classes"]
            pct = self._cfg("mecanicas", "juros_pct") + P["juros"]
            maximo = self._cfg("mecanicas", "juros_max") + P["juros_max"]
            juros = min(int(maximo), regras.arred(h["bits"] * pct / 100))
            if juros > 0:
                self._ganho("juros", f"juros da carteira ({cl['empreendedor']['nome']})", bits=juros, ts=ts)
        # streak: dia sem pomodoro quebra, a não ser que haja um Congelar streak ativo
        h = self._h()
        if h["streak_dia"] and h["streak_dia"] < dia and h["streak"] > 0:
            if C.tem_efeito(self.b, "congelar"):
                self.b.x("DELETE FROM efeitos WHERE id = (SELECT id FROM efeitos WHERE tipo = 'congelar' LIMIT 1)")
                self.b.x("UPDATE heroi SET streak_dia = ? WHERE id = 1", (dia,))
                self._registro("streak", "streak congelado: o dia sem pomodoro não quebrou", ts)
            else:
                self.b.x("UPDATE heroi SET streak = 0 WHERE id = 1")
        # dormir cura um pouco
        cura = int(hd["hp_por_dia"] + P["hp_dia"])
        if cura > 0 and self.atual()["fase"] != "desmaio":
            self._ganho("dia", "a noite de sono curou", hp=cura, ts=ts)

    # ------------------------------------------------------------ pomodoro
    def _quest_aberta(self, qid):
        q = self.b.um("SELECT * FROM quests WHERE id = ?", (qid,))
        if q is None or q["estado"] != "aberta":
            raise ErroJogo("quest não encontrada ou já fechada")
        return q

    def _quest_desbloqueada(self, q) -> None:
        deps = C.depende_de(q)
        if not deps:
            return
        ph = ",".join("?" for _ in deps)
        feitas = {int(r[0]) for r in self.b.todos(f"SELECT id FROM quests WHERE id IN ({ph}) AND estado = 'feita'", deps)}
        faltam = [f"#{d}" for d in deps if d not in feitas]
        if faltam:
            raise ErroJogo(f"quest bloqueada: conclua {', '.join(faltam)} antes")

    def iniciar(self, quest_id=None) -> dict:
        h = self._h()
        a = self.atual()
        agora = self.agora()
        if a["fase"] == "desmaio":
            raise ErroJogo("você desmaiou: acorda depois da pausa longa")
        if a["fase"] == "foco":
            raise ErroJogo("já tem um pomodoro rodando")
        pulou = a["fase"] in ("pausa", "longa") and C.restante(a, agora) > 0
        qid = None
        if quest_id not in (None, ""):
            q = self._quest_aberta(inteiro(quest_id, "quest", 1, 10**9))
            self._quest_desbloqueada(q)
            qid = q["id"]
        retomar = a["guardado_quest"] is not None or a["guardado_seg"] > 0
        if retomar and (qid is None or qid == a["guardado_quest"]):
            qid = a["guardado_quest"]
            inicio = agora - a["guardado_seg"]
        else:
            retomar = False
            inicio = agora
            if qid is None:
                f = C.fila(self.b, self.cfg, self.hoje())
                qid = f[0]["id"] if f else None
        if qid is not None and self.b.um("SELECT 1 FROM quests WHERE id = ? AND estado = 'aberta'", (qid,)) is None:
            qid = None
        n = 0 if a["fase"] == "longa" else a["n"]
        dia = self.hoje()
        if not self.b.um("SELECT 1 FROM ganhos WHERE dia = ? AND origem = 'inicio_dia'", (dia,)):
            self._registro("inicio_dia", f"dia começou: meta de {self._cfg('pomodoro', 'meta_diaria')}", agora)
        with self.b.transacao():
            self.b.x("UPDATE atual SET fase = 'foco', quest_id = ?, inicio = ?, duracao = ?, pausado_em = NULL, n = ?, "
                     "avisou = 0, guardado_quest = CASE WHEN ? THEN NULL ELSE guardado_quest END, "
                     "guardado_seg = CASE WHEN ? THEN 0 ELSE guardado_seg END WHERE id = 1",
                     (qid, inicio, self._cfg("pomodoro", "minutos_foco") * 60, n, retomar, retomar))
        self.emitir({"evento": "pomodoro", "fase": "foco", "retomou": retomar, "pulou_pausa": pulou})
        return {"quest_id": qid, "retomou": retomar, "pulou_pausa": pulou}

    def pausar(self) -> dict:
        a = self.atual()
        if a["fase"] != "foco":
            raise ErroJogo("nenhum pomodoro rodando")
        agora = self.agora()
        if a["pausado_em"]:
            self.b.x("UPDATE atual SET inicio = inicio + ?, pausado_em = NULL WHERE id = 1", (agora - a["pausado_em"],))
            pausado = False
        else:
            self.b.x("UPDATE atual SET pausado_em = ? WHERE id = 1", (agora,))
            pausado = True
        self.emitir({"evento": "pomodoro", "fase": "foco", "pausado": pausado})
        return {"pausado": pausado}

    def _registrar_pomodoro(self, a, fim: float, estado: str, combo: float = 1.0, xp: int = 0) -> int:
        q = self.b.um("SELECT materia FROM quests WHERE id = ?", (a["quest_id"],)) if a["quest_id"] else None
        minutos = round(max(0.0, (a["pausado_em"] or fim) - a["inicio"]) / 60, 2)
        cur = self.b.x("INSERT INTO pomodoros (quest_id, materia, inicio, fim, dia, estado, minutos, combo, xp) "
                       "VALUES (?,?,?,?,?,?,?,?,?)",
                       (a["quest_id"], q["materia"] if q else "", a["inicio"], fim, C.dia_de(fim), estado, minutos, combo, xp))
        return cur.lastrowid

    def abandonar(self) -> dict:
        h = self._h()
        a = self.atual()
        if a["fase"] != "foco":
            raise ErroJogo("nenhum pomodoro rodando")
        agora = self.agora()
        dec = C.decorrido(a, agora)
        pc = self.cfg["pomodoro"]
        livre = dec < pc["abandono_livre_min"] * 60
        P = self.P(h)
        custo = 0
        if not livre:
            mult = (2.0 if C.tem_efeito(self.b, "arriscar") else 1.0) * (P["abandono_mult"] or 1.0)
            custo = regras.arred(pc["abandono_hp"] * max(0.0, 1 - P["abandono_hp"] / 100) * mult)
        with self.b.transacao():
            self._registrar_pomodoro(a, agora, "abandonado")
            self.b.x("UPDATE atual SET fase = 'parado', inicio = 0, duracao = 0, pausado_em = NULL WHERE id = 1")
            self.b.x("DELETE FROM efeitos WHERE tipo IN ('arriscar', 'commit_mais')")
            if not livre:
                self.b.x("UPDATE heroi SET seguidos = 0 WHERE id = 1")
                self.b.x("DELETE FROM efeitos WHERE tipo = 'proximo_xp'")
        perdeu = self._perder_hp(custo, "abandono", f"pomodoro abandonado aos {int(dec // 60)} min") if custo else 0
        self.emitir({"evento": "abandono", "hp": perdeu, "livre": livre})
        return {"hp": perdeu, "livre": livre, "minutos": int(dec // 60)}

    def _guardar(self, auto: bool = False) -> dict:
        a = self.atual()
        if a["fase"] != "foco":
            raise ErroJogo("nenhum pomodoro rodando para guardar")
        dec = C.decorrido(a, self.agora())
        self.b.x("UPDATE atual SET fase = 'parado', guardado_quest = ?, guardado_seg = ?, inicio = 0, duracao = 0, "
                 "pausado_em = NULL WHERE id = 1", (a["quest_id"], dec))
        self.emitir({"evento": "guardado", "auto": auto, "minutos": int(dec // 60)})
        return {"guardado": True, "minutos": int(dec // 60)}

    def pular_pausa(self) -> dict:
        a = self.atual()
        if a["fase"] not in ("pausa", "longa"):
            raise ErroJogo("nenhuma pausa em andamento")
        self.b.x("UPDATE atual SET fase = 'parado', inicio = 0, duracao = 0, n = CASE WHEN fase = 'longa' THEN 0 ELSE n END "
                 "WHERE id = 1")
        self.emitir({"evento": "pausa_fim", "respeitada": False})
        return {"mana": 0}

    def tick(self) -> None:
        """Tudo que depende do relógio, na ordem em que aconteceu: fim do pomodoro, fim da pausa, acordar, virada do
        dia e o aviso de 1 minuto. Com o serviço parado por horas, um pomodoro que acabou ontem conta para ontem
        antes da virada do dia."""
        if self.heroi() is None:
            return
        agora = self.agora()
        hoje = C.dia_de(agora)
        ultimo = self.b.meta("dia") or hoje
        limite = (C.data(hoje) - timedelta(days=60)).isoformat()
        if ultimo < limite:  # serviço parado por mais de 60 dias: processa só os últimos 60
            ultimo = limite
            self.b.definir_meta("dia", ultimo)
        for _ in range(200):
            a = self.atual()
            ultimo = self.b.meta("dia") or hoje
            evs = []
            virada = C.inicio_do_dia(C.amanha(ultimo))
            if virada <= agora:
                evs.append((virada, 1, "dia"))
            fim = a["inicio"] + a["duracao"]
            if a["fase"] == "foco":
                if a["pausado_em"]:
                    limite_pausa = a["pausado_em"] + self._cfg("pomodoro", "max_pausado_min") * 60
                    if limite_pausa <= agora:
                        evs.append((limite_pausa, 0, "guardar"))
                elif fim <= agora:
                    evs.append((fim, 0, "foco"))
            elif a["fase"] in ("pausa", "longa", "desmaio") and fim <= agora:
                evs.append((fim, 0, a["fase"]))
            if not evs:
                break
            t, _, tipo = min(evs)
            if tipo == "dia":
                self._fim_do_dia(ultimo)
                self.b.definir_meta("dia", C.amanha(ultimo))
                self.emitir({"evento": "dia", "dia": C.amanha(ultimo)})
            elif tipo == "foco":
                self._concluir_pomodoro(t)
            elif tipo == "guardar":
                self._guardar(auto=True)
            elif tipo == "desmaio":
                self._acordar(t)
            else:
                self._fim_pausa(t, tipo)
        a = self.atual()
        if a["fase"] == "foco" and not a["pausado_em"] and not a["avisou"]:
            falta = a["inicio"] + a["duracao"] - agora
            if 0 < falta <= 60 and "despertador" in C.posses(self.b):
                self.b.x("UPDATE atual SET avisou = 1 WHERE id = 1")
                self.notificar("Falta 1 minuto", "feche o raciocínio")

    def proxima_espera(self, maximo: float = 60.0) -> float:
        """Segundos até o próximo evento de relógio (para o serviço dormir o resto)."""
        agora = self.agora()
        a = self.atual()
        espera = maximo
        if a is not None and a["fase"] in C.FASES_RODANDO and not a["pausado_em"]:
            espera = min(espera, max(0.05, C.restante(a, agora)))
            if a["fase"] == "foco" and not a["avisou"]:
                falta = C.restante(a, agora) - 60
                if falta > 0:
                    espera = min(espera, falta)
        elif a is not None and a["pausado_em"]:
            espera = min(espera, 30.0)
        meia_noite = C.inicio_do_dia(C.amanha(C.dia_de(agora))) - agora
        return max(0.05, min(espera, meia_noite + 0.5))

    def _concluir_pomodoro(self, fim: float) -> None:
        h = self._h()
        a = self.atual()
        dia = C.dia_de(fim)
        P = C.passivos(self.b, self.cfg, dia, h)
        feitos_antes = C.feitos_dia(self.b, dia)
        seg = C.seguidos_validos(self.cfg, h, a["inicio"])
        gamer = h["classe"] == "gamer"
        cmb = regras.combo(seg, self.cfg, gamer, P["combo_max"])
        extra = self._consumir("proximo_xp") + self._consumir("arriscar")
        self._consumir("commit_mais")
        mult = 1.0
        hpm = C.hp_max(self.cfg, h, P)
        cl = self.cfg["classes"]
        virada = False
        if h["classe"] == "otaku":
            limite = (self._cfg("mecanicas", "otaku_virada_pct") + P["virada_limite"]) / 100
            if h["hp"] < hpm * limite:
                mult *= self._cfg("mecanicas", "otaku_virada_mult") + P["virada"] / 100
                virada = True
        ot = feitos_antes >= C.teto(self.cfg, P)
        xp = regras.xp_pomodoro(self.cfg, cmb, P["xp_pomodoro"] + extra, ot, mult)
        pid = self._registrar_pomodoro(a, fim, "feito", cmb, xp)
        bits = regras.bits_de(xp, self.cfg, P["bits"])
        n_dia = feitos_antes + 1
        self._ganho("pomodoro", f"pomodoro {n_dia} concluído" + (" (overtraining)" if ot else ""), xp=xp, bits=bits,
                    ref=pid, ts=fim)
        h = self._h()
        self.b.x("UPDATE heroi SET seguidos = ?, seguidos_dia = ?, ultimo_fim = ? WHERE id = 1", (seg + 1, dia, fim))
        novo = regras.combo(seg + 1, self.cfg, gamer, P["combo_max"])
        if novo > cmb:
            self._registro("combo", f"combo subiu para x{novo:.1f}", fim)
        self._contar_streak(dia)
        n = a["n"] + 1
        pc = self.cfg["pomodoro"]
        longa = n >= pc["por_sessao"]
        dur = (pc["minutos_pausa_longa"] if longa else pc["minutos_pausa_curta"]) * 60
        self.b.x("UPDATE atual SET fase = ?, inicio = ?, duracao = ?, pausado_em = NULL, n = ? WHERE id = 1",
                 ("longa" if longa else "pausa", fim, dur, n))
        self._verificar_conquistas(fim)
        q = self.b.um("SELECT titulo FROM quests WHERE id = ?", (a["quest_id"],)) if a["quest_id"] else None
        self.emitir({"evento": "pomodoro_fim", "xp": xp, "combo": novo, "combo_antes": cmb, "overtraining": ot,
                     "virada": virada, "n_dia": n_dia, "quest": q["titulo"] if q else "", "pausa_longa": longa,
                     "classe": cl[h["classe"]]["nome"]})
        self.notificar(f"Pomodoro {n_dia} concluído", f"+{xp} xp · pausa {'longa' if longa else 'curta'} de "
                                                      f"{dur // 60} min")

    def _fim_pausa(self, fim: float, fase: str) -> None:
        h = self._h()
        P = C.passivos(self.b, self.cfg, C.dia_de(fim), h)
        pc = self.cfg["pomodoro"]
        mp = (pc["mp_pausa_longa"] if fase == "longa" else pc["mp_pausa_curta"]) + int(P["mp_pausa"])
        hp = int(P["hp_pausa"]) + (self._cfg("mecanicas", "rato_hp_pausa") if h["classe"] == "rato" else 0)
        self.b.x("UPDATE atual SET fase = 'parado', inicio = 0, duracao = 0, n = CASE WHEN ? THEN 0 ELSE n END WHERE id = 1",
                 (fase == "longa",))
        self._ganho("pausa", "pausa respeitada", hp=max(0, hp), mp=max(0, mp), ts=fim)
        self.emitir({"evento": "pausa_fim", "respeitada": True, "mp": mp, "hp": hp})
        self.notificar("Pausa acabou", "hora do próximo pomodoro")

    # ------------------------------------------------------------ commits (só o vigia do serviço chama)
    def _vinculado(self, repo, quest_id) -> bool:
        if not repo["materia"]:
            return True
        if not quest_id:
            return False
        q = self.b.um("SELECT materia FROM quests WHERE id = ?", (quest_id,))
        return bool(q and q["materia"].strip().lower() == repo["materia"].strip().lower())

    def observar_commit(self, repo, c: dict) -> dict | None:
        """c: hash, ts, assunto, mais, menos, coautor_claude. Devolve o registro, ou None se já existia."""
        if self.b.um("SELECT 1 FROM commits WHERE repo_id = ? AND hash = ?", (repo["id"], c["hash"])):
            return None
        h = self._h()
        ts = float(c["ts"])
        agora = self.agora()
        dia = C.dia_de(ts)
        a = self.atual()
        pom_inicio, quest_id = None, None
        if a["fase"] == "foco" and a["inicio"] - 5 <= ts <= agora + 5:
            pom_inicio, quest_id = a["inicio"], a["quest_id"]
        else:
            p = self.b.um("SELECT inicio, quest_id FROM pomodoros WHERE estado = 'feito' AND inicio - 5 <= ? AND ? <= fim + 60 "
                          "ORDER BY fim DESC LIMIT 1", (ts, ts))
            if p:
                pom_inicio, quest_id = p["inicio"], p["quest_id"]
        vinculado = pom_inicio is not None and self._vinculado(repo, quest_id)
        tipo = regras.tipo_commit(c["assunto"])
        linhas = int(c.get("mais", 0)) + int(c.get("menos", 0))
        cc = self.cfg["commit"]
        P = C.passivos(self.b, self.cfg, dia, h)
        motivo = ""
        if c.get("coautor_claude") and cc["ignorar_coautor_claude"]:
            xp, motivo = 0, "co-autor Claude: o Mestre não dá XP"
        elif int(self.b.escalar("SELECT COUNT(*) FROM commits WHERE dia = ? AND xp > 0", (dia,), 0)) >= cc["max_por_dia"]:
            xp, motivo = 0, "teto de commits do dia"
        elif vinculado and int(self.b.escalar("SELECT COUNT(*) FROM commits WHERE pomodoro_inicio = ? AND xp > 0",
                                              (pom_inicio,), 0)) >= cc["max_por_pomodoro"]:
            xp, motivo = 0, "teto de commits do pomodoro"
        else:
            ci = (cc["ci_verde_pct"] + P["ci_verde"]) if h["classe"] == "programa" else 0
            bonus = P["xp_commit"] + (C.efeito(self.b, "commit_mais") if pom_inicio == a["inicio"] else 0)
            xp = regras.xp_commit(tipo, linhas, vinculado, self.cfg, ci, bonus, P["solto"])
            if xp == 0:
                motivo = "sem linhas mudadas" if linhas <= 0 else f"tipo {tipo} não conta"
        assunto = texto(str(c.get("assunto") or "")[:200], "assunto", 200)
        cur = self.b.x("INSERT INTO commits (repo_id, hash, ts, dia, assunto, tipo, mais, menos, vinculado, pomodoro_inicio, "
                       "xp, motivo) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (repo["id"], c["hash"], ts, dia, assunto, tipo, int(c.get("mais", 0)), int(c.get("menos", 0)),
                        int(vinculado), pom_inicio, xp, motivo))
        cid = cur.lastrowid
        self.b.x("UPDATE repos SET ultimo = MAX(ultimo, ?) WHERE id = ?", (ts, repo["id"]))
        if xp > 0:
            self._ganho("commit", f"{c['hash'][:7]} {assunto}", xp=xp, bits=regras.bits_de(xp, self.cfg, P["bits"]),
                        ref=cid, ts=min(ts, agora))
        self.emitir({"evento": "commit", "hash": c["hash"][:7], "assunto": assunto, "xp": xp, "vinculado": vinculado,
                     "repo": repo["nome"], "motivo": motivo})
        m = FECHA_QUEST.search(c.get("assunto", "") + "\n" + c.get("corpo", ""))
        if m:
            q = self.b.um("SELECT * FROM quests WHERE id = ? AND estado = 'aberta'", (int(m.group(1)),))
            if q is not None:
                try:
                    self._concluir(q, f"commit {c['hash'][:7]}", ts=min(ts, agora))
                except ErroJogo:
                    pass
        if xp > 0:
            self._verificar_conquistas(min(ts, agora))
        return {"id": cid, "xp": xp, "vinculado": vinculado, "motivo": motivo}

    # ------------------------------------------------------------ quests
    def _campos_quest(self, a: dict, parcial: bool) -> dict:
        if any(k in a for k in ("xp", "bits", "recompensa", "xp_previsto", "bits_previstos", "nivel", "hp", "mp")):
            raise ErroJogo("a recompensa sai da tabela do jogo (est e dif); não dá para escolher")
        q = self.cfg["quest"]
        f = {}
        if not parcial or "titulo" in a:
            f["titulo"] = texto(a.get("titulo"), "título", 120, obrigatorio=True)
        if not parcial or "materia" in a:
            f["materia"] = texto(a.get("materia"), "matéria", 40)
        if not parcial or "est" in a:
            f["est"] = inteiro(a.get("est"), "estimativa", 1, q["est_max"])
        if not parcial or "dif" in a:
            f["dif"] = dificuldade(a.get("dif"))
        if not parcial or "arco" in a:
            f["arco_nome"] = texto(a.get("arco"), "arco", 40)
        if not parcial or "prazo" in a:
            f["prazo"] = data_valida(a.get("prazo"))
        if not parcial or "descricao" in a or "desc" in a or "porque" in a:
            bruto = a["descricao"] if "descricao" in a else (a["desc"] if "desc" in a else a.get("porque"))
            f["porque"] = texto(bruto, "descrição", 800)
        if not parcial or "prio" in a:
            f["prio"] = inteiro(a.get("prio", 2) if a.get("prio") not in (None, "") else 2, "prioridade", 1, 3)
        if not parcial or "depende_de" in a:
            deps = a.get("depende_de", [])
            if isinstance(deps, str):
                deps = [x.strip() for x in deps.split(",") if x.strip()]
            if not isinstance(deps, list) or len(deps) > 8:
                raise ErroJogo("depende_de: lista de até 8 ids")
            f["depende_de"] = json.dumps([inteiro(d, "depende_de", 1, 10**9) for d in deps])
        if "tipo" in a:
            if a["tipo"] not in ("normal", "daily"):
                raise ErroJogo("tipo: normal ou daily")
            f["tipo"] = a["tipo"]
        if "subtarefas" in a:
            subs = a["subtarefas"]
            if not isinstance(subs, list) or len(subs) > 12:
                raise ErroJogo("subtarefas: lista de até 12")
            f["subtarefas"] = json.dumps([{"texto": texto(s.get("texto") if isinstance(s, dict) else s, "subtarefa", 80,
                                                          obrigatorio=True),
                                           "feita": bool(s.get("feita")) if isinstance(s, dict) else False} for s in subs],
                                         ensure_ascii=False)
        return f

    def _arco_id(self, nome: str) -> int | None:
        if not nome:
            return None
        r = self.b.um("SELECT id FROM arcos WHERE lower(nome) = lower(?)", (nome,))
        if r:
            return r[0]
        n = int(self.b.escalar("SELECT COUNT(*) FROM arcos", (), 0))
        cur = self.b.x("INSERT INTO arcos (nome, cor, criado) VALUES (?, ?, ?)", (nome, CORES_ARCO[n % len(CORES_ARCO)],
                                                                                 self.agora()))
        return cur.lastrowid

    def _proxima_ordem(self) -> int:
        return int(self.b.escalar("SELECT MAX(ordem) FROM quests", (), 0)) + 1

    def _resumo_quest(self, qid: int) -> dict:
        q = self.b.um("SELECT * FROM quests WHERE id = ?", (qid,))
        xp = regras.xp_quest(q["est"], q["dif"], self.cfg)
        return {"id": qid, "titulo": q["titulo"], "estado": q["estado"], "xp_previsto": xp,
                "bits_previstos": regras.bits_de(xp, self.cfg)}

    def nova_quest(self, **a) -> dict:
        self._h()
        f = self._campos_quest(a, parcial=False)
        f.setdefault("tipo", "normal")
        f.setdefault("subtarefas", "[]")
        hoje = 1 if a.get("hoje", True) else 0
        with self.b.transacao():
            arco = self._arco_id(f["arco_nome"])
            cur = self.b.x("INSERT INTO quests (titulo, materia, est, dif, prio, depende_de, arco_id, arco_nome, prazo, tipo, "
                           "estado, origem, porque, ordem, hoje, subtarefas, criada, aprovada) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?,'aberta','jogador',?,?,?,?,?,?)",
                           (f["titulo"], f["materia"], f["est"], f["dif"], f["prio"], f["depende_de"], arco, f["arco_nome"],
                            f["prazo"], f["tipo"], f["porque"], self._proxima_ordem(), hoje, f["subtarefas"],
                            self.agora(), self.agora()))
        self.emitir({"evento": "quest", "id": cur.lastrowid})
        return self._resumo_quest(cur.lastrowid)

    def rascunho(self, **a) -> dict:
        """O Mestre propõe. A recompensa sai da fórmula; nada vale até o jogador aprovar."""
        self._h()
        f = self._campos_quest(a, parcial=False)
        f["tipo"] = "normal"
        maximo = self._cfg("mestre", "max_rascunhos_por_dia")
        if maximo > 0:
            ini = C.inicio_do_dia(self.hoje())
            if int(self.b.escalar("SELECT COUNT(*) FROM quests WHERE origem = 'mestre' AND criada >= ?", (ini,), 0)) >= maximo:
                raise ErroJogo(f"limite de {maximo} rascunhos por dia")
        cur = self.b.x("INSERT INTO quests (titulo, materia, est, dif, prio, depende_de, arco_nome, prazo, tipo, estado, "
                       "origem, porque, ordem, criada) VALUES (?,?,?,?,?,?,?,?,'normal','rascunho','mestre',?,?,?)",
                       (f["titulo"], f["materia"], f["est"], f["dif"], f["prio"], f["depende_de"], f["arco_nome"],
                        f["prazo"], f["porque"], self._proxima_ordem(), self.agora()))
        self.emitir({"evento": "rascunho", "id": cur.lastrowid})
        return self._resumo_quest(cur.lastrowid)

    def editar_rascunho(self, id=None, **a) -> dict:
        qid = inteiro(id, "id", 1, 10**9)
        q = self.b.um("SELECT * FROM quests WHERE id = ?", (qid,))
        if q is None or q["estado"] != "rascunho":
            raise ErroJogo("só dá para editar rascunho que ainda não foi aprovado")
        a.pop("tipo", None)
        a.pop("subtarefas", None)
        f = self._campos_quest(a, parcial=True)
        if f:
            sets = ", ".join(f"{k} = ?" for k in f)
            self.b.x(f"UPDATE quests SET {sets} WHERE id = ?", (*f.values(), qid))
        self.emitir({"evento": "rascunho", "id": qid})
        return self._resumo_quest(qid)

    def editar_quest(self, id=None, **a) -> dict:
        qid = inteiro(id, "id", 1, 10**9)
        q = self.b.um("SELECT * FROM quests WHERE id = ?", (qid,))
        if q is None or q["estado"] not in ("aberta", "rascunho"):
            raise ErroJogo("quest não encontrada ou já fechada")
        f = self._campos_quest(a, parcial=True)
        muda_conta = ("est" in f and f["est"] != q["est"]) or ("dif" in f and f["dif"] != q["dif"])
        custo = 0
        if muda_conta and q["estado"] == "aberta" and C.quest_feitos(self.b, qid) > 0:
            if C.tem_efeito(self.b, "reestimar"):
                self.b.x("DELETE FROM efeitos WHERE id = (SELECT id FROM efeitos WHERE tipo = 'reestimar' LIMIT 1)")
            else:
                custo = self._cfg("quest", "custo_reestimar_bits")
                if self._h()["bits"] < custo:
                    raise ErroJogo(f"reestimar uma quest começada custa {custo} bits")
        with self.b.transacao():
            if "arco_nome" in f:
                f["arco_id"] = self._arco_id(f["arco_nome"]) if q["estado"] == "aberta" else None
            if f:
                sets = ", ".join(f"{k} = ?" for k in f)
                self.b.x(f"UPDATE quests SET {sets} WHERE id = ?", (*f.values(), qid))
            if custo:
                self._ganho("reestimar", f"reestimou: {q['titulo']}", bits=-custo)
        self.emitir({"evento": "quest", "id": qid})
        return self._resumo_quest(qid)

    def aprovar(self, id=None) -> dict:
        qid = inteiro(id, "id", 1, 10**9)
        q = self.b.um("SELECT * FROM quests WHERE id = ?", (qid,))
        if q is None or q["estado"] != "rascunho":
            raise ErroJogo("rascunho não encontrado")
        with self.b.transacao():
            arco = self._arco_id(q["arco_nome"])
            self.b.x("UPDATE quests SET estado = 'aberta', arco_id = ?, aprovada = ?, hoje = 1 WHERE id = ?",
                     (arco, self.agora(), qid))
        self._registro("aprovar", f"aprovou o rascunho #{qid}: {q['titulo']}")
        self.emitir({"evento": "quest", "id": qid})
        return self._resumo_quest(qid)

    def aprovar_todos(self) -> dict:
        ids = [r[0] for r in self.b.todos("SELECT id FROM quests WHERE estado = 'rascunho' ORDER BY id")]
        for qid in ids:
            self.aprovar(id=qid)
        return {"aprovados": len(ids)}

    def descartar_rascunho(self, id=None) -> dict:
        qid = inteiro(id, "id", 1, 10**9)
        q = self.b.um("SELECT * FROM quests WHERE id = ?", (qid,))
        if q is None or q["estado"] != "rascunho":
            raise ErroJogo("rascunho não encontrado")
        self.b.x("UPDATE quests SET estado = 'descartada' WHERE id = ?", (qid,))
        self.emitir({"evento": "quest", "id": qid})
        return {"id": qid}

    def descartar_quest(self, id=None) -> dict:
        qid = inteiro(id, "id", 1, 10**9)
        q = self._quest_aberta(qid)
        self.b.x("UPDATE quests SET estado = 'descartada' WHERE id = ?", (q["id"],))
        self.emitir({"evento": "quest", "id": qid})
        return {"id": qid}

    def concluir_quest(self, id=None, nota="") -> dict:
        qid = inteiro(id, "id", 1, 10**9)
        q = self._quest_aberta(qid)
        self._quest_desbloqueada(q)
        return self._concluir(q, texto(nota, "nota", 200))

    def _concluir(self, q, nota: str, ts: float | None = None) -> dict:
        ts = self.agora() if ts is None else ts
        dia = C.dia_de(ts)
        daily = q["tipo"] == "daily"
        if daily and q["daily_feita"] == dia:
            raise ErroJogo("essa daily já foi feita hoje")
        feitos = C.quest_feitos(self.b, q["id"], dia if daily else None)
        h = self._h()
        P = C.passivos(self.b, self.cfg, dia, h)
        xp = regras.xp_quest_concluida(q["est"], q["dif"], feitos, self.cfg, P["xp_quest"])
        bits = regras.bits_de(xp, self.cfg, P["bits"])
        with self.b.transacao():
            if daily:
                self.b.x("UPDATE quests SET daily_feita = ?, nota = ? WHERE id = ?", (dia, nota, q["id"]))
            else:
                self.b.x("UPDATE quests SET estado = 'feita', concluida = ?, nota = ?, xp_ganho = ? WHERE id = ?",
                         (ts, nota, xp, q["id"]))
            if xp > 0:
                self._ganho("quest", f"quest: {q['titulo']}", xp=xp, bits=bits, ref=q["id"], ts=ts)
            else:
                self._registro("quest", f"quest sem pomodoro: {q['titulo']} (0 xp)", ts)
        cheio = feitos >= regras.xp_cheio_minimo(q["est"], self.cfg)
        self.emitir({"evento": "quest_feita", "id": q["id"], "titulo": q["titulo"], "xp": xp, "bits": bits, "cheio": cheio})
        if not daily and q["arco_id"]:
            self._verificar_chefe(q["arco_id"], ts)
        return {"id": q["id"], "xp": xp, "bits": bits, "feitos": feitos, "cheio": cheio}

    def _verificar_chefe(self, arco_id: int, ts: float) -> None:
        arco = self.b.um("SELECT * FROM arcos WHERE id = ?", (arco_id,))
        if arco is None or arco["bonus_em"] is not None:
            return
        abertas = int(self.b.escalar("SELECT COUNT(*) FROM quests WHERE arco_id = ? AND estado = 'aberta'", (arco_id,), 0))
        feitas = self.b.todos("SELECT xp_ganho FROM quests WHERE arco_id = ? AND estado = 'feita'", (arco_id,))
        if abertas or not feitas:
            return
        if arco["data"] and C.dia_de(ts) > arco["data"]:
            return
        h = self._h()
        P = C.passivos(self.b, self.cfg, C.dia_de(ts), h)
        extra = P["chefe"] + (self._cfg("mecanicas", "otaku_chefe_pct") if h["classe"] == "otaku" else 0)
        xp = regras.chefe_xp([r[0] for r in feitas], self.cfg, extra)
        self.b.x("UPDATE arcos SET bonus_em = ? WHERE id = ?", (ts, arco_id))
        if xp > 0:
            self._ganho("arco", f"chefe vencido: {arco['chefe'] or arco['nome']}", xp=xp,
                        bits=regras.bits_de(xp, self.cfg, P["bits"]), ref=arco_id, ts=ts)
        self.emitir({"evento": "chefe", "arco": arco["nome"], "xp": xp})
        self._verificar_conquistas(ts)

    def mover_fila(self, id=None, passo=1) -> dict:
        qid = inteiro(id, "id", 1, 10**9)
        passo = inteiro(passo, "passo", -50, 50)
        ids = [q["id"] for q in C.fila(self.b, self.cfg, self.hoje())]
        if qid not in ids:
            raise ErroJogo("a quest não está na fila de hoje")
        i = ids.index(qid)
        j = max(0, min(len(ids) - 1, i + passo))
        ids.insert(j, ids.pop(i))
        self._reordenar(ids)
        return {"ordem": ids}

    def ordenar_fila(self, ids=None) -> dict:
        if not isinstance(ids, list) or len(ids) > 500:
            raise ErroJogo("ordem inválida")
        ids = [inteiro(i, "id", 1, 10**9) for i in ids]
        self._reordenar(ids)
        return {"ordem": ids}

    def _reordenar(self, ids: list[int]) -> None:
        resto = [r[0] for r in self.b.todos("SELECT id FROM quests ORDER BY ordem, id") if r[0] not in ids]
        with self.b.transacao():
            for n, qid in enumerate(ids + resto, 1):
                self.b.x("UPDATE quests SET ordem = ? WHERE id = ?", (n, qid))
        self.emitir({"evento": "fila"})

    def marcar_hoje(self, id=None, valor=True) -> dict:
        qid = inteiro(id, "id", 1, 10**9)
        self._quest_aberta(qid)
        self.b.x("UPDATE quests SET hoje = ? WHERE id = ?", (1 if valor else 0, qid))
        self.emitir({"evento": "fila"})
        return {"id": qid, "hoje": bool(valor)}

    def subtarefa(self, id=None, indice=0, feita=None, texto_novo=None) -> dict:
        qid = inteiro(id, "id", 1, 10**9)
        q = self.b.um("SELECT * FROM quests WHERE id = ? AND estado IN ('aberta', 'rascunho')", (qid,))
        if q is None:
            raise ErroJogo("quest não encontrada")
        subs = C.subtarefas(q)
        if texto_novo is not None:
            if len(subs) >= 12:
                raise ErroJogo("no máximo 12 subtarefas")
            subs.append({"texto": texto(texto_novo, "subtarefa", 80, obrigatorio=True), "feita": False})
        else:
            i = inteiro(indice, "índice", 0, max(0, len(subs) - 1))
            if not subs:
                raise ErroJogo("sem subtarefas")
            subs[i]["feita"] = (not subs[i].get("feita")) if feita is None else bool(feita)
        self.b.x("UPDATE quests SET subtarefas = ? WHERE id = ?", (json.dumps(subs, ensure_ascii=False), qid))
        self.emitir({"evento": "quest", "id": qid})
        return {"subtarefas": subs}

    def novo_arco(self, nome=None, chefe="", data="") -> dict:
        nome = texto(nome, "nome do arco", 40, obrigatorio=True)
        if self.b.um("SELECT 1 FROM arcos WHERE lower(nome) = lower(?)", (nome,)):
            raise ErroJogo("já existe um arco com esse nome")
        aid = self._arco_id(nome)
        self.b.x("UPDATE arcos SET chefe = ?, data = ? WHERE id = ?", (texto(chefe, "chefe", 60), data_valida(data, "data"), aid))
        self.emitir({"evento": "arco", "id": aid})
        return {"id": aid}

    def editar_arco(self, id=None, nome=None, chefe=None, data=None) -> dict:
        aid = inteiro(id, "id", 1, 10**9)
        a = self.b.um("SELECT * FROM arcos WHERE id = ?", (aid,))
        if a is None:
            raise ErroJogo("arco não encontrado")
        novo = texto(nome, "nome do arco", 40, obrigatorio=True) if nome is not None else a["nome"]
        with self.b.transacao():
            self.b.x("UPDATE arcos SET nome = ?, chefe = ?, data = ? WHERE id = ?",
                     (novo, texto(chefe, "chefe", 60) if chefe is not None else a["chefe"],
                      data_valida(data, "data") if data is not None else a["data"], aid))
            self.b.x("UPDATE quests SET arco_nome = ? WHERE arco_id = ?", (novo, aid))
        self.emitir({"evento": "arco", "id": aid})
        return {"id": aid}

    def nota(self, texto_=None) -> dict:
        t = texto(texto_, "nota", 200, obrigatorio=True)
        a = self.atual()
        ts = self.agora()
        self.b.x("INSERT INTO notas (ts, dia, quest_id, texto) VALUES (?,?,?,?)", (ts, C.dia_de(ts), a["quest_id"], t))
        self.emitir({"evento": "nota"})
        return {}

    # ------------------------------------------------------------ skills
    def aprender(self, skill=None) -> dict:
        h = self._h()
        s = self.cfg["skills"].get(skill)
        if s is None or s["classe"] != h["classe"]:
            raise ErroJogo("essa skill não é da sua classe")
        est = C.skills_estado(self.b, self.cfg, h).get(skill)
        if est == "aprendida":
            raise ErroJogo("já aprendida")
        if est == "bloqueada":
            raise ErroJogo("aprenda a skill de cima no mesmo ramo antes")
        custo = C.custo_skill(s)
        if h["pontos"] < custo:
            raise ErroJogo(f"precisa de {custo} ponto{'s' if custo > 1 else ''} de skill")
        with self.b.transacao():
            self.b.x("UPDATE heroi SET pontos = pontos - ? WHERE id = 1", (custo,))
            self.b.x("INSERT INTO skills (skill, em, custo) VALUES (?, ?, ?)", (skill, self.agora(), custo))
        self._registro("skill", f"aprendeu {s['nome']}")
        self.emitir({"evento": "skill", "skill": skill})
        return {"skill": skill, "pontos": h["pontos"] - custo}

    def respec(self, skill=None) -> dict:
        h = self._h()
        s = self.cfg["skills"].get(skill)
        if s is None or not self.b.um("SELECT 1 FROM skills WHERE skill = ?", (skill,)):
            raise ErroJogo("essa skill não está aprendida")
        acima = [k for k in self.cfg.skills_da_classe(h["classe"]) if self.cfg["skills"][k]["ramo"] == s["ramo"]
                 and self.cfg["skills"][k]["pos"] > s["pos"] and self.b.um("SELECT 1 FROM skills WHERE skill = ?", (k,))]
        if acima:
            raise ErroJogo("desfaça antes as skills de baixo no mesmo ramo")
        custo = self._cfg("loja", "respec_skill_bits")
        if h["bits"] < custo:
            raise ErroJogo(f"respec custa {custo} bits; faltam {custo - h['bits']}")
        pontos = int(self.b.escalar("SELECT custo FROM skills WHERE skill = ?", (skill,), 1))
        with self.b.transacao():
            self.b.x("DELETE FROM skills WHERE skill = ?", (skill,))
            self.b.x("UPDATE heroi SET pontos = pontos + ? WHERE id = 1", (pontos,))
            self._ganho("respec", f"respec de {s['nome']}", bits=-custo)
        self.emitir({"evento": "skill", "skill": skill})
        return {"skill": skill, "pontos_devolvidos": pontos}

    def usar_skill(self, skill=None) -> dict:
        h = self._h()
        s = self.cfg["skills"].get(skill)
        if s is None or s["classe"] != h["classe"] or s["tipo"] != "ativa":
            raise ErroJogo("skill ativa desconhecida")
        if not self.b.um("SELECT 1 FROM skills WHERE skill = ?", (skill,)):
            raise ErroJogo("skill ainda não aprendida")
        dia = self.hoje()
        usada = C.uso_hoje(self.b, skill, dia)
        if usada:
            raise ErroJogo(f"já usada hoje às {C.hora(usada)}")
        P = self.P(h)
        custo = C.custo_mana(self.cfg, s, P)
        if h["mp"] < custo:
            raise ErroJogo(f"mana insuficiente: {s['nome']} custa {custo}, você tem {h['mp']}")
        ef, valor = s["efeito"], s.get("valor", 0)
        a = self.atual()
        msg = ""
        # conferências antes de gastar a mana
        if ef == "guardar" and a["fase"] != "foco":
            raise ErroJogo("só dá para guardar um pomodoro em andamento")
        if ef == "desfazer_hp" and h["ultima_perda"] <= 0:
            raise ErroJogo("nenhuma perda de HP para desfazer")
        pendente = None
        if ef == "descartar":
            pendente = next((q for q in C.fila(self.b, self.cfg, dia) if q["tipo"] == "daily"), None)
            if pendente is None:
                raise ErroJogo("nenhuma daily pendente hoje")
        if ef == "carta" and h["classe"] != "mistico":
            raise ErroJogo("só o Jovem Místico tira cartas")
        with self.b.transacao():
            self.b.x("INSERT INTO usos (skill, dia, em) VALUES (?, ?, ?)", (skill, dia, self.agora()))
            hp = 0
            if ef == "guardar":
                self._guardar()
                msg = "pomodoro guardado; o combo continua"
            elif ef in ("proximo_xp", "arriscar"):
                self._efeito("proximo_xp" if ef == "proximo_xp" else "arriscar", float(valor), skill)
                msg = f"o próximo pomodoro vale +{valor}%"
            elif ef == "torre":
                self.b.x("UPDATE heroi SET seguidos = 0 WHERE id = 1")
                self._efeito("proximo_xp", float(valor), skill)
                msg = f"combo zerado; o próximo pomodoro vale +{valor}%"
            elif ef == "sorte":
                v = self.rng.choice([-50, -25, 0, 25, 50, 75, 100])
                self._efeito("proximo_xp", float(v), skill)
                msg = f"saiu x{1 + v / 100:.2f} para o próximo pomodoro".replace(".", ",")
            elif ef == "escudo":
                self._efeito("escudo", 1, skill)
                msg = "a próxima perda de HP não acontece"
            elif ef == "desfazer_hp":
                hp = int(h["ultima_perda"])
                self.b.x("UPDATE heroi SET ultima_perda = 0 WHERE id = 1")
                msg = f"+{hp} de HP de volta"
            elif ef == "cura":
                hp = int(valor)
                msg = "HP recuperado"
            elif ef == "mana_hp":
                hp = int(valor)
                msg = f"{custo} de mana viraram {hp} de HP"
            elif ef == "descartar":
                self.b.x("UPDATE quests SET daily_livre = ? WHERE id = ?", (dia, pendente["id"]))
                msg = f"daily dispensada hoje: {pendente['titulo']}"
            elif ef == "combo_mais":
                seg = C.seguidos_validos(self.cfg, h, self.agora())
                self.b.x("UPDATE heroi SET seguidos = ?, seguidos_dia = ?, ultimo_fim = ? WHERE id = 1",
                         (seg + int(valor), dia, self.agora()))
                msg = f"combo x{C.combo_de(self.cfg, self._h(), P, self.agora()):.1f}"
            elif ef == "commit_mais":
                self._efeito("commit_mais", float(valor), skill)
                msg = f"commits deste pomodoro valem +{valor}%"
            elif ef == "carta":
                giro = int(self.b.escalar("SELECT COUNT(*) FROM usos WHERE skill = ?", (skill,), 1))
                buff, debuff = C.sortear_carta(self.cfg, dia, h["nome"], giro)
                self.b.x("INSERT INTO cartas (dia, buff, debuff, revelada) VALUES (?, ?, ?, 1) ON CONFLICT(dia) DO UPDATE "
                         "SET buff = excluded.buff, debuff = excluded.debuff, revelada = 1", (dia, buff, debuff))
                msg = f"nova carta: {self.cfg['cartas'][buff]['nome']} e {self.cfg['cartas'][debuff]['nome']}"
            self._ganho("skill", f"{s['nome']}: {msg}", mp=-custo, hp=hp)
        self.emitir({"evento": "skill_usada", "skill": skill, "nome": s["nome"], "texto": msg})
        return {"skill": skill, "mana": custo, "texto": msg}

    # ------------------------------------------------------------ cartas do Místico
    def revelar_carta(self) -> dict:
        h = self._h()
        if h["classe"] != "mistico":
            raise ErroJogo("só o Jovem Místico tira cartas")
        dia = self.hoje()
        buff, debuff, _ = C.carta_do_dia(self.b, self.cfg, dia, h)
        self.b.x("INSERT INTO cartas (dia, buff, debuff, revelada) VALUES (?, ?, ?, 1) ON CONFLICT(dia) DO UPDATE SET revelada = 1",
                 (dia, buff, debuff))
        self.emitir({"evento": "carta", "buff": buff, "debuff": debuff})
        return {"buff": buff, "debuff": debuff}

    # ------------------------------------------------------------ loja
    def comprar(self, item=None, qtd=1) -> dict:
        h = self._h()
        it = self.cfg["itens"].get(item)
        if it is None:
            raise ErroJogo("item desconhecido")
        qtd = inteiro(qtd, "quantidade", 1, 20)
        cat = it["categoria"]
        if cat != "consumivel":
            qtd = 1
            if item in C.posses(self.b):
                raise ErroJogo("você já tem esse item")
        preco = int(it["preco"]) * qtd
        if h["bits"] < preco:
            raise ErroJogo(f"faltam {preco - h['bits']} bits")
        with self.b.transacao():
            if cat == "consumivel":
                self.b.x("INSERT INTO mochila (item, qtd) VALUES (?, ?) ON CONFLICT(item) DO UPDATE SET qtd = qtd + ?",
                         (item, qtd, qtd))
            else:
                self.b.x("INSERT INTO posses (item, em) VALUES (?, ?)", (item, self.agora()))
            if preco:
                self._ganho("loja", f"comprou {it['nome']}" + (f" x{qtd}" if qtd > 1 else ""), bits=-preco)
        self.emitir({"evento": "compra", "item": item, "nome": it["nome"], "bits": preco, "qtd": qtd})
        return {"item": item, "qtd": qtd, "bits": preco}

    def usar_item(self, item=None) -> dict:
        h = self._h()
        it = self.cfg["itens"].get(item)
        if it is None or it["categoria"] != "consumivel":
            raise ErroJogo("item desconhecido")
        if C.mochila(self.b).get(item, 0) <= 0:
            raise ErroJogo("não tem na mochila")
        ef, valor = it["efeito"], it["valor"]
        msg = ""
        with self.b.transacao():
            self.b.x("UPDATE mochila SET qtd = qtd - 1 WHERE item = ?", (item,))
            if ef == "cura":
                r = self._ganho("item", f"usou {it['nome']}", hp=int(valor))
                msg = f"+{r['hp']} de HP"
            elif ef == "mana":
                r = self._ganho("item", f"usou {it['nome']}", mp=int(valor))
                msg = f"+{r['mp']} de mana"
            elif ef in ("congelar", "reestimar"):
                self._efeito(ef, 1, item)
                self._registro("item", f"usou {it['nome']}")
                msg = "ativo" if ef == "congelar" else "a próxima reestimativa sai de graça"
            elif ef == "caixa":
                cc = self.cfg["loja"]
                faltam = [k for k in self.cfg.itens_da_categoria("cosmetico") if k not in C.posses(self.b)]
                if faltam and self.rng.random() * 100 < cc["caixa_chance_cosmetico"]:
                    ganhou = self.rng.choice(faltam)
                    self.b.x("INSERT INTO posses (item, em) VALUES (?, ?)", (ganhou, self.agora()))
                    self._registro("caixa", f"a caixa trouxe {self.cfg['itens'][ganhou]['nome']}")
                    msg = f"saiu {self.cfg['itens'][ganhou]['nome']}"
                else:
                    bits = self.rng.randint(cc["caixa_bits_min"], cc["caixa_bits_max"])
                    self._ganho("caixa", "a caixa trouxe bits", bits=bits)
                    msg = f"saíram {bits} bits"
            elif ef == "respec_total":
                pontos = int(self.b.escalar("SELECT SUM(custo) FROM skills", (), 0))
                self.b.x("DELETE FROM skills")
                self.b.x("UPDATE heroi SET pontos = pontos + ? WHERE id = 1", (pontos,))
                self._registro("item", f"elixir: {pontos} pontos devolvidos")
                msg = f"{pontos} pontos de skill de volta"
            self.b.x("DELETE FROM mochila WHERE qtd <= 0")
        self.emitir({"evento": "item_usado", "item": item, "nome": it["nome"], "texto": msg})
        return {"item": item, "texto": msg}

    def equipar(self, item=None) -> dict:
        h = self._h()
        it = self.cfg["itens"].get(item)
        if it is None or it["categoria"] not in ("cosmetico", "titulo", "tema"):
            raise ErroJogo("esse item não se equipa")
        if item not in C.posses(self.b):
            raise ErroJogo("compre antes de equipar")
        coluna = {"moldura": "moldura", "cor_retrato": "cor_retrato", "titulo": "titulo", "tema_calor": "tema_calor"}[it["efeito"]]
        valor = it["valor"]
        if h[coluna] == valor and coluna != "tema_calor":
            valor = ""
        self.b.x(f"UPDATE heroi SET {coluna} = ? WHERE id = 1", (valor,))
        self.emitir({"evento": "equipou", "item": item, "ligado": bool(valor)})
        return {"item": item, "ligado": bool(valor)}

    # ------------------------------------------------------------ taverna e repositórios
    def taverna_registrar(self, papel=None, texto_=None, extra=None) -> dict:
        if papel not in ("voce", "mestre", "cli", "sistema"):
            raise ErroJogo("papel inválido")
        t = texto(texto_, "mensagem", 4000, obrigatorio=True) if papel != "mestre" else str(texto_ or "")[:4000]
        ex = json.dumps(extra, ensure_ascii=False)[:2000] if extra else ""
        self.b.x("INSERT INTO taverna (ts, papel, texto, extra) VALUES (?,?,?,?)", (self.agora(), papel, t, ex))
        self.b.x("DELETE FROM taverna WHERE id <= (SELECT MAX(id) - 500 FROM taverna)")
        self.emitir({"evento": "taverna"})
        return {}

    def repo_adicionar(self, caminho=None, materia="") -> dict:
        from oma_rpg.nucleo import git
        self._h()
        r = git.validar_repo(texto(caminho, "caminho", 400, obrigatorio=True))
        mat = texto(materia, "matéria", 40)
        if self.b.um("SELECT 1 FROM repos WHERE caminho = ?", (r["caminho"],)):
            raise ErroJogo("esse repositório já está registrado")
        cur = self.b.x("INSERT INTO repos (caminho, nome, materia, base, registrado) VALUES (?,?,?,?,?)",
                       (r["caminho"], r["nome"], mat, r["head"], self.agora()))
        self.emitir({"evento": "repos"})
        return {"id": cur.lastrowid, "nome": r["nome"]}

    # ------------------------------------------------------------ pastas que o Mestre pode ler
    def pasta_adicionar(self, caminho=None, modo="sempre") -> dict:
        """Só o jogador (pela interface). A pasta é resolvida e conferida (nunca ~, /, nem pasta sensível)."""
        from oma_rpg.nucleo import pastas
        if modo not in ("sempre", "uma_vez"):
            raise ErroJogo("modo: sempre ou uma_vez")
        real = pastas.validar_raiz(texto(caminho, "caminho", 500, obrigatorio=True))
        agora = self.agora()
        atual = self.b.um("SELECT modo FROM pastas WHERE caminho = ?", (real,))
        if not (atual and atual["modo"] == "sempre" and modo == "uma_vez"):
            expira = None if modo == "sempre" else agora + self._cfg("mestre", "pasta_uma_vez_min") * 60
            self.b.x("INSERT INTO pastas (caminho, modo, criada, expira) VALUES (?,?,?,?) ON CONFLICT(caminho) DO UPDATE SET "
                     "modo = excluded.modo, expira = excluded.expira", (real, modo, agora, expira))
        for r in self.b.todos("SELECT id, caminho FROM pedidos_pasta WHERE estado = 'pendente'"):
            if r["caminho"] == real or r["caminho"].startswith(real.rstrip("/") + "/"):
                self.b.x("UPDATE pedidos_pasta SET estado = 'liberado' WHERE id = ?", (r["id"],))
        self.emitir({"evento": "pastas"})
        return {"caminho": real, "modo": modo}

    def pasta_remover(self, caminho=None) -> dict:
        c = texto(caminho, "caminho", 500, obrigatorio=True)
        n = self.b.x("DELETE FROM pastas WHERE caminho = ?", (c,)).rowcount
        if not n:
            raise ErroJogo("essa pasta não está liberada")
        self.emitir({"evento": "pastas"})
        return {"caminho": c}

    def pedir_pasta(self, caminho=None, motivo="") -> dict:
        """O Mestre pede para ler uma pasta. Só registra o pedido: quem libera é o jogador, na taverna."""
        from pathlib import Path

        from oma_rpg.nucleo import consultas, pastas
        alvo = pastas.pasta_pedida(texto(caminho, "caminho", 500, obrigatorio=True))
        if not Path(alvo).is_dir():
            raise ErroJogo("a pasta não existe")
        m = pastas.motivo_sensivel(Path(alvo))
        if m:
            raise ErroJogo(m)
        try:
            pastas.resolver(alvo, consultas.caminhos_liberados(self.b, self.agora()))
            return {"liberada": True, "caminho": alvo}
        except ErroJogo:
            pass
        r = self.b.um("SELECT id FROM pedidos_pasta WHERE estado = 'pendente' AND caminho = ?", (alvo,))
        if r:
            return {"liberada": False, "id": r[0], "caminho": alvo}
        if len(consultas.pedidos_pendentes(self.b)) >= self._cfg("mestre", "max_pedidos_pasta"):
            raise ErroJogo("muitos pedidos de pasta esperando resposta")
        cur = self.b.x("INSERT INTO pedidos_pasta (caminho, ts, motivo) VALUES (?,?,?)",
                       (alvo, self.agora(), texto(motivo, "motivo", 200)))
        self.emitir({"evento": "pedido_pasta", "id": cur.lastrowid, "caminho": alvo, "motivo": texto(motivo, "motivo", 200)})
        return {"liberada": False, "id": cur.lastrowid, "caminho": alvo}

    def responder_pedido(self, id=None, resposta=None) -> dict:
        pid = inteiro(id, "id", 1, 10**9)
        if resposta not in ("sempre", "uma_vez", "negar"):
            raise ErroJogo("resposta: sempre, uma_vez ou negar")
        r = self.b.um("SELECT * FROM pedidos_pasta WHERE id = ?", (pid,))
        if r is None or r["estado"] != "pendente":
            raise ErroJogo("pedido não encontrado ou já respondido")
        if resposta == "negar":
            self.b.x("UPDATE pedidos_pasta SET estado = 'negado' WHERE id = ?", (pid,))
            self.emitir({"evento": "pastas"})
            return {"id": pid, "resposta": "negar"}
        try:
            self.pasta_adicionar(r["caminho"], resposta)
        except ErroJogo:
            self.b.x("UPDATE pedidos_pasta SET estado = 'negado' WHERE id = ?", (pid,))
            raise
        return {"id": pid, "resposta": resposta, "caminho": r["caminho"]}

    def repo_remover(self, id=None) -> dict:
        rid = inteiro(id, "id", 1, 10**9)
        self.b.x("DELETE FROM repos WHERE id = ?", (rid,))
        self.emitir({"evento": "repos"})
        return {"id": rid}
