"""Serviço em segundo plano (oma-rpg servico, unidade systemd de usuário oma-rpg.service).

Uma thread só, um laço com `selectors`: o socket Unix, os clientes, o inotify dos repositórios e o relógio. Em repouso
(sem pomodoro e sem commit), o laço dorme até a virada do dia, no máximo 60 s por volta, e confere o mtime dos
repositórios a cada 30 s quando não há inotify.

Protocolo, uma linha JSON por mensagem: pedido {"id", "cmd", "args"}; resposta {"id", "ok", "r"} ou {"id", "ok": false,
"erro"}; aviso {"evento", ...} para todos os clientes. O primeiro pedido pode ser {"cmd": "ola", "args": {"chave"}}:
com a chave de $XDG_RUNTIME_DIR/oma-rpg/jogador.chave (0600, nova a cada início) a conexão vira papel jogador; sem ela,
é Mestre e só lê e cria rascunhos. O socket é 0600 e o serviço confere o usuário do outro lado (SO_PEERCRED).
"""

from __future__ import annotations

import fcntl
import hmac
import json
import logging
import os
import secrets
import selectors
import shutil
import signal
import socket
import struct
import subprocess
import time
from pathlib import Path

from oma_rpg import __version__, caminhos
from oma_rpg.comandos import ErroPapel, executar
from oma_rpg.nucleo.jogo import ErroJogo

log = logging.getLogger("oma-rpg")
MAX_LINHA = 256 * 1024
MAX_CLIENTES = 16
INTERVALO_MTIME = 30.0


def _escapar(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def notificar_padrao(titulo: str, corpo: str) -> None:
    """notify-send (o mako mostra). Texto escapado: título de quest não vira marcação."""
    exe = shutil.which("notify-send")
    if not exe:
        return
    try:
        subprocess.Popen([exe, "-a", "oma-rpg", "-i", "appointment-soon", _escapar(titulo)[:120], _escapar(corpo)[:300]],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        pass


class _Cliente:
    __slots__ = ("sock", "buf", "papel")

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.buf = b""
        self.papel = "mestre"


class Servico:
    def __init__(self, jogo=None, socket_path: Path | None = None, chave_path: Path | None = None, notificar=None,
                 usar_inotify: bool = True, banco_path: Path | None = None, cfg=None) -> None:
        if jogo is None:
            from oma_rpg.config import Config
            from oma_rpg.nucleo.banco import Banco
            from oma_rpg.nucleo.jogo import Jogo
            cfg = cfg or Config.carregar()
            for aviso in cfg.avisos:
                log.warning("balanceamento: %s", aviso)
            jogo = Jogo(Banco(banco_path or caminhos.arquivo_banco()), cfg)
        self.jogo = jogo
        self.jogo.notificar = notificar or notificar_padrao
        self.socket_path = Path(socket_path or caminhos.arquivo_socket())
        self.chave_path = Path(chave_path or caminhos.arquivo_chave())
        self.chave = secrets.token_hex(24)
        self.sel = selectors.DefaultSelector()
        self.clientes: dict[int, _Cliente] = {}
        self._sock: socket.socket | None = None
        self._r, self._w = os.pipe()
        os.set_blocking(self._r, False)
        os.set_blocking(self._w, False)
        from oma_rpg.nucleo.git import Vigia
        self.vigia = Vigia(usar_inotify=usar_inotify)
        self._parar = False
        self._thread = None
        self._ult_mtime = 0.0
        self._ler_repos: dict[int, float] = {}  # repo id -> quando ler (debounce do inotify)

    # ------------------------------------------------------------ ciclo de vida
    def iniciar(self, em_thread: bool = True) -> None:
        caminhos.garantir(self.socket_path.parent)
        try:
            self.socket_path.unlink()
        except FileNotFoundError:
            pass
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        antiga = os.umask(0o177)
        try:
            s.bind(str(self.socket_path))
            self._gravar_chave()
        finally:
            os.umask(antiga)
        os.chmod(self.socket_path, 0o600)
        s.listen(8)
        s.setblocking(False)
        self._sock = s
        self.sel.register(s, selectors.EVENT_READ, "aceitar")
        self.sel.register(self._r, selectors.EVENT_READ, "acordar")
        self._recarregar_repos()
        if self.vigia.fd >= 0:
            self.sel.register(self.vigia.fd, selectors.EVENT_READ, "inotify")
        self._tick()
        if em_thread:
            import threading
            self._thread = threading.Thread(target=self.laco, name="servico", daemon=True)
            self._thread.start()

    def _gravar_chave(self) -> None:
        fd = os.open(self.chave_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(self.chave)
        os.chmod(self.chave_path, 0o600)

    def acordar(self) -> None:
        """Acorda o laço (testes com relógio falso, sinal de parar)."""
        try:
            os.write(self._w, b"x")
        except OSError:
            pass

    def encerrar(self) -> None:
        self._parar = True
        self.acordar()
        if self._thread is not None:
            self._thread.join(5)
        for c in list(self.clientes.values()):
            self._fechar(c)
        if self._sock is not None:
            try:
                self.sel.unregister(self._sock)
            except (KeyError, ValueError):
                pass
            self._sock.close()
        for p in (self.socket_path, self.chave_path):
            try:
                p.unlink()
            except OSError:
                pass
        self.vigia.fechar()
        try:
            self.sel.close()
        except OSError:
            pass
        for fd in (self._r, self._w):
            try:
                os.close(fd)
            except OSError:
                pass

    # ------------------------------------------------------------ laço
    def laco(self) -> None:
        while not self._parar:
            espera = self._espera()
            try:
                eventos = self.sel.select(espera)
            except (OSError, ValueError):
                if self._parar:
                    break
                raise
            for chave, _ in eventos:
                tipo = chave.data
                if tipo == "aceitar":
                    self._aceitar()
                elif tipo == "acordar":
                    try:
                        os.read(self._r, 4096)
                    except OSError:
                        pass
                elif tipo == "inotify":
                    agora = time.monotonic()
                    for rid in self.vigia.eventos():
                        self._ler_repos.setdefault(rid, agora + 1.5)
                elif isinstance(tipo, _Cliente):
                    self._ler(tipo)
            if self._parar:
                break
            try:
                self._tick()
            except Exception:
                log.exception("falha no tick")

    def _espera(self) -> float:
        e = self.jogo.proxima_espera(60.0)
        agora = time.monotonic()
        if self._ler_repos:
            e = min(e, max(0.05, min(self._ler_repos.values()) - agora))
        if self.vigia.fd < 0 and self.vigia.pastas:
            e = min(e, max(0.05, self._ult_mtime + INTERVALO_MTIME - agora))
        return max(0.05, e)

    def _tick(self) -> None:
        agora = time.monotonic()
        if self.vigia.fd < 0 and self.vigia.pastas and agora - self._ult_mtime >= INTERVALO_MTIME:
            self._ult_mtime = agora
            for rid in self.vigia.conferir_mtime():
                self._ler_repos.setdefault(rid, agora)
        prontos = [rid for rid, t in self._ler_repos.items() if t <= agora]
        for rid in prontos:
            del self._ler_repos[rid]
            self.ler_repo(rid)
        self.jogo.tick()
        self._difundir_eventos()

    def ler_repo(self, rid: int) -> int:
        """Lê os commits novos de um repositório e passa ao motor. Devolve quantos eram novos."""
        from oma_rpg.nucleo import git
        b = self.jogo.b
        r = b.um("SELECT * FROM repos WHERE id = ?", (rid,))
        if r is None:
            return 0
        desde = max(r["registrado"], r["ultimo"] - 86400)
        novos = 0
        try:
            commits = git.ler_commits(r["caminho"], base=r["base"], desde=desde)
        except Exception:
            log.warning("repositório %d: leitura falhou", rid)
            return 0
        for c in commits:
            if c["ts"] < r["registrado"] - 1:
                continue
            try:
                if self.jogo.observar_commit(r, c) is not None:
                    novos += 1
            except ErroJogo:
                continue
        if commits:
            b.x("UPDATE repos SET base = ? WHERE id = ?", (commits[-1]["hash"], rid))
        return novos

    def _recarregar_repos(self) -> None:
        repos = self.jogo.b.todos("SELECT * FROM repos")
        self.vigia.sincronizar(repos)

    # ------------------------------------------------------------ socket
    def _aceitar(self) -> None:
        while True:
            try:
                c, _ = self._sock.accept()
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                return
            try:
                cred = c.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
                _, uid, _ = struct.unpack("3i", cred)
            except OSError:
                uid = -1
            if uid != os.getuid() or len(self.clientes) >= MAX_CLIENTES:
                c.close()
                continue
            c.setblocking(False)
            cli = _Cliente(c)
            self.clientes[c.fileno()] = cli
            self.sel.register(c, selectors.EVENT_READ, cli)

    def _fechar(self, cli: _Cliente) -> None:
        try:
            self.sel.unregister(cli.sock)
        except (KeyError, ValueError):
            pass
        self.clientes.pop(cli.sock.fileno(), None)
        try:
            cli.sock.close()
        except OSError:
            pass

    def _ler(self, cli: _Cliente) -> None:
        try:
            dados = cli.sock.recv(65536)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            dados = b""
        if not dados:
            self._fechar(cli)
            return
        cli.buf += dados
        if len(cli.buf) > MAX_LINHA and b"\n" not in cli.buf:
            self._fechar(cli)
            return
        while b"\n" in cli.buf:
            linha, cli.buf = cli.buf.split(b"\n", 1)
            try:
                p = json.loads(linha)
            except ValueError:
                continue
            if isinstance(p, dict):
                self._tratar(cli, p)
        self._difundir_eventos()

    def _enviar(self, cli: _Cliente, d: dict) -> bool:
        dados = (json.dumps(d, ensure_ascii=False, default=str) + "\n").encode()
        try:
            cli.sock.setblocking(True)
            cli.sock.settimeout(2.0)
            cli.sock.sendall(dados)
            cli.sock.setblocking(False)
            return True
        except OSError:
            self._fechar(cli)
            return False

    def _tratar(self, cli: _Cliente, p: dict) -> None:
        rid, cmd, args = p.get("id"), p.get("cmd"), p.get("args") or {}
        if cmd == "ola":
            chave = args.get("chave") if isinstance(args, dict) else None
            if isinstance(chave, str) and hmac.compare_digest(chave.encode(), self.chave.encode()):
                cli.papel = "jogador"
            self._enviar(cli, {"id": rid, "ok": True, "r": {"papel": cli.papel, "versao": __version__}})
            return
        try:
            r = executar(self.jogo, cmd, args, cli.papel)
            if cmd in ("repo_adicionar", "repo_remover"):
                self._recarregar_repos()
                if self.vigia.fd >= 0:
                    try:
                        self.sel.register(self.vigia.fd, selectors.EVENT_READ, "inotify")
                    except (KeyError, ValueError):
                        pass
            self._enviar(cli, {"id": rid, "ok": True, "r": r})
        except ErroPapel as e:
            self._enviar(cli, {"id": rid, "ok": False, "erro": str(e), "papel": True})
        except ErroJogo as e:
            self._enviar(cli, {"id": rid, "ok": False, "erro": str(e)})
        except (KeyError, ValueError, TypeError) as e:
            self._enviar(cli, {"id": rid, "ok": False, "erro": f"pedido inválido ({type(e).__name__})"})
        except Exception as e:  # não derruba o serviço
            log.exception("falha em %s", cmd)
            self._enviar(cli, {"id": rid, "ok": False, "erro": f"falha inesperada ({type(e).__name__})"})

    def _difundir_eventos(self) -> None:
        for ev in self.jogo.soltar_eventos():
            for cli in list(self.clientes.values()):
                self._enviar(cli, ev)


def rodar() -> int:
    """Ponto de entrada do `oma-rpg servico`."""
    logging.basicConfig(level=os.environ.get("OMA_RPG_LOG", "WARNING").upper(), format="%(levelname)s %(message)s")
    pasta = caminhos.garantir(caminhos.pasta_runtime())
    trava = open(pasta / "servico.lock", "w")
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("oma-rpg: o serviço já está rodando.")
        return 0
    caminhos.garantir(caminhos.pasta_dados())
    s = Servico()
    s.iniciar(em_thread=False)

    def parar(*_):
        s._parar = True
        s.acordar()
    signal.signal(signal.SIGTERM, parar)
    signal.signal(signal.SIGINT, parar)
    try:
        s.laco()
    finally:
        s.encerrar()
        trava.close()
    return 0
