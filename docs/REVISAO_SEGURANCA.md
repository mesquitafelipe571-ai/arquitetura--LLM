# Revisão de segurança

Data: 07/11/2026. Revisão manual feita por um único revisor (Claude Code), lendo o
código e procurando padrões de risco. A varredura multiagente do plugin Claude
Security **não** rodou: a ferramenta de workflows que ela exige não estava
disponível na sessão. Não houve painel de verificação independente.

## Escopo

Lido integralmente: `scripts/` (setup.py, paperclip-native.py, install-orca.py,
check-repo.py, scripts shell), `.github/workflows/`, `.devcontainer/`,
`compose.paperclip.json`, `config/components.lock.json`, `.codex/`, `.claude/`,
`package.json` e `.gitmodules`. `scripts/audit-history.py` foi lido só em parte (80 linhas) na revisão manual;
a falha abaixo estava no trecho que não foi lido.

Busca por padrões de risco, sem leitura linha a linha, em `.agents/skills/`
(scripts copiados de terceiros): `shell=True`, `os.system`, `eval`/`exec`,
`pickle`, `yaml.load`, `verify=False`, `child_process.exec`, `curl | sh`.

Fora do escopo: o código-fonte dos submódulos (Orca, Paperclip e catálogos),
que pertence a outros projetos e não estava baixado.

## Vulnerabilidade encontrada pela revisão de segurança do Codex

**Esgotamento de memória no leitor local de históricos** (`scripts/audit-history.py`,
gravidade média, só disponibilidade local). Introduzida no commit `62b9547`
(PR #1); corrigida no PR #4.

- **Causa:** `text_units()` copiava a chave inteira de um dicionário JSON para o
  localizador de cada item da lista abaixo dela, e `consume()` guardava esses
  localizadores. Os limites existentes contavam profundidade e quantidade de
  evidências, mas não bytes.
- **Exploração:** um JSON de ~300 KB com uma chave de 256 KiB e 1.024 links, aberto
  por quem roda o leitor, encerrava o processo com `MemoryError` (reproduzido com
  limite de 128 MiB). Exige que a pessoa execute o leitor sobre o arquivo; não há
  serviço remoto envolvido.
- **Correção:** chaves com mais de 128 caracteres viram `#sha256:<16 hex>` no
  localizador (também nos IDs de `mapping`), e a soma dos localizadores guardados
  tem limite de 4 MiB, que gera o erro `evidence_bytes_limit` em vez de derrubar o
  processo. Testes em `tests/test_history_audit.py`; o mesmo ataque passa a
  terminar com código 0.

## Injeção de código no gerador de tokens (skill de terceiros)

**Execução de código pela configuração Tailwind gerada**
(`.agents/skills/design-system/scripts/generate-tokens.cjs`, encontrada pela
revisão de segurança do Codex). Veio com a cópia da skill UI/UX Pro Max
(`nextlevelbuilder/ui-ux-pro-max-skill` em `b7d5353`) e existe também no projeto
de origem.

- **Causa:** com `--format tailwind`, o gerador serializava as cores com
  `JSON.stringify` e trocava todas as `"` por `'`, sem escapar as aspas simples já
  presentes nos nomes. Um nome de token como `x':(globalThis.__TOKEN_POC=1337),//`
  fechava a string e injetava uma expressão que rodava ao carregar o módulo.
- **Exploração:** exige que alguém gere a configuração Tailwind a partir de um
  `tokens.json` com nomes manipulados e depois carregue o módulo (build do
  frontend). Nenhum fluxo do repositório faz isso automaticamente; a integração
  da skill de marca usa só o formato CSS e nomes fixos.
- **Correção:** a troca de aspas foi removida (o JSON já é JavaScript válido) e
  cada nome de token precisa seguir `^[A-Za-z0-9_.-]+$`; nomes fora disso
  interrompem a geração com erro. O template da própria skill continua gerando um
  módulo válido. Teste em `tests/test_generate_tokens.py`, que falha sem a correção.
- **Pendente:** reportar ao projeto de origem.

## Execução de código local pelas skills de Office (skills de terceiros)

Skills copiadas de `anthropics/skills@2c5958e`; os defeitos existem na origem.

- **Perfil LibreOffice previsível** (`docx/scripts/accept_changes.py`, apontado pela
  revisão de segurança do Codex): a macro era lida de
  `/tmp/libreoffice_docx_profile`, aceita se contivesse `AcceptAllTrackedChanges`.
  Em máquina compartilhada, outro usuário podia criar esse perfil antes e ter
  Basic executado com os privilégios de quem usa `$docx`. Agora cada execução cria
  um perfil privado.
- **Biblioteca `LD_PRELOAD` previsível** (`office/soffice.py` em docx, pptx e xlsx,
  encontrado durante a correção acima): se `/tmp/lo_socket_shim.so` existisse, era
  carregado no LibreOffice sem verificação. Só ocorre onde o shim é necessário
  (ambientes sem sockets Unix). Agora o shim é compilado em diretório privado.
- **XSS no visualizador de avaliações** (`skill-creator/eval-viewer/viewer.html`,
  apontado pela revisão de segurança do Codex): `escapeHtml()` não escapava aspas
  e o resultado ia para um atributo `title`; uma evidência com `"` criava um
  handler como `onmouseover` que podia ler os dados embutidos. Agora a função
  escapa aspas, protegendo todos os usos em atributos. Junto, o JSON embutido
  passou a escapar `<` (saídas com `</script>`).
- **Visualizador sem autenticação** (`skill-creator/eval-viewer/generate_review.py`,
  apontado pela revisão de segurança do Codex): o servidor em `127.0.0.1:3117`
  servia prompts e saídas e aceitava gravação de `feedback.json` para qualquer
  usuário local, contornando as permissões dos arquivos. Agora cada execução gera
  um token aleatório exigido em todas as rotas.
- **Empacotador seguia links simbólicos** (`skill-creator/scripts/package_skill.py`,
  apontado pela revisão de segurança do Codex): `is_file()` e `ZipFile.write()`
  seguiam links, então uma skill recebida com um link para `credentials.env`
  levava o segredo para dentro do `.skill` entregue. Agora o empacotamento para
  em qualquer link ou caminho que saia da pasta da skill e apaga o arquivo parcial.
- Testes em `tests/test_anthropic_skill_fixes.py`, que falham com os arquivos
  originais. Pendente: reportar à origem.

## Resultado da revisão manual

Fora o item acima, nenhuma vulnerabilidade explorável foi encontrada no código
do projeto. Pontos verificados:

- Comandos externos são chamados com lista de argumentos, sem shell; nenhum
  `shell=True`.
- O pacote do Orca é baixado por HTTPS e verificado por SHA-256 antes da
  instalação.
- Os segredos do Paperclip são gerados com `secrets` e gravados com modo 600
  (`O_EXCL`). Os comandos recusam arquivos de segredo com permissões abertas e
  destinos que sejam symlinks, e os segredos não passam pelo `sudo`.
- Os componentes externos são fixados por commit SHA completo e a origem é
  conferida. A imagem oficial do Paperclip só é ativada se a revisão e o digest
  conferirem.
- O Paperclip escuta só em `127.0.0.1:3100`.

## Hardening aplicado

| Item | Antes | Depois |
| --- | --- | --- |
| Actions de terceiros | Fixadas por tag (`@v4`, `@v5`), que pode ser movida | Fixadas por SHA completo; `check-repo.py` falha se alguma voltar a usar tag (coberto por `tests/test_check_repo.py`) |
| Token do checkout | Gravado em `.git/config` durante o job (`persist-credentials` padrão) | `persist-credentials: false` |
| Análise estática | Nenhuma | CodeQL para Python e para os workflows (Actions). Sem JavaScript: o projeto não tem JS próprio; o JS das skills de terceiros fica em `.agents/`, que o CodeQL ignora |
| Dependências | Sem Dependabot | Dependabot para npm, pip, Actions, Docker, dev container e submódulos |

Já estavam corretos: `permissions: contents: read` nos dois workflows existentes.

## Observações sem correção neste momento

- `.devcontainer/Dockerfile` usa `node:24-bookworm` por tag, sem digest. Afeta
  só o ambiente de desenvolvimento, e o Dependabot passa a acompanhar a imagem.
  Fixar por digest é opcional.
- `.codex/config.toml`, `.claude/agents/rea.md` e os scripts npm executam
  pacotes pela versão exata (`rea-agents@6.8.0`, `pnpm@12.14.0`,
  `ecc-universal@2.2.3`), mas sem hash de integridade. Isso depende da
  confiança no registro npm.
- `.agents/skills/brainstorming/scripts/server.cjs` executa, por shell, o
  comando definido na variável `BRAINSTORM_OPEN_CMD`. Só quem configura o
  ambiente define essa variável, e o recurso é opt-in. É código de terceiros
  (Superpowers) e deve ser reportado ao projeto original, se for o caso.
