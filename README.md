# Arquitetura LLM — setup organizado para Google VM

Instalador e catálogo para manter Paperclip, Orca e skills em uma VM Linux, com fontes por commit, dados persistentes separados e downloads paralelos.

O alvo inicial é **Ubuntu 24.04, amd64 ou arm64**. Não há provisionamento de recursos Google, alteração de firewall nem ativação automática de agentes pagos.

| Componente | Entrega |
| --- | --- |
| Paperclip | Build Docker oficial `production`, autenticação, dados persistentes, acesso em `127.0.0.1:3100`, healthcheck e backup |
| Orca | Instalador opcional do pacote 1.4.250 com SHA256; servidor beta ativado manualmente |
| ECC | Duas skills selecionadas por projeto; sem hooks ou instalação global |
| Ponytail | Três skills selecionadas por projeto; sem hooks ou instalação global |
| UI UX Pro Max | Fonte candidata catalogada; sincronização e instalação opcionais |

## Instalação

Siga [o guia da VM Google](docs/INSTALACAO_GOOGLE_VM.md). Dentro deste checkout:

```bash
sudo bash scripts/bootstrap-ubuntu.sh
python3 scripts/setup.py --sudo-docker doctor
python3 scripts/setup.py plan
python3 scripts/setup.py init
python3 scripts/setup.py sync --jobs 3
python3 scripts/setup.py --sudo-docker paperclip build
python3 scripts/setup.py --sudo-docker paperclip up
```

O build inicial pode demorar: o Dockerfile upstream compila Rust, servidor e interface. Nenhuma chave de provedor é necessária para iniciar a aplicação; agentes exigem autenticação própria e podem gerar custos.

## Organização

```text
config/components.lock.json      Origens, commits, licenças e hashes de pacotes
compose.paperclip.json           Serviço Paperclip e suas fronteiras de rede/dados
scripts/setup.py                 Planejar, sincronizar, exportar skills e operar
scripts/bootstrap-ubuntu.sh      Pré-requisitos do sistema
scripts/install-orca.py          Download verificado e instalação opcional
docs/                           Instalação, componentes, operação e orquestração
tests/                          Testes sem cloud, Docker ou APIs pagas
```

Runtime padrão: `~/.local/share/arquitetura-llm/`.

```text
config/paperclip.env             Segredos locais, modo 600
sources/<componente>/<commit>/   Checkouts imutáveis separados
data/paperclip/                  Banco, uploads e workspaces
state/                          Recibos de sincronização e imagem
backups/                        Dados + configuração privada
```

Use `--root /caminho/absoluto` antes do subcomando para mudar o runtime. Nenhum dado de execução pertence a este repositório. Código upstream é baixado pelos SHAs do catálogo, preservando os repositórios e licenças originais.

## Documentação e validação

- [Instalação na VM Google](docs/INSTALACAO_GOOGLE_VM.md)
- [Componentes e decisões](docs/COMPONENTES.md)
- [Operação, atualização e recuperação](docs/OPERACAO.md)
- [Orquestração e limites das sessões](docs/ORQUESTRACAO.md)
- [Resultado da validação](docs/VALIDACAO.md)

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
bash -n scripts/bootstrap-ubuntu.sh
```

O instalador foi preparado e testado localmente. Build e funcionamento dos upstreams na VM ainda precisam ser verificados durante a instalação. Os SHAs fixam o código; o Dockerfile Paperclip contém dependências mutáveis. O recibo registra a imagem realmente produzida.
