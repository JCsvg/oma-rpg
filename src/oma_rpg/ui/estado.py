"""Contexto da interface em $XDG_RUNTIME_DIR/oma-rpg/estado.json (tmpfs: some no reboot).

Guarda só posição: painel aberto, aba, camada e período do mapa, categoria da loja. Nunca texto de quest, de
nota ou da taverna. Copiado do oma-mail (que veio do oma-spotify), com outra lista de chaves proibidas.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from oma_rpg import caminhos

VERSAO = 1
PROIBIDAS = re.compile(r"(token|secret|senha|chave|pass|texto|nota|mensagem|titulo)", re.I)


class Estado:
    def __init__(self, pasta: Path | None = None) -> None:
        self.pasta = pasta or caminhos.pasta_runtime()
        self.dados: dict = {}

    @property
    def arquivo(self) -> Path:
        return self.pasta / "estado.json"

    @property
    def marcador(self) -> Path:
        return self.pasta / "abertura-mostrada"

    def preparar(self) -> None:
        caminhos.garantir(self.pasta)

    def ja_abriu(self) -> bool:
        return self.marcador.exists()

    def marcar_abertura(self) -> None:
        try:
            self.preparar()
            self.marcador.write_text("1")
        except OSError:
            pass

    def carregar(self) -> dict:
        """Arquivo ausente, corrompido ou de outra versão: começa do zero, sem erro."""
        try:
            bruto = json.loads(self.arquivo.read_text())
            if isinstance(bruto, dict) and bruto.get("versao") == VERSAO and isinstance(bruto.get("dados"), dict):
                self.dados = bruto["dados"]
                return self.dados
        except (OSError, ValueError):
            pass
        self.dados = {}
        return self.dados

    def salvar(self) -> None:
        try:
            self.preparar()
            tmp = self.arquivo.with_suffix(".tmp")
            tmp.write_text(json.dumps({"versao": VERSAO, "dados": self.dados}, ensure_ascii=False))
            os.replace(tmp, self.arquivo)
        except OSError:
            pass

    def definir(self, chave: str, valor) -> None:
        if PROIBIDAS.search(chave):
            return
        if self.dados.get(chave) != valor:
            self.dados[chave] = valor
            self.salvar()

    def obter(self, chave: str, padrao=None):
        return self.dados.get(chave, padrao)
