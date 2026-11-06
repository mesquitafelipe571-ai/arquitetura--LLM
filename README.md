# arquitetura--LLM

## Preparar todas as integrações

No Linux/macOS, instale os requisitos nativos descritos abaixo e execute:

```bash
npm run setup
```

Esse comando baixa o catálogo, instala o Orca (incluindo a verificação obrigatória
do Electron) e prepara o Paperclip. As 54 skills já são arquivos do projeto.
No GitHub Codespaces, o ambiente inclui Node.js 24, Rust 1.97.1 e desktop virtual,
e executa esse mesmo comando ao ser criado.

Para iniciar, use dois terminais:

```bash
npm run orca:dev:container  # Codespaces/Dev Container
npm run paperclip:dev      # http://localhost:3100
```

Em um desktop local, use `npm run orca:dev`. O comando com sufixo `:container`
desativa o sandbox do Electron para o ambiente de desenvolvimento isolado;
reserve-o para esse ambiente. No Codespaces, abra o desktop pela porta 6080 e o
Paperclip pela porta 3100; mantenha ambas privadas.

Os runtimes auxiliares do ECC ficam acessíveis por `npm run ecc -- memory --help`
e `npm run ecc:canvas -- --help`. Contas, logins e credenciais dos provedores são
configurados nas próprias aplicações, conforme o uso.

Consulte o [resultado da revisão das seis integrações](docs/INTEGRACOES.md).

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
2. Aguarde a criação do ambiente. O comando `npm run setup` baixa os três submódulos, instala Orca e Paperclip e verifica o runtime Electron. O Rust do Paperclip já faz parte do ambiente.
3. No terminal do Codespace, execute:

   ```bash
   npm run orca:dev:container
   ```

4. Abra a aba **Ports**, acesse a porta **6080 — Desktop do Orca**, clique em **Connect** e use a senha padrão `vscode`. A janela do Orca aparece nesse desktop. Mantenha a porta com visibilidade **Private**.

A primeira instalação pode demorar vários minutos. Se a criação for interrompida, execute `npm run orca:setup` novamente. Codespaces usa a cota e as regras de cobrança da sua conta.

### Usar no computador

Instale **Git** e **Node.js 24**. Com nvm, use `nvm install` e `nvm use` depois de clonar. O pnpm é obtido automaticamente por `npm exec`, sem instalação global. Em redes com proxy, use `NODE_USE_ENV_PROXY=1 npm run orca:setup`; o container já configura essa opção.

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
| `npm run orca:runtime` | Verifica o binário Electron e os módulos nativos; falha se não estiverem prontos. |
| `npm run orca:dev` | Inicia o Orca em desenvolvimento no desktop local. |
| `npm run orca:dev:container` | Inicia o Orca no desktop do Codespaces/Dev Container. |

O Bun usado pelos testes é uma dependência fixada do Orca e é instalado pelo pnpm. A criação de pacotes Linux de distribuição exige ferramentas adicionais, incluindo Docker para o helper de clipboard; consulte o guia oficial antes de gerar esses pacotes.

Para atualizar o Orca, escolha e revise uma nova revisão dentro de `orca/`, confira os requisitos e o `packageManager` dela e registre o novo ponteiro do submódulo neste repositório. Os comandos de setup não acompanham automaticamente mudanças em `main`.

### Validação da instalação

A instalação da raiz e de `mobile/`, o carregamento dos módulos nativos do Electron, a compilação em desenvolvimento e a inicialização do Orca foram verificados em 06/11/2026. A imagem base do container também foi construída, e as features de desktop e Rust foram instaladas e verificadas em contêiner isolado. O [relatório das integrações](docs/INTEGRACOES.md) detalha as evidências e as verificações que dependem de serviços externos.

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

## Ponytail

O [Ponytail](https://github.com/DietrichGebert/ponytail) está instalado neste
repositório como instruções e skills de projeto. Não exige dependências.

- [AGENTS.md](AGENTS.md): regras para assistentes que leem instruções do projeto.
- [.agents/skills](.agents/skills): seis skills disponíveis ao abrir este
  repositório em um assistente compatível.

No Codex, inicie uma nova sessão na pasta do projeto e invoque as skills pelo nome:

| Skill | Uso |
| --- | --- |
| `$ponytail` | Aplicar o modo de desenvolvimento com a menor mudança completa. |
| `$ponytail-review` | Revisar uma alteração ou um diff. |
| `$ponytail-audit` | Auditar o repositório. |
| `$ponytail-debt` | Listar atalhos registrados em comentários. |
| `$ponytail-gain` | Consultar os resultados do benchmark publicado pelo autor. |
| `$ponytail-help` | Consultar a referência de uso. |

Esta instalação usa skills de projeto, com nomes sem o prefixo de plugin
`ponytail:`. Os hooks de ativação, a persistência de níveis e o painel do Claude
Code dependem da instalação do plugin no assistente e não são habilitados por
estes arquivos. Consulte as
[instruções oficiais de instalação](https://github.com/DietrichGebert/ponytail/blob/96608e078b2d5ea607c5c3b8b5a54d1c1fba6846/INSTALL.md)
para esses recursos. As opções de configuração e atualização descritas em
`ponytail-help` referem-se ao plugin; as cópias deste repositório são atualizadas
manualmente.

Versão incorporada: **5.3.3**, commit
[`96608e078b2d5ea607c5c3b8b5a54d1c1fba6846`](https://github.com/DietrichGebert/ponytail/tree/96608e078b2d5ea607c5c3b8b5a54d1c1fba6846).
As instruções e as seis skills foram copiadas sem alterações. A licença MIT do
Ponytail está em [licenses/ponytail-MIT.txt](licenses/ponytail-MIT.txt) e se aplica
a esses arquivos.

Os números de `$ponytail-gain` vêm do
[benchmark do autor](https://github.com/DietrichGebert/ponytail/blob/96608e078b2d5ea607c5c3b8b5a54d1c1fba6846/benchmarks/results/2026-10-07-agentic.md),
não de medições realizadas neste projeto.

## Awesome Linux Dev Tools

O catálogo [madbob/awesome-linux-dev](https://github.com/madbob/awesome-linux-dev)
está disponível no submódulo `awesome-linux-dev/`, fixado no commit
[`57ed4c8619ef`](https://github.com/madbob/awesome-linux-dev/commit/57ed4c8619ef5b8b4dc51ca551c183d6a5d577cd).
Consulte a [lista de ferramentas](awesome-linux-dev/README.md) para referências
de editores, terminais, bancos de dados e outros recursos para desenvolvimento Linux.

Em uma cópia já clonada deste repositório, baixe o catálogo com:

```bash
git submodule update --init -- awesome-linux-dev
```

O catálogo contém documentação e dispensa compilação ou configuração de serviço.
Os aplicativos listados são instalados individualmente, conforme sua distribuição
Linux e as instruções de cada projeto. O conteúdo mantém a
[licença original](awesome-linux-dev/LICENSE).
