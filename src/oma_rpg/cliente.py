"""Clientes do serviço.

ClienteServico: o socket Unix, com uma thread de leitura. A interface se apresenta com a chave de jogador; o CLI nunca
lê a chave e fica com o papel de Mestre.
ClienteLocal: o motor no mesmo processo, para o --demo e os testes da interface. Passa pela mesma tabela de comandos
e papéis do serviço.

Nos dois, `depois(ok, resultado)` pode rodar em outra thread: quem chama (a interface) cuida de voltar para a sua.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from oma_rpg import caminhos


def iniciar_servico_padrao() -> str:
    exe = shutil.which("systemctl")
    if exe:
        try:
            r = subprocess.run([exe, "--user", "start", "oma-rpg.service"], capture_output=True, timeout=10)
            if r.returncode == 0:
                return "systemd"
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        subprocess.Popen([sys.executable, "-m", "oma_rpg", "servico"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, env={**os.environ})
        return "processo"
    except OSError:
        return ""


class ClienteServico:
    demo = False

    def __init__(self, socket_path: Path | None = None, chave_path: Path | None = None, papel: str = "jogador",
                 iniciar=iniciar_servico_padrao) -> None:
        self.socket_path = Path(socket_path or caminhos.arquivo_socket())
        self.chave_path = Path(chave_path or caminhos.arquivo_chave())
        self.papel_pedido = papel
        self.papel = "mestre"
        self.iniciar = iniciar
        self.ao_evento = lambda d: None
        self._sock: socket.socket | None = None
        self._lk = threading.Lock()
        self._pend: dict[int, object] = {}
        self._n = 0
        self.conectado = False

    def conectar(self) -> bool:
        if self.conectado:
            return True
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        try:
            s.connect(str(self.socket_path))
        except OSError:
            s.close()
            return False
        s.settimeout(None)
        self._sock = s
        self.conectado = True
        threading.Thread(target=self._ler, args=(s,), daemon=True, name="socket").start()
        if self.papel_pedido == "jogador":
            try:
                chave = self.chave_path.read_text().strip()
            except OSError:
                chave = ""
            pronto = threading.Event()

            def ola(ok, r):
                if ok and isinstance(r, dict):
                    self.papel = r.get("papel", "mestre")
                pronto.set()
            self.pedir("ola", {"chave": chave}, ola)
            pronto.wait(2.0)
        return True

    def garantir_servico(self, espera: float = 4.0) -> str:
        if self.conectar():
            return "rodando"
        como = self.iniciar() if self.iniciar else ""
        fim = time.monotonic() + espera
        while time.monotonic() < fim:
            time.sleep(0.15)
            if self.conectar():
                return como or "rodando"
        return ""

    def _ler(self, s: socket.socket) -> None:
        arq = s.makefile("rb")
        try:
            for linha in arq:
                try:
                    d = json.loads(linha)
                except ValueError:
                    continue
                if "evento" in d:
                    self.ao_evento(d)
                elif "id" in d:
                    with self._lk:
                        f = self._pend.pop(d["id"], None)
                    if f is not None:
                        f(bool(d.get("ok")), d.get("r") if d.get("ok") else d.get("erro", "erro"))
        except (OSError, ValueError):
            pass
        self.conectado = False
        with self._lk:
            pend, self._pend = self._pend, {}
        for f in pend.values():
            f(False, "O serviço do oma-rpg parou.")
        self.ao_evento({"evento": "desconectado"})

    def pedir(self, cmd: str, args: dict | None = None, depois=None) -> None:
        if not self.conectado and not self.conectar():
            if depois:
                threading.Thread(target=depois, args=(False, "O serviço do oma-rpg não está rodando."), daemon=True).start()
            return
        with self._lk:
            self._n += 1
            rid = self._n
            if depois:
                self._pend[rid] = depois
        try:
            self._sock.sendall((json.dumps({"id": rid, "cmd": cmd, "args": args or {}}, ensure_ascii=False) + "\n").encode())
        except OSError:
            with self._lk:
                self._pend.pop(rid, None)
            self.conectado = False
            if depois:
                threading.Thread(target=depois, args=(False, "O serviço do oma-rpg não está rodando."), daemon=True).start()

    def pedir_e_esperar(self, cmd: str, args: dict | None = None, tempo: float = 5.0):
        """Para o CLI: devolve (ok, resultado)."""
        ev = threading.Event()
        caixa: list = []

        def fim(ok, r):
            caixa.append((ok, r))
            ev.set()
        self.pedir(cmd, args, fim)
        if not ev.wait(tempo):
            return False, "o serviço não respondeu"
        return caixa[0]

    def tick(self) -> None:
        pass

    def fechar(self) -> None:
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
                self._sock.close()
            except OSError:
                pass


class ClienteLocal:
    """O motor no mesmo processo (demo e testes). `tick` precisa ser chamado pela interface enquanto há relógio rodando."""

    demo = True
    conectado = True

    def __init__(self, jogo, papel: str = "jogador") -> None:
        self.jogo = jogo
        self.papel = papel
        self.ao_evento = lambda d: None

    def conectar(self) -> bool:
        return True

    def garantir_servico(self, espera: float = 0) -> str:
        return "rodando"

    def _soltar(self) -> None:
        for ev in self.jogo.soltar_eventos():
            self.ao_evento(ev)

    def pedir(self, cmd: str, args: dict | None = None, depois=None) -> None:
        from oma_rpg.comandos import executar
        from oma_rpg.nucleo.jogo import ErroJogo
        try:
            r = executar(self.jogo, cmd, args or {}, self.papel)
            ok = True
        except ErroJogo as e:
            r, ok = str(e), False
        self._soltar()
        if depois:
            depois(ok, r)

    def tick(self) -> None:
        self.jogo.tick()
        self._soltar()

    def fechar(self) -> None:
        pass
