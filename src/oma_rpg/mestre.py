"""O Mestre da taverna: o Claude Code do usuário, com a skill oma-rpg.

MestreClaude roda `claude -p` (a mensagem vai pela entrada padrão, nunca pela linha de comando de um shell) só com
leitura:
- ferramentas: Bash, Read, Glob e Grep (`--tools`); Write, Edit, rede e Agent/Task não existem nem são permitidos;
- Bash só para os comandos do oma-rpg (status, quests, history, draft, editar, pastas, ls e ver);
- Read, Glob e Grep só nas pastas que o JC liberou na taverna (`--add-dir` e `Read(//pasta/**)`), com as pastas
  sensíveis negadas de novo (`--disallowedTools Read(//...)`);
- sem as configurações do usuário (`--setting-sources project`: nem o agente padrão nem as regras amplas do JC entram)
  e sem servidores MCP (`--strict-mcp-config`); o que não está liberado é negado (`--permission-mode dontAsk`).
Restringir `ls` e `find` do Bash por caminho não é seguro (`..`, links simbólicos, comandos encadeados); por isso o
Mestre lista e lê pelo `oma-rpg ls` e `oma-rpg ver`, que conferem o caminho resolvido. Mesmo que o modelo tente, o CLI
não tem como aprovar, concluir, liberar pasta ou dar XP (ver comandos.py). A saída `stream-json` vira as mensagens da
taverna; o que vem do modelo é texto, nunca marcação nem comando.

MestreFalso responde com frases prontas no --demo e cria rascunhos com o papel de Mestre.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading

from oma_rpg import caminhos

AGENTES = (
    {"id": "claude", "rotulo": "Claude Code", "comando": "claude", "modelos": ["", "sonnet", "opus", "haiku"]},
    {"id": "agy", "rotulo": "Antigravity (agy)", "comando": "agy",
     "modelos": ["", "gemini-3-pro", "gemini-3-flash", "claude-sonnet-4-6", "claude-opus-4-6"]},
    {"id": "codex", "rotulo": "Codex", "comando": "codex", "modelos": ["", "o3", "o4-mini", "gpt-4.1"]},
    {"id": "opencode", "rotulo": "OpenCode", "comando": "opencode", "modelos": [""]},
)
_POR_ID = {a["id"]: a for a in AGENTES}


def detectar_agentes(forcar: dict[str, str] | None = None) -> list[dict]:
    """Lista os agentes suportados com o executável encontrado no PATH."""
    saida = []
    for a in AGENTES:
        exe = forcar.get(a["id"]) if forcar is not None else shutil.which(a["comando"])
        saida.append({**a, "exe": exe, "disponivel": bool(exe)})
    return saida


def ler_preferencia() -> tuple[str, str]:
    """Lê (agente, modelo) salvos em ~/.config/oma-rpg/mestre.json."""
    try:
        d = json.loads(caminhos.arquivo_mestre().read_text("utf-8"))
        ag = str(d.get("agente") or "claude")
        mod = str(d.get("modelo") or "").strip()
        return (ag if ag in _POR_ID else "claude", mod)
    except (OSError, ValueError, TypeError):
        return ("claude", "")


def salvar_preferencia(agente: str, modelo: str = "") -> None:
    """Grava (agente, modelo) em ~/.config/oma-rpg/mestre.json."""
    if agente not in _POR_ID:
        return
    arq = caminhos.arquivo_mestre()
    caminhos.garantir(arq.parent)
    arq.write_text(json.dumps({"agente": agente, "modelo": modelo.strip()}, ensure_ascii=False, indent=2) + "\n", "utf-8")


PERMITIDOS = ["Bash(oma-rpg status:*)", "Bash(oma-rpg quests:*)", "Bash(oma-rpg history:*)", "Bash(oma-rpg draft:*)",
              "Bash(oma-rpg editar:*)", "Bash(oma-rpg pastas:*)", "Bash(oma-rpg ls:*)", "Bash(oma-rpg ver:*)"]
FERRAMENTAS = "Bash,Read,Glob,Grep"
BLOQUEADOS = ["Write", "Edit", "MultiEdit", "NotebookEdit", "WebFetch", "WebSearch", "Agent", "Task"]
PROMPT = (
    "Você é o Mestre do oma-rpg, um RPG de estudo. Use a skill oma-rpg se ela estiver instalada. Para o jogo, use só "
    "oma-rpg status, quests, history, draft e editar, sempre com --json. Para ver as pastas de estudo do JC, use "
    "oma-rpg pastas --json (as liberadas), oma-rpg ls PASTA --json e oma-rpg ver ARQUIVO --json; dentro delas você "
    "também pode usar Read, Glob e Grep. Só leitura: não escreva, não edite, não rode outros comandos e não delegue a "
    "subagentes. PDF grande: veja só nome e tamanho, e peça o texto (ver --texto) só do arquivo que o JC quiser. Se a "
    "pasta não estiver liberada, peça ao JC para liberar na Taverna (tecla P); o oma-rpg ls numa pasta nova também "
    "pergunta a ele. Você ajuda a definir quests (rascunhos), mas não aprova, não conclui e não dá XP: a recompensa sai "
    "da tabela do jogo e o jogador aprova pela interface. Responda em português do Brasil, curto, sem travessão, no "
    "tom da classe do herói."
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


def _regra(caminho: str) -> str:
    """Caminho absoluto na sintaxe de regra do Claude Code: `//` no começo é a raiz do sistema."""
    return "/" + caminho.rstrip("/") if caminho.startswith("/") else caminho


def _pastas_validas(pastas: list[str] | tuple) -> list[str]:
    from pathlib import Path

    from oma_rpg.nucleo import pastas as P
    validas = []
    for p in pastas:
        try:
            r = Path(os.path.realpath(p, strict=True))
        except (OSError, RuntimeError):
            continue
        if r.is_dir() and not P.motivo_sensivel(r) and str(r) not in validas:
            validas.append(str(r))
    return validas


def comando_claude(exe: str, sessao: str | None = None, pastas: list[str] | tuple = (), modelo: str = "") -> list[str]:
    """Os argumentos do `claude -p` da taverna. As pastas são conferidas de novo (nada sensível passa)."""
    from oma_rpg.nucleo import pastas as P
    validas = _pastas_validas(pastas)
    cmd = [exe, "-p", "--output-format", "stream-json", "--verbose", "--setting-sources", "project", "--strict-mcp-config",
           "--tools", FERRAMENTAS, "--permission-mode", "dontAsk", "--append-system-prompt", PROMPT]
    if modelo:
        cmd += ["--model", modelo]
    if sessao and all(c in "0123456789abcdef-" for c in sessao) and len(sessao) <= 64:
        cmd[2:2] = ["--resume", sessao]
    for p in validas:
        cmd += ["--add-dir", p]
    cmd += ["--disallowedTools", *BLOQUEADOS, *[f"Read({_regra(str(s))}/**)" for s in P.sensiveis()]]
    cmd += ["--allowedTools", *PERMITIDOS, *[f"Read({_regra(p)}/**)" for p in validas]]
    return cmd


def comando_agente(agente: str, exe: str, sessao: str | None = None, pastas: list[str] | tuple = (),
                   modelo: str = "", entrada: str = "") -> tuple[list[str], bool]:
    """Monta (argv, prompt_em_argv) para o agente escolhido."""
    if agente == "claude":
        return comando_claude(exe, sessao, pastas, modelo), False
    validas = _pastas_validas(pastas)
    sessao_ok = bool(sessao and all(c in "0123456789abcdef-" for c in sessao) and len(sessao) <= 64)
    if agente == "agy":
        cmd = [exe, "--output-format", "stream-json", "--mode", "plan"]
        if modelo:
            cmd += ["--model", modelo]
        if sessao_ok:
            cmd += ["--conversation", sessao]
        for p in validas:
            cmd += ["--add-dir", p]
        texto = entrada if sessao_ok else f"{PROMPT}\n\nPedido do JC:\n{entrada}"
        cmd.append(f"--print={texto}")
        return cmd, True
    if agente == "codex":
        cmd = [exe, "exec", "--json", "--sandbox", "read-only", "--skip-git-repo-check"]
        if modelo:
            cmd += ["-m", modelo]
        cmd.append("-")
        return cmd, False
    if agente == "opencode":
        cmd = [exe, "run", "--format", "json"]
        if modelo:
            cmd += ["-m", modelo]
        return cmd, False
    return comando_claude(exe, sessao, pastas, modelo), False


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
            if isinstance(dados, dict) and "itens" in dados:
                return f"{len(dados['itens'])} itens em {dados['pasta']}"
            if isinstance(dados, dict) and "arquivo" in dados:
                return f"{dados['arquivo']} ({dados['tamanho']} bytes)" + ("" if dados.get("conteudo") is not None else ", só metadados")
            if isinstance(dados, dict) and "pastas" in dados:
                return f"{len(dados['pastas'])} pastas liberadas"
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
    def __init__(self, exe: str | None = None, pasta=None, agente: str | None = None, modelo: str | None = None) -> None:
        super().__init__()
        ag_salvo, mod_salvo = ler_preferencia()
        self.agente = agente if agente in _POR_ID else ag_salvo
        self.modelo = (modelo if modelo is not None else mod_salvo).strip()
        self.pasta = pasta
        self._proc: subprocess.Popen | None = None
        self.sessao: str | None = None
        if exe is not None:
            self.exe = exe
        else:
            self.exe = self._resolver_exe(self.agente)
            if not self.exe:
                for info in detectar_agentes():
                    if info["disponivel"]:
                        self.agente = info["id"]
                        self.exe = info["exe"]
                        self.modelo = ""
                        break
        self.estado = "pronto" if self.exe else "ausente"

    @staticmethod
    def _resolver_exe(agente: str) -> str | None:
        cmd = _POR_ID.get(agente, {}).get("comando", "claude")
        return shutil.which(cmd)

    def rotulo(self) -> str:
        return f"{self.agente} · {self.modelo}" if self.modelo else self.agente

    def definir_agente(self, agente: str, modelo: str = "", salvar: bool = True) -> None:
        if agente not in _POR_ID:
            return
        mod = modelo.strip()
        if agente != self.agente or mod != self.modelo:
            self.sessao = None
            if self.app is not None:
                self.app.estado.definir("taverna_sessao", None)
        self.agente = agente
        self.modelo = mod
        self.exe = self._resolver_exe(agente)
        if salvar:
            salvar_preferencia(agente, mod)
        self._mudar("pronto" if self.exe else "ausente")

    def enviar(self, texto: str) -> None:
        if not self.exe:
            cmd = _POR_ID.get(self.agente, {}).get("comando", self.agente)
            self._registrar("sistema", f"O comando {cmd} não está instalado. Pressione M para escolher outro agente.")
            return
        if self.estado == "pensando":
            return
        self._registrar("voce", texto)
        self._mudar("pensando")
        pastas: list[str] = []
        if self.app is not None:  # lido aqui, na thread da interface (o banco não é dividido com a thread do agente)
            from oma_rpg.nucleo import consultas
            pastas = consultas.caminhos_liberados(self.app.b, self.app.agora())
        threading.Thread(target=self._rodar, args=(expandir(texto), pastas), daemon=True).start()

    def _rodar(self, prompt: str, pastas: list[str] | None = None) -> None:
        from oma_rpg import caminhos
        pasta = self.pasta or caminhos.garantir(caminhos.pasta_dados() / "taverna")
        if self.app is not None and not self.sessao:
            self.sessao = self.app.estado.obter("taverna_sessao")
        pendentes: dict[str, str] = {}
        respondeu = False
        try:
            entrada = prompt if (self.agente == "claude" or self.sessao) else f"{PROMPT}\n\nPedido do JC:\n{prompt}"
            argv, em_argv = comando_agente(self.agente, self.exe, self.sessao, pastas or [], self.modelo, prompt)
            self._proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL if em_argv else subprocess.PIPE,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(pasta),
                                          env={**os.environ, "OMA_RPG_MESTRE": "1"}, text=True, start_new_session=True)
            if not em_argv and self._proc.stdin is not None:
                self._proc.stdin.write(entrada)
                self._proc.stdin.close()
            for linha in self._proc.stdout:
                try:
                    d = json.loads(linha)
                except ValueError:
                    continue
                if self._tratar(d, pendentes):
                    respondeu = True
            rc = self._proc.wait(timeout=10)
            err = (self._proc.stderr.read() if self._proc.stderr else "").strip()
            if rc != 0 or not respondeu:
                detalhe = err.splitlines()[-1][:240] if err else f"código {rc}"
                self._registrar("sistema", f"O agente {self.agente} não respondeu ({detalhe}).")
        except (OSError, subprocess.SubprocessError) as e:
            self._registrar("sistema", f"O Mestre não respondeu ({type(e).__name__}).")
        finally:
            self._proc = None
            self.app._na_ui(self._mudar, "pronto") if self.app else None

    def _tratar(self, d: dict, pendentes: dict[str, str]) -> bool:
        tipo = d.get("type")
        ev = d.get("event")
        sid = d.get("session_id") or d.get("conversation_id") or d.get("thread_id")
        if not sid and isinstance(d.get("result"), dict):
            sid = d["result"].get("conversation_id")
        if sid and sid != self.sessao:
            self.sessao = sid
            if self.app is not None:
                self.app._na_ui(self.app.estado.definir, "taverna_sessao", self.sessao)
        respondeu = False
        if tipo == "assistant":
            for c in (d.get("message") or {}).get("content") or []:
                if c.get("type") == "text" and c.get("text", "").strip():
                    self._registrar("mestre", c["text"].strip())
                    respondeu = True
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
        elif tipo == "item.completed":
            item = d.get("item") or {}
            if item.get("type") == "agent_message" and item.get("text", "").strip():
                self._registrar("mestre", item["text"].strip())
                respondeu = True
            elif item.get("type") == "command_execution":
                cmd = str(item.get("command", ""))[:300]
                res = resumo_resultado(item.get("aggregated_output"))
                self._registrar("cli", cmd or "(comando)", {"resultado": res})
        elif ev == "result":
            res = d.get("result") or {}
            txt = str(res.get("response") or "").strip()
            if txt:
                self._registrar("mestre", txt)
                respondeu = True
        return respondeu

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
        self.agente = "claude"
        self.modelo = ""

    def rotulo(self) -> str:
        return f"{self.agente} · {self.modelo}" if self.modelo else self.agente

    def definir_agente(self, agente: str, modelo: str = "", salvar: bool = False) -> None:
        if agente in _POR_ID:
            self.agente = agente
            self.modelo = modelo.strip()
            self._mudar("pronto")

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
