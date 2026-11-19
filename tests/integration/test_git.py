"""Repositório git temporário observado pelo serviço: commit solto 30%, dentro do pomodoro 100% com CI verde,
`closes quest-N`, autor de fora ignorado e o inotify acordando o serviço."""

import os
import random
import subprocess
import time

import pytest

from oma_rpg.nucleo import git
from oma_rpg.nucleo.jogo import ErroJogo, Jogo, Relogio
from oma_rpg.servico import Servico

pytestmark = pytest.mark.skipif(subprocess.run(["which", "git"], capture_output=True).returncode != 0, reason="sem git")


def g(repo, *args, data=None, email="jc@exemplo.org"):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_AUTHOR_NAME": "JC", "GIT_AUTHOR_EMAIL": email, "GIT_COMMITTER_NAME": "JC",
                "GIT_COMMITTER_EMAIL": email, "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(repo.parent)})
    if data is not None:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"@{int(data)} +0000"
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, env=env).stdout


def commit(repo, nome, msg, linhas=3, data=None, email="jc@exemplo.org"):
    (repo / nome).write_text("\n".join(f"linha {i}" for i in range(linhas)) + "\n")
    g(repo, "add", nome)
    g(repo, "commit", "-q", "-m", msg, data=data, email=email)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "work" / "compiladores"
    r.mkdir(parents=True)
    g(r, "init", "-q", "-b", "main")
    g(r, "config", "user.email", "jc@exemplo.org")
    g(r, "config", "user.name", "JC")
    commit(r, "a.txt", "chore: começo")
    return r


@pytest.fixture
def jogo_real(tmp_path, cfg):
    from oma_rpg.nucleo.banco import Banco
    cfg["conquistas"] = {}
    j = Jogo(Banco(tmp_path / "rpg.sqlite3"), cfg, Relogio(), random.Random(2))
    j.criar_heroi("yahiro", "programa")
    yield j
    j.b.fechar()


def test_ler_commits_so_os_novos_e_do_autor(repo):
    base = git.validar_repo(str(repo))["head"]
    assert len(base) == 40
    commit(repo, "b.txt", "feat(tipos): unificação de variáveis livres", linhas=5)
    commit(repo, "c.txt", "fix: coisa de outra pessoa", email="outra@exemplo.org")
    cs = git.ler_commits(str(repo), base=base)
    assert [c["assunto"] for c in cs] == ["feat(tipos): unificação de variáveis livres"]
    assert cs[0]["mais"] == 5 and cs[0]["menos"] == 0 and not cs[0]["coautor_claude"]


def test_repo_invalido(tmp_path):
    with pytest.raises(ErroJogo):
        git.validar_repo(str(tmp_path / "nao-existe"))
    (tmp_path / "pasta").mkdir()
    with pytest.raises(ErroJogo):
        git.validar_repo(str(tmp_path / "pasta"))


def test_commit_solto_vale_30_e_dentro_do_pomodoro_100_com_ci_verde(repo, jogo_real, tmp_path):
    j = jogo_real
    j.repo_adicionar(str(repo), "Compiladores")
    s = Servico(jogo=j, socket_path=tmp_path / "run" / "s.sock", chave_path=tmp_path / "run" / "c", usar_inotify=False,
                notificar=lambda t, c: None)
    rid = j.b.um("SELECT id FROM repos")[0]
    commit(repo, "b.txt", "feat: solto", linhas=4)
    assert s.ler_repo(rid) == 1
    assert j.b.um("SELECT xp, vinculado FROM commits")[:] == (2, 0)  # 7 × 0,3
    q = j.nova_quest(titulo="Ler: inferência de tipos", materia="Compiladores", est=2, dif=2)
    j.iniciar(q["id"])
    commit(repo, "c.txt", "feat(tipos): unificação", linhas=4)
    commit(repo, "d.txt", "test: casos de let", linhas=2)
    commit(repo, "e.txt", "chore: formata", linhas=2)
    assert s.ler_repo(rid) == 3
    xps = [r[0] for r in j.b.todos("SELECT xp FROM commits ORDER BY id")]
    assert xps == [2, 9, 6, 0]
    assert s.ler_repo(rid) == 0  # nada novo
    q2 = j.nova_quest(titulo="Outra matéria", materia="Redes", est=1, dif=1)
    j.abandonar()
    j.iniciar(q2["id"])
    commit(repo, "f.txt", "feat: em pomodoro de Redes", linhas=3)
    s.ler_repo(rid)
    assert j.b.um("SELECT xp, vinculado FROM commits ORDER BY id DESC")[:] == (2, 0)  # matéria diferente: solto
    s.encerrar()


def test_closes_quest_conclui_sozinha(repo, jogo_real, tmp_path):
    j = jogo_real
    j.repo_adicionar(str(repo), "")
    s = Servico(jogo=j, socket_path=tmp_path / "run" / "s.sock", chave_path=tmp_path / "run" / "c", usar_inotify=False,
                notificar=lambda t, c: None)
    q = j.nova_quest(titulo="Lista 4", materia="Compiladores", est=1, dif=1)
    j.b.x("INSERT INTO pomodoros (quest_id, materia, inicio, fim, dia, estado, minutos, combo, xp) "
          "VALUES (?, 'Compiladores', ?, ?, ?, 'feito', 25, 1, 24)", (q["id"], time.time() - 3000, time.time() - 1500, j.hoje()))
    commit(repo, "g.txt", f"feat: lista pronta\n\ncloses quest-{q['id']}")
    s.ler_repo(j.b.um("SELECT id FROM repos")[0])
    assert j.b.um("SELECT estado FROM quests WHERE id = ?", (q["id"],))[0] == "feita"
    assert j.b.um("SELECT xp FROM ganhos WHERE origem = 'quest'")[0] == 14
    s.encerrar()


def test_commit_antigo_nao_conta(repo, jogo_real, tmp_path):
    """O que já existia antes de registrar o repositório não vira XP."""
    j = jogo_real
    commit(repo, "x.txt", "feat: de ontem", data=time.time() - 86400)
    j.repo_adicionar(str(repo), "")
    s = Servico(jogo=j, socket_path=tmp_path / "run" / "s.sock", chave_path=tmp_path / "run" / "c", usar_inotify=False)
    assert s.ler_repo(j.b.um("SELECT id FROM repos")[0]) == 0
    s.encerrar()


def test_inotify_acorda_o_servico(repo, jogo_real, tmp_path):
    j = jogo_real
    j.repo_adicionar(str(repo), "")
    s = Servico(jogo=j, socket_path=tmp_path / "run" / "s.sock", chave_path=tmp_path / "run" / "c",
                notificar=lambda t, c: None)
    if s.vigia.fd < 0:
        s.encerrar()
        pytest.skip("sem inotify neste kernel")
    s.iniciar()
    commit(repo, "h.txt", "feat: visto pelo inotify", linhas=2)
    from oma_rpg.nucleo.banco import Banco
    leitor = Banco(j.b.caminho, leitura=True)
    fim = time.time() + 6
    n = 0
    while time.time() < fim:
        n = leitor.escalar("SELECT COUNT(*) FROM commits", (), 0)
        if n:
            break
        time.sleep(0.1)
    leitor.fechar()
    s.encerrar()
    assert n == 1
