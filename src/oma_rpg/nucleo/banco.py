"""SQLite (WAL) em ~/.local/share/oma-rpg/rpg.sqlite3.

Quem escreve é o serviço (ou o Jogo do --demo e dos testes). A interface e o CLI de leitura abrem só leitura
(`mode=ro` e `PRAGMA query_only`). O XP e os Bits de uma quest não ficam gravados: saem sempre da fórmula, a partir
de est e dif, então não existe coluna onde alguém possa escrever uma recompensa.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

VERSAO = 1

ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS heroi (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  nome TEXT NOT NULL, classe TEXT NOT NULL,
  nivel INTEGER NOT NULL DEFAULT 1, xp INTEGER NOT NULL DEFAULT 0, xp_total INTEGER NOT NULL DEFAULT 0,
  bits INTEGER NOT NULL DEFAULT 0, hp INTEGER NOT NULL, mp INTEGER NOT NULL, pontos INTEGER NOT NULL DEFAULT 0,
  seguidos INTEGER NOT NULL DEFAULT 0, seguidos_dia TEXT NOT NULL DEFAULT '', ultimo_fim REAL NOT NULL DEFAULT 0,
  streak INTEGER NOT NULL DEFAULT 0, streak_dia TEXT NOT NULL DEFAULT '', streak_antes INTEGER NOT NULL DEFAULT 0,
  melhor_streak INTEGER NOT NULL DEFAULT 0, ultima_perda INTEGER NOT NULL DEFAULT 0,
  titulo TEXT NOT NULL DEFAULT '', moldura TEXT NOT NULL DEFAULT '', cor_retrato TEXT NOT NULL DEFAULT '',
  tema_calor TEXT NOT NULL DEFAULT 'green', konami INTEGER NOT NULL DEFAULT 0, criado REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS atual (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  fase TEXT NOT NULL DEFAULT 'parado', quest_id INTEGER, inicio REAL NOT NULL DEFAULT 0,
  duracao REAL NOT NULL DEFAULT 0, pausado_em REAL, n INTEGER NOT NULL DEFAULT 0,
  guardado_quest INTEGER, guardado_seg REAL NOT NULL DEFAULT 0, avisou INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS arcos (
  id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE, cor TEXT NOT NULL, chefe TEXT NOT NULL DEFAULT '',
  data TEXT NOT NULL DEFAULT '', criado REAL NOT NULL, bonus_em REAL
);
CREATE TABLE IF NOT EXISTS quests (
  id INTEGER PRIMARY KEY, titulo TEXT NOT NULL, materia TEXT NOT NULL DEFAULT '',
  est INTEGER NOT NULL, dif INTEGER NOT NULL, arco_id INTEGER, arco_nome TEXT NOT NULL DEFAULT '',
  prazo TEXT NOT NULL DEFAULT '', tipo TEXT NOT NULL DEFAULT 'normal', estado TEXT NOT NULL, origem TEXT NOT NULL,
  porque TEXT NOT NULL DEFAULT '', ordem INTEGER NOT NULL DEFAULT 0, hoje INTEGER NOT NULL DEFAULT 0,
  subtarefas TEXT NOT NULL DEFAULT '[]', nota TEXT NOT NULL DEFAULT '', criada REAL NOT NULL,
  aprovada REAL, concluida REAL, daily_feita TEXT NOT NULL DEFAULT '', daily_livre TEXT NOT NULL DEFAULT '',
  xp_ganho INTEGER NOT NULL DEFAULT 0, reestimou INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS quests_estado ON quests(estado);
CREATE TABLE IF NOT EXISTS pomodoros (
  id INTEGER PRIMARY KEY, quest_id INTEGER, materia TEXT NOT NULL DEFAULT '', inicio REAL NOT NULL,
  fim REAL NOT NULL, dia TEXT NOT NULL, estado TEXT NOT NULL, minutos REAL NOT NULL,
  combo REAL NOT NULL DEFAULT 1, xp INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS pomodoros_dia ON pomodoros(dia);
CREATE INDEX IF NOT EXISTS pomodoros_quest ON pomodoros(quest_id);
CREATE TABLE IF NOT EXISTS repos (
  id INTEGER PRIMARY KEY, caminho TEXT NOT NULL UNIQUE, nome TEXT NOT NULL, materia TEXT NOT NULL DEFAULT '',
  base TEXT NOT NULL DEFAULT '', registrado REAL NOT NULL, ultimo REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS commits (
  id INTEGER PRIMARY KEY, repo_id INTEGER NOT NULL, hash TEXT NOT NULL, ts REAL NOT NULL, dia TEXT NOT NULL,
  assunto TEXT NOT NULL, tipo TEXT NOT NULL, mais INTEGER NOT NULL, menos INTEGER NOT NULL,
  vinculado INTEGER NOT NULL, pomodoro_inicio REAL, xp INTEGER NOT NULL, motivo TEXT NOT NULL DEFAULT '',
  UNIQUE (repo_id, hash)
);
CREATE INDEX IF NOT EXISTS commits_dia ON commits(dia);
CREATE TABLE IF NOT EXISTS ganhos (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, dia TEXT NOT NULL, origem TEXT NOT NULL, ref INTEGER,
  texto TEXT NOT NULL, xp INTEGER NOT NULL DEFAULT 0, bits INTEGER NOT NULL DEFAULT 0,
  hp INTEGER NOT NULL DEFAULT 0, mp INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ganhos_dia ON ganhos(dia);
CREATE TABLE IF NOT EXISTS skills (skill TEXT PRIMARY KEY, em REAL NOT NULL, custo INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS usos (skill TEXT NOT NULL, dia TEXT NOT NULL, em REAL NOT NULL, PRIMARY KEY (skill, dia));
CREATE TABLE IF NOT EXISTS efeitos (id INTEGER PRIMARY KEY, tipo TEXT NOT NULL, valor REAL NOT NULL DEFAULT 0,
  origem TEXT NOT NULL, criado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mochila (item TEXT PRIMARY KEY, qtd INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS posses (item TEXT PRIMARY KEY, em REAL NOT NULL);
CREATE TABLE IF NOT EXISTS conquistas (id TEXT PRIMARY KEY, em REAL NOT NULL);
CREATE TABLE IF NOT EXISTS notas (id INTEGER PRIMARY KEY, ts REAL NOT NULL, dia TEXT NOT NULL, quest_id INTEGER,
  texto TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS taverna (id INTEGER PRIMARY KEY, ts REAL NOT NULL, papel TEXT NOT NULL, texto TEXT NOT NULL,
  extra TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS cartas (dia TEXT PRIMARY KEY, buff TEXT NOT NULL, debuff TEXT NOT NULL,
  revelada INTEGER NOT NULL DEFAULT 0);
"""


class Banco:
    def __init__(self, caminho: Path | str, leitura: bool = False) -> None:
        self.caminho = Path(caminho)
        self.leitura = leitura
        self.memoria = False
        if leitura:
            if not self.caminho.exists():
                # sem banco ainda (serviço nunca rodou): um banco vazio em memória, com o esquema, para as telas abrirem
                self.c = sqlite3.connect(":memory:", check_same_thread=False)
                self.c.executescript(ESQUEMA)
                self.memoria = True
            else:
                self.c = sqlite3.connect(f"file:{self.caminho}?mode=ro", uri=True, timeout=5, check_same_thread=False)
                self.c.execute("PRAGMA query_only = ON")
                self.c.execute("PRAGMA cache_size = -512")  # 512 KiB: a interface lê pouco de cada vez (memória)
        else:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            self.c = sqlite3.connect(self.caminho, timeout=5, isolation_level=None, check_same_thread=False)
            self.c.execute("PRAGMA journal_mode = WAL")
            self.c.execute("PRAGMA synchronous = NORMAL")
            self.c.execute("PRAGMA cache_size = -1024")
            self.c.executescript(ESQUEMA)
            if self.meta("versao") is None:
                self.definir_meta("versao", str(VERSAO))
            self.c.execute("INSERT OR IGNORE INTO atual (id) VALUES (1)")
            try:
                self.caminho.chmod(0o600)
            except OSError:
                pass
        self.c.row_factory = sqlite3.Row
        self._nivel = 0

    @contextmanager
    def transacao(self):
        """BEGIN IMMEDIATE ... COMMIT; aninhado vira parte da transação de fora."""
        if self._nivel:
            self._nivel += 1
            try:
                yield
            finally:
                self._nivel -= 1
            return
        self.c.execute("BEGIN IMMEDIATE")
        self._nivel = 1
        try:
            yield
        except BaseException:
            self._nivel = 0
            self.c.execute("ROLLBACK")
            raise
        self._nivel = 0
        self.c.execute("COMMIT")

    def x(self, sql: str, args=()) -> sqlite3.Cursor:
        return self.c.execute(sql, args)

    def um(self, sql: str, args=()):
        return self.c.execute(sql, args).fetchone()

    def todos(self, sql: str, args=()) -> list:
        return self.c.execute(sql, args).fetchall()

    def escalar(self, sql: str, args=(), padrao=None):
        r = self.c.execute(sql, args).fetchone()
        return padrao if r is None or r[0] is None else r[0]

    def meta(self, chave: str, padrao: str | None = None) -> str | None:
        r = self.um("SELECT valor FROM meta WHERE chave = ?", (chave,))
        return r[0] if r else padrao

    def definir_meta(self, chave: str, valor: str) -> None:
        self.x("INSERT INTO meta (chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
               (chave, valor))

    def fechar(self) -> None:
        try:
            self.c.close()
        except sqlite3.Error:
            pass


def agora() -> float:
    return time.time()
