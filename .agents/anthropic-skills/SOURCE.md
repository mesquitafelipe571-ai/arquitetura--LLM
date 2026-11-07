# Origem das skills da Anthropic

- Projeto: [anthropics/skills](https://github.com/anthropics/skills).
- Commit de origem: `2c5958ecac7cee2b583967a2c4981d0f4a75c579`.
- Diretório original: [skills](https://github.com/anthropics/skills/tree/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills).
- Licença: Apache 2.0, com o texto em `LICENSE.txt` dentro de cada skill.
  Avisos de componentes de terceiros em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

18 skills foram copiadas sem alterações para `.agents/skills/<nome>/`:
`academy-guide`, `algorithmic-art`, `brand-guidelines`, `canvas-design`,
`claude-api`, `discernment-nudge`, `docx`, `frontend-design`, `internal-comms`,
`mcp-builder`, `pdf`, `pptx`, `skill-creator`, `slack-gif-creator`,
`theme-factory`, `web-artifacts-builder`, `webapp-testing` e `xlsx`.

`doc-coauthoring` ficou de fora: não tem arquivo de licença nem campo `license`,
e o repositório não declara licença na raiz.

Algumas skills usam ferramentas externas (por exemplo Python com bibliotecas de
documentos, Node ou Playwright), conforme as instruções de cada `SKILL.md`. Copiar
as skills não instala essas dependências.

Para atualizar, substitua as pastas pelas de um novo commit e registre-o aqui.
