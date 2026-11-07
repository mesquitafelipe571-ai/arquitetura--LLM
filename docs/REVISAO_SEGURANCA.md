# Revisão de segurança

Data: 07/11/2026. Revisão manual feita por um único revisor (Claude Code), lendo o
código e procurando padrões de risco. A varredura multiagente do plugin Claude
Security **não** rodou: a ferramenta de workflows que ela exige não estava
disponível na sessão. Não houve painel de verificação independente.

## Escopo

Lido integralmente: `scripts/` (setup.py, paperclip-native.py, install-orca.py,
check-repo.py, scripts shell), `.github/workflows/`, `.devcontainer/`,
`compose.paperclip.json`, `config/components.lock.json`, `.codex/`, `.claude/`,
`package.json` e `.gitmodules`. Lido parcialmente: `scripts/audit-history.py`
(as primeiras 80 linhas, que fazem a análise da entrada).

Busca por padrões de risco, sem leitura linha a linha, em `.agents/skills/`
(scripts copiados de terceiros): `shell=True`, `os.system`, `eval`/`exec`,
`pickle`, `yaml.load`, `verify=False`, `child_process.exec`, `curl | sh`.

Fora do escopo: o código-fonte dos submódulos (Orca, Paperclip e catálogos),
que pertence a outros projetos e não estava baixado.

## Resultado

Nenhuma vulnerabilidade explorável encontrada no código do projeto. Pontos
verificados:

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
| Actions de terceiros | Fixadas por tag (`@v4`, `@v5`), que pode ser movida | Fixadas por SHA completo; `check-repo.py` falha se alguma voltar a usar tag |
| Token do checkout | Gravado em `.git/config` durante o job (`persist-credentials` padrão) | `persist-credentials: false` |
| Análise estática | Nenhuma | CodeQL para Python, JavaScript/TypeScript e Actions |
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
