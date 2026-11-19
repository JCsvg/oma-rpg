"""O Mestre da taverna: o Claude Code do usuário, com a skill oma-rpg.

MestreClaude roda `claude -p` (a mensagem vai pela entrada padrão, nunca pela linha de comando de um shell) com
todas as ferramentas e pastas liberadas (`--permission-mode bypassPermissions` e `--add-dir /`). Mesmo que o modelo
tente, o CLI não tem como aprovar, concluir ou dar XP (ver comandos.py). A saída `stream-json` vira as mensagens da
taverna; o que vem do modelo é texto, nunca marcação nem comando.

MestreFalso responde com frases prontas no --demo e cria rascunhos com o papel de Mestre.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading

PROMPT = (
    "Você é o Mestre do oma-rpg, um RPG de estudo. Use a skill oma-rpg se ela estiver instalada. Para interagir com o "
    "jogo, use os comandos oma-rpg status, quests, history, draft e editar, sempre com --json; você também tem acesso "
    "às ferramentas e pastas do sistema quando precisar consultar arquivos ou projetos. Você ajuda a definir quests "
    "(rascunhos), mas não aprova, não conclui e não dá XP: a recompensa sai da tabela do jogo e o jogador aprova pela "
    "interface. Responda em português do Brasil, curto, sem travessão, no tom da classe do herói."
)
ATALHOS = {
    "/revisão": "Faça a revisão semanal: rode oma-rpg status --json e oma-rpg history --days 7 --json, diga em 3 linhas o "
                "que foi bem e o que travou, leia as notas rápidas e sugira no máximo 3 rascunhos para a próxima semana.",
    "/revisao": "",
    "/rascunhos": "Rode oma-rpg quests --json e comente em uma linha cada rascunho que está esperando aprovação.",
    "/meta": "Rode oma-rpg status --json e sugira quantos pomodoros fazer ainda hoje, respeitando o teto diário e o HP.",
}
ATALHOS["/revisao"] = ATALHOS["/revisão"]


def expandir(texto: str) -> str:
    t = texto.strip()
    return ATALHOS.get(t.split()[0].lower(), t) if t.startswith("/") else t


def comando_claude(exe: str, sessao: str | None = None) -> list[str]:
    cmd = [exe, "-p", "--output-format", "stream-json", "--verbose", "--tools", "default",
           "--permission-mode", "bypassPermissions", "--add-dir", "/", "--append-system-prompt", PROMPT]
    if sessao and all(c in "0123456789abcdef-" for c in sessao) and len(sessao) <= 64:
        cmd[2:2] = ["--resume", sessao]
    return cmd


def resumo_resultado(conteudo) -> str:
    """Uma linha do que o comando devolveu (o JSON do oma-rpg vira ok/erro e o essencial)."""
    if isinstance(conteudo, list):
        conteudo = " ".join(c.get("text", "") for c in conteudo if isinstance(c, dict))
    s = str(conteudo or "").strip()
    try:
        d = json.loads(s)
        if isinstance(d, dict) and "ok" in d:
            if not d["ok"]:
                return f"erro: {d.get('erro', '')}"[:120]
            dados = d.get("dados")
            if isinstance(dados, dict) and "xp_previsto" in dados:
                return f"rascunho #{dados['id']} criado · {dados['xp_previsto']} xp (tabela do jogo)"
            if isinstance(dados, dict) and "heroi" in dados and dados["heroi"]:
                h = dados["heroi"]
                return f"hp {h['hp']}/{h['hp_max']} · nível {h['nivel']} · {dados['hoje']['pomodoros']} pomodoros hoje"
            if isinstance(dados, dict) and "quests" in dados:
                return f"{len(dados['quests'])} quests, {len(dados['rascunhos'])} rascunhos"
            if isinstance(dados, dict) and "dias" in dados:
                return f"{sum(x['pomodoros'] for x in dados['dias'])} pomodoros em {len(dados['dias'])} dias"
            return "ok"
    except ValueError:
        pass
    return s.splitlines()[0][:120] if s else ""


class _Base:
    def __init__(self) -> None:
        self.app = None
        self.estado = "pronto"
        self.ao_mudar = lambda: None

    def _mudar(self, estado: str) -> None:
        self.estado = estado
        self.ao_mudar()

    def _registrar(self, papel: str, texto: str, extra: dict | None = None) -> None:
        if self.app is None:
            return
        self.app._na_ui(self.app.pedir, "taverna", {"papel": papel, "texto": texto[:4000], **({"extra": extra} if extra else {})})

    def parar(self) -> None:
        pass


class MestreClaude(_Base):
    def __init__(self, exe: str | None = None, pasta=None) -> None:
        super().__init__()
        self.exe = exe or shutil.which("claude")
        self.pasta = pasta
        self.estado = "pronto" if self.exe else "ausente"
        self._proc: subprocess.Popen | None = None
        self.sessao: str | None = None

    def enviar(self, texto: str) -> None:
        if not self.exe:
            self._registrar("sistema", "O Claude Code não está instalado (comando claude). A taverna precisa dele.")
            return
        if self.estado == "pensando":
            return
        self._registrar("voce", texto)
        self._mudar("pensando")
        threading.Thread(target=self._rodar, args=(expandir(texto),), daemon=True).start()

    def _rodar(self, prompt: str) -> None:
        from oma_rpg import caminhos
        pasta = self.pasta or caminhos.garantir(caminhos.pasta_dados() / "taverna")
        if self.app is not None and not self.sessao:
            self.sessao = self.app.estado.obter("taverna_sessao")
        pendentes: dict[str, str] = {}
        try:
            self._proc = subprocess.Popen(comando_claude(self.exe, self.sessao), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL, cwd=str(pasta), env={**os.environ, "OMA_RPG_MESTRE": "1"},
                                          text=True, start_new_session=True)
            self._proc.stdin.write(prompt)
            self._proc.stdin.close()
            for linha in self._proc.stdout:
                try:
                    d = json.loads(linha)
                except ValueError:
                    continue
                self._tratar(d, pendentes)
            self._proc.wait(timeout=10)
        except (OSError, subprocess.SubprocessError) as e:
            self._registrar("sistema", f"O Mestre não respondeu ({type(e).__name__}).")
        finally:
            self._proc = None
            self.app._na_ui(self._mudar, "pronto") if self.app else None

    def _tratar(self, d: dict, pendentes: dict[str, str]) -> None:
        tipo = d.get("type")
        if d.get("session_id") and d.get("session_id") != self.sessao:
            self.sessao = d["session_id"]
            if self.app is not None:
                self.app._na_ui(self.app.estado.definir, "taverna_sessao", self.sessao)
        if tipo == "assistant":
            for c in (d.get("message") or {}).get("content") or []:
                if c.get("type") == "text" and c.get("text", "").strip():
                    self._registrar("mestre", c["text"].strip())
                elif c.get("type") == "tool_use":
                    cmd = str((c.get("input") or {}).get("command", c.get("name", "")))[:300]
                    pendentes[c.get("id", "")] = cmd
        elif tipo == "user":
            for c in (d.get("message") or {}).get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    cmd = pendentes.pop(c.get("tool_use_id", ""), "")
                    res = resumo_resultado(c.get("content"))
                    if c.get("is_error") and not res.startswith("erro"):
                        res = "negado: " + res
                    self._registrar("cli", cmd or "(comando)", {"resultado": res})

    def parar(self) -> None:
        p = self._proc
        if p is not None:
            try:
                p.terminate()
            except OSError:
                pass


class MestreFalso(_Base):
    """O Mestre do --demo: frases prontas, um rascunho de verdade criado com o papel de Mestre."""

    def __init__(self, cliente) -> None:
        super().__init__()
        self.cliente = cliente
        self.n = 0

    def enviar(self, texto: str) -> None:
        if self.estado == "pensando" or self.app is None:
            return
        self._registrar("voce", texto)
        self._mudar("pensando")
        self.app.set_timer(1.2, lambda: self._responder(expandir(texto)))

    def _responder(self, texto: str) -> None:
        from oma_rpg.comandos import executar
        from oma_rpg.nucleo.jogo import ErroJogo
        jogo = self.cliente.jogo
        self.n += 1
        st = executar(jogo, "status", {}, "mestre")
        self._registrar("cli", "oma-rpg status --json", {"resultado": resumo_resultado(json.dumps({"ok": True, "dados": st}))})
        try:
            r = executar(jogo, "rascunho", {"titulo": f"Revisão de flashcards de Redes ({self.n})", "materia": "Redes",
                                            "est": 1, "dif": 1, "arco": "Redes", "porque": "você pediu de manhã; 1 pomodoro basta."},
                         "mestre")
            self._registrar("cli", 'oma-rpg draft --titulo "Revisão de flashcards de Redes" --est 1 --dif 1 --json',
                            {"resultado": f"rascunho #{r['id']} criado · {r['xp_previsto']} xp (tabela do jogo)"})
            self._registrar("mestre", f"Pronto: criei o rascunho #{r['id']} para amanhã cedo. Ele vale {r['xp_previsto']} xp pela "
                                      "tabela do jogo e só conta depois que você aprovar com a.")
        except ErroJogo as e:
            self._registrar("mestre", f"Não consegui criar o rascunho: {e}.")
        for ev in jogo.soltar_eventos():
            self.cliente.ao_evento(ev)
        self._mudar("pronto")
