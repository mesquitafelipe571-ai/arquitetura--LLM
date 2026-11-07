# Arquitetura

Este repositório reúne, num só lugar, o ambiente de trabalho com agentes de IA:
dois aplicativos de orquestração (Paperclip e Orca), um catálogo de skills e
agentes para Codex e Claude Code, e a esteira de verificação e segurança que
protege o `main`. Os diagramas abaixo usam Mermaid e aparecem desenhados no
GitHub.

## 1. Visão geral

```mermaid
flowchart TB
    subgraph REPO["Repositório arquitetura--LLM"]
        direction TB
        AG["AGENTS.md<br/>regras dos agentes"]
        SK[".agents/skills<br/>125 skills"]
        CX[".codex/<br/>agente rea + MCP"]
        CL[".claude/<br/>agente rea + skill"]
        SC["scripts/<br/>instaladores e utilitários"]
        CF["config/<br/>catálogo da VM e contrato de tarefas"]
        SM["submódulos<br/>orca, paperclip, catálogos"]
        GH[".github/<br/>workflows e Dependabot"]
    end

    subgraph PERFIS["Perfis de execução"]
        DEV["Desenvolvimento<br/>Codespaces / Dev Container"]
        VM["VM Google Cloud<br/>southamerica-east1"]
        NAT["Paperclip nativo via npm<br/>instalação já preparada"]
    end

    subgraph ASSIST["Assistentes"]
        CODEX["Codex"]
        CLAUDE["Claude Code"]
    end

    subgraph APPS["Aplicativos"]
        PC["Paperclip<br/>coordenação de agentes<br/>127.0.0.1:3100"]
        OR["Orca<br/>agentes, terminais e worktrees"]
    end

    subgraph SEC["Verificação e segurança"]
        CI["CI: check, validate, CodeQL"]
        DB["Dependabot"]
        RS["Regra proteger-main"]
        RV["Revisão do Codex nos PRs"]
    end

    REPO --> PERFIS
    SM --> DEV
    SC --> DEV
    SC --> VM
    CF --> VM
    SC --> NAT
    DEV --> PC
    DEV --> OR
    VM --> PC
    VM -.->|opcional| OR
    NAT --> PC
    AG --> CODEX
    AG --> CLAUDE
    SK --> CODEX
    CX --> CODEX
    CL --> CLAUDE
    GH --> CI
    GH --> DB
    CI --> RS
    RV --> RS
```

| Camada | Onde fica | Função |
| --- | --- | --- |
| Instruções | `AGENTS.md` | Regras para qualquer agente: mudança mínima completa, português, segurança, nada de segredos no Git |
| Skills | `.agents/skills/` | 125 skills de 9 origens, lidas pelo Codex ao abrir o projeto |
| Agentes | `.codex/`, `.claude/` | Agente `rea` de engenharia reversa e agente `decisao` (Ollaya, winnow:e4b), cada um com servidor MCP |
| Aplicativos | `paperclip/`, `orca/` (submódulos) | Orquestração de agentes |
| Instalação | `scripts/`, `config/`, `compose.paperclip.json`, `.devcontainer/` | Três perfis de execução |
| Verificação | `.github/`, `tests/`, `SECURITY.md` | CI, análise estática, dependências e política de segurança |

## 2. Perfil de desenvolvimento (Codespaces / Dev Container)

Tudo que é gerado fica em `.runtime/`, ignorada pelo Git.

```mermaid
flowchart LR
    subgraph DC[".devcontainer/"]
        IMG["Imagem node:24-bookworm<br/>+ bibliotecas do Electron e Xvfb"]
        FEAT["Features fixadas por digest:<br/>common-utils, desktop-lite, rust 1.97.1"]
        PORTS["Portas: 6080 desktop noVNC<br/>3100 Paperclip"]
    end

    PC_CMD["postCreateCommand<br/>npm run setup"]

    subgraph SETUP["npm run setup"]
        CAT["catalog:setup<br/>git submodule --depth 1"]
        ORS["orca:setup<br/>pnpm 12.14.0 --frozen-lockfile<br/>+ ensure:electron-runtime"]
        PCS["paperclip:setup<br/>scripts/install-paperclip.sh"]
    end

    subgraph SUBS["Submódulos"]
        S1["awesome-linux-dev"]
        S2["claude-melhores-skills"]
        S3["awesome-claude-code-mods"]
        S4["claude-code"]
        S5["orca @ 6ff6b39"]
        S6["paperclip @ 7351a9d"]
    end

    subgraph RT[".runtime/"]
        R1["paperclip/<br/>config, chaves, PostgreSQL, uploads"]
        R2["bin/, cache/, pnpm-store/"]
    end

    DEVCMD["npm run orca:dev[:container]<br/>npm run paperclip:dev"]

    DC --> PC_CMD --> SETUP
    CAT --> S1 & S2 & S3 & S4
    ORS --> S5
    PCS --> S6
    PCS --> R1
    PCS --> R2
    SETUP --> DEVCMD
```

- **Orca**: `npm run orca:dev` no desktop local; `orca:dev:container` desativa o
  sandbox do Electron apenas dentro do contêiner.
- **Paperclip**: `install-paperclip.sh` exige Node 24.11+, pnpm 9.15.4 (via
  Corepack) e Rust; aplica as migrações e grava os dados em `PAPERCLIP_HOME`
  (padrão `.runtime/paperclip`). `start-paperclip.sh` sobe a aplicação em
  `http://localhost:3100`.
- **Utilitários npm**: `npm run ecc` e `ecc:canvas` (ECC 2.2.3), `npm run rea` e
  `rea:setup` (REA 6.8.0), `npm run ollaya:install` e `ollaya` (Ollaya 0.18.0
  em `.runtime/ollaya`), `npm run check`.

## 3. Perfil da VM Google Cloud

Executado na VM Ubuntu 24.04 por `scripts/setup.py`, que usa só a biblioteca
padrão do Python. O runtime fica fora do repositório.

```mermaid
flowchart TB
    BOOT["sudo bash scripts/bootstrap-ubuntu.sh<br/>git, python3, docker, compose v2, buildx"]

    subgraph CLI["python3 scripts/setup.py"]
        PLAN["plan / doctor"]
        INIT["init<br/>gera segredos, modo 600"]
        SYNC["sync --jobs 1..6<br/>checkouts por SHA completo"]
        PULL["paperclip pull<br/>imagem oficial ghcr.io<br/>confere revisão e digest"]
        BUILD["paperclip build<br/>build local do mesmo SHA"]
        UP["paperclip up<br/>confere image ID com o recibo"]
        OPS["status / logs / stop"]
        BKP["paperclip backup<br/>para o container, arquiva, retoma o mesmo"]
        SKL["skills ecc|ponytail --project<br/>exporta skills sem sobrescrever"]
    end

    LOCK["config/components.lock.json<br/>paperclip d361f92, orca b98a0fb,<br/>ecc, ponytail, ui-ux-pro-max"]

    subgraph ROOT["~/.local/share/arquitetura-llm  (modo 700)"]
        RC["config/paperclip.env<br/>segredos, modo 600"]
        RS2["sources/&lt;id&gt;/&lt;commit&gt;/"]
        RD["data/paperclip/<br/>bind mount do container"]
        RST["state/<br/>sync.json, paperclip-build.json"]
        RB["backups/&lt;data&gt;/<br/>data.tar, env, manifest.json"]
        RL[".setup.lock<br/>uma mutação por vez"]
    end

    subgraph DOCKER["Docker Compose: compose.paperclip.json"]
        CT["container paperclip<br/>target production<br/>porta 127.0.0.1:3100<br/>healthcheck status=ok"]
    end

    ORCA["python3 scripts/install-orca.py --install<br/>.deb 1.4.250 com SHA-256 conferido"]
    ORSERVE["orca-ide serve (beta)<br/>escuta em 0.0.0.0: exige revisar a rede antes"]

    BOOT --> CLI
    LOCK --> CLI
    INIT --> RC
    SYNC --> RS2
    SYNC --> RST
    PULL --> RST
    BUILD --> RST
    UP --> DOCKER
    RC --> DOCKER
    RD --- CT
    BKP --> RB
    CLI --- RL
    ORCA -.-> ORSERVE
```

Proteções do `setup.py`:

- recusa runtime em `/`, no diretório pessoal ou dentro do repositório;
- recusa symlinks em segredos, locks, estado e destinos de skills;
- comandos externos sempre por lista de argumentos, sem shell;
- segredos nunca passam pelo `sudo` nem aparecem nas saídas;
- `up` só inicia a imagem cujo ID confere com o recibo de `pull` ou `build`.

Recuperação e atualização: [OPERACAO.md](OPERACAO.md). Instalação passo a
passo: [INSTALACAO_GOOGLE_VM.md](INSTALACAO_GOOGLE_VM.md).

## 4. Paperclip nativo (npm)

Caminho alternativo, registrado em [PAPERCLIP_NATIVO.md](PAPERCLIP_NATIVO.md),
para uma instalação npm já preparada.

```mermaid
flowchart LR
    CTL["scripts/paperclip-native.py<br/>start | status | stop | logs"]
    subgraph NROOT["--root do runtime"]
        APP["app/node_modules/paperclipai"]
        NODE["toolchain Node<br/>state/node-artifact.json"]
        ENV["config/paperclip.env (600)"]
        PID["state/native-service.json<br/>PID + início + linha de comando"]
        LOG["state/native-service.log (600)"]
    end
    SRV["Paperclip<br/>127.0.0.1:3100<br/>authenticated / private"]

    CTL --> APP
    CTL --> NODE
    CTL --> ENV
    CTL --> PID
    CTL --> LOG
    CTL -->|"grupo de processos próprio"| SRV
```

O controlador só sinaliza o processo cuja identidade (PID, tempo de início e
linha de comando) confere com o registro, e um lock impede controles
concorrentes.

## 5. Camada de agentes: skills, agentes e MCP

```mermaid
flowchart TB
    subgraph ORIG["Origens das skills (cada uma com SOURCE.md e licença)"]
        O1["ECC 2.2.3: 47"]
        O2["Matt Pocock 1.3.2: 27"]
        O3["Anthropic skills: 18"]
        O4["Superpowers 7.0.2: 15"]
        O5["UI/UX Pro Max 2.15.0: 7"]
        O6["Ponytail 5.3.3: 6"]
        O7["REA 6.8.0: 2"]
        O8["i-have-adhd 0.4.1: 1"]
        O9["Ollaya 0.18.0: 2"]
    end

    SKD[".agents/skills/<br/>125 skills"]
    ORIG --> SKD

    subgraph CODEXS["Codex"]
        CSK["$skill"]
        CRS["$rea<br/>.agents/skills/rea"]
        CAG[".codex/agents/rea.toml<br/>subagente rea"]
        CCF[".codex/config.toml<br/>mcp_servers.rea<br/>só em projeto confiável"]
        CDS["$decisao<br/>.agents/skills/decisao"]
        CDA[".codex/agents/decisao.toml<br/>subagente decisao"]
        CDF[".codex/config.toml<br/>mcp_servers.ollaya"]
    end

    subgraph CLAUDES["Claude Code"]
        KRS["/rea<br/>.claude/skills/rea<br/>context: fork"]
        KAG[".claude/agents/rea.md<br/>MCP rea embutido no agente"]
        KDS["/decisao<br/>.claude/skills/decisao<br/>context: fork"]
        KDA[".claude/agents/decisao.md<br/>MCP ollaya embutido no agente"]
    end

    MCP["Servidor MCP REA<br/>npx -y rea-agents@6.8.0 mcp"]
    RE["Skill reverse-engineer-anything<br/>roteiro oficial do REA"]
    ENG["Ghidra / Hopper / IDA / Kuna<br/>instalados no computador"]
    OMCP["Servidor MCP Ollaya<br/>sh scripts/ollaya.sh mcp"]
    OD["Daemon Ollaya 127.0.0.1:11435<br/>modelos em .runtime/ollaya/models<br/>winnow:e4b"]
    OS["Skill ollaya-decisions<br/>roteiro oficial do Ollaya"]

    SKD --> CSK
    CRS --> CAG
    CAG --> CCF --> MCP
    KRS --> KAG --> MCP
    CAG -.lê.-> RE
    KAG -.lê.-> RE
    MCP -.binários nativos.-> ENG
    CDS --> CDA --> CDF --> OMCP
    KDS --> KDA --> OMCP
    OMCP --> OD
    CDA -.lê.-> OS
    KDA -.lê.-> OS
```

- No **Codex**, o servidor MCP fica no `.codex/config.toml` do projeto, porque
  agentes do Codex não podem ter servidores próprios; as ferramentas do REA
  aparecem também na sessão principal.
- No **Claude Code**, cada servidor existe só dentro do seu agente (`rea`, `decisao`).
- O agente `decisao` só decide: devolve a resposta tipada e a probabilidade, e o
  que fica abaixo dos limites da skill vai para revisão humana.
- Skills de terceiros com alterações locais (correções de segurança e de bugs)
  estão listadas nos `SOURCE.md` de `.agents/ui-ux-pro-max/` e
  `.agents/anthropic-skills/`.

## 6. Orquestração de trabalho

```mermaid
flowchart LR
    T["Tarefa<br/>config/task-handoff.example.json:<br/>objetivo, branch base, critérios,<br/>limites, responsável"]
    D{"Quem coordena?"}
    P["Paperclip<br/>tarefas e adaptadores de agentes"]
    O["Orca<br/>agentes, terminais e worktrees"]
    W["Um worktree e uma branch por tarefa<br/>um único responsável pela escrita"]
    R["Revisão em paralelo"]
    PR["Pull request<br/>uma integração por vez"]

    T --> D
    D -->|um ou outro, nunca os dois| P
    D --> O
    P --> W
    O --> W
    W --> PR
    R --> PR
```

O contrato de passagem proíbe por padrão chamadas pagas, deploy, exclusões e
mudanças de credenciais (`external_actions`), e limita a concorrência a
`max_workers: 3`. Detalhes em [ORQUESTRACAO.md](ORQUESTRACAO.md).

## 7. Verificação, segurança e entrega

```mermaid
flowchart LR
    BR["Branch de trabalho"] --> PRQ["Pull request para main"]

    subgraph CHECKS["Verificações em cada PR"]
        C1["check<br/>scripts/check-repo.py:<br/>skills, agentes, TOML, JSON,<br/>Actions fixadas por SHA"]
        C2["validate<br/>testes unittest + sintaxe shell<br/>+ setup.py plan"]
        C3["CodeQL<br/>python e actions<br/>security-extended"]
        C4["Revisão do Codex<br/>código e segurança"]
    end

    PRQ --> C1 & C2 & C3 & C4
    C1 & C2 & C3 & C4 --> MG{"Merge"}
    RULE["Regra proteger-main:<br/>só via PR, sem force push,<br/>sem apagar o main"] --> MG
    MG --> MAIN["main"]

    DEP["Dependabot semanal:<br/>npm, pip, actions, docker,<br/>devcontainers, submódulos"] -.PRs.-> PRQ
    CQW["CodeQL semanal no main"] -.-> MAIN
    PVR["SECURITY.md<br/>reporte privado de vulnerabilidades<br/>prazos 7 / 14 / 90 dias"] -.-> MAIN
```

- Todos os workflows rodam com `contents: read`, Actions fixadas por SHA e
  `persist-credentials: false`.
- Revisões e correções de segurança ficam registradas em
  [REVISAO_SEGURANCA.md](REVISAO_SEGURANCA.md).

## 8. Fronteiras de confiança e dados

```mermaid
flowchart TB
    subgraph PUB["Público / Git"]
        G1["Código, skills, documentação,<br/>catálogos com commits fixados"]
    end
    subgraph LOCAL["Máquina local ou VM (privado)"]
        L1["Segredos: paperclip.env, modo 600"]
        L2["Dados do Paperclip: PostgreSQL, uploads"]
        L3["Backups: contêm segredos"]
        L4["Históricos e relatórios do<br/>audit-history.py (saída modo 600)"]
    end
    subgraph NET["Rede"]
        N1["Paperclip: só 127.0.0.1:3100"]
        N2["Orca serve: 0.0.0.0<br/>exige revisão de firewall/VPC"]
        N3["Downloads: GitHub, ghcr.io, npm<br/>conferidos por SHA, digest ou versão fixa"]
    end

    G1 -->|"nunca recebe"| L1
    L1 --> N1
    N3 --> G1
```

Regras que valem em todos os perfis, do `AGENTS.md`:

- nada de chaves, históricos de chats, bancos, URLs de pairing ou backups no Git;
- serviços do perfil de VM só em loopback; Orca remoto exige revisão da rede;
- nenhum recurso Google, serviço público, agente pago ou exclusão sem autorização;
- fontes fixadas por SHA completo; mudança de versão exige evidência e revisão.

## 9. Mapa de arquivos

| Caminho | Conteúdo |
| --- | --- |
| `AGENTS.md` | Instruções para agentes |
| `SECURITY.md` | Política de segurança e reporte privado |
| `README.md` | Uso de cada integração |
| `package.json` | Comandos `npm run` (setup, orca, paperclip, ecc, rea, ollaya, check) |
| `compose.paperclip.json` | Serviço Paperclip do perfil de VM |
| `config/components.lock.json` | Componentes do perfil de VM, fixados por SHA |
| `config/task-handoff.example.json` | Contrato de passagem de tarefas |
| `scripts/setup.py` | Gerenciador do perfil de VM |
| `scripts/bootstrap-ubuntu.sh` | Pré-requisitos da VM (root) |
| `scripts/install-orca.py` | Download e instalação verificada do Orca |
| `scripts/install-paperclip.sh`, `start-paperclip.sh`, `paperclip-env.sh` | Paperclip no perfil de desenvolvimento |
| `scripts/paperclip-native.py` | Controle do Paperclip nativo |
| `scripts/audit-history.py` | Leitor local de históricos (links e menções ao REA) |
| `scripts/check-repo.py` | Verificação estrutural usada pela CI |
| `tests/` | Testes do instalador, do leitor de históricos, da verificação e das correções em skills |
| `.agents/skills/` | Skills; `.agents/<origem>/` guarda SOURCE.md e licenças |
| `.codex/`, `.claude/` | Agentes e skills `rea` e `decisao` |
| `scripts/ollaya.sh` | Instala e roda o Ollaya fixado, só em loopback e em `.runtime/ollaya` |
| `.devcontainer/` | Ambiente de Codespaces |
| `.github/workflows/` | `check`, `validate`, `codeql` |
| `.github/dependabot.yml` | Atualizações de dependências |
| `docs/` | Guias, operação, revisões e esta arquitetura |
