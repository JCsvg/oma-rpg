"""Pastas liberadas para o Mestre ler (só leitura, com as subpastas).

Regras, todas conferidas no caminho já resolvido (`realpath`, que segue os links simbólicos):
- Caminho absoluto (ou com ~), sem nenhum componente `..`.
- Nunca libera `/`, a home, nem pasta que contenha a home ou uma pasta sensível (liberar ~/.local abriria
  ~/.local/share/oma-rpg). Sensíveis: as pastas escondidas da home (~/.ssh, ~/.config, ~/.claude, ~/.gnupg...), o
  estado, a configuração e o runtime do próprio oma-rpg (banco e chave do jogador) e as pastas do sistema.
- Ler (`ls`, `ver`) só vale para alvo cujo caminho resolvido fica dentro de uma pasta liberada: um link simbólico que
  aponta para fora é negado. Arquivos com cara de segredo (.env, chaves, credenciais) nunca são mostrados.
- Arquivo binário ou grande mostra só os metadados; o texto de um PDF sai só com `--texto`, pelo pdftotext.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import time
from pathlib import Path

from oma_rpg.nucleo.jogo import ErroJogo

LIMITE_TEXTO = 200_000       # bytes de texto devolvidos por arquivo
LIMITE_ITENS = 300           # entradas por listagem
PROFUNDIDADE_MAX = 4
SISTEMA = ("/etc", "/root", "/proc", "/sys", "/dev", "/boot", "/run", "/var", "/usr", "/bin", "/sbin", "/lib", "/lib64",
           "/srv", "/lost+found")
SEGREDO = re.compile(r"(^\.env($|\.)|\.pem$|\.key$|\.p12$|\.pfx$|\.kdbx$|^id_(rsa|dsa|ecdsa|ed25519)|^\.netrc$|^\.pgpass$|"
                     r"credentials|secret|\.gpg$|\.asc$)", re.I)
BINARIOS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip", ".gz", ".tar", ".xz", ".7z", ".rar", ".mp3", ".mp4",
            ".mkv", ".ogg", ".wav", ".exe", ".so", ".o", ".a", ".bin", ".class", ".jar", ".pyc", ".sqlite", ".sqlite3", ".db",
            ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".epub", ".iso"}


def _real(p: str | Path, estrito: bool = False) -> Path:
    return Path(os.path.realpath(p, strict=estrito))


def home() -> Path:
    return _real(Path.home())


def sensiveis() -> list[Path]:
    from oma_rpg import caminhos
    h = Path.home()
    lista = [h / ".ssh", h / ".gnupg", h / ".config", h / ".claude", h / ".password-store", h / ".aws", h / ".kube",
             h / ".docker", h / ".mozilla", h / ".local", caminhos.pasta_dados(), caminhos.pasta_config(),
             caminhos.pasta_runtime()]
    lista += [Path(s) for s in SISTEMA]
    xdg_rt = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_rt:
        lista.append(Path(xdg_rt))
    return [_real(p) for p in lista]


def _dentro(p: Path, raiz: Path) -> bool:
    return p == raiz or raiz in p.parents


def _bruto(caminho: str) -> Path:
    if not isinstance(caminho, str) or not caminho.strip():
        raise ErroJogo("caminho vazio")
    if "\x00" in caminho:
        raise ErroJogo("caminho inválido")
    p = Path(os.path.expanduser(caminho.strip()))
    if not p.is_absolute():
        raise ErroJogo("use o caminho completo (começando com / ou ~)")
    if ".." in p.parts:
        raise ErroJogo("caminho com .. recusado")
    return p


def motivo_sensivel(p: Path) -> str:
    """Por que esta pasta (já resolvida) não pode ser liberada; vazio se pode."""
    h = home()
    if p == Path("/") or _dentro(h, p):
        return "o oma-rpg nunca libera a raiz, a home nem uma pasta que contenha a home"
    if p in (Path("/tmp"), Path("/mnt"), Path("/media"), Path("/opt")):
        return "pasta inteira do sistema: libere uma subpasta"
    for s in sensiveis():
        if _dentro(p, s) or _dentro(s, p):
            return f"pasta sensível ({s}): o oma-rpg nunca libera"
    if _dentro(p, h):
        primeira = p.relative_to(h).parts[0] if p != h else ""
        if primeira.startswith("."):
            return "pastas escondidas da home (configurações e chaves) não são liberadas"
    return ""


def validar_raiz(caminho: str) -> str:
    """Resolve e confere uma pasta antes de liberar. Devolve o caminho absoluto resolvido."""
    p = _bruto(caminho)
    try:
        r = _real(p, estrito=True)
    except (OSError, RuntimeError):
        raise ErroJogo("a pasta não existe") from None
    if not r.is_dir():
        raise ErroJogo("não é uma pasta")
    m = motivo_sensivel(r)
    if m:
        raise ErroJogo(m)
    return str(r)


def resolver(alvo: str, raizes: list[str]) -> tuple[Path, Path]:
    """(alvo resolvido, pasta liberada que o contém). Levanta ErroJogo se estiver fora, se não existir ou se for segredo."""
    p = _bruto(alvo)
    try:
        r = _real(p, estrito=True)
    except (OSError, RuntimeError):
        raise ErroJogo("não existe") from None
    for raiz in raizes:
        try:
            rr = _real(raiz, estrito=True)
        except (OSError, RuntimeError):
            continue
        if motivo_sensivel(rr):
            continue
        if _dentro(r, rr):
            if any(SEGREDO.search(parte) for parte in r.relative_to(rr).parts):
                raise ErroJogo("arquivo com cara de segredo (.env, chave, credencial): não é mostrado")
            return r, rr
    raise ErroJogo("fora das pastas liberadas")


def pasta_pedida(alvo: str) -> str:
    """A pasta que faz sentido pedir para liberar a partir de um alvo (o próprio, se for pasta; senão a pasta dele)."""
    p = _bruto(alvo)
    r = _real(p)
    if r.is_file():
        r = r.parent
    return str(r)


def _tipo(e: os.DirEntry | Path) -> str:
    try:
        if e.is_symlink():
            return "link"
        if e.is_dir():
            return "pasta"
    except OSError:
        return "?"
    return "arquivo"


def listar(alvo: str, raizes: list[str], recursivo: bool = False, profundidade: int = 2) -> dict:
    r, raiz = resolver(alvo, raizes)
    if not r.is_dir():
        raise ErroJogo("não é uma pasta: use oma-rpg ver para arquivos")
    profundidade = max(1, min(PROFUNDIDADE_MAX, int(profundidade))) if recursivo else 1
    itens: list[dict] = []
    ocultos = 0
    cortado = False

    def andar(d: Path, nivel: int) -> None:
        nonlocal ocultos, cortado
        try:
            entradas = sorted(os.scandir(d), key=lambda e: (_tipo(e) != "pasta", e.name.lower()))
        except OSError:
            return
        for e in entradas:
            if len(itens) >= LIMITE_ITENS:
                cortado = True
                return
            if e.name.startswith(".") or SEGREDO.search(e.name):
                ocultos += 1
                continue
            tipo = _tipo(e)
            item = {"nome": str(Path(e.path).relative_to(r)), "tipo": tipo}
            if tipo == "link":
                try:
                    destino = _real(e.path)
                    item["fora"] = not _dentro(destino, raiz)
                except OSError:
                    item["fora"] = True
            elif tipo == "arquivo":
                try:
                    item["tamanho"] = e.stat(follow_symlinks=False).st_size
                except OSError:
                    item["tamanho"] = 0
            itens.append(item)
            if tipo == "pasta" and nivel < profundidade:
                andar(Path(e.path), nivel + 1)
    andar(r, 1)
    return {"pasta": str(r), "itens": itens, "ocultos": ocultos, "cortado": cortado}


def _parece_binario(p: Path) -> bool:
    if p.suffix.lower() in BINARIOS:
        return True
    try:
        with open(p, "rb") as f:
            cabeca = f.read(8192)
    except OSError:
        return True
    if b"\x00" in cabeca:
        return True
    try:
        cabeca.decode("utf-8")
    except UnicodeDecodeError as e:
        return e.start < len(cabeca) - 4  # um caractere cortado no fim do bloco não é binário
    return False


def ver(alvo: str, raizes: list[str], texto: bool = False) -> dict:
    r, _ = resolver(alvo, raizes)
    if r.is_dir():
        raise ErroJogo("é uma pasta: use oma-rpg ls")
    try:
        st = r.stat()
    except OSError:
        raise ErroJogo("não consegui ler o arquivo") from None
    if not stat.S_ISREG(st.st_mode):
        raise ErroJogo("não é um arquivo comum")
    meta = {"arquivo": str(r), "tamanho": st.st_size, "modificado": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
            "tipo": r.suffix.lower().lstrip(".") or "sem extensão"}
    binario = _parece_binario(r)
    if binario:
        if not texto:
            meta["conteudo"] = None
            meta["nota"] = "binário: só os metadados (peça o texto com --texto, só se precisar)"
            return meta
        if r.suffix.lower() != ".pdf":
            meta["conteudo"] = None
            meta["nota"] = "binário sem extrator de texto"
            return meta
        exe = shutil.which("pdftotext")
        if not exe:
            meta["conteudo"] = None
            meta["nota"] = "o texto de PDF precisa do pdftotext (poppler)"
            return meta
        try:
            out = subprocess.run([exe, "-q", "-enc", "UTF-8", str(r), "-"], capture_output=True, timeout=20,
                                 stdin=subprocess.DEVNULL).stdout
        except (OSError, subprocess.SubprocessError):
            raise ErroJogo("o pdftotext falhou") from None
        meta["conteudo"] = out[:LIMITE_TEXTO].decode("utf-8", "replace")
        meta["cortado"] = len(out) > LIMITE_TEXTO
        return meta
    with open(r, "rb") as f:
        dados = f.read(LIMITE_TEXTO + 1)
    meta["conteudo"] = dados[:LIMITE_TEXTO].decode("utf-8", "replace")
    meta["cortado"] = len(dados) > LIMITE_TEXTO
    return meta
