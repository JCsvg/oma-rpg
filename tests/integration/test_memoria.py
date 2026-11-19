"""Memória (VmRSS) dos processos de verdade.

A interface roda `python -m oma_rpg --demo` num pseudo-terminal de 180x48: em repouso e depois de usar (os 7 painéis,
as classes, abas, camadas, busca, ajuda, árvore, loja, mapa e taverna). O serviço roda `python -m oma_rpg servico` com o
banco do demo (um ano de histórico) e um repositório git observado, em repouso.
Metas do JC: interface em repouso até 55 MB e em uso até 85 MB; serviço em repouso até 40 MB.
"""

import fcntl
import json
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

import pytest

from tests.conftest import env_sub

TETO_REPOUSO_MB = 55
TETO_USO_MB = 85
TETO_SERVICO_MB = 40
RAIZ = Path(__file__).parents[2]
CTRL = {"dir": "\x1b[1;5C", "esq": "\x1b[1;5D", "cima": "\x1b[1;5A", "baixo": "\x1b[1;5B"}
ALT_DIR, ALT_ESQ = "\x1b[1;3C", "\x1b[1;3D"


def rss_mb(pid) -> float:
    for linha in Path(f"/proc/{pid}/status").read_text().splitlines():
        if linha.startswith("VmRSS"):
            return int(linha.split()[1]) / 1024
    return 0.0


@pytest.mark.skipif(not Path("/proc/self/status").exists(), reason="precisa de /proc")
def test_rss_da_interface_em_repouso_e_depois_de_usar(tmp_path):
    fd, escravo = pty.openpty()
    fcntl.ioctl(escravo, termios.TIOCSWINSZ, struct.pack("HHHH", 48, 180, 0, 0))
    env = dict(env_sub(tmp_path), TERM="xterm-256color", COLORTERM="truecolor")
    for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        os.makedirs(env[k], exist_ok=True)
    proc = subprocess.Popen([sys.executable, "-m", "oma_rpg", "--demo", "--sem-abertura"], stdin=escravo, stdout=escravo,
                            stderr=escravo, env=env, start_new_session=True)
    os.close(escravo)

    def drenar(seg: float) -> None:
        fim = time.time() + seg
        while time.time() < fim:
            if select.select([fd], [], [], 0.05)[0]:
                try:
                    os.read(fd, 65536)
                except OSError:
                    return

    def teclas(*ts, pausa=0.15):
        for t in ts:
            os.write(fd, t.encode())
            drenar(pausa)
    try:
        drenar(7)
        assert proc.poll() is None
        repouso = rss_mb(proc.pid)
        for rodada in range(4):
            for n in "1234567":
                teclas("\x1b" + n, pausa=0.4)
                teclas(CTRL["dir"], CTRL["baixo"], "j", "j", "k", CTRL["esq"], CTRL["cima"], CTRL["baixo"])
            teclas("\x1b4", pausa=0.4)
            teclas("j", "l", "l", "k", ALT_DIR, ALT_DIR, ALT_ESQ, ALT_ESQ, "c", pausa=0.3)
            teclas(ALT_DIR, ALT_DIR, "\r", pausa=0.4)
            teclas("\x1b5", pausa=0.4)
            teclas("j", "j", ALT_DIR, "j", ALT_DIR, ALT_ESQ, ALT_ESQ, "k")
            teclas("\x1b6", pausa=0.4)
            teclas("h", "h", "j", ALT_DIR, ALT_DIR, ALT_ESQ, ALT_ESQ, "]", "[", "\r")
            teclas("\x1b3", pausa=0.4)
            teclas(ALT_DIR, ALT_DIR, ALT_DIR, ALT_ESQ, ALT_ESQ, ALT_ESQ, "j", "j")
            teclas("\x1bOP", pausa=0.3)
            teclas("\x1b", pausa=0.3)
            teclas("/", *"redes", pausa=0.08)
            teclas("\x1b", pausa=0.4)
            if rodada % 2:
                teclas("\x1b7", pausa=0.6)
                teclas(*"me ajuda com a semana", "\r", pausa=0.08)
                drenar(2)
        drenar(3)
        uso = rss_mb(proc.pid)
        print(f"\nRSS da interface: repouso {repouso:.1f} MB, depois de usar {uso:.1f} MB")
        assert proc.poll() is None
        assert 0 < repouso <= TETO_REPOUSO_MB
        assert uso <= TETO_USO_MB
    finally:
        try:
            os.write(fd, b"q")
            drenar(1)
        except OSError:
            pass
        proc.kill()
        proc.wait(5)
        os.close(fd)


@pytest.mark.skipif(not Path("/proc/self/status").exists(), reason="precisa de /proc")
def test_rss_do_servico_em_repouso(tmp_path, cfg):
    env = env_sub(tmp_path)
    for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        os.makedirs(env[k], exist_ok=True)
    # o banco do demo (um ano de histórico) no lugar do banco real do teste, e um repositório git de verdade
    from oma_rpg.falso import popular
    from oma_rpg.nucleo.banco import Banco
    dados = Path(env["XDG_DATA_HOME"]) / "oma-rpg"
    b = Banco(dados / "rpg.sqlite3")
    popular(b, cfg, "pausa")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    b.x("UPDATE repos SET caminho = ? WHERE id = 1", (str(repo),))
    b.fechar()
    proc = subprocess.Popen([sys.executable, "-m", "oma_rpg", "servico"], env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
    try:
        sock = Path(env["XDG_RUNTIME_DIR"]) / "oma-rpg" / "servico.sock"
        fim = time.time() + 15
        while time.time() < fim and not sock.exists():
            time.sleep(0.1)
        assert sock.exists()
        r = subprocess.run([sys.executable, "-m", "oma_rpg", "status", "--json"], env=env, capture_output=True, text=True, timeout=20)
        assert json.loads(r.stdout)["dados"]["heroi"]["nome"] == "yahiro"
        r = subprocess.run([sys.executable, "-m", "oma_rpg", "draft", "--titulo", "x", "--est", "1", "--dif", "1", "--json"],
                           env=env, capture_output=True, text=True, timeout=20)
        assert json.loads(r.stdout)["ok"]
        time.sleep(3)
        repouso = rss_mb(proc.pid)
        print(f"\nRSS do serviço: {repouso:.1f} MB com um ano de histórico e um repositório observado")
        assert proc.poll() is None
        assert 0 < repouso <= TETO_SERVICO_MB
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
