# Origem das skills da Anthropic

- Projeto: [anthropics/skills](https://github.com/anthropics/skills).
- Commit de origem: `2c5958ecac7cee2b583967a2c4981d0f4a75c579`.
- Diretório original: [skills](https://github.com/anthropics/skills/tree/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills).
- Licença: Apache 2.0, com o texto em `LICENSE.txt` dentro de cada skill.
  Avisos de componentes de terceiros em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

18 skills foram copiadas para `.agents/skills/<nome>/`:
`academy-guide`, `algorithmic-art`, `brand-guidelines`, `canvas-design`,
`claude-api`, `discernment-nudge`, `docx`, `frontend-design`, `internal-comms`,
`mcp-builder`, `pdf`, `pptx`, `skill-creator`, `slack-gif-creator`,
`theme-factory`, `web-artifacts-builder`, `webapp-testing` e `xlsx`.

## Alterações locais

A revisão do Codex no PR #15 apontou 5 defeitos que também existem na origem.
Eles foram corrigidos aqui e cobertos por `tests/test_anthropic_skill_fixes.py`
(todos os testes falham com os arquivos originais):

| Arquivo | Defeito | Correção |
| --- | --- | --- |
| `pptx/scripts/clean.py` | Lia `<p:sldId>` por regex; com outro prefixo de namespace, apagava slides válidos | Lê `sldId` e `r:id` pelo namespace XML, também na proteção contra exclusão |
| `docx/scripts/accept_changes.py` | Tempo esgotado do LibreOffice era informado como sucesso | Retorna erro (código de saída 1) |
| `docx/scripts/comment.py` | Sem `word/_rels/document.xml.rels`, os comentários ficavam desconectados | Cria o arquivo de relacionamentos vazio antes de registrar os comentários |
| `webapp-testing/scripts/with_server.py` | `terminate()` encerrava só o shell; o servidor filho continuava rodando | Cada servidor roda em um grupo de processos próprio, encerrado inteiro |
| `mcp-builder/scripts/evaluation.py` | Respondia só a primeira chamada de ferramenta de cada turno | Executa todas e envia todos os `tool_result` juntos |

Ao atualizar as skills, confira se a origem já corrigiu cada item antes de
sobrescrever esses arquivos, e reporte os que continuarem pendentes.

`doc-coauthoring` ficou de fora: não tem arquivo de licença nem campo `license`,
e o repositório não declara licença na raiz.

Algumas skills usam ferramentas externas (por exemplo Python com bibliotecas de
documentos, Node ou Playwright), conforme as instruções de cada `SKILL.md`. Copiar
as skills não instala essas dependências.

Para atualizar, substitua as pastas pelas de um novo commit e registre-o aqui.
