"""Linha de comando.

oma-rpg                         abre a interface (e inicia o serviço se ele não estiver rodando)
oma-rpg --demo                  dados inventados, sem serviço e sem mexer no estado real
oma-rpg servico                 o serviço em segundo plano (é o que a unidade oma-rpg.service roda)

O contrato do Mestre (Claude Code), sempre com --json:
oma-rpg status [--json|--barra]                           herói, combo, HP, pomodoros de hoje; sem opção, uma linha para a barra
oma-rpg quests [--arco X] [--json]                        quests e rascunhos
oma-rpg history --days 30 [--json]                        pomodoros e commits por dia
oma-rpg draft --titulo ... --materia ... --est 2 --dif 2 [--arco X] [--prazo AAAA-MM-DD] [--porque ...] [--json]
oma-rpg editar ID [--titulo ...] [--est N] [--dif N] ... [--json]     edita um rascunho que ainda não foi aprovado
oma-rpg pastas [--json]                                   as pastas que o JC liberou para o Mestre ler
oma-rpg ls PASTA [-r] [--json]                            lista uma pasta liberada (só leitura)
oma-rpg ver ARQUIVO [--texto] [--json]                    mostra um arquivo de pasta liberada (binário: só metadados)

Resposta com --json: {"ok": true, "dados": ...} ou {"ok": false, "erro": "..."}.
Nenhum subcomando aprova, conclui, compra, libera pasta ou muda XP, Bits, HP, nível ou skills: isso é só pela interface.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from oma_rpg import __version__

SUBCOMANDOS = ("servico", "serviço", "status", "quests", "history", "historico", "histórico", "draft", "rascunho", "editar",
               "pastas", "ls", "ver")


def _saida(ok: bool, dados, como_json: bool, texto: str = "") -> int:
    if como_json:
        d = {"ok": True, "dados": dados} if ok else {"ok": False, "erro": str(dados)}
        print(json.dumps(d, ensure_ascii=False))
    elif ok:
        print(texto)
    else:
        print(f"oma-rpg: {dados}", file=sys.stderr)
    return 0 if ok else 1


def _leitura():
    from oma_rpg import caminhos
    from oma_rpg.config import Config
    from oma_rpg.nucleo.banco import Banco
    return Banco(caminhos.arquivo_banco(), leitura=True), Config.carregar()


def linha_barra(st: dict) -> tuple[str, str, str]:
    """(texto, dica, classe) curtos para a barra."""
    from oma_rpg.nucleo.consultas import mmss
    if not st.get("heroi"):
        return "oma-rpg", "crie o herói: oma-rpg", "vazio"
    h, p, hoje = st["heroi"], st["pomodoro"], st["hoje"]
    dica = (f"{h['nome']} · nível {h['nivel']} · vida {h['hp']}/{h['hp_max']} · mana {h['mp']}/{h['mp_max']} · "
            f"{hoje['pomodoros']} de {hoje['meta']} pomodoros")
    if p["fase"] == "foco":
        if p["pausado"]:
            return f"⏸ {mmss(p['restante_s'])}", dica, "pausado"
        return f"● {mmss(p['restante_s'])} x{h['combo']:.1f}", dica + (f" · {p['quest']}" if p["quest"] else ""), "foco"
    if p["fase"] in ("pausa", "longa"):
        return f"☕ {mmss(p['restante_s'])}", dica, "pausa"
    if p["fase"] == "desmaio":
        return f"✗ {mmss(p['restante_s'])}", dica, "desmaio"
    return f"nv {h['nivel']} · ♥ {h['hp']} · {hoje['pomodoros']}/{hoje['meta']}", dica, "parado"


def cmd_status(a) -> int:
    from oma_rpg.nucleo import consultas as C
    b, cfg = _leitura()
    st = C.status(b, cfg, time.time())
    b.fechar()
    if a.barra:
        t, dica, classe = linha_barra(st)
        pct = 0
        if st.get("heroi"):
            pct = round(100 * st["hoje"]["pomodoros"] / max(1, st["hoje"]["meta"]))
        print(json.dumps({"text": t, "tooltip": dica, "class": classe, "alt": classe, "percentage": min(100, pct)},
                         ensure_ascii=False))
        return 0
    t, _, _ = linha_barra(st)
    return _saida(True, st, a.json, t)


def cmd_quests(a) -> int:
    from oma_rpg.comandos import _quests
    from oma_rpg.nucleo import consultas as C
    from oma_rpg.nucleo.jogo import ErroJogo
    b, cfg = _leitura()

    class _J:  # leitura não precisa do motor
        pass
    j = _J()
    j.b, j.cfg = b, cfg
    j.hoje = lambda: C.dia_de(time.time())
    try:
        d = _quests(j, {"arco": a.arco} if a.arco else {})
    except ErroJogo as e:
        return _saida(False, e, a.json)
    finally:
        b.fechar()
    linhas = []
    for q in d["rascunhos"] + d["quests"]:
        marca = {"rascunho": "?", "feita": "✓", "aberta": " "}.get(q["estado"], " ")
        linhas.append(f"{marca} #{q['id']:<4} {q['titulo'][:48]:<48} {q['materia'][:14]:<14} {q['feitos']}/{q['est']} "
                      f"dif {q['dif']}  +{q['xp']} xp  +{q['bits']} bits")
    return _saida(True, d, a.json, "\n".join(linhas) or "nenhuma quest")


def cmd_history(a) -> int:
    from oma_rpg.nucleo import consultas as C
    b, cfg = _leitura()
    try:
        dias = max(1, min(400, int(a.days)))
        d = {"dias": C.historico(b, cfg, time.time(), dias)}
    finally:
        b.fechar()
    linhas = [f"{x['dia']}  {x['pomodoros']:>2} pomodoros  {x['commits']:>2} commits" for x in d["dias"]]
    return _saida(True, d, a.json, "\n".join(linhas))


def _pedir_mestre(cmd: str, args: dict):
    """Pelo serviço, como Mestre; sem serviço, abre o banco e roda o mesmo comando com o mesmo papel."""
    from oma_rpg.cliente import ClienteServico
    c = ClienteServico(papel="mestre", iniciar=None)
    if c.conectar():
        try:
            return c.pedir_e_esperar(cmd, args)
        finally:
            c.fechar()
    from oma_rpg import caminhos
    from oma_rpg.comandos import executar
    from oma_rpg.config import Config
    from oma_rpg.nucleo.banco import Banco
    from oma_rpg.nucleo.jogo import ErroJogo, Jogo
    caminhos.garantir(caminhos.pasta_dados())
    b = Banco(caminhos.arquivo_banco())
    try:
        return True, executar(Jogo(b, Config.carregar()), cmd, args, "mestre")
    except ErroJogo as e:
        return False, str(e)
    finally:
        b.fechar()


def _campos(a, parcial: bool) -> dict:
    d = {}
    for k in ("titulo", "materia", "est", "dif", "arco", "prazo", "porque"):
        v = getattr(a, k, None)
        if v is not None or not parcial:
            if v is not None:
                d[k] = v
    return d


def cmd_draft(a) -> int:
    ok, r = _pedir_mestre("rascunho", _campos(a, parcial=False))
    t = f"rascunho #{r['id']} criado: +{r['xp_previsto']} xp, +{r['bits_previstos']} bits (tabela do jogo)" if ok else ""
    return _saida(ok, r, a.json, t)


def cmd_editar(a) -> int:
    d = _campos(a, parcial=True)
    d["id"] = a.id
    ok, r = _pedir_mestre("editar_rascunho", d)
    t = f"rascunho #{r['id']} editado: +{r['xp_previsto']} xp, +{r['bits_previstos']} bits" if ok else ""
    return _saida(ok, r, a.json, t)


def _liberadas() -> list[str]:
    from oma_rpg.nucleo import consultas as C
    b, _ = _leitura()
    try:
        return C.caminhos_liberados(b, time.time())
    finally:
        b.fechar()


def _estado_pedido(pid: int) -> str:
    b, _ = _leitura()
    try:
        r = b.um("SELECT estado FROM pedidos_pasta WHERE id = ?", (pid,))
        return r[0] if r else "negado"
    finally:
        b.fechar()


def _com_pasta(alvo: str, acao):
    """Roda `acao(raizes)`. Fora das pastas liberadas, dentro da taverna (OMA_RPG_MESTRE=1), pede ao JC e espera a
    resposta; fora da taverna, só explica como liberar."""
    import os

    from oma_rpg.nucleo.jogo import ErroJogo
    try:
        return acao(_liberadas())
    except ErroJogo as e:
        if str(e) != "fora das pastas liberadas":
            raise
    if os.environ.get("OMA_RPG_MESTRE") != "1":
        raise ErroJogo("fora das pastas liberadas: o JC libera na taverna do oma-rpg (tecla P)")
    ok, r = _pedir_mestre("pedir_pasta", {"caminho": alvo})
    if not ok:
        raise ErroJogo(str(r))
    if r.get("liberada"):
        return acao(_liberadas())
    from oma_rpg.config import Config
    fim = time.time() + Config.carregar()["mestre"]["espera_pedido_s"]
    while time.time() < fim:
        time.sleep(0.5)
        estado = _estado_pedido(r["id"])
        if estado == "liberado":
            return acao(_liberadas())
        if estado == "negado":
            raise ErroJogo("o JC negou a leitura desta pasta")
    raise ErroJogo("o JC não respondeu a tempo: peça para ele liberar a pasta na taverna (tecla P)")


def _tamanho(n: int) -> str:
    for unid in ("B", "KB", "MB", "GB"):
        if n < 1024 or unid == "GB":
            return f"{n:.0f} {unid}" if unid == "B" else f"{n:.1f} {unid}".replace(".", ",")
        n /= 1024
    return str(n)


def cmd_pastas(a) -> int:
    from oma_rpg.nucleo import consultas as C
    b, _ = _leitura()
    try:
        ps = C.pastas(b, time.time())
    finally:
        b.fechar()
    linhas = [f"{p['caminho']}" + ("  (uma vez)" if p["modo"] == "uma_vez" else "") for p in ps]
    return _saida(True, {"pastas": ps}, a.json, "\n".join(linhas) or "nenhuma pasta liberada (o JC libera na taverna, tecla P)")


def cmd_ls(a) -> int:
    from oma_rpg.nucleo import pastas
    from oma_rpg.nucleo.jogo import ErroJogo
    try:
        d = _com_pasta(a.pasta, lambda raizes: pastas.listar(a.pasta, raizes, a.recursivo, a.fundo))
    except ErroJogo as e:
        return _saida(False, e, a.json)
    linhas = [f"{i['nome']}/" if i["tipo"] == "pasta" else f"{i['nome']}  {_tamanho(i.get('tamanho', 0))}" if i["tipo"] == "arquivo"
              else f"{i['nome']} (link{' para fora: negado' if i.get('fora') else ''})" for i in d["itens"]]
    if d["ocultos"]:
        linhas.append(f"({d['ocultos']} ocultos: arquivos com ponto ou com cara de segredo)")
    if d["cortado"]:
        linhas.append("(lista cortada)")
    return _saida(True, d, a.json, "\n".join(linhas) or "pasta vazia")


def cmd_ver(a) -> int:
    from oma_rpg.nucleo import pastas
    from oma_rpg.nucleo.jogo import ErroJogo
    try:
        d = _com_pasta(a.arquivo, lambda raizes: pastas.ver(a.arquivo, raizes, a.texto))
    except ErroJogo as e:
        return _saida(False, e, a.json)
    if d.get("conteudo") is None:
        t = f"{d['arquivo']}: {d['tipo']}, {_tamanho(d['tamanho'])}, modificado {d['modificado']} ({d.get('nota', '')})"
    else:
        t = d["conteudo"] + ("\n(cortado no limite de 200 KB)" if d.get("cortado") else "")
    return _saida(True, d, a.json, t)


def _parser_sub() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="oma-rpg", description="RPG de estudo: comandos para o Mestre (Claude Code) e a barra")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status", help="herói, combo, HP e pomodoros de hoje")
    s.add_argument("--json", action="store_true")
    s.add_argument("--barra", action="store_true", help="JSON curto para um módulo de barra (text, tooltip, class)")
    s.set_defaults(f=cmd_status)
    for nome in ("quests",):
        q = sub.add_parser(nome, help="quests e rascunhos")
        q.add_argument("--arco")
        q.add_argument("--json", action="store_true")
        q.set_defaults(f=cmd_quests)
    for nome in ("history", "historico", "histórico"):
        h = sub.add_parser(nome, help="pomodoros e commits por dia")
        h.add_argument("--days", "--dias", dest="days", type=int, default=30)
        h.add_argument("--json", action="store_true")
        h.set_defaults(f=cmd_history)
    for nome in ("draft", "rascunho"):
        d = sub.add_parser(nome, help="cria um rascunho de quest (o jogador aprova pela interface)")
        d.add_argument("--titulo", required=True)
        d.add_argument("--materia", default="")
        d.add_argument("--est", required=True, type=int, help="pomodoros de 25 min (1 a 8)")
        d.add_argument("--dif", required=True, help="1 fácil, 2 média, 3 difícil")
        d.add_argument("--arco")
        d.add_argument("--prazo", help="AAAA-MM-DD")
        d.add_argument("--porque", help="uma linha: por que esta quest")
        d.add_argument("--json", action="store_true")
        d.set_defaults(f=cmd_draft)
    e = sub.add_parser("editar", help="edita um rascunho ainda não aprovado")
    e.add_argument("id", type=int)
    e.add_argument("--titulo")
    e.add_argument("--materia")
    e.add_argument("--est", type=int)
    e.add_argument("--dif")
    e.add_argument("--arco")
    e.add_argument("--prazo")
    e.add_argument("--porque")
    e.add_argument("--json", action="store_true")
    e.set_defaults(f=cmd_editar)
    ps = sub.add_parser("pastas", help="as pastas que o JC liberou para o Mestre ler")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(f=cmd_pastas)
    ls = sub.add_parser("ls", help="lista uma pasta liberada (só leitura)")
    ls.add_argument("pasta")
    ls.add_argument("-r", "--recursivo", action="store_true", help="entra nas subpastas")
    ls.add_argument("--fundo", type=int, default=2, help="profundidade com -r (1 a 4)")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(f=cmd_ls)
    v = sub.add_parser("ver", help="mostra um arquivo de pasta liberada (binário: só metadados)")
    v.add_argument("arquivo")
    v.add_argument("--texto", action="store_true", help="extrai o texto de um PDF (pdftotext)")
    v.add_argument("--json", action="store_true")
    v.set_defaults(f=cmd_ver)
    return p


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("servico", "serviço"):
        from oma_rpg.servico import rodar
        sys.exit(rodar())
    if argv and argv[0] in SUBCOMANDOS:
        p = _parser_sub()
        a = p.parse_args(argv)
        sys.exit(a.f(a))
    p = argparse.ArgumentParser(prog="oma-rpg", description="RPG de estudo em TUI: pomodoro, quests, nível, vida e mana",
                                epilog="Subcomandos: status, quests, history, draft, editar, servico (oma-rpg status -h)")
    p.add_argument("--demo", action="store_true", help="dados inventados, sem serviço e sem mexer no estado real")
    p.add_argument("--sem-abertura", action="store_true", help="não mostra a abertura OMA RPG")
    p.add_argument("--version", action="version", version=f"oma-rpg {__version__}")
    a = p.parse_args(argv)
    from oma_rpg.ui.app import OmaRpgApp
    if a.demo:
        from oma_rpg.falso import montar_demo
        app = OmaRpgApp(**montar_demo(), abertura=not a.sem_abertura)
    else:
        app = OmaRpgApp(abertura=not a.sem_abertura)
    app.run()


if __name__ == "__main__":
    main()
