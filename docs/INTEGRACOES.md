# Revisão das integrações

Este relatório registra a validação do ambiente de desenvolvimento. O perfil
opcional de VM tem [validação própria](VALIDACAO.md), catálogo e dados separados.
Após sua integração, AGENTS.md mantém o texto base Ponytail com instruções
específicas do projeto; as seis skills Ponytail e sua licença permanecem intactas.

Data: 06/11/2026. Escopo: as seis integrações iniciais encontradas no
`mesquitafelipe571-ai/arquitetura--LLM`, único repositório próprio disponibilizado
pela conexão GitHub nesta revisão.

## Resultado

| Integração | Estado verificado | Evidência |
| --- | --- | --- |
| Orca 1.4.214 | CONFIRMADO: instalado e iniciado em desenvolvimento | Raiz e mobile instalados com lockfiles; Electron 43.8.6 e módulos nativos carregados; compilação do desktop; HTTP 200 do renderer; CDP identificou a página Orca; CLI compilada sem erros de tipos em 3.826 arquivos; teste oficial criou worktree e terminal e confirmou saída real de comando (PASS) em contêiner isolado. |
| Paperclip | CONFIRMADO: instalado e iniciado em desenvolvimento | pnpm 9.15.4; Rust 1.97.1; runner nativo compilado em release; 430 migrações aplicadas e repetição sem pendências; HTTP 200 em `/`, `/api/companies` e `/api/health`, com `status: ok`; backup SQL.gz criado e íntegro, saúde sem avisos. |
| ECC 2.2.3 para Codex | CONFIRMADO: distribuição local íntegra | 47 skills; 113 arquivos comparados com os blobs da origem e licença verificada; 114 hashes SHA-256 do manifesto conferidos. Runtimes `ecc memory` e `ecc-plan-canvas` responderam a `--help`; memória inicializada em projeto temporário e `memory doctor` retornou `ok: true`. |
| Ponytail 5.3.3 | CONFIRMADO: arquivos de projeto íntegros | Seis skills, AGENTS.md e licença comparados com a revisão de origem: oito arquivos idênticos. |
| i-have-adhd 0.4.1 | CONFIRMADO: skill local íntegra | Skill e licença comparadas com a revisão de origem: dois arquivos idênticos. |
| Awesome Linux Dev Tools | CONFIRMADO: catálogo disponível | Submódulo baixado na revisão fixada; README e licença CC0 presentes. É um catálogo de referências, sem serviço ou compilação. |
| Superpowers 7.0.2 | CONFIRMADO: skills locais | 15 skills copiadas sem alterações do commit `22f0b46`; hooks fora da instalação. |
| Skills de Matt Pocock 1.3.2 | CONFIRMADO: skills locais | As 27 skills listadas no `plugin.json` foram copiadas sem alterações do commit `4ae2317`. |
| UI/UX Pro Max 2.15.0 | CONFIRMADO: skills locais e busca executada | 7 skills do commit `b7d5353`; caminho do script ajustado para relativo; `scripts/search.py` retornou resultados com Python 3 a partir de `.agents/skills`. |
| REA 6.8.0 | PARCIAL: configurado, servidor não iniciado | Agente e skill `rea` para Codex (`.codex/`, `.agents/skills/rea`) e Claude Code (`.claude/`); skill oficial `reverse-engineer-anything` copiada sem alterações do commit `de8b2f3`; arquivos TOML e frontmatter validados. `rea-agents@6.8.0` existe no npm, mas o servidor `npx -y rea-agents@6.8.0 mcp` não foi iniciado nesta revisão. |
| Ollaya 0.18.0 | PARCIAL: configurado, não instalado | Agente e skill `decisao` para Codex e Claude Code, servidor MCP `ollaya` e skill oficial `ollaya-decisions` copiada sem alterações da tag `v0.18.0` (`a8bce96`). O instalador não foi executado nesta revisão; `winnow:e4b` não foi baixado nem testado. |
| claude-melhores-skills | CONFIRMADO: catálogo disponível | Submódulo no commit `2c52b2a`; o repositório não declara licença. |
| Awesome Claude Code Mods | CONFIRMADO: catálogo disponível | Submódulo no commit `febe9d6`; licença CC0. |

As 125 skills estão disponíveis como arquivos de projeto para uma nova sessão do
Codex. As 125 possuem frontmatter válido, descrição e nomes únicos. A verificação
de integridade não representa um teste de cada serviço externo citado pelas skills. A distribuição Codex do ECC possui 47 skills; ela
tem escopo próprio, documentado em `.agents/ecc/SOURCE.md`.

## Correções aplicadas

- `npm run setup` prepara catálogo, Orca e Paperclip em sequência. O comando completo foi executado com sucesso e sua repetição preservou a instalação.
- O instalador do Orca termina com `orca:runtime`. O upstream pode concluir o
  postinstall mesmo quando o download do Electron falha; agora essa situação
  impede que o setup seja anunciado como concluído.
- O container inclui Rust 1.97.1 e executa o setup dos dois aplicativos. As três features oficiais estão fixadas por digest em `.devcontainer/devcontainer-lock.json`.
- Node.js exige a versão 24.11 ou superior da série 24, atendendo ao Paperclip.
- As portas de desktop 6080 e Paperclip 3100 estão configuradas no Dev Container.
- O comando `orca:dev:container` usa a opção oficial `--noSandbox` do
  electron-vite para contêineres de desenvolvimento. O comando de desktop local
  mantém a configuração normal do Electron.
- O container configura `NODE_USE_ENV_PROXY=1` para os downloads Node respeitarem
  o proxy. A verificação foi executada mantendo TLS e a confiança CA do ambiente.
- A imagem base usa Node 24 com Debian Bookworm e teve build e bibliotecas
  verificadas. O download da imagem MCR anterior foi impedido pelo domínio de
  distribuição bloqueado na rede desta sessão.
- Paperclip e catálogo usam clone superficial das revisões fixadas.
- O instalador do Paperclip cria o arquivo local de ambiente exigido pelo dev
  runner para checkouts com `.git` em arquivo, como submódulos. Reutiliza o
  gravador do upstream, mantém dados em `PAPERCLIP_HOME`, preserva um arquivo de
  ambiente preexistente e confere o resultado com o próprio carregador do servidor.
- Os comandos `npm run ecc` e `npm run ecc:canvas` selecionam ECC 2.2.3.

## Limites da validação

- Não foi criado um Codespace hospedado. O Dockerfile base foi construído;
  as três features fixadas foram instaladas em um contêiner isolado, onde
  Node.js 24.22.2, Rust 1.97.1 como usuário `node` e o desktop noVNC com HTTP 200
  foram confirmados. A CA do proxy desta sessão foi montada somente para leitura
  durante essa verificação, com TLS habilitado. O build completo pelo CLI do
  Dev Container encontrou a CA ausente nas etapas de features; a instalação e
  execução dessas etapas foram verificadas separadamente no contêiner, sem
  gravar a CA nas imagens ou no repositório.
- O Orca foi iniciado em display virtual separado. O teste de terminal foi
  executado em contêiner com perfil novo e diretório pessoal gravável. Logins e
  hooks vinculados às contas reais dos provedores precisam ser configurados
  no ambiente em que o aplicativo será usado.
- Não foram executadas tarefas de IA com provedores externos: não havia
  credenciais configuradas. Hooks e painéis específicos de outros assistentes
  permanecem fora da instalação local de skills para Codex.
- Não foi executada uma suíte completa de regressão dos projetos upstream nem
  gerado um instalador de distribuição. A validação se concentra na instalação,
  inicialização e integridade das integrações deste repositório. O teste de
  terminal do Orca foi o smoke test
  oficial `smoke:serve-terminal`, executado com Electron sem sandbox dentro
  do contêiner de validação.

Não foi feito um ensaio de restauração do backup; foi verificada a integridade
do arquivo gzip e o diagnóstico do serviço de backup.

Logs e dados gerados ficaram em `.runtime/`, ignorada pelo Git. Não há chaves,
perfis de execução, bancos ou dependências incluídos no commit desta revisão.
