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

Resposta com --json: {"ok": true, "dados": ...} ou {"ok": false, "erro": "..."}.
Nenhum subcomando aprova, conclui, compra ou muda XP, Bits, HP, nível ou skills: isso é só pela interface.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from oma_rpg import __version__

SUBCOMANDOS = ("servico", "serviço", "status", "quests", "history", "historico", "histórico", "draft", "rascunho", "editar")


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
