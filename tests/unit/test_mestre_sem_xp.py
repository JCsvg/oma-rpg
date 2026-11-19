"""O Mestre (Claude Code, pela skill e pelo CLI) ajuda a definir quests, mas não dá XP.

A garantia está em três lugares e os três são testados aqui:
1. a tabela de comandos: o papel mestre só tem leitura e rascunho;
2. o motor: nenhum comando recebe valor de recompensa, e XP só entra no livro com origem de pomodoro ou commit;
3. o CLI: não existe subcomando para aprovar, concluir, comprar ou mexer no herói.
"""

import pytest

from oma_rpg.comandos import COMANDOS, DO_MESTRE, ErroPapel, executar
from oma_rpg.nucleo.jogo import ErroJogo
from tests.conftest import pomodoro

RECURSOS = ("nivel", "xp", "xp_total", "bits", "hp", "mp", "pontos", "streak", "classe", "titulo")


def foto(j):
    h = j.heroi()
    return ({k: h[k] for k in RECURSOS},
            j.b.escalar("SELECT COUNT(*) FROM ganhos WHERE xp != 0 OR bits != 0 OR hp != 0 OR mp != 0", (), 0),
            [r[0] for r in j.b.todos("SELECT skill FROM skills ORDER BY skill")],
            j.b.todos("SELECT id, estado FROM quests ORDER BY id"))


ARGS_MESTRE = {
    "ping": [{}],
    "status": [{}],
    "quests": [{}, {"arco": "TCC"}],
    "historico": [{"dias": 30}],
    "rascunho": [{"titulo": "Seção 2.1 do TCC", "materia": "TCC", "est": 3, "dif": 3, "arco": "TCC",
                  "prazo": "2026-11-20", "porque": "a parte mais longa"}],
    "editar_rascunho": [{"id": 0, "est": 2}],
}


def test_papel_mestre_so_le_e_cria_rascunho():
    assert DO_MESTRE == {"ping", "status", "quests", "historico", "rascunho", "editar_rascunho"}


@pytest.mark.parametrize("cmd", sorted(set(COMANDOS) - DO_MESTRE))
def test_todo_comando_de_jogador_e_recusado_ao_mestre(heroi, cmd):
    antes = foto(heroi)
    with pytest.raises(ErroPapel):
        executar(heroi, cmd, {}, "mestre")
    assert foto(heroi) == antes


def test_nada_que_o_mestre_faz_muda_o_heroi(heroi):
    j = heroi
    q = j.nova_quest(titulo="Ler: inferência de tipos", materia="Compiladores", est=2, dif=2)
    pomodoro(j, quest=q["id"])
    antes_heroi = foto(j)[0]
    antes_livro = foto(j)[1]
    rid = None
    for cmd, lista in ARGS_MESTRE.items():
        for a in lista:
            a = dict(a)
            if cmd == "editar_rascunho":
                a["id"] = rid
            r = executar(j, cmd, a, "mestre")
            if cmd == "rascunho":
                rid = r["id"]
                assert r["xp_previsto"] == 77 and r["bits_previstos"] == 19
    depois = foto(j)
    assert depois[0] == antes_heroi and depois[1] == antes_livro
    assert j.b.um("SELECT estado FROM quests WHERE id = ?", (rid,))[0] == "rascunho"


@pytest.mark.parametrize("extra", [{"xp": 500}, {"bits": 999}, {"recompensa": "500 xp"}, {"xp_previsto": 500},
                                   {"hp": 100}, {"nivel": 99}, {"pontos": 9}])
def test_o_mestre_nao_escolhe_a_recompensa(heroi, extra):
    a = {"titulo": "põe 500 xp nessa", "materia": "TCC", "est": 1, "dif": 1, **extra}
    with pytest.raises(ErroJogo, match="tabela do jogo"):
        executar(heroi, "rascunho", a, "mestre")
    assert heroi.b.escalar("SELECT COUNT(*) FROM quests", (), 0) == 0


def test_rascunho_nao_vale_nada_ate_o_jogador_aprovar(heroi):
    j = heroi
    r = executar(j, "rascunho", {"titulo": "Revisão de Redes", "materia": "Redes", "est": 2, "dif": 2}, "mestre")
    # o Mestre não aprova nem conclui
    for cmd in ("aprovar", "concluir_quest", "iniciar", "aprovar_todos"):
        with pytest.raises(ErroPapel):
            executar(j, cmd, {"id": r["id"]} if cmd in ("aprovar", "concluir_quest") else {}, "mestre")
    # pomodoro numa quest em rascunho não começa
    with pytest.raises(ErroJogo):
        j.iniciar(r["id"])
    executar(j, "aprovar", {"id": r["id"]}, "jogador")
    assert j.heroi()["xp_total"] == 0  # aprovar também não dá XP: só os pomodoros depois


def test_editar_rascunho_nao_mexe_em_quest_aprovada(heroi):
    j = heroi
    q = executar(j, "nova_quest", {"titulo": "Minha", "est": 1, "dif": 1}, "jogador")
    with pytest.raises(ErroJogo):
        executar(j, "editar_rascunho", {"id": q["id"], "est": 8}, "mestre")


def test_xp_so_entra_por_pomodoro_e_commit(heroi):
    """Rodando todos os comandos de jogador que existem, o XP só mexe com pomodoro concluído no relógio."""
    j = heroi
    j.b.x("UPDATE heroi SET bits = 2000, pontos = 3, mp = 60")
    q = executar(j, "nova_quest", {"titulo": "A", "est": 1, "dif": 1}, "jogador")
    for cmd, a in [("aprender", {"skill": "git_stash"}), ("aprender", {"skill": "hotfix"}), ("usar_skill", {"skill": "hotfix"}),
                   ("comprar", {"item": "cafe"}), ("usar_item", {"item": "cafe"}), ("comprar", {"item": "titulo_cafe"}),
                   ("equipar", {"item": "titulo_cafe"}), ("marcar_hoje", {"id": q["id"]}), ("novo_arco", {"nome": "Arco"}),
                   ("nota", {"texto": "anotação"}), ("concluir_quest", {"id": q["id"]})]:
        executar(j, cmd, a, "jogador")
    assert j.heroi()["xp_total"] == 0
    pomodoro(j)
    assert j.heroi()["xp_total"] > 0
    assert {r[0] for r in j.b.todos("SELECT DISTINCT origem FROM ganhos WHERE xp > 0")} == {"pomodoro"}


def test_commit_com_coautor_claude_nao_da_xp(heroi):
    j = heroi
    j.b.x("INSERT INTO repos (id, caminho, nome, registrado) VALUES (1, '/tmp/x', 'x', 0)")
    repo = j.b.um("SELECT * FROM repos")
    j.iniciar()
    j.rel.avancar(60)
    r = j.observar_commit(repo, {"hash": "a" * 40, "ts": j.agora(), "assunto": "feat: tudo", "mais": 30, "menos": 2,
                                 "coautor_claude": True})
    assert r["xp"] == 0 and "Claude" in r["motivo"]
    r = j.observar_commit(repo, {"hash": "b" * 40, "ts": j.agora(), "assunto": "feat: meu", "mais": 3, "menos": 1})
    assert r["xp"] == 9 and r["vinculado"]


def test_comando_desconhecido_e_argumento_estranho(heroi):
    with pytest.raises(ErroJogo):
        executar(heroi, "dar_xp", {"xp": 1000}, "jogador")
    with pytest.raises(ErroJogo):
        executar(heroi, "status", {"xp": 1}, "mestre")
    with pytest.raises(ErroJogo):
        executar(heroi, "iniciar", {"quest": 1, "duracao": 1}, "jogador")
    with pytest.raises(ErroPapel):
        executar(heroi, "status", {}, "admin")
