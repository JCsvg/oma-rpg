"""Repositórios observados: só metadados locais, por `git log`, sem rede.

O vigia usa inotify (pela libc, com ctypes) na pasta `logs` de cada .git: todo commit acrescenta uma linha em
`logs/HEAD`. Sem inotify, ou num repositório sem reflog, confere o `mtime` desses arquivos a cada 30 s.

O git roda sempre com a lista de argumentos (sem shell), com `--no-ext-diff --no-textconv` e com
`core.fsmonitor` desligado: nada configurado no repositório vira comando executado por aqui.
"""

from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
from pathlib import Path

SEP = "\x1f"
FIM = "\x1e"
COAUTOR_CLAUDE = re.compile(r"^co-authored-by:\s*claude\b", re.I | re.M)
HASH = re.compile(r"^[0-9a-f]{7,64}$")


class ErroGit(Exception):
    pass


def _git(caminho: str, *args: str, timeout: float = 8.0) -> str:
    exe = shutil.which("git")
    if not exe:
        raise ErroGit("git não está instalado")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"LC_ALL": "C", "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat"})
    cmd = [exe, "-C", caminho, "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", *args]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        raise ErroGit(f"git falhou ({type(e).__name__})") from None
    if r.returncode != 0:
        raise ErroGit(r.stderr.decode("utf-8", "replace").strip().splitlines()[-1:][0] if r.stderr else "git falhou")
    return r.stdout.decode("utf-8", "replace")


def pasta_git(caminho: str) -> Path | None:
    """A pasta .git de verdade (também a de worktree, em que .git é um arquivo `gitdir: ...`)."""
    p = Path(caminho) / ".git"
    if p.is_dir():
        return p
    if p.is_file():
        try:
            linha = p.read_text(errors="replace").strip()
        except OSError:
            return None
        if linha.startswith("gitdir:"):
            alvo = Path(linha.split(":", 1)[1].strip())
            alvo = alvo if alvo.is_absolute() else (Path(caminho) / alvo)
            return alvo.resolve() if alvo.is_dir() else None
    return None


def validar_repo(caminho: str) -> dict:
    from oma_rpg.nucleo.jogo import ErroJogo
    p = Path(os.path.expanduser(caminho))
    try:
        p = p.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ErroJogo("a pasta não existe") from None
    if not p.is_dir():
        raise ErroJogo("não é uma pasta")
    if pasta_git(str(p)) is None:
        raise ErroJogo("a pasta não é um repositório git (sem .git)")
    try:
        head = _git(str(p), "rev-parse", "--verify", "-q", "HEAD").strip()
    except ErroGit:
        head = ""  # repositório sem nenhum commit ainda
    return {"caminho": str(p), "nome": p.name, "head": head if HASH.match(head) else ""}


def email(caminho: str) -> str:
    try:
        return _git(caminho, "config", "--get", "user.email").strip().lower()
    except ErroGit:
        return ""


def ler_commits(caminho: str, base: str = "", desde: float = 0.0, limite: int = 50) -> list[dict]:
    """Commits novos de HEAD (sem merges), do mais antigo para o mais novo, só do autor configurado no repositório.

    `base` é o último commit já visto; se ele sumiu (rebase, outra branch), vale `desde` (timestamp)."""
    fmt = SEP.join(["%H", "%at", "%ae", "%s", "%b"]) + FIM
    args = ["log", "--no-merges", "--no-ext-diff", "--no-textconv", "--no-color", "--numstat",
            f"--format={FIM}{fmt}", f"-n{int(limite)}"]
    if base and HASH.match(base):
        try:
            _git(caminho, "merge-base", "--is-ancestor", base, "HEAD")
            args.append(f"{base}..HEAD")
        except ErroGit:
            args += [f"--since=@{int(desde)}", "HEAD"]
    else:
        args += [f"--since=@{int(desde)}", "HEAD"] if desde else ["HEAD"]
    try:
        saida = _git(caminho, *args)
    except ErroGit:
        return []
    meu = email(caminho)
    commits = []
    # formato: FIM <campos separados por SEP> FIM <numstat> FIM <campos> FIM <numstat> ...
    partes = saida.split(FIM)
    i = 1
    while i < len(partes) - 1:
        cab = partes[i]
        stat = partes[i + 1] if i + 1 < len(partes) else ""
        i += 2
        campos = cab.split(SEP)
        if len(campos) < 5:
            continue
        h, at, ae, assunto, corpo = campos[0].strip(), campos[1], campos[2].strip().lower(), campos[3], campos[4]
        if not HASH.match(h):
            continue
        if meu and ae != meu:
            continue
        mais = menos = 0
        for linha in stat.strip().splitlines():
            p = linha.split("\t")
            if len(p) >= 3:
                mais += int(p[0]) if p[0].isdigit() else 0
                menos += int(p[1]) if p[1].isdigit() else 0
        try:
            ts = float(at)
        except ValueError:
            continue
        if ts < desde - 1:
            continue
        commits.append({"hash": h, "ts": ts, "assunto": assunto.strip(), "corpo": corpo[:2000], "mais": mais,
                        "menos": menos, "coautor_claude": bool(COAUTOR_CLAUDE.search(corpo))})
    commits.reverse()
    return commits


# ------------------------------------------------------------ inotify
IN_MODIFY = 0x00000002
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
_EVENTO = struct.Struct("iIII")


class Inotify:
    """inotify pela libc. Se não der (ctypes, kernel, limite de watches), `ok` fica False e o vigia confere por mtime."""

    def __init__(self) -> None:
        self.fd = -1
        self.ok = False
        self._libc = None
        try:
            import ctypes
            import ctypes.util
            self._libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
            fd = self._libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
            if fd >= 0:
                self.fd, self.ok = fd, True
        except (OSError, AttributeError):
            self.ok = False

    def observar(self, pasta: str) -> int:
        if not self.ok:
            return -1
        return self._libc.inotify_add_watch(self.fd, os.fsencode(pasta), IN_MODIFY | IN_CLOSE_WRITE | IN_MOVED_TO | IN_CREATE)

    def remover(self, wd: int) -> None:
        if self.ok and wd >= 0:
            self._libc.inotify_rm_watch(self.fd, wd)

    def ler(self) -> set[int]:
        """Os descritores que mudaram (lê tudo o que está pendente)."""
        wds: set[int] = set()
        if not self.ok:
            return wds
        while True:
            try:
                dados = os.read(self.fd, 8192)
            except BlockingIOError:
                break
            except OSError:
                break
            if not dados:
                break
            i = 0
            while i + _EVENTO.size <= len(dados):
                wd, _mask, _cookie, n = _EVENTO.unpack_from(dados, i)
                wds.add(wd)
                i += _EVENTO.size + n
        return wds

    def fechar(self) -> None:
        if self.fd >= 0:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = -1


class Vigia:
    """Liga cada repositório registrado ao inotify (ou ao mtime) e diz quais pediram uma leitura."""

    def __init__(self, usar_inotify: bool = True) -> None:
        self.ino = Inotify() if usar_inotify else None
        self.wds: dict[int, int] = {}  # wd -> repo id
        self.mtimes: dict[int, float] = {}
        self.pastas: dict[int, Path] = {}

    @property
    def fd(self) -> int:
        return self.ino.fd if self.ino and self.ino.ok else -1

    def sincronizar(self, repos: list) -> None:
        ids = {r["id"] for r in repos}
        for wd, rid in list(self.wds.items()):
            if rid not in ids:
                if self.ino:
                    self.ino.remover(wd)
                del self.wds[wd]
        for rid in list(self.pastas):
            if rid not in ids:
                self.pastas.pop(rid, None)
                self.mtimes.pop(rid, None)
        for r in repos:
            if r["id"] in self.pastas:
                continue
            g = pasta_git(r["caminho"])
            if g is None:
                continue
            self.pastas[r["id"]] = g
            self.mtimes[r["id"]] = self._mtime(g)
            if self.ino and self.ino.ok:
                logs = g / "logs"
                alvo = logs if logs.is_dir() else g
                wd = self.ino.observar(str(alvo))
                if wd >= 0:
                    self.wds[wd] = r["id"]

    def _mtime(self, g: Path) -> float:
        m = 0.0
        for nome in ("logs/HEAD", "HEAD", "packed-refs"):
            try:
                m = max(m, (g / nome).stat().st_mtime)
            except OSError:
                pass
        return m

    def eventos(self) -> set[int]:
        if not self.ino:
            return set()
        return {self.wds[wd] for wd in self.ino.ler() if wd in self.wds}

    def conferir_mtime(self) -> set[int]:
        mudou = set()
        for rid, g in self.pastas.items():
            m = self._mtime(g)
            if m != self.mtimes.get(rid):
                self.mtimes[rid] = m
                mudou.add(rid)
        return mudou

    def fechar(self) -> None:
        if self.ino:
            self.ino.fechar()
