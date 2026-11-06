# Origem do ECC para Codex

- Projeto: [affaan-m/ECC](https://github.com/affaan-m/ECC).
- Versão do projeto: `2.2.3`.
- Commit de origem: `b38be6a7f6350964d59328b52f0624e1d1d552d1`.
- Diretório original: [.agents/skills](https://github.com/affaan-m/ECC/tree/b38be6a7f6350964d59328b52f0624e1d1d552d1/.agents/skills).
- Licença: MIT, copyright (c) 2026 Affaan Mustafa; texto integral em [LICENSE](LICENSE).

## Conteúdo instalado

Esta instalação inclui as **47 skills que o upstream prepara para descoberta
local pelo Codex**: 47 arquivos `SKILL.md`, 47 metadados `agents/openai.yaml` e
19 arquivos de apoio, como referências e scripts. Todos os 113 arquivos foram
copiados integralmente, sem alterações, para `.agents/skills/<nome>/`.

O [manifesto](manifest.json) registra os caminhos relativos à raiz deste
repositório e o SHA-256 de cada arquivo importado, incluindo a licença.
A skill `i-have-adhd` tem origem e licença próprias e é mantida separadamente.

O catálogo completo do plugin nativo ECC possui 314 skills no mesmo commit.
Aqui está instalada a distribuição local de 47 skills para Codex, com seus
metadados específicos; os números descrevem distribuições diferentes.

## Uso e dependências

O Codex descobre as skills em `.agents/skills/` ao iniciar uma sessão neste
projeto. Use, por exemplo, `$verification-loop`, `$tdd-workflow` ou
`$security-review` com o pedido. Os nomes e descrições também orientam a seleção
automática pelo assistente, conforme a configuração do Codex.

As instruções de cada skill identificam eventuais ferramentas externas, contas,
credenciais ou executáveis necessários para uma tarefa. Copiar uma skill não
instala esses serviços nem fornece credenciais.

As skills `unified-memory` e `plan-canvas`, por exemplo, utilizam comandos do
runtime `ecc-universal`. Quando necessário, use o pacote fixado na mesma versão:

```bash
npx --yes --package ecc-universal@2.2.3 ecc memory --help
npx --yes --package ecc-universal@2.2.3 ecc-plan-canvas --help
```

Esses comandos baixam o runtime pelo npm quando executados. A instalação local
das skills funciona sem esse download; as ferramentas opcionais são preparadas
conforme a tarefa exigir.

Hooks e servidores MCP têm configuração e revisão próprias no Codex. Esta
cópia de skills não registra hooks, servidores MCP ou políticas globais. Evite
habilitar simultaneamente uma segunda cópia das mesmas skills pelo plugin
global ECC na mesma sessão.

## Atualização

Os arquivos estão fixados no commit acima e não se atualizam automaticamente.
Para atualizar, revise um novo commit do upstream e compare o diretório
`.agents/skills/`. Atualize somente os arquivos de propriedade do ECC listados
no manifesto; preserve as demais skills do projeto. Registre a nova versão,
o commit e os hashes nesta pasta.
