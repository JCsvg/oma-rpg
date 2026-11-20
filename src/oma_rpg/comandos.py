"""Os comandos do jogo e quem pode chamar cada um.

Dois papéis:
- mestre: o Claude Code pela skill e o CLI `oma-rpg`. Lê status, quests, histórico e as pastas liberadas, cria e edita
  rascunhos e pede para ler uma pasta (o pedido não libera nada: quem libera é o jogador). Só isso.
- jogador: a interface. Tudo o que o mestre faz e mais aprovar, concluir, pomodoro, skills, loja e o resto.

Nenhum comando, de nenhum papel, recebe um valor de XP, Bits, HP, MP, nível ou pontos: o XP nasce dentro do motor,
de pomodoro concluído (relógio do serviço) e de commit observado (vigia do git), que não são comandos.
O serviço e o cliente local do --demo usam esta mesma tabela.
"""

from __future__ import annotations

from oma_rpg.nucleo import consultas as C
from oma_rpg.nucleo.jogo import ErroJogo

CAMPOS_QUEST = {"titulo", "materia", "est", "dif", "prio", "depende_de", "pericias", "arco", "prazo", "porque", "desc",
                "descricao"}


class ErroPapel(ErroJogo):
    pass


def _status(j, a):
    return C.status(j.b, j.cfg, j.agora())


def _quests(j, a):
    arco = a.get("arco") or None
    if arco is not None and not isinstance(arco, str):
        raise ErroJogo("arco: precisa ser texto")
    dia = j.hoje()
    todas = C.quests(j.b, j.cfg, dia, arco=arco)
    return {"quests": [q for q in todas if q["estado"] != "rascunho"],
            "rascunhos": [q for q in todas if q["estado"] == "rascunho"]}


def _historico(j, a):
    from oma_rpg.nucleo.jogo import inteiro
    return {"dias": C.historico(j.b, j.cfg, j.agora(), inteiro(a.get("dias", 30), "dias", 1, 400))}


# nome: (função, campos aceitos, só jogador)
COMANDOS: dict[str, tuple] = {
    "ping": (lambda j, a: {"ok": True}, set(), False),
    "status": (_status, set(), False),
    "quests": (_quests, {"arco"}, False),
    "historico": (_historico, {"dias"}, False),
    "rascunho": (lambda j, a: j.rascunho(**a), CAMPOS_QUEST, False),
    "editar_rascunho": (lambda j, a: j.editar_rascunho(**a), CAMPOS_QUEST | {"id"}, False),
    "pastas": (lambda j, a: {"pastas": C.pastas(j.b, j.agora())}, set(), False),
    # pedir não libera: só registra o pedido, e a interface pergunta ao jogador
    "pedir_pasta": (lambda j, a: j.pedir_pasta(a.get("caminho"), a.get("motivo", "")), {"caminho", "motivo"}, False),
    "salvar_entrevista": (lambda j, a: j.salvar_entrevista(a.get("estrategia"), a.get("notas"),
                                                           a.get("atributos"), a.get("pericias")),
                          {"estrategia", "notas", "atributos", "pericias"}, False),
    # daqui para baixo, só a interface (papel jogador)
    "criar_heroi": (lambda j, a: j.criar_heroi(a.get("nome"), a.get("classe"), a.get("perfil")), {"nome", "classe", "perfil"}, True),
    "salvar_perfil": (lambda j, a: j.salvar_perfil(**a),
                      {"ocupacao", "objetivos", "hobbies", "altura_cm", "peso_kg", "treina", "treino_tipo", "treino_freq",
                       "tempo_estudo", "dificuldade_estudo", "dificuldade_metas", "atencao", "estilo_estudo", "rotina",
                       "estilo_vida", "sono", "obstaculos", "tamanho_bloco", "pericias_iniciais"}, True),
    "aplicar_proposta_perfil": (lambda j, a: j.aplicar_proposta_perfil(), set(), True),
    "descartar_proposta_perfil": (lambda j, a: j.descartar_proposta_perfil(), set(), True),
    "gastar_atributo": (lambda j, a: j.gastar_atributo(a.get("attr")), {"attr"}, True),
    "nova_pericia": (lambda j, a: j.nova_pericia(a.get("nome")), {"nome"}, True),
    "aprovar_pericia": (lambda j, a: j.aprovar_pericia(a.get("id")), {"id"}, True),
    "remover_pericia": (lambda j, a: j.remover_pericia(a.get("id")), {"id"}, True),
    "trocar_classe": (lambda j, a: j.trocar_classe(a.get("classe")), {"classe"}, True),
    "konami": (lambda j, a: j.konami(), set(), True),
    "acordar": (lambda j, a: j.acordar(), set(), True),
    "iniciar": (lambda j, a: j.iniciar(a.get("quest")), {"quest"}, True),
    "pausar": (lambda j, a: j.pausar(), set(), True),
    "abandonar": (lambda j, a: j.abandonar(), set(), True),
    "pular_pausa": (lambda j, a: j.pular_pausa(), set(), True),
    "nova_quest": (lambda j, a: j.nova_quest(**a), CAMPOS_QUEST | {"tipo", "hoje", "subtarefas"}, True),
    "editar_quest": (lambda j, a: j.editar_quest(**a), CAMPOS_QUEST | {"id", "tipo", "subtarefas"}, True),
    "aprovar": (lambda j, a: j.aprovar(a.get("id")), {"id"}, True),
    "aprovar_todos": (lambda j, a: j.aprovar_todos(), set(), True),
    "descartar_rascunho": (lambda j, a: j.descartar_rascunho(a.get("id")), {"id"}, True),
    "descartar_todos_rascunhos": (lambda j, a: j.descartar_todos_rascunhos(), set(), True),
    "descartar_quest": (lambda j, a: j.descartar_quest(a.get("id")), {"id"}, True),
    "concluir_quest": (lambda j, a: j.concluir_quest(a.get("id"), a.get("nota", "")), {"id", "nota"}, True),
    "mover_fila": (lambda j, a: j.mover_fila(a.get("id"), a.get("passo", 1)), {"id", "passo"}, True),
    "ordenar_fila": (lambda j, a: j.ordenar_fila(a.get("ids")), {"ids"}, True),
    "marcar_hoje": (lambda j, a: j.marcar_hoje(a.get("id"), bool(a.get("valor", True))), {"id", "valor"}, True),
    "subtarefa": (lambda j, a: j.subtarefa(a.get("id"), a.get("indice", 0), a.get("feita"), a.get("texto")),
                  {"id", "indice", "feita", "texto"}, True),
    "novo_arco": (lambda j, a: j.novo_arco(a.get("nome"), a.get("chefe", ""), a.get("data", "")), {"nome", "chefe", "data"}, True),
    "editar_arco": (lambda j, a: j.editar_arco(a.get("id"), a.get("nome"), a.get("chefe"), a.get("data")),
                    {"id", "nome", "chefe", "data"}, True),
    "nota": (lambda j, a: j.nota(a.get("texto")), {"texto"}, True),
    "aprender": (lambda j, a: j.aprender(a.get("skill")), {"skill"}, True),
    "respec": (lambda j, a: j.respec(a.get("skill")), {"skill"}, True),
    "usar_skill": (lambda j, a: j.usar_skill(a.get("skill")), {"skill"}, True),
    "revelar_carta": (lambda j, a: j.revelar_carta(), set(), True),
    "comprar": (lambda j, a: j.comprar(a.get("item"), a.get("qtd", 1)), {"item", "qtd"}, True),
    "usar_item": (lambda j, a: j.usar_item(a.get("item")), {"item"}, True),
    "equipar": (lambda j, a: j.equipar(a.get("item")), {"item"}, True),
    "taverna": (lambda j, a: j.taverna_registrar(a.get("papel"), a.get("texto"), a.get("extra")),
                {"papel", "texto", "extra"}, True),
    "limpar_taverna": (lambda j, a: j.limpar_taverna(), set(), True),
    "repo_adicionar": (lambda j, a: j.repo_adicionar(a.get("caminho"), a.get("materia", "")), {"caminho", "materia"}, True),
    "repo_remover": (lambda j, a: j.repo_remover(a.get("id")), {"id"}, True),
    "pasta_adicionar": (lambda j, a: j.pasta_adicionar(a.get("caminho"), a.get("modo", "sempre")), {"caminho", "modo"}, True),
    "pasta_remover": (lambda j, a: j.pasta_remover(a.get("caminho")), {"caminho"}, True),
    "responder_pedido": (lambda j, a: j.responder_pedido(a.get("id"), a.get("resposta")), {"id", "resposta"}, True),
}

DO_MESTRE = frozenset(k for k, (_, _, so_jogador) in COMANDOS.items() if not so_jogador)
PAPEIS = ("mestre", "jogador")


def executar(jogo, cmd, args, papel: str = "mestre"):
    """Confere o papel e os campos, roda o comando e devolve o resultado (ou levanta ErroJogo)."""
    if papel not in PAPEIS:
        raise ErroPapel("papel desconhecido")
    if not isinstance(cmd, str) or cmd not in COMANDOS:
        raise ErroJogo(f"comando desconhecido: {str(cmd)[:40]}")
    f, campos, so_jogador = COMANDOS[cmd]
    if so_jogador and papel != "jogador":
        raise ErroPapel(f"o Mestre não pode fazer isso ({cmd}): só o jogador, pela interface")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ErroJogo("argumentos inválidos")
    sobra = set(args) - campos
    if sobra:
        recompensa = sobra & {"xp", "bits", "hp", "mp", "nivel", "pontos", "recompensa", "xp_previsto", "bits_previstos"}
        if recompensa:
            raise ErroJogo("a recompensa sai da tabela do jogo (est e dif); não dá para escolher")
        raise ErroJogo(f"argumento desconhecido: {sorted(sobra)[0][:40]}")
    jogo.tick()
    r = f(jogo, args)
    jogo.tick()
    return r
