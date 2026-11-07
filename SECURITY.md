# Política de segurança

## Responsável

- **Mantenedor responsável pela segurança:** João Antonio Mesquita Felipe
- **GitHub:** [@mesquitafelipe571-ai](https://github.com/mesquitafelipe571-ai)
- **Ambiente de execução:** Google Cloud Platform, região `southamerica-east1`
  (veja [docs/INSTALACAO_GOOGLE_VM.md](docs/INSTALACAO_GOOGLE_VM.md))

## Escopo

Dentro do escopo: o código e a configuração mantidos neste repositório —
`scripts/`, `tests/`, `.github/workflows/`, `.devcontainer/`, `.codex/`,
`.claude/`, `config/`, `compose.paperclip.json` e `package.json`.

Fora do escopo deste repositório: as skills copiadas em `.agents/skills/` e os
submódulos Git (`orca`, `paperclip`, `awesome-linux-dev`, `claude-melhores-skills`,
`awesome-claude-code-mods`). Reporte falhas nesses componentes aos projetos de
origem; cada `.agents/<origem>/SOURCE.md` indica o link. Se uma falha de origem
afetar a forma como este repositório usa esse código, o reporte também é bem-vindo
aqui.

## Versões com suporte

Somente a branch `main` atual recebe correções de segurança.

## Como reportar uma vulnerabilidade

**Não abra uma issue pública.** Use o reporte privado de vulnerabilidades do GitHub:

1. Abra a aba **Security** do repositório.
2. Escolha **Report a vulnerability**.
3. Descreva o problema, o arquivo ou comando afetado, os passos para reproduzir e
   o impacto esperado.

## Prazos

| Etapa | Prazo |
| --- | --- |
| Confirmar o recebimento do reporte | até 7 dias |
| Avaliação inicial (procedente ou não, gravidade) | até 14 dias |
| Correção ou mitigação de falhas confirmadas | até 90 dias após o reporte |

A divulgação é coordenada: depois que a correção entra no `main`, um GitHub
Security Advisory é publicado para cada vulnerabilidade confirmada, com crédito a
quem reportou, salvo pedido em contrário. Se a correção precisar de mais de 90
dias, o mantenedor combina uma nova data com quem reportou antes de qualquer
divulgação pública.

## Verificações do repositório

- `scripts/check-repo.py` e a suíte de testes rodam em cada pull request
  (`.github/workflows/`). A verificação também falha se um workflow usar uma
  GitHub Action que não esteja fixada por SHA completo.
- O CodeQL (`.github/workflows/codeql.yml`) analisa o código Python e os
  workflows do GitHub Actions em cada pull request, no `main` e semanalmente.
- Os workflows rodam com `contents: read` e não mantêm o token do checkout.
- O Dependabot acompanha npm, pip, GitHub Actions, a imagem e as features do dev
  container e os submódulos Git fixados (`.github/dependabot.yml`).
- Alterações no `main` passam por pull request.
- A revisão de segurança manual mais recente está registrada em
  [docs/REVISAO_SEGURANCA.md](docs/REVISAO_SEGURANCA.md).
