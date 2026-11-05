# Componentes e decisões

As origens e revisões estão em [components.lock.json](../config/components.lock.json), verificadas em 2026-11-05. Cada componente conserva seu checkout e licença MIT. O instalador não cria um monorepo com os arquivos de terceiros.

## Paperclip

Origem: https://github.com/paperclipai/paperclip  
Commit: `d361f920716ac3aeb5c771246071abe8f2672efe`.

O Compose deriva do [quickstart oficial fixado](https://github.com/paperclipai/paperclip/blob/d361f920716ac3aeb5c771246071abe8f2672efe/docker/docker-compose.quickstart.yml), com:

- target Docker `production` explícito; o último estágio upstream é `cloud`;
- porta somente `127.0.0.1:3100`;
- PostgreSQL embutido, uploads, workspaces e chaves locais em um bind mount dedicado;
- sessão autenticada, duas chaves independentes e logs com rotação;
- healthcheck que exige JSON `status=ok`; HTTP 200 com `starting` não basta;
- image ID registrado após o build, para detectar troca de imagem.

Node >=24.11, pnpm 9.15.4 e Rust ficam no build/container. Não instale essas versões no host apenas para executar Paperclip.

**Reprodutibilidade:** o commit fixa o código. O [Dockerfile upstream](https://github.com/paperclipai/paperclip/blob/d361f920716ac3aeb5c771246071abe8f2672efe/Dockerfile) ainda usa `node:24-trixie-slim`, resolução de dependências e CLIs `@latest`. Builds do mesmo SHA podem produzir imagens diferentes. Preserve a imagem de um deployment que queira recuperar exatamente.

## Orca opcional

Origem: https://github.com/stablyai/orca  
Release: `1.4.250`; código: `b98a0fba16561fadc06868fe3e8710781d705efd`.

Verifique o download sem instalar:

```bash
python3 scripts/install-orca.py
```

Instale o pacote com hash verificado:

```bash
python3 scripts/install-orca.py --install
/usr/bin/orca-ide status --json
```

O download é temporário, o SHA256 vem do catálogo e a versão instalada é conferida com dpkg-query. A instalação não inicia o servidor remoto.

O recurso remoto é **beta**. A CLI pública `serve` escuta em **0.0.0.0**; `--pairing-address` apenas altera o endereço anunciado. Antes de iniciar, confira as regras da VPC e do host para permitir somente a rede privada desejada. A configuração de firewall não faz parte deste setup.

Após essa verificação, o comando documentado é:

```bash
/usr/bin/orca-ide serve --port 6768 --pairing-address ENDERECO_PRIVADO
```

O serviço de usuário pode ser examinado antes de instalar:

```bash
/usr/bin/orca-ide serve service install --port 6768 --dry-run --json
```

URLs de pairing concedem acesso e não devem ir ao Git. O launcher usa seu runtime Node e pode anunciar fallback Electron; bibliotecas gráficas/Xvfb podem ser necessárias em caminhos específicos. O gerenciador de pacotes resolve as dependências declaradas pelo .deb. Provedores/CLIs precisam ser autenticados no runtime do Orca.

Fonte: [servidores remotos](https://github.com/stablyai/orca/blob/b98a0fba16561fadc06868fe3e8710781d705efd/docs/site/content/docs/remote-servers.mdx).

## ECC e Ponytail

O perfil inicial oferece **skills sob demanda**, não os plugins completos com hooks.

| Origem | Skills |
| --- | --- |
| ECC 2.2.3 | `coding-standards`, `architecture-decision-records` |
| Ponytail 5.3.3 | `ponytail`, `ponytail-review`, `ponytail-audit` |

As cinco pastas verificadas contêm SKILL.md sem scripts obrigatórios externos. A skill de ADR solicita aprovação antes de criar decisões. Carregue cada uma quando pertinente: convenções diferentes podem conflitar, e as instruções do projeto e do usuário prevalecem.

ECC `--target codex` escreve em `~/.codex`; não existe alvo `codex-project` no adapter verificado. Por isso este setup não executa seu instalador global. Também não copia AGENTS.md upstream. A integração completa de hooks exigiria uma etapa separada de reconciliação das configurações.

Fontes: [ECC](https://github.com/affaan-m/ECC/tree/b38be6a7f6350964d59328b52f0624e1d1d552d1), [Ponytail](https://github.com/DietrichGebert/ponytail/tree/96608e078b2d5ea607c5c3b8b5a54d1c1fba6846).

## UI UX Pro Max opcional

`nextlevelbuilder/ui-ux-pro-max-skill` é uma correspondência de nome; a origem pretendida ainda precisa ser confirmada. Não faz parte de `sync` sem seleção.

```bash
python3 scripts/setup.py sync --component ui-ux-pro-max
```

O mecanismo de busca usa Python stdlib:

```bash
UI_SOURCE="$HOME/.local/share/arquitetura-llm/sources/ui-ux-pro-max/b7d5353e0130feb8c5574ef1251f8a1db1873ccb"
python3 "$UI_SOURCE/src/ui-ux-pro-max/scripts/search.py" "dashboard" --domain style --json
```

Isso ainda não instala a skill. Para gerar a skill oficial Codex, copie o checkout para um diretório de trabalho separado, use Node 24 e execute os comandos documentados:

```bash
UI_WORK="$HOME/.local/share/arquitetura-llm/tooling/ui-ux-pro-max"
mkdir -p "$(dirname "$UI_WORK")"
test ! -e "$UI_WORK" && cp -a "$UI_SOURCE" "$UI_WORK"
npm --prefix "$UI_WORK/cli" ci --ignore-scripts --no-audit --no-fund
npm --prefix "$UI_WORK/cli" run build
cd /caminho/do/projeto
node "$UI_WORK/cli/dist/index.js" init --ai codex --offline --dry-run
node "$UI_WORK/cli/dist/index.js" init --ai codex --offline
```

Revise o dry-run antes do último comando. Não use `--global`, `--force` ou `--legacy`. Node/npm não são instalados pelo bootstrap: são dependências desta opção. Preserve o checkout pinado; faça builds somente na cópia de trabalho.

Fonte: [CLI fixado](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/b7d5353e0130feb8c5574ef1251f8a1db1873ccb/cli/src/commands/init.ts).
