"""Pastas liberadas para o Mestre: o que pode ser liberado, o que o `ls` e o `ver` mostram, e quem pode mudar a lista."""

import os
from pathlib import Path

import pytest

from oma_rpg.comandos import ErroPapel, executar
from oma_rpg.nucleo import consultas as C
from oma_rpg.nucleo import pastas
from oma_rpg.nucleo.jogo import ErroJogo


@pytest.fixture
def estudo(tmp_path):
    """~/Projects/Codespace/Comp-Deci de mentira, com arquivos de texto, um PDF, um segredo e um link para fora."""
    e = tmp_path / "Codespace" / "Comp-Deci"
    (e / "aulas").mkdir(parents=True)
    (e / "aulas" / "aula1.md").write_text("# Árvores de decisão\nentropia e ganho\n")
    (e / "lista1.txt").write_text("1. calcule a entropia\n")
    (e / "livro.pdf").write_bytes(b"%PDF-1.4\n" + b"\x00\xff" * 50_000)
    (e / ".env").write_text("SENHA=123\n")
    (e / "chaves").mkdir()
    (e / "chaves" / "id_ed25519").write_text("segredo\n")
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "privado.txt").write_text("não pode\n")
    (e / "atalho").symlink_to(fora)
    (e / "atalho-arquivo.txt").symlink_to(fora / "privado.txt")
    return e


def test_liberar_resolve_o_caminho(estudo):
    assert pastas.validar_raiz(str(estudo)) == os.path.realpath(estudo)
    assert pastas.validar_raiz(str(estudo / "aulas") + "/") == str(estudo / "aulas")


@pytest.mark.parametrize("ruim", ["/", "~", "~/", "~/.ssh", "~/.config", "~/.config/hypr", "~/.claude", "~/.local",
                                  "~/.local/share", "/etc", "/home", "/tmp", "/usr/lib", "relativo/pasta", ""])
def test_caminho_sensivel_e_recusado_ao_liberar(ruim):
    alvo = os.path.expanduser(ruim) if ruim.startswith("~") else ruim
    if alvo and alvo.startswith("/") and not os.path.isdir(alvo):
        pytest.skip(f"{alvo} não existe nesta máquina")
    with pytest.raises(ErroJogo):
        pastas.validar_raiz(ruim)


def test_estado_e_chave_do_oma_rpg_sao_recusados():
    from oma_rpg import caminhos
    for p in (caminhos.pasta_dados(), caminhos.pasta_runtime(), caminhos.pasta_config()):
        p.mkdir(parents=True, exist_ok=True)
        with pytest.raises(ErroJogo, match="sensível"):
            pastas.validar_raiz(str(p))
        with pytest.raises(ErroJogo):
            pastas.validar_raiz(str(p.parent))  # a pasta que contém o estado também não


def test_ponto_ponto_e_recusado(estudo):
    with pytest.raises(ErroJogo, match=r"\.\."):
        pastas.validar_raiz(str(estudo / "aulas" / ".." / "aulas"))
    with pytest.raises(ErroJogo, match=r"\.\."):
        pastas.resolver(str(estudo / ".." / "fora" / "privado.txt"), [str(estudo)])


def test_fora_da_lista_e_negado(estudo, tmp_path):
    with pytest.raises(ErroJogo, match="fora das pastas liberadas"):
        pastas.listar(str(tmp_path / "fora"), [str(estudo)])
    with pytest.raises(ErroJogo, match="fora das pastas liberadas"):
        pastas.ver(str(tmp_path / "fora" / "privado.txt"), [str(estudo)])


def test_link_simbolico_para_fora_e_negado(estudo):
    with pytest.raises(ErroJogo, match="fora das pastas liberadas"):
        pastas.listar(str(estudo / "atalho"), [str(estudo)])
    with pytest.raises(ErroJogo, match="fora das pastas liberadas"):
        pastas.ver(str(estudo / "atalho-arquivo.txt"), [str(estudo)])
    itens = {i["nome"]: i for i in pastas.listar(str(estudo), [str(estudo)])["itens"]}
    assert itens["atalho"]["tipo"] == "link" and itens["atalho"]["fora"]


def test_segredos_nao_aparecem(estudo):
    d = pastas.listar(str(estudo), [str(estudo)], recursivo=True)
    nomes = {i["nome"] for i in d["itens"]}
    assert ".env" not in nomes and "chaves/id_ed25519" not in nomes and d["ocultos"] >= 2
    for alvo in (estudo / ".env", estudo / "chaves" / "id_ed25519"):
        with pytest.raises(ErroJogo, match="segredo"):
            pastas.ver(str(alvo), [str(estudo)])


def test_ls_recursivo_e_ver_texto(estudo):
    d = pastas.listar(str(estudo), [str(estudo)], recursivo=True)
    nomes = [i["nome"] for i in d["itens"]]
    assert "aulas" in nomes and "aulas/aula1.md" in nomes and nomes.index("aulas") < nomes.index("lista1.txt")
    v = pastas.ver(str(estudo / "aulas" / "aula1.md"), [str(estudo)])
    assert v["conteudo"].startswith("# Árvores de decisão") and not v["cortado"]


def test_pdf_grande_so_metadados(estudo):
    v = pastas.ver(str(estudo / "livro.pdf"), [str(estudo)])
    assert v["conteudo"] is None and v["tamanho"] > 90_000 and v["tipo"] == "pdf" and "metadados" in v["nota"]


def test_texto_grande_e_cortado(estudo):
    (estudo / "grande.txt").write_text("a" * 300_000)
    v = pastas.ver(str(estudo / "grande.txt"), [str(estudo)])
    assert len(v["conteudo"]) == pastas.LIMITE_TEXTO and v["cortado"]


# ---------------------------------------------------------------- a lista é do jogador
def test_jogador_libera_e_remove(heroi, estudo):
    r = executar(heroi, "pasta_adicionar", {"caminho": str(estudo)}, "jogador")
    assert r["caminho"] == str(estudo)
    assert C.caminhos_liberados(heroi.b, heroi.agora()) == [str(estudo)]
    executar(heroi, "pasta_remover", {"caminho": str(estudo)}, "jogador")
    assert C.caminhos_liberados(heroi.b, heroi.agora()) == []


def test_uma_vez_expira(heroi, estudo):
    executar(heroi, "pasta_adicionar", {"caminho": str(estudo), "modo": "uma_vez"}, "jogador")
    assert C.caminhos_liberados(heroi.b, heroi.agora()) == [str(estudo)]
    heroi.rel.avancar(61 * 60)
    assert C.caminhos_liberados(heroi.b, heroi.agora()) == []


@pytest.mark.parametrize("cmd,args", [("pasta_adicionar", {"caminho": "/tmp"}), ("pasta_remover", {"caminho": "/tmp"}),
                                      ("responder_pedido", {"id": 1, "resposta": "sempre"})])
def test_mestre_nao_mexe_na_lista(heroi, cmd, args):
    with pytest.raises(ErroPapel):
        executar(heroi, cmd, args, "mestre")


def test_pedido_do_mestre_nao_libera(heroi, estudo):
    r = executar(heroi, "pedir_pasta", {"caminho": str(estudo / "aulas" / "aula1.md"), "motivo": "montar as quests"}, "mestre")
    assert r["liberada"] is False and r["caminho"] == str(estudo / "aulas")
    assert C.caminhos_liberados(heroi.b, heroi.agora()) == []
    evs = heroi.soltar_eventos()
    assert any(e["evento"] == "pedido_pasta" and e["id"] == r["id"] for e in evs)
    # o mesmo pedido de novo não duplica
    assert executar(heroi, "pedir_pasta", {"caminho": str(estudo / "aulas")}, "mestre")["id"] == r["id"]
    executar(heroi, "responder_pedido", {"id": r["id"], "resposta": "sempre"}, "jogador")
    assert C.caminhos_liberados(heroi.b, heroi.agora()) == [str(estudo / "aulas")]
    assert executar(heroi, "pedir_pasta", {"caminho": str(estudo / "aulas")}, "mestre")["liberada"] is True


def test_pedido_negado_e_pedido_sensivel(heroi, estudo):
    r = executar(heroi, "pedir_pasta", {"caminho": str(estudo)}, "mestre")
    executar(heroi, "responder_pedido", {"id": r["id"], "resposta": "negar"}, "jogador")
    assert heroi.b.um("SELECT estado FROM pedidos_pasta WHERE id = ?", (r["id"],))[0] == "negado"
    assert C.caminhos_liberados(heroi.b, heroi.agora()) == []
    with pytest.raises(ErroJogo):
        executar(heroi, "pedir_pasta", {"caminho": str(Path.home() / ".ssh")}, "mestre")


# ---------------------------------------------------------------- os argumentos do claude da taverna
def test_argumentos_do_claude_batem_com_a_lista(estudo, tmp_path):
    from oma_rpg.mestre import comando_claude
    outra = tmp_path / "outra"
    outra.mkdir()
    cmd = comando_claude("claude", "abc-123", [str(estudo), str(outra), str(Path.home()), "/", str(tmp_path / "nao-existe")])
    adds = [cmd[i + 1] for i, x in enumerate(cmd) if x == "--add-dir"]
    assert adds == [str(estudo), str(outra)]  # a home, a raiz e o que não existe ficam de fora
    i_allow = cmd.index("--allowedTools")
    i_deny = cmd.index("--disallowedTools")
    permitidos = cmd[i_allow + 1:]
    negados = cmd[i_deny + 1:i_allow]
    assert [p for p in permitidos if p.startswith("Read(")] == [f"Read(/{estudo}/**)", f"Read(/{outra}/**)"]
    assert all(p.startswith("Bash(oma-rpg ") for p in permitidos if p.startswith("Bash("))
    assert {"Bash(oma-rpg ls:*)", "Bash(oma-rpg ver:*)", "Bash(oma-rpg pastas:*)"} <= set(permitidos)
    assert "Bash" not in permitidos and not any(p in permitidos for p in ("Write", "Edit", "Agent", "Task", "Glob", "Grep"))
    assert {"Write", "Edit", "Agent", "Task", "WebFetch", "WebSearch"} <= set(negados)
    assert f"Read(/{Path(os.path.realpath(Path.home() / '.ssh'))}/**)" in negados
    assert cmd[cmd.index("--tools") + 1] == "Bash,Read,Glob,Grep"
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    assert "--strict-mcp-config" in cmd and cmd[cmd.index("--setting-sources") + 1] == "project"
    assert "bypassPermissions" not in cmd and "--dangerously-skip-permissions" not in cmd
    assert cmd[cmd.index("--resume") + 1] == "abc-123"


def test_sem_pasta_liberada_nao_ha_add_dir():
    from oma_rpg.mestre import comando_claude
    cmd = comando_claude("claude", None, [])
    assert "--add-dir" not in cmd and not any(x.startswith("Read(") for x in cmd[cmd.index("--allowedTools"):])
