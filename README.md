# arquitetura--LLM

Paperclip integrado em [`paperclip/`](https://github.com/paperclipai/paperclip/tree/7351a9d74ff8e413a1ea1bfd47a1e3c26a81cc06), como submódulo Git fixado no commit `7351a9d74ff8e413a1ea1bfd47a1e3c26a81cc06`.

## Instalação

Em Linux ou macOS, tenha Git, Node.js 24.11 ou superior, Corepack (ou pnpm 9.15.4), Rust via rustup e um compilador C/C++ disponíveis. O instalador prepara a versão de Rust indicada pelo Paperclip. A primeira compilação nativa pode levar vários minutos.

```bash
git clone --recurse-submodules https://github.com/mesquitafelipe571-ai/arquitetura--LLM.git
cd arquitetura--LLM
./scripts/install-paperclip.sh
./scripts/start-paperclip.sh
```

Abra **http://localhost:3100** na máquina em que o servidor está rodando. A interface permite configurar a organização, os agentes e seus provedores de IA.

Se já clonou este repositório, o instalador inicializa o submódulo automaticamente.

## Dados e configuração

- `.runtime/paperclip/`: configuração, chaves locais, banco PostgreSQL, uploads e logs.
- `.runtime/`: ferramentas e caches locais, ignorados pelo Git.
- `PAPERCLIP_HOME`: permite escolher outro diretório para os dados persistentes.

```bash
PAPERCLIP_HOME=/caminho/dados ./scripts/install-paperclip.sh
PAPERCLIP_HOME=/caminho/dados ./scripts/start-paperclip.sh
```

Use o mesmo `PAPERCLIP_HOME` nos dois comandos. Guarde esse diretório ao mover a instalação e faça backup dos dados. As credenciais dos provedores são configuradas na instalação local.

## Verificação

Com o servidor iniciado:

```bash
curl http://localhost:3100/api/health
```

O resultado deve incluir `"status":"ok"`.

O submódulo preserva o código, a licença e o histórico do [Paperclip original](https://github.com/paperclipai/paperclip). Consulte seu README para detalhes de operação e configuração.

## Skill i-have-adhd

A skill está instalada neste repositório em
[.agents/skills/i-have-adhd/SKILL.md](.agents/skills/i-have-adhd/SKILL.md).
Ela organiza respostas com a ação principal primeiro, passos numerados e menos
distrações.

Para usar no Codex:

1. Abra uma nova sessão do Codex na pasta deste repositório.
2. Digite `$i-have-adhd` junto do seu pedido.

A ativação é manual. Depois de ativada, a skill orienta as respostas da sessão
até você pedir `stop adhd mode` ou `normal mode`.

Esta cópia local dispensa a instalação global do plugin para uso neste projeto.
Consulte a [origem e versão](.agents/skills/i-have-adhd/SOURCE.md) e a
[licença MIT](.agents/skills/i-have-adhd/LICENSE).
