# PLAN.md

Plano para evoluir o `mktsk` de criador de pastas para mini-gestor de tarefas, com o `.md`
como única fonte de verdade. Um passo de cada vez, cada um com um prompt para o agente.

Ponto de partida: v0.4.1, 344 testes, cobertura 100%.

## Como usar

1. Fazer commit deste ficheiro num branch `docs/plan` (`docs: add the plan`).
2. Correr os passos por ordem. Um prompt por sessão do agente, um branch por passo.
3. Rever o diff, fundir em `main` e só então passar ao passo seguinte.
4. Entre o passo 2 e o passo 3, correr a migração nas tarefas reais (ver passo 2).

## Passos

| # | Passo | Branch |
|---|-------|--------|
| 1 | Parser puro do `.md` | `feat/md-parser` |
| 2 | Script de migração do formato | `feat/md-migration` |
| 3 | Formato novo no código | `feat/new-md-format` |
| 4 | Listagem por última actividade (CLI) | `feat/activity-listing` |
| 5 | Dividir o `gui.py` | `refactor/split-gui` |
| 6 | GUI com actividade | `feat/gui-activity` |
| 7 | Estado como dados e `--state` | `feat/task-state` |
| 8 | Transições automáticas de estado | `feat/state-transitions` |
| 9 | Estado nas listagens e acção na GUI | `feat/state-listing` |
| 10 | Fechar = arquivo comprimido | `feat/close-task` |
| 11 | Reabrir uma tarefa arquivada | `feat/reopen-task` |

Porquê esta ordem: o parser não tem risco e tudo depende dele; a migração vem cedo porque
cada tarefa nova no formato antigo é mais uma para converter; a leitura (4 a 6) vem antes
da escrita de estado (7 a 9) e valida o parser com dados reais; fechar e reabrir (10 e 11)
são os únicos passos que apagam pastas e ficam por último.

## Decisões tomadas

- Estados: `aberto`, `em-progresso`, `espera`, `fechado`
- O estado vive no próprio `.md`, em eventos invisíveis no render
- A data de cada intervenção é um heading de nível 1: `# 02/10/2026`
- O `.md` deixa de ter `# Título`; o título é o da pasta e o do nome do ficheiro
- Fechar comprime a pasta num zip; o zip é o estado `fechado`
- Sem compatibilidade com o formato antigo: migra-se tudo de uma vez

## Decisões em aberto (valores por omissão já nos prompts)

- Estado `espera`: incluído. Se não o quiseres, tira-o do passo 1 (`STATES`) e dos passos 7 e 9
- Onde fica o zip: ao lado de onde estava a pasta, como `YYMMDD - Titulo.zip`. A alternativa
  é uma pasta `_Arquivo`, que obriga a tratá-la como excepção nas categorias
- Retomar uma tarefa arquivada: reabre sem pedir confirmação, porque fechar de novo é barato

## Formato do .md

```markdown
# 18/09/2026

Pedido do cliente, ver anexo.

## Problema

Texto livre, com os níveis 2 a 6 à disposição.

# 02/10/2026

Resposta do fornecedor.

[mktsk:2026-09-18T10:02]: # "aberto"
[mktsk:2026-10-02T09:40]: # "em-progresso"
```

Regras:

1. Sem `# Título`. A pasta e o nome do `.md` dizem qual é a tarefa.
2. Intervenção: heading de nível 1 cuja linha contém uma data válida. Forma canónica
   `# dd/mm/yyyy` (`DATE_FORMAT`). Na leitura toleram-se `dd-mm-yyyy`, `dd.mm.yyyy`,
   `yyyy-mm-dd` e `dd/mm/yy`, e texto depois da data (`# 29/09/2026 - resposta`). Uma data
   impossível não conta. Um `# Outra coisa` sem data é só um heading
3. Os níveis 2 a 6 são livres para as notas
4. Estado: linhas `[mktsk:YYYY-MM-DDTHH:MM]: # "estado"`, hora local, em qualquer posição
   do ficheiro. O mktsk escreve-as sempre num bloco no fim, depois de uma linha em branco.
   Sem essa linha em branco o Markdown mostra-as como texto
5. Estado actual: o último evento por ordem no ficheiro. Um valor desconhecido ignora-se.
   Sem eventos, o estado é derivado: `aberto` com no máximo uma intervenção, `em-progresso`
   com mais
6. Blocos de código (` ``` ` e `~~~`) são ignorados em tudo
7. Formato antigo: a primeira linha não vazia é `# <texto sem data>` e o ficheiro tem pelo
   menos um `## <data>`. Nunca se lê como formato novo

## Regras comuns

Valem para todos os prompts.

- Ler `AGENTS.md` e este `PLAN.md` antes de mexer em código
- Um branch por passo, criado a partir de `main` actualizada, com o nome indicado. Nunca
  trabalhar em `main`. Nunca fazer push, abrir PR ou criar tags
- Commits `<type>: <description>`, uma linha, minúsculas, sem ponto final. Um commit por tópico
- Antes de terminar, tudo verde: `ruff check .`, `pyright mktsk/` e `pytest`, com a cobertura
  em 100%
- Testes só com `tmp_path`. Nunca ler nem escrever nas pastas reais de tarefas
- Actualizar `AGENTS.md` (Structure, Domain rules, CLI, GUI) e `README.md` quando o
  comportamento visível mudar. Uma regra de `AGENTS.md` que o passo substitui é reescrita no
  mesmo commit, nunca deixada a contradizer o código
- Estilo: curto, directo, sem emojis. Funções pequenas, docstrings com `Args:` / `Returns:` /
  `Raises:`, não apagar comentários existentes
- Dúvida de desenho: escolher a opção mais simples e registá-la no relatório. Parar e
  perguntar só se houver risco de perder dados do utilizador
- Relatório final, no máximo 15 linhas: o que mudou por ficheiro, número de testes e
  cobertura, decisões tomadas, dúvidas por resolver

---

## Passo 1 — Parser puro do .md

**Resultado:** módulo novo e testado que lê o texto de um `.md` e devolve intervenções,
eventos de estado e última actividade. Não está ligado a mais nada.

**Termina quando:** o módulo cobre todos os casos de borda e o resto do código não mudou.

````text
Papel: és um engenheiro Python sénior a trabalhar no repositório mktsk, uma CLI e GUI que
cria pastas de tarefa `YYMMDD - Titulo`, cada uma com um `.md`.

Objectivo: criar o módulo `mktsk/parsing.py`, só com funções puras, que transforma o texto
de um `.md` de tarefa em dados. Este passo não liga o módulo a mais nada: `workers.py`,
`main.py` e `gui.py` não mudam.

Antes de começar, lê `AGENTS.md` e, em `PLAN.md`, as secções "Regras comuns" e "Formato do
.md". Branch: `feat/md-parser`.

Detalhes:
- O formato é o descrito em "Formato do .md". Este passo implementa só a leitura
- API (podes ajustar nomes se houver razão, e registas no relatório):
  - `STATES = ("aberto", "em-progresso", "espera", "fechado")`
  - `Intervention(NamedTuple)`: `date: datetime.date`, `heading: str`, `line: int` (base 1)
  - `StateEvent(NamedTuple)`: `timestamp: datetime.datetime` (naive, hora local),
    `state: str`, `line: int`
  - `ParsedTask(NamedTuple)`: `interventions: list[Intervention]`,
    `events: list[StateEvent]`, `last_activity: datetime.date | None`
  - `parse_task(content: str) -> ParsedTask`
  - `is_legacy(content: str) -> bool`, conforme a regra 7 do formato
- Intervenção: linha que começa por `#` seguido de espaço (até 3 espaços de indentação), com
  um nível só. `#hashtag` e `##` não contam
- Datas: procurar candidatos com expressões regulares (`dd/mm/yyyy`, `dd-mm-yyyy`,
  `dd.mm.yyyy`, `dd/mm/yy`, `yyyy-mm-dd`) e validar com `datetime.date(...)`. Anos de dois
  dígitos são 2000 mais o ano. Usa o primeiro candidato válido do heading. Um `2026-10-02`
  não pode ser lido também como `26-10-02`
- Evento: linha inteira `[mktsk:YYYY-MM-DDTHH:MM]: # "estado"`. Timestamp inválido ou estado
  fora de `STATES` fazem o evento ser ignorado, nunca um erro
- `last_activity`: a data mais recente entre as intervenções, não a última por ordem
- Linhas dentro de blocos de código (` ``` ` e `~~~`, o fecho com o mesmo carácter) são
  ignoradas em tudo
- O parser recebe texto, não um `Path`. Aceita `\r\n` e `\n`
- O ruff tem a regra `DTZ` activa (ver `pyproject.toml` e `AGENTS.md`); segue o padrão de
  `# noqa: DTZ007` que o `workers.py` já usa

Testes em `tests/test_parsing.py`, que cubram pelo menos: ficheiro vazio; só intervenções;
só eventos; heading com texto depois da data; data impossível; `#hashtag`; datas fora de
ordem; os cinco formatos de data; `2026-10-02` sem leitura dupla; eventos em qualquer
posição; evento inválido; bloco de código com um `# 12/01/2026` lá dentro; CRLF;
`is_legacy` com ficheiro antigo, novo e vazio, e com um `## Prazo 05/10/2026` num ficheiro
novo, que não é antigo.

Documentação: acrescenta o módulo a "Structure" em `AGENTS.md` e descreve o formato numa
secção própria, marcada como ainda não usada por `workers.py`.

Verificação: `ruff check .`, `pyright mktsk/` e `pytest` verdes, cobertura 100%, e
`git diff --stat` a mostrar só o módulo novo, os testes novos e `AGENTS.md`.

Commit: `feat: add a parser for the task markdown`.

Formato da resposta: o relatório final descrito em "Regras comuns" de `PLAN.md`.
````

---

## Passo 2 — Script de migração do formato

**Resultado:** um script que converte um `.md` do formato antigo para o novo, com simulação
por omissão. O mktsk continua a escrever o formato antigo.

**Termina quando:** a migração está testada e o `--dry-run` mostra um diff correcto sobre uma
cópia das tarefas reais.

**Feito por ti, a seguir ao merge:** zip da pasta das tarefas, correr o script sem `--apply`,
ler o diff, correr com `--apply`. Só depois o passo 3.

````text
Papel: és um engenheiro Python sénior a trabalhar no repositório mktsk. Os `.md` das tarefas
estão no formato antigo e vão passar para um formato novo.

Objectivo: criar `mktsk/migration.py` com a conversão de um `.md` do formato antigo para o
novo e um modo de linha de comando que a aplica a uma árvore de tarefas. O mktsk continua a
escrever o formato antigo neste passo.

Antes de começar, lê `AGENTS.md` e, em `PLAN.md`, "Regras comuns" e "Formato do .md". O
módulo `mktsk/parsing.py` já existe e deve ser reutilizado para reconhecer datas e blocos de
código. Branch: `feat/md-migration`.

Formato antigo: o `.md` começa por `# <Titulo>` (o título da pasta), cada visita é um
`## dd/mm/yyyy`, e as notas ficam por baixo. Formato novo: sem o `# Titulo`; cada visita é
`# dd/mm/yyyy`.

Detalhes:
- `migrate_content(content: str, title: str) -> Migration`, com `Migration(NamedTuple)`:
  `content: str` e `review: list[str]` (avisos para um humano rever). Função pura
- Regras:
  1. Se a primeira linha não vazia é `# <texto>`, o texto não tem data e é igual a `title`,
     apagá-la e as linhas em branco que se lhe seguem. Se o texto for outro, deixar e avisar
  2. Cada `## <data>` passa a `# <data>`. A data reconhece-se como em `parsing.py`
  3. Dentro de uma secção de data antiga, os headings de nível 3 a 6 sobem um nível
  4. Um `##` sem data dentro dessas secções fica como está e entra em `review`
  5. Um `# <data>` que já esteja no formato novo não se mexe
  6. Blocos de código nunca se tocam
  7. O resultado termina numa única mudança de linha
- Idempotente: migrar um ficheiro já migrado devolve o mesmo conteúdo e nenhum aviso
- Linha de comando `python -m mktsk.migration <pasta> [--apply]`: percorre a pasta e as
  subpastas imediatas (as categorias), como `find_task_groups`, só tarefas reconhecidas por
  `is_task_folder`, e usa o `.md` com o nome do título. Sem `--apply` é só simulação: imprime
  por ficheiro o estado (`migrado`, `já no formato novo`, `rever`) e um diff unificado, e
  não escreve nada. Com `--apply` escreve cada ficheiro de forma atómica (ficheiro temporário
  na mesma pasta e `os.replace`) e lembra, antes de começar, que convém ter uma cópia
  de segurança
- Ler e escrever com `newline=""` para preservar o separador de linha de cada ficheiro
- Cada ficheiro falha de forma isolada: um erro de leitura entra no relatório e o script
  continua
- O módulo sai de `pragma: no cover` só no bloco `if __name__ == "__main__"`

Testes em `tests/test_migration.py`: título removido; título diferente avisado e mantido;
`## data` convertido; `###` a subir; `##` sem data avisado; ficheiro já novo inalterado; um
`# 29/09/2026` com um só `#` inalterado; blocos de código; CRLF preservado; ficheiro só com
título; ficheiro vazio; idempotência; simulação sem escrever; `--apply` a escrever; erro
isolado por ficheiro.

Documentação: `AGENTS.md` (Structure e um parágrafo sobre como correr a migração) e
`README.md` se fizer sentido.

Verificação: tudo verde, cobertura 100%, e a simulação sobre um directório de teste com
formato antigo mostra o diff esperado.

Commit: `feat: add a migration for the task markdown format`.

Formato da resposta: o relatório final descrito em "Regras comuns" de `PLAN.md`.
````

---

## Passo 3 — Formato novo no código

**Resultado:** o mktsk passa a escrever e a ler só o formato novo. Um ficheiro no formato
antigo dá um erro claro em vez de ser mal lido.

**Termina quando:** criar, retomar e renomear tarefas funciona sobre as tarefas reais já
migradas.

````text
Papel: és um engenheiro Python sénior a trabalhar no repositório mktsk.

Objectivo: fazer `workers.py` escrever e ler o formato novo do `.md`, e recusar o formato
antigo com um erro claro. As tarefas reais já foram migradas pelo utilizador.

Antes de começar, lê `AGENTS.md` (sobretudo "Domain rules") e, em `PLAN.md`, "Regras
comuns" e "Formato do .md". Reutiliza `mktsk/parsing.py`. Branch: `feat/new-md-format`.

Detalhes:
- Tarefa nova: o `.md` nasce com `# dd/mm/yyyy` (a data de hoje) e uma linha em branco. Já não
  tem `# Titulo`
- Retomar: o `.md` da pasta continua a ser o do título que a pasta carrega. Se o ficheiro
  está vazio, escreve `# <hoje>`. Se não, acrescenta `# <hoje>` no fim (depois de
  `rstrip` e uma linha em branco) a não ser que `parse_task` já mostre uma intervenção com a
  data de hoje. A mensagem devolvida ao utilizador continua a dizer o que aconteceu e
  mostra o novo heading
- Remover `sign_md_file` e `_retitled`: já não há título dentro do ficheiro
- `rename_task` passa a mexer só em nomes: renomeia o `.md` dentro da pasta e depois a
  pasta, mantendo o desfazer actual se o segundo passo falhar. O que depende do conteúdo
  do heading desaparece
- Guarda: se `is_legacy(content)` for verdadeiro ao retomar, levanta `TaskError` com uma
  mensagem que indique o ficheiro e o comando de migração. Nada se escreve nesse caso
- `find_task_folder`, a regra de unicidade do título e o `exclude` não mudam
- Não mexas na listagem nem na GUI além do que os testes existentes exigirem

Testes: actualiza os existentes que dependiam do formato antigo e acrescenta: tarefa nova
com `# hoje`; retomar acrescenta `# hoje`; retomar no mesmo dia não duplica; ficheiro vazio;
ficheiro antigo dá `TaskError` sem escrever; rename só de caixa continua a funcionar;
rename não toca no conteúdo do ficheiro.

Documentação: reescreve em `AGENTS.md` as regras de domínio que falam do heading de título e
de `## data`, e actualiza `README.md` onde descreve o `.md`.

Verificação: tudo verde, cobertura 100%, e uma passagem pelo código a confirmar que não
sobra nenhuma referência a `sign_md_file`, `_retitled` ou a `##` como data.

Commit: `feat: write the new markdown format`.

Formato da resposta: o relatório final descrito em "Regras comuns" de `PLAN.md`.
````

---

## Passo 4 — Listagem por última actividade (CLI)

**Resultado:** `TaskEntry` sabe a última actividade e o número de intervenções, a ordenação
passa a ser por actividade e o `--list` mostra os dois.

**Termina quando:** uma tarefa retomada hoje aparece em primeiro na listagem.

````text
Papel: és um engenheiro Python sénior a trabalhar no repositório mktsk.

Objectivo: fazer a listagem de tarefas usar a última actividade do `.md` em vez da data da
pasta, e mostrá-la no `--list`.

Antes de começar, lê `AGENTS.md` e, em `PLAN.md`, "Regras comuns" e "Formato do .md".
Reutiliza `mktsk/parsing.py`. Branch: `feat/activity-listing`.

Detalhes:
- `TaskEntry` ganha `last_activity: datetime.date` e `interventions: int`. `date` continua a
  ser a data da pasta
- `_tasks_in` lê o `.md` de cada tarefa com `parse_task`. `last_activity` é a de
  `parse_task`, ou a data da pasta quando o ficheiro não existe, não se lê ou não tem
  intervenções. Um erro de leitura nunca derruba a listagem
- Ordenação: por `last_activity` decrescente e depois por título
- `--list` mostra, em cada tarefa, o número de intervenções e a última actividade, mantendo
  o formato e a língua do que já existe. Lê a secção "CLI" de `AGENTS.md` e o `README.md`
  antes de escolher o formato
- A GUI não muda por decisão. Se a ordem da lista na GUI mudar por consequência, regista-o

Testes: tarefa retomada depois sobe na ordem; ficheiro sem intervenções cai para a data da
pasta; ficheiro ilegível não derruba a listagem; contagem de intervenções; ficheiro no
formato antigo cai para a data da pasta; saída do `--list`.

Documentação: `AGENTS.md` (regras de listagem e CLI) e `README.md`.

Verificação: tudo verde, cobertura 100%.

Commit: `feat: list tasks by their last activity`.

Formato da resposta: o relatório final descrito em "Regras comuns" de `PLAN.md`.
````

---

## Passo 5 — Dividir o gui.py

**Resultado:** o `gui.py` (cerca de 730 linhas) fica repartido por responsabilidade, sem
nenhuma mudança de comportamento.

**Termina quando:** os testes de GUI passam sem alterações além dos imports e o executável
continua a construir-se.

````text
Papel: és um engenheiro Python sénior a trabalhar no repositório mktsk, com experiência em
PySide6.

Objectivo: dividir `mktsk/gui.py` em módulos por responsabilidade, sem mudar comportamento.

Antes de começar, lê `AGENTS.md` (secções "Structure", "GUI" e "Conventions") e, em
`PLAN.md`, "Regras comuns". Branch: `refactor/split-gui`.

Detalhes:
- Transforma `mktsk/gui.py` num pacote `mktsk/gui/`. Separa, por exemplo, os ícones
  desenhados, a listagem de tarefas e a janela principal. Decide as fronteiras lendo o
  código. Cada módulo deve ficar com uma responsabilidade e um tamanho razoável
- O caminho `mktsk.gui` e tudo o que os testes e o ponto de entrada `mktsk-gui` importam
  continuam a funcionar. `__init__.py` reexporta o necessário
- Procura todas as referências a `gui.py` e a `mktsk.gui` em `pyproject.toml`, `.github/`,
  `README.md` e `AGENTS.md`, e confirma que o alvo do PyInstaller e o import absoluto de
  `__main__.py` continuam válidos
- Não mudes lógica, nomes de classes, textos, atalhos nem estilos. Só movimentação de código
  e os imports necessários
- Mantém os testes como estão; só se admitem alterações aos imports. Se algum teste fizer
  `monkeypatch` a um caminho que mudou, ajusta apenas esse caminho
- Dois commits: primeiro a movimentação, depois, se for preciso, a actualização da
  documentação

Verificação: tudo verde, cobertura 100%, os testes de GUI sem diferenças de comportamento, e
`git diff --stat -M` a mostrar sobretudo renomeações e movimentos.

Commits: `refactor: split the gui module` e, se houver, `docs: update the gui structure`.

Formato da resposta: o relatório final descrito em "Regras comuns" de `PLAN.md`, com a lista
dos módulos novos e a responsabilidade de cada um.
````

---

## Passo 6 — GUI com actividade

**Resultado:** a GUI mostra o número de intervenções e há quantos dias foi a última
actividade de cada tarefa.

**Termina quando:** cada linha da lista mostra os dois valores e a ordem é a da actividade.

````text
Papel: és um engenheiro Python sénior a trabalhar no repositório mktsk, com experiência em
PySide6.

Objectivo: mostrar, em cada tarefa da lista da GUI, o número de intervenções e há quantos dias
foi a última actividade.

Antes de começar, lê `AGENTS.md` (secção "GUI") e, em `PLAN.md`, "Regras comuns". `TaskEntry`
já tem `last_activity` e `interventions`. Branch: `feat/gui-activity`.

Detalhes:
- Cada linha mostra o número de intervenções e uma idade relativa ("hoje", "ontem", "há N
  dias"), no idioma e no estilo das strings que a GUI já tem
- A idade calcula-se contra a data de hoje, injectável para os testes (`freeze_time` já é
  usado no projecto)
- A ordem da lista é a que a camada de listagem já devolve; não reordenes na GUI
- Mantém os separadores por categoria, a barra de acções e tudo o resto como está
- Segue o estilo das células e dos widgets existentes; não introduzas novas dependências

Testes (headless, como os existentes): linha com texto de actividade; "hoje", "ontem" e "há N
dias"; tarefa sem intervenções; ordem pela actividade.

Documentação: `AGENTS.md` (secção "GUI").

Verificação: tudo verde, cobertura 100%.

Commit: `feat: show the activity of a task in the gui`.

Formato da resposta: o relatório final descrito em "Regras comuns" de `PLAN.md`.
````

---

## Passo 7 — Estado como dados e --state

**Resultado:** o mktsk sabe ler e escrever o estado de uma tarefa no `.md`, e há uma opção
de linha de comando para o mudar. Ainda sem transições automáticas.

**Termina quando:** `mktsk --state Foo espera` regista o evento e o parser lê-o de volta.

````text
Papel: és um engenheiro Python sénior a trabalhar no repositório mktsk.

Objectivo: guardar o estado de uma tarefa como eventos no fim do `.md` e dar uma opção de
linha de comando para o mudar.

Antes de começar, lê `AGENTS.md` e, em `PLAN.md`, "Regras comuns" e "Formato do .md",
sobretudo as regras 4 e 5. Reutiliza `mktsk/parsing.py`. Branch: `feat/task-state`.

Detalhes:
- Módulo novo `mktsk/state.py`, com uma camada pura e uma fina:
  - `current_state(content: str) -> str`: o último evento válido, ou o valor derivado da
    regra 5 quando não há eventos
  - `with_state(content: str, state: str, now: datetime.datetime) -> str`: devolve o
    conteúdo com o evento acrescentado. Função pura. Recusa estados fora de `STATES` com
    `TaskError`
  - `set_state(file: Path, state: str) -> bool`: lê, aplica `with_state`, escreve de
    forma atómica e devolve se escreveu
- `with_state`: tira o bloco contíguo de eventos que está no fim (se existir), mantém os
  eventos antigos pela mesma ordem, acrescenta o novo, e escreve o bloco no fim depois de
  uma linha em branco. Eventos que estejam noutros sítios do ficheiro não se mexem. Não
  acrescenta nada se o último evento já tem esse estado
- Hora: local, formato `YYYY-MM-DDTHH:MM`, sem fuso
- `append_date_section` passa a inserir a nova data antes do bloco final de eventos, para o
  bloco ficar sempre no fim. Sem bloco, comporta-se como hoje
- CLI: `--state TITULO ESTADO`, no estilo de `--list`, `--rename` e `--new-category`. O título
  resolve-se como em `mktsk Foo` (normalizado e procurado com `find_task_folder`). Aceita
  `aberto`, `em-progresso` e `espera`; `fechado` só virá do passo 10. Imprime uma linha com o
  estado novo e não abre nada. Título desconhecido dá `TaskError`, não cria a tarefa
- Nenhum outro comportamento muda

Testes: `with_state` com e sem bloco; eventos antigos preservados; sem duplicar o mesmo
estado; estado inválido; linha em branco antes do bloco; `current_state` com eventos, sem
eventos e com eventos inválidos; `append_date_section` a inserir antes do bloco; `--state` a
funcionar, título desconhecido e `fechado` recusado.

Documentação: `AGENTS.md` (Structure, regras de estado, CLI) e `README.md`.

Verificação: tudo verde, cobertura 100%.

Commit: `feat: keep the state of a task in its markdown`.

Formato da resposta: o relatório final descrito em "Regras comuns" de `PLAN.md`.
````

---

## Passo 8 — Transições automáticas de estado

**Resultado:** o estado acompanha o que fazes sem teres de o mexer: criar dá `aberto` e voltar
à tarefa num dia novo dá `em-progresso`.

**Termina quando:** o ciclo criar, retomar noutro dia, retomar de novo tem os eventos certos.

````text
Papel: és um engenheiro Python sénior a trabalhar no repositório mktsk.

Objectivo: fazer o mktsk registar sozinho as mudanças de estado óbvias.

Antes de começar, lê `AGENTS.md` e, em `PLAN.md`, "Regras comuns" e "Formato do .md". O
módulo `mktsk/state.py` já existe. Branch: `feat/state-transitions`.

Regras de transição:
- Criar uma tarefa regista o evento `aberto`
- Retomar uma tarefa onde se acrescentou uma nova secção de data, porque é um dia novo,
  regista `em-progresso` quando o estado actual era `aberto`, `espera` ou `fechado`
- Retomar no mesmo dia (sem nova secção) nunca muda o estado
- Se o estado já é `em-progresso`, não se escreve evento nenhum
- Abrir uma tarefa só para consultar não é um sinal de trabalho: só uma nova secção de data
  conta

Detalhes:
- O estado actual é o de `current_state`, calculado antes de acrescentar a secção
- A mensagem devolvida por `open_or_create_task` e `resume_task` indica a mudança de estado,
  quando houver (por exemplo `(state: em-progresso)`)
- Se a escrita do estado falhar, a tarefa abre na mesma e a mensagem diz que o estado não foi
  registado; nunca se perde a abertura por causa do estado
- Nada de interface nova neste passo

Testes: criar regista `aberto`; dia novo a partir de `aberto` regista `em-progresso`; dia novo
a partir de `espera`; mesmo dia não mexe; já `em-progresso` não escreve; tarefa sem eventos
(estado derivado) num dia novo; falha na escrita do estado não impede a abertura; as
mensagens.

Documentação: `AGENTS.md` (regras de estado) e `README.md`.

Verificação: tudo verde, cobertura 100%.

Commit: `feat: change the state of a task as it is used`.

Formato da resposta: o relatório final descrito em "Regras comuns" de `PLAN.md`.
````

---

## Passo 9 — Estado nas listagens e acção na GUI

**Resultado:** o estado aparece na listagem da CLI e da GUI, dá para filtrar na CLI e para
mudar à mão na GUI.

**Termina quando:** `mktsk --list --only espera` mostra só as tarefas em espera e a GUI
permite mudar entre os três estados abertos.

````text
Papel: és um engenheiro Python sénior a trabalhar no repositório mktsk, com experiência em
PySide6.

Objectivo: mostrar o estado de cada tarefa nas listagens e permitir mudá-lo.

Antes de começar, lê `AGENTS.md` (secções "CLI" e "GUI") e, em `PLAN.md`, "Regras comuns" e
"Formato do .md". Branch: `feat/state-listing`.

Detalhes:
- `TaskEntry` ganha `state: str`, calculado com `current_state` a partir do `.md` já lido
  pela listagem, sem uma segunda leitura. Se o ficheiro não se lê, o estado é `aberto`
- CLI: `--list` mostra o estado de cada tarefa. `--list --only ESTADO` filtra por estado. Não
  uses `--state`, que já existe para outra coisa. Estado desconhecido dá `TaskError`
- GUI: cada linha mostra o estado, no estilo das células existentes, e há uma acção
  "mudar estado" com os três estados `aberto`, `em-progresso` e `espera`. `fechado` não
  aparece, porque só se chega lá fechando a tarefa (passo 10). A acção usa `set_state` e
  actualiza a lista
- Mantém a ordem por actividade e os separadores por categoria como estão
- Segue o idioma e o estilo das strings já existentes na GUI e na CLI

Testes: estado em cada linha; filtro `--only`; filtro com estado desconhecido; ficheiro
ilegível dá `aberto`; a acção da GUI muda o estado e a lista; a acção não oferece `fechado`.

Documentação: `AGENTS.md` (CLI, GUI) e `README.md`.

Verificação: tudo verde, cobertura 100%.

Commit: `feat: show and change the state of a task`.

Formato da resposta: o relatório final descrito em "Regras comuns" de `PLAN.md`.
````

---

## Passo 10 — Fechar = arquivo comprimido

**Resultado:** fechar uma tarefa comprime a pasta num zip ao lado da original. O zip é o
estado `fechado`. Reabrir só chega no passo 11.

**Termina quando:** `mktsk --close Foo` deixa um zip verificado, apaga a pasta só depois de o
verificar, e `mktsk Foo` não cria uma tarefa duplicada.

````text
Papel: és um engenheiro Python sénior a trabalhar no repositório mktsk. Este passo apaga
pastas do utilizador: a regra é nunca apagar nada antes de confirmar que o resultado existe
e abre.

Objectivo: fechar uma tarefa comprimindo a sua pasta num ficheiro zip.

Antes de começar, lê `AGENTS.md` e, em `PLAN.md`, "Regras comuns" e "Formato do .md". Os
módulos `mktsk/parsing.py` e `mktsk/state.py` já existem. Branch: `feat/close-task`.

Desenho:
- O arquivo fica no mesmo directório da pasta, com o nome `YYMMDD - Titulo.zip`. Dentro,
  todos os ficheiros da pasta com o caminho `YYMMDD - Titulo/<caminho relativo>`, e a
  compressão `ZIP_DEFLATED`
- O `.md` dentro do arquivo leva o evento `fechado`, obtido com `with_state` e gravado com
  `ZipFile.writestr`. O `.md` da pasta original nunca é alterado, para que uma falha a meio
  não deixe a tarefa a meio caminho
- `close_task(folder: Path, title: str) -> TaskResult`, por esta ordem:
  1. recusar se já existe um arquivo com esse título nesse directório
  2. escrever o zip com um nome temporário no mesmo directório (por exemplo
     `.<nome>.zip.part`)
  3. verificar: `testzip()` devolve `None`, o conjunto de nomes é o esperado e os tamanhos
     batem certo
  4. `os.replace` para o nome final
  5. só então apagar a pasta com `shutil.rmtree`
- Falha antes do passo 5: apagar o ficheiro temporário e deixar a pasta intacta. Falha no
  passo 5 (no Windows, um ficheiro aberto num editor, por exemplo): manter o zip e a pasta e
  levantar `TaskError` a explicar que a tarefa está arquivada mas a pasta não pôde ser
  removida. Nunca se perde nada
- Tarefas arquivadas: `is_task_archive(name)` reconhece `YYMMDD - Titulo.zip` e
  `find_task_archive(location, title)` procura-os sem distinguir maiúsculas. A regra de
  unicidade do título passa a incluir arquivos: `mktsk Foo` não cria uma tarefa nova se
  existir `Foo.zip`; levanta `TaskError` a dizer que está arquivada (reabrir é o passo 11).
  Renomear uma arquivada também dá `TaskError`, e o destino de um rename não pode colidir
  com um arquivo
- Listagem: as tarefas arquivadas aparecem como entradas com o estado `fechado`, lidas do
  `.md` de dentro do zip, com a mesma contagem de intervenções e última actividade. Por
  omissão a listagem esconde as fechadas; `--list --only fechado` mostra-as. Uma pergunta ao
  zip que falhe nunca derruba a listagem
- CLI: `--close TITULO`. Escolhe o título como em `--state`. Imprime uma linha com o nome do
  arquivo criado. A opção `--state ... fechado` continua recusada
- GUI: acção "fechar" numa tarefa, com uma caixa de confirmação, e um separador "fechadas"
  que lista os arquivos. Segue o estilo dos separadores e das acções existentes

Testes: fechar cria o zip e apaga a pasta; o `.md` no zip tem o evento `fechado` e o da
pasta não foi tocado antes; ficheiros extra e subpastas vão no zip; falha na escrita do zip
deixa a pasta; falha ao apagar deixa os dois e dá `TaskError`; `mktsk Foo` com `Foo.zip` não
duplica; rename recusado; listagem das fechadas; `--list` esconde-as por omissão; GUI com
confirmação e separador. Usa `tmp_path`, nunca pastas reais.

Documentação: `AGENTS.md` (regras de arquivo, CLI, GUI) e `README.md`.

Verificação: tudo verde, cobertura 100%.

Commit: `feat: close a task into an archive`.

Formato da resposta: o relatório final descrito em "Regras comuns" de `PLAN.md`, com a
descrição de qualquer decisão sobre como o arquivo aparece na listagem.
````

---

## Passo 11 — Reabrir uma tarefa arquivada

**Resultado:** `mktsk Foo` e o botão da GUI extraem o arquivo, a tarefa volta a ser uma pasta
e fica `em-progresso`.

**Termina quando:** fechar e reabrir devolve a pasta exactamente como estava, mais uma secção
de data e o evento novo.

````text
Papel: és um engenheiro Python sénior a trabalhar no repositório mktsk. Este passo extrai
arquivos e apaga um zip: a regra é nunca apagar o arquivo antes de confirmar que a pasta
extraída existe, está completa e abre.

Objectivo: reabrir uma tarefa arquivada.

Antes de começar, lê `AGENTS.md` e, em `PLAN.md`, "Regras comuns" e "Formato do .md". O
fecho (`close_task`, `find_task_archive`) já existe. Branch: `feat/reopen-task`.

Desenho:
- `reopen_task(location: Path, title: str) -> TaskResult`, por esta ordem:
  1. localizar o arquivo com `find_task_archive`
  2. extrair para um directório temporário no mesmo directório (por exemplo
     `.<nome>.part`), validando cada membro antes de o escrever: rejeitar caminhos
     absolutos e qualquer um que, resolvido, saia do directório de destino (zip slip)
  3. verificar: `testzip()` devolve `None`, e os ficheiros extraídos batem com o conjunto e
     os tamanhos do arquivo
  4. renomear o directório temporário para o nome da pasta
  5. retomar a tarefa com a lógica normal de retomar: acrescenta a secção de data de hoje
     e, pela regra do passo 8, muda o estado de `fechado` para `em-progresso`
  6. só então apagar o zip
- Qualquer falha até ao passo 5 inclusive: remover a pasta extraída (ou o temporário) e
  deixar o arquivo intacto. Falha ao apagar o zip: manter os dois e levantar `TaskError`
  a explicar a situação
- `open_or_create_task` e `resume_task` passam a reabrir um arquivo em vez de levantar o erro
  do passo 10. A mensagem diz `Reopened: <pasta>` e o que foi acrescentado
- Reabrir sem pedir confirmação, na CLI e na GUI. Na GUI, a acção de retomar numa tarefa do
  separador "fechadas" reabre e actualiza as listas
- A regra de unicidade do título mantém-se: depois de reabrir, não há zip e pasta com o
  mesmo título
- Se existir uma pasta e um arquivo com o mesmo título (herança de uma falha antiga), a
  pasta ganha e a situação não se corrige sozinha; `TaskError` com uma mensagem clara

Testes: ciclo fechar e reabrir devolve os mesmos ficheiros, mais a secção de hoje e o evento
`em-progresso`; membro com `..` rejeitado e nada escrito fora do destino; membro com caminho
absoluto rejeitado; zip corrompido deixa o arquivo e não cria a pasta; falha ao retomar
remove a pasta extraída; falha ao apagar o zip deixa os dois e dá `TaskError`;
mensagem `Reopened`; GUI a reabrir pelo separador "fechadas". Usa `tmp_path`.

Documentação: `AGENTS.md` (regras de arquivo, CLI, GUI) e `README.md`.

Verificação: tudo verde, cobertura 100%.

Commit: `feat: reopen an archived task`.

Formato da resposta: o relatório final descrito em "Regras comuns" de `PLAN.md`.
````

---

## Depois do passo 11

- Apagar `mktsk/migration.py` quando não fizer falta, num `refactor:` à parte
- Subir a `version` em `pyproject.toml` num branch próprio e só depois criar a tag, como diz
  `AGENTS.md`
