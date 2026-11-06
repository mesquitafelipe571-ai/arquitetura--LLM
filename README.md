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

## Orca

Ambiente para baixar, instalar e executar o [Orca](https://github.com/stablyai/orca), aplicativo desktop para trabalhar com agentes de programação.

O código oficial fica no submódulo `orca/`, fixado no commit [`6ff6b39e837d`](https://github.com/stablyai/orca/commit/6ff6b39e837da842df6977fcfe5e4a560fb0e748) (versão declarada 1.4.214). Os comandos usam pnpm 12.14.0, conforme o projeto oficial, e preservam os lockfiles. As dependências são baixadas no ambiente de desenvolvimento; não são armazenadas no GitHub.

### Usar no GitHub Codespaces

1. Abra **Code → Codespaces → Create codespace on main**. A configuração solicita 4 CPUs, 8 GB de RAM e 32 GB de armazenamento.
2. Aguarde a criação do ambiente. O comando `npm run orca:setup` baixa o submódulo e instala as dependências da raiz e de `mobile/`, incluindo a compilação dos módulos nativos.
3. No terminal do Codespace, execute:

   ```bash
   npm run orca:dev
   ```

4. Abra a aba **Ports**, acesse a porta **6080 — Desktop do Orca**, clique em **Connect** e use a senha padrão `vscode`. A janela do Orca aparece nesse desktop. Mantenha a porta com visibilidade **Private**.

A primeira instalação pode demorar vários minutos. Se a criação for interrompida, execute `npm run orca:setup` novamente. Codespaces usa a cota e as regras de cobrança da sua conta.

### Usar no computador

Instale **Git** e **Node.js 24**. Com nvm, use `nvm install` e `nvm use` depois de clonar. O pnpm é obtido automaticamente por `npm exec`, sem instalação global.

Também são necessários os requisitos nativos da sua plataforma:

- **macOS:** Xcode Command Line Tools (`xcode-select --install`).
- **Windows:** Python 3 e Visual Studio Build Tools com a carga **Desktop development with C++**.
- **Linux:** compilador C++, Python 3, bibliotecas do Electron e uma sessão gráfica. Em Debian 12:

  ```bash
  sudo apt-get update
  sudo apt-get install -y build-essential python3 pkg-config xvfb libgtk-3-0 libnss3 libgbm1 libasound2 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libxss1
  ```

  Em Ubuntu 24.04+ e Debian 13+, use `libasound2t64` no lugar de `libasound2`.

Clone e execute:

```bash
git clone https://github.com/mesquitafelipe571-ai/arquitetura--LLM.git
cd arquitetura--LLM
npm run orca:setup
npm run orca:dev
```

Os mesmos arquivos `.devcontainer/` podem ser usados no VS Code com a extensão **Dev Containers** e Docker. No container, use a porta 6080 para acessar o desktop.

### Comandos

| Comando | Função |
| --- | --- |
| `npm run orca:setup` | Baixa a revisão fixada do Orca e instala suas dependências. |
| `npm run orca:install` | Repete a instalação das dependências de um submódulo já baixado. |
| `npm run orca:dev` | Inicia o Orca em desenvolvimento no desktop disponível. |

O Bun usado pelos testes é uma dependência fixada do Orca e é instalado pelo pnpm. A criação de pacotes Linux de distribuição exige ferramentas adicionais, incluindo Docker para o helper de clipboard; consulte o guia oficial antes de gerar esses pacotes.

Para atualizar o Orca, escolha e revise uma nova revisão dentro de `orca/`, confira os requisitos e o `packageManager` dela e registre o novo ponteiro do submódulo neste repositório. Os comandos de setup não acompanham automaticamente mudanças em `main`.

### Estado da preparação

A configuração foi conferida contra o [guia oficial de instalação](https://github.com/stablyai/orca/blob/6ff6b39e837da842df6977fcfe5e4a560fb0e748/.github/CONTRIBUTING.md). A instalação completa, a construção do container e a abertura da interface ainda precisam de validação: o ambiente de execução desta sessão estava indisponível ao preparar estes arquivos.

A configuração não inicia nem cria um Codespace por conta própria. Para usar agentes dentro do Orca, configure as CLIs e as autenticações dos provedores que você pretende utilizar. O código do Orca mantém sua [licença MIT](https://github.com/stablyai/orca/blob/6ff6b39e837da842df6977fcfe5e4a560fb0e748/LICENSE).

## ECC para Codex

O [ECC](https://github.com/affaan-m/ECC) está instalado neste projeto por meio
das **47 skills da distribuição para Codex**, em
[.agents/skills](.agents/skills). Os arquivos estão versionados no próprio
repositório e ficam disponíveis após um clone normal.

Para usar:

1. Abra uma nova sessão do Codex na pasta deste repositório.
2. Digite o nome da skill junto do pedido, por exemplo:
   `$verification-loop confira as alterações`, `$tdd-workflow implemente esta
   função` ou `$security-review revise este código`.

Versão de origem: **ECC 2.2.3**. Consulte a
[origem, o escopo e as dependências opcionais](.agents/ecc/SOURCE.md), o
[manifesto de integridade](.agents/ecc/manifest.json) e a
[licença MIT](.agents/ecc/LICENSE).
