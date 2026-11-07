# Origem do UI/UX Pro Max

- Projeto: [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill).
- Versão na origem: `2.15.0`.
- Commit de origem: `b7d5353e0130feb8c5574ef1251f8a1db1873ccb`.
- Diretório original: [.claude/skills](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/b7d5353e0130feb8c5574ef1251f8a1db1873ccb/.claude/skills).
- Licença: MIT, copyright (c) 2024 Next Level Builder; texto integral em [LICENSE](LICENSE).

As 7 skills (`ui-ux-pro-max`, `banner-design`, `brand`, `design`, `design-system`,
`slides` e `ui-styling`), com seus scripts e dados, foram copiadas para
`.agents/skills/<nome>/`.

Única alteração: em `ui-ux-pro-max/SKILL.md`, o caminho
`${CLAUDE_PLUGIN_ROOT}/.claude/skills/ui-ux-pro-max/scripts/` virou `scripts/`,
relativo à pasta da skill, como as outras skills do pacote já fazem. A variável só
existe na instalação como plugin do Claude Code.

Segunda alteração, de segurança: em `design-system/scripts/generate-tokens.cjs`,
a saída `--format tailwind` trocava `"` por `'` no resultado do `JSON.stringify`,
e um nome de token com aspa simples injetava código no módulo gerado. A troca foi
removida e os nomes de token passam a aceitar só letras, dígitos, `_`, `.` e `-`
(teste em `tests/test_generate_tokens.py`). As chaves de metadados do DTCG (que começam com `$`, como `$extensions`)
são ignoradas antes da validação, como no original. A falha existe no commit de origem
acima; reporte-a ao projeto original e, ao atualizar a skill, confira se a
correção foi incorporada antes de sobrescrever este arquivo.

Os scripts de busca exigem só Python 3. Os scripts de geração de imagem de
`design`, `brand` e `banner-design` também pedem `google-genai`, `pillow` e uma
chave da API Gemini, conforme as instruções de cada skill.

Para atualizar, substitua as pastas pelas de um novo commit, repita a troca de
caminho acima e registre o novo commit aqui.
