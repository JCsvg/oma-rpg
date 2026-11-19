# Decisões técnicas, oma-rpg

Fatos sobre as escolhas do projeto. Cada decisão diz quem a tomou.

## 1. Escopo da 0.1.0 (decisão do JC)

O design inteiro, todas as 11 telas do README de design (mockups em 180x48, modelo do herdr). Serviço de usuário que guarda o timer e observa os repositórios git que o usuário registrar, sem rede. Notificação pelo mako. O Claude Code ajuda a definir quests pela skill, mas não dá XP. Leve: só a biblioteca padrão além do Textual, sem Pillow.

## 2. O Mestre não dá XP (pedido do JC; a arquitetura é do agente)

A regra do design ("o agente propõe, o jogo calcula, o usuário aprova") está em três camadas, todas testadas em `tests/unit/test_mestre_sem_xp.py`, `tests/integration/test_cli.py` e `tests/integration/test_servico.py`:

- **O livro.** Toda mudança de XP, Bits, HP e MP passa por `Jogo._ganho`, que grava uma linha em `ganhos` com a origem. XP positivo só aceita `pomodoro`, `commit`, `quest`, `arco` e `conquista`; qualquer outra origem levanta `PermissionError`. As cinco nascem de pomodoro concluído no relógio do serviço ou de commit visto no git: a quest libera XP proporcional aos pomodoros feitos nela (zero sem pomodoro), o chefe do arco soma o XP das quests do arco e a conquista conta pomodoros, streak e commits. O XP e os Bits de uma quest não são gravados: saem da fórmula a cada leitura, a partir de `est` e `dif`.
- **Os papéis.** `comandos.py` tem a tabela de comandos com dois papéis. O Mestre só tem `ping`, `status`, `quests`, `historico`, `rascunho` e `editar_rascunho` (este, só em rascunho ainda não aprovado). Nenhum comando de nenhum papel recebe valor de XP, Bits, HP, MP, nível ou pontos; campos assim são recusados com "a recompensa sai da tabela do jogo". `tick` e `observar_commit` não são comandos.
- **O socket e o CLI.** A conexão nasce Mestre. Vira jogador só com a chave de `$XDG_RUNTIME_DIR/oma-rpg/jogador.chave` (0600, nova a cada início do serviço), que só a interface lê. O CLI `oma-rpg` nunca lê a chave e só tem `status`, `quests`, `history`, `draft` e `editar`.
- **A taverna.** O `claude` roda com `--tools Bash`, `--permission-mode dontAsk` e só `Bash(oma-rpg status:*)`, `quests`, `history`, `draft` e `editar` liberados.
- **Commit do agente.** Commit com o trailer `Co-Authored-By: Claude` vale 0 xp (`commit.ignorar_coautor_claude`), com o motivo gravado.

Limite honesto: um processo do mesmo usuário com shell pode ler a chave ou abrir o SQLite e escrever o que quiser. A proteção vale para o caminho que o agente tem pela skill e pelo CLI; não é sandbox. Os arquivos são 0600 e a skill proíbe mexer em `~/.local/share/oma-rpg/`.

## 3. Serviço e interface separados (decisão do JC; o desenho é do agente)

- O serviço (`oma-rpg servico`, unidade `oma-rpg.service` do usuário) é o único que escreve o banco em `~/.local/share/oma-rpg/rpg.sqlite3` (WAL). A interface abre só leitura e pede tudo pelo socket `$XDG_RUNTIME_DIR/oma-rpg/servico.sock` (0600, `SO_PEERCRED`), uma linha JSON por mensagem, como no oma-mail.
- Uma thread só, com `selectors`: socket, clientes, inotify e relógio no mesmo laço. Sem trava no banco, sem corrida. Em repouso o laço dorme até a próxima coisa marcada (fim do pomodoro, fim da pausa, aviso de 1 minuto, virada do dia), no máximo 60 s por volta.
- O timer fica no banco (tabela `atual`: fase, início, duração, pausado em). Fechar a janela ou reiniciar o serviço não perde o pomodoro: o `tick` processa os eventos de relógio em ordem cronológica, então um pomodoro que acabou às 23:50 com o serviço parado conta para o dia em que acabou, antes da virada (achado num teste).
- O CLI de leitura (`status`, `quests`, `history`) lê o banco direto, sem socket. `draft` e `editar` vão pelo socket como Mestre; sem serviço, abrem o banco e rodam o mesmo comando com o mesmo papel.
- Se o serviço não estiver rodando, a interface tenta `systemctl --user start oma-rpg.service` e, sem a unidade, inicia `python -m oma_rpg servico` solto.
- O `--demo` roda o motor no mesmo processo (`ClienteLocal`), pela mesma tabela de comandos e papéis, num banco temporário.

## 4. Git (decisão do JC; detalhes do agente)

- Só metadados locais: `git log --no-merges --numstat` com `--no-ext-diff --no-textconv`, `core.fsmonitor=false`, sem shell, sem pager, sem rede. Só os commits do `user.email` configurado no repositório contam (o que vem de `git pull` é de outra pessoa). O que já existia antes de registrar o repositório não vira XP.
- Vigia: inotify pela libc com `ctypes`, na pasta `.git/logs` (todo commit acrescenta uma linha em `logs/HEAD`), com 1,5 s de espera para o git terminar de escrever. Sem inotify, confere o `mtime` a cada 30 s.
- Vinculado: o commit cai dentro de um pomodoro (o atual ou um concluído) e o repositório tem a mesma matéria da quest, ou não tem matéria. Vinculado vale 100%; o resto vale 30% (design).
- `closes quest-N` (ou `fecha` e `conclui`) na mensagem conclui a quest, pelas mesmas regras do `espaço` (sem pomodoro, 0 xp).
- Repositórios entram e saem pelo diálogo da interface (clique em "git · N repositórios" nos ativos). Não há CLI para isso, para o agente não escolher o que conta.

## 5. Balanceamento: o que o design deixou em aberto (decisão do agente, conservadora)

Tudo em `src/oma_rpg/balanceamento.toml` (números) e `src/oma_rpg/conteudo.toml` (classes, skills, cartas, itens, conquistas). O usuário muda em `~/.config/oma-rpg/balanceamento.toml`; chave desconhecida ou tipo errado é ignorado com aviso no log, sem derrubar o serviço.

| Valor | Escolha | Motivo |
|---|---|---|
| teto diário | 10 pomodoros, depois XP x0,5 | 4 h10 de foco; a meta do design é 6 |
| XP por nível | 50 + 250 × n | o design mostra 1.800 no nível 7; nível 1 pede 300 (uns 12 pomodoros) |
| subir de nível | +1 ponto, +10 de HP (cura), +25 bits | design; o HP máximo não cresce, porque o design mostra 100 no nível 7 |
| XP de commit | feat/fix/perf 7, test/docs/refactor 5, sem tipo 4, chore/style/ci/merge 0 | com o CI verde (+25%) dá os +9 e +6 do design; chore +0 como no design |
| teto de commits | 5 por pomodoro, 20 por dia | commit miúdo não vira fábrica de XP |
| mana da pausa | +6 na curta, +12 na longa; pular a pausa não dá | "mana ao fim +6" do design |
| HP | a virada do dia cura 10; Rato cura 3 por pausa | sem isso só poção cura, e o HP só desceria |
| pausa esquecida | pausado por 30 min, o pomodoro é guardado sozinho | não deixa um pomodoro pausado eternamente |
| reestimar | 20 bits para mudar est ou dif de quest já começada | o Pergaminho de reestimar do design faz "sem custo"; então reestimar custa algo |
| respec | 150 bits desfaz a última skill de um ramo; o Elixir (1.500) desfaz a árvore | o design mostra os dois preços |
| chefe do arco | 50% da soma do XP das quests do arco, se todas fecharem até a data | o Otaku ganha +50% |
| juros (Empreendedor) | 1% dos bits por dia de meta cumprida, até 50 | "rendem juros todo dia em que você cumpre a meta" |
| Gamer | combo até x2,0; quebra com 45 min entre pomodoros | "vai até x2.0, mas quebra mais fácil" |
| Otaku | abaixo de 30% de HP, o pomodoro vale x2 | "virada: Otaku x2" do design |
| desmaio | acorda com 50% de HP depois de 15 min; perde 10% dos bits e o streak de hoje | design; com `backup` fica o streak de ontem |
| abandono | antes de 5 min, de graça e sem perder combo; depois, 8 HP e combo zerado | design |
| streak | conta o dia com 1 pomodoro ou mais | a regra mais gentil |
| skills ativas | uma vez por dia cada; as teclas 1 a 4 do foco são as 4 primeiras ativas aprendidas, na ordem da árvore | o design mostra "usada hoje às 08:52" |
| skills das 5 outras classes | 75 skills no mesmo vocabulário de efeitos do Garoto de Programa, com números próximos | o design dá nome e tipo; os números ficam no TOML |
| cartas do Místico | 5 buffs e 5 debuffs, sorteio pela data e pelo nome (o mesmo no serviço e na interface) | A Estrela +15% de Bits e A Torre daily x2 HP como no design |
| bits | round(xp / 4) em todo ganho de XP | a fórmula do design vale para tudo |
| Bilhete de caixa | 20 a 120 bits, ou 40% de chance de um cosmético que você não tem | sorte pequena, nada que valha fora do jogo |

Arredondamento: o `round` do design é o escolar (0,5 sobe). O `round` do Python arredonda 76,5 para 76, e o design mostra 77 xp para uma quest difícil de 3 pomodoros, então o código usa `arred`.

## 6. Interface (decisão do agente, seguindo o design)

- Base copiada do oma-mail (que veio do oma-spotify), não importada: tema a partir do `colors.toml`, lista virtualizada com Line API (acréscimo: arrastar com o mouse para reordenar), botão de uma linha, rodapé clicável, avisos no canto, abertura uma vez por boot, contexto em `$XDG_RUNTIME_DIR`.
- Uma página montada por vez: trocar de painel desmonta a anterior. Cada janela olha para a sua página (`pagina_de`), não para a aberta agora: na troca, a página velha ainda pinta uma última vez (achado nos testes).
- Ctrl+setas pela tabela escrita de cada página (`VIZINHAS`), com o topo em cima de todas e a coluna dos painéis à esquerda. A tabela está no README e cada linha tem teste.
- Título com texto à direita na borda ("alt+4 skills", "meta 3 de 6"), montado como no oma-mail.
- Timer de 1 s só com pomodoro, pausa ou desmaio rodando; parado, nada pisca. O giro da taverna só roda com o Mestre pensando.
- Abaixo de 120 colunas, meia tela: uma janela por vez na tela toda, Ctrl+setas trocam pela mesma tabela e a coluna dos painéis vira uma janela.
- Busca (`/`) num diálogo em cima, em quests, skills e itens, sem diferenciar acento.

## 7. O que difere do design e por quê

- **O comando de rascunho** é `oma-rpg draft` (o do README de design). O mockup da taverna mostra `oma-rpg quest add --draft`; a taverna do app mostra o comando de verdade.
- **"aparece como pendente"** do commit solto no foco: o commit solto entra na hora com 30%, e a linha diz isso. Deixar pendente pediria uma regra de quando liberar que o design não diz.
- **Diálogos** são modais de verdade; a tela 10 do design (todos lado a lado) existe como vitrine para a captura (`Vitrine`).
- **Classes**: a vista das 6 classes não tem a coluna dos painéis, como no design; `t` troca para a classe escolhida (pede confirmação, perde os pontos gastos).
- **Repositórios**: o design não tem tela para registrar; virou um diálogo aberto pelo "git · N repositórios" da coluna da esquerda.
- **Barra do omarchy-shell**: o design pede ícone com o timer. O app não mexe no shell nem no Hyprland; `oma-rpg status` dá uma linha curta e `oma-rpg status --barra` dá JSON (`text`, `tooltip`, `class`) para um módulo de barra consumir (ver README).
- **Skills ativas**: as teclas 1 a 4 usam as 4 primeiras ativas aprendidas, na ordem da árvore; o design não diz como escolher.
- **HP máximo** não cresce com o nível; "+10 de HP" ao subir é cura.

## 8. Memória (pedido do JC)

Medido com Textual 8.2.8, `VmRSS`: interface `--demo` em pty 180x48, 51,6 MB em repouso e 62,8 MB depois de 4 rodadas por todas as telas (Python 3.14.8; 49,9 e 60,9 MB no 3.13.18); serviço com um ano de histórico e um repositório observado, 25,0 MB (22,6 MB no 3.13). Tetos do teste: 55, 85 e 40 MB. O cache do SQLite das conexões de leitura caiu para 512 KiB e valeu 1,2 MB no repouso. O que segura a memória: biblioteca padrão para banco, socket, git e inotify; páginas, diálogos e o `TextArea` da taverna importados só quando abrem; uma página montada por vez; listas virtualizadas; timer só com relógio rodando; o serviço numa thread só.

## 9. Capturas

Geradas pelo próprio Textual (`export_screenshot`) com o `--demo` e o relógio parado em 18/11/2026, convertidas com `rsvg-convert` (técnica do oma-mail). Script: `tests/manual/capturas.py`. Nenhuma captura da tela do JC.

## 10. Pastas liberadas ao Mestre na 0.2.0 (pedido do JC; detalhes do agente)

- **Lista controlada só pelo jogador.** As pastas liberadas ficam no banco e só aceitam alteração pela interface (com a chave de jogador), pela tecla `P` ou botão na Taverna, ou pelo diálogo de confirmação quando o Mestre pede uma pasta nova ("liberar uma vez", "liberar sempre" ou "negar"). O Mestre e o CLI sem chave não adicionam nem removem pastas.
- **Caminhos sensíveis recusados.** Nunca podem ser liberados: `/`, `~`, `~/.ssh`, `~/.config`, `~/.local/share/oma-rpg` e a pasta de estado/chave em `$XDG_RUNTIME_DIR/oma-rpg`. A recusa acontece ao adicionar e de novo ao montar os argumentos do `claude`.
- **Leitura validada pelo CLI.** Em vez de liberar `ls`/`find` genéricos no Bash, o Mestre usa `oma-rpg pastas`, `oma-rpg ls` e `oma-rpg ver`, que resolvem o caminho com `realpath` e recusam `..`, links simbólicos que apontem para fora da pasta liberada e arquivos secretos. PDFs grandes mostram só nome e tamanho, salvo quando `--texto` é pedido para um arquivo específico.
- **Permissões no `claude -p`.** O processo da Taverna recebe `--add-dir` e `Read(//pasta/**)` só para as pastas liberadas, com `--disallowedTools` bloqueando `Write`, `Edit`, `MultiEdit`, `NotebookEdit`, `WebFetch`, `WebSearch`, `Agent`, `Task` e as pastas sensíveis.
