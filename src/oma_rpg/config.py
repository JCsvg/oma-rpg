"""Valores do jogo: balanceamento.toml e conteudo.toml do pacote, com ~/.config/oma-rpg/balanceamento.toml por cima.

O arquivo do usuário só troca valores que já existem e com o mesmo tipo (número por número, texto por texto).
Chave desconhecida ou tipo errado é ignorado e anotado em `avisos`, para um erro de digitação não derrubar o serviço.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

AQUI = Path(__file__).parent


def _ler(p: Path) -> dict:
    with open(p, "rb") as f:
        return tomllib.load(f)


def _mesclar(base: dict, novo: dict, caminho: str, avisos: list[str]) -> None:
    for k, v in novo.items():
        onde = f"{caminho}.{k}" if caminho else k
        if k not in base:
            avisos.append(f"chave desconhecida: {onde}")
            continue
        atual = base[k]
        if isinstance(atual, dict):
            if isinstance(v, dict):
                _mesclar(atual, v, onde, avisos)
            else:
                avisos.append(f"tipo errado: {onde}")
        elif isinstance(atual, bool) or isinstance(v, bool):
            if isinstance(atual, bool) and isinstance(v, bool):
                base[k] = v
            else:
                avisos.append(f"tipo errado: {onde}")
        elif isinstance(atual, (int, float)) and isinstance(v, (int, float)):
            base[k] = type(atual)(v) if isinstance(atual, float) else (int(v) if float(v).is_integer() else float(v))
        elif isinstance(atual, str) and isinstance(v, str):
            base[k] = v[:300]
        elif isinstance(atual, list) and isinstance(v, list) and all(isinstance(x, str) for x in v):
            base[k] = [x[:200] for x in v][:20]
        else:
            avisos.append(f"tipo errado: {onde}")


class Config(dict):
    """Um dicionário com as seções dos dois arquivos. `avisos` lista o que foi ignorado do arquivo do usuário."""

    avisos: list[str]

    @classmethod
    def carregar(cls, usuario: Path | None = None, usar_usuario: bool = True) -> "Config":
        c = cls(_ler(AQUI / "balanceamento.toml"))
        c.update(_ler(AQUI / "conteudo.toml"))
        c.avisos = []
        if usar_usuario:
            if usuario is None:
                from oma_rpg import caminhos
                usuario = caminhos.arquivo_balanceamento_usuario()
            try:
                dados = _ler(usuario)
            except FileNotFoundError:
                dados = {}
            except (OSError, tomllib.TOMLDecodeError) as e:
                c.avisos.append(f"{usuario.name} ilegível ({type(e).__name__}); usando o padrão")
                dados = {}
            _mesclar(c, dados, "", c.avisos)
        return c

    def v(self, secao: str, chave: str):
        return self[secao][chave]

    # atalhos para o conteúdo
    def classe(self, cid: str) -> dict:
        return self["classes"][cid]

    def classes_ordem(self) -> list[str]:
        return sorted(self["classes"], key=lambda c: self["classes"][c]["ordem"])

    def skill(self, sid: str) -> dict:
        return self["skills"][sid]

    def skills_da_classe(self, cid: str) -> list[str]:
        s = self["skills"]
        return sorted((k for k in s if s[k]["classe"] == cid), key=lambda k: (s[k]["ramo"], s[k]["pos"]))

    def item(self, iid: str) -> dict:
        return self["itens"][iid]

    def itens_da_categoria(self, cat: str) -> list[str]:
        it = self["itens"]
        return sorted((k for k in it if it[k]["categoria"] == cat), key=lambda k: it[k]["ordem"])
