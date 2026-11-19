"""Testes da escolha de agente e modelo da taverna."""

from __future__ import annotations

from oma_rpg import mestre


def test_preferencia_agente_e_modelo_salva_e_le():
    assert mestre.ler_preferencia() == ("claude", "")
    mestre.salvar_preferencia("agy", "gemini-3-pro")
    assert mestre.ler_preferencia() == ("agy", "gemini-3-pro")


def test_comando_agente_para_cada_cli(tmp_path):
    pasta = tmp_path / "estudo"
    pasta.mkdir()

    argv_c, pref_c = mestre.comando_agente("claude", "/bin/claude", sessao="abc-123", pastas=[str(pasta)], modelo="sonnet")
    assert "--model" in argv_c and "sonnet" in argv_c
    assert "--resume" in argv_c and "abc-123" in argv_c
    assert "--add-dir" in argv_c and str(pasta.resolve()) in argv_c
    assert pref_c is False

    argv_a, pref_a = mestre.comando_agente("agy", "/bin/agy", sessao=None, pastas=[str(pasta)], modelo="gemini-3-pro")
    assert argv_a[:4] == ["/bin/agy", "-p", "--output-format", "stream-json"]
    assert "--model" in argv_a and "gemini-3-pro" in argv_a
    assert "--add-dir" in argv_a and str(pasta.resolve()) in argv_a
    assert pref_a is True

    argv_a2, pref_a2 = mestre.comando_agente("agy", "/bin/agy", sessao="abcd-1234", pastas=[], modelo="")
    assert "--conversation" in argv_a2 and "abcd-1234" in argv_a2
    assert pref_a2 is False

    argv_x, pref_x = mestre.comando_agente("codex", "/bin/codex", sessao=None, pastas=[], modelo="o4-mini")
    assert argv_x[:5] == ["/bin/codex", "exec", "--json", "--sandbox", "read-only"]
    assert "-m" in argv_x and "o4-mini" in argv_x
    assert argv_x[-1] == "-"
    assert pref_x is True


def test_detectar_agentes_e_definir_limpa_sessao(monkeypatch):
    monkeypatch.setattr(mestre.shutil, "which", lambda cmd: f"/usr/bin/{cmd}" if cmd in ("claude", "agy") else None)
    lista = {a["id"]: a for a in mestre.detectar_agentes()}
    assert lista["claude"]["disponivel"] is True
    assert lista["agy"]["disponivel"] is True
    assert lista["codex"]["disponivel"] is False

    m = mestre.MestreClaude(agente="claude", modelo="")
    m.sessao = "sessao-antiga"
    m.definir_agente("agy", "gemini-3-flash")
    assert m.agente == "agy"
    assert m.modelo == "gemini-3-flash"
    assert m.rotulo() == "agy · gemini-3-flash"
    assert m.sessao is None
    assert m.estado == "pronto"
