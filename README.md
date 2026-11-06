# Arquitetura LLM — setup organizado para Google VM

Instalador e catálogo para manter Paperclip, Orca e skills em uma VM Linux, com fontes por commit, dados persistentes separados e downloads paralelos. O código oficial do Paperclip está incluído como submódulo Git em `vendor/paperclip`.

O alvo inicial é **Ubuntu 24.04, amd64 ou arm64**. Não há provisionamento de recursos Google, alteração de firewall nem ativação automática de agentes pagos.

| Componente | Entrega |
| --- | --- |
| Paperclip | Build Docker oficial `production`, autenticação, dados persistentes, acesso em `127.0.0.1:3100`, healthcheck e backup |
| Orca | Instalador opcional do pacote 1.4.250 com SHA256; servidor beta ativado manualmente |
| ECC | Duas skills selecionadas por projeto; sem hooks ou instalação global |
| Ponytail | Três skills selecionadas por projeto; sem hooks ou instalação global |
| UI UX Pro Max | Fonte candidata catalogada; sincronização e instalação opcionais |

## Instalação

Baixe o projeto com o código do Paperclip:

```bash
git clone --recurse-submodules https://github.com/mesquitafelipe571-ai/arquitetura--LLM.git
cd arquitetura--LLM
python3 scripts/check-paperclip-source.py --checkout
```

Siga [o guia da VM Google](docs/INSTALACAO_GOOGLE_VM.md). Para instalar somente o Paperclip:

```bash
sudo bash scripts/bootstrap-ubuntu.sh
python3 scripts/setup.py --sudo-docker doctor
python3 scripts/setup.py plan
python3 scripts/setup.py init
python3 scripts/setup.py sync --component paperclip
python3 scripts/setup.py --sudo-docker paperclip pull
python3 scripts/setup.py --sudo-docker paperclip up
```

O comando pull baixa a imagem oficial correspondente ao SHA e verifica revisão/digest. Para compilar localmente, use paperclip build; o Dockerfile upstream compila Rust, servidor e interface. Para baixar também os demais componentes verificados, execute `python3 scripts/setup.py sync --jobs 3`. Nenhuma chave de provedor é necessária para iniciar a aplicação; agentes exigem autenticação própria e podem gerar custos.

## Organização

```text
config/components.lock.json      Origens, commits, licenças e hashes de pacotes
vendor/paperclip/                Código oficial completo via submódulo fixado
compose.paperclip.json           Serviço Paperclip e suas fronteiras de rede/dados
scripts/setup.py                 Planejar, sincronizar, exportar skills e operar
scripts/bootstrap-ubuntu.sh      Pré-requisitos do sistema
scripts/install-orca.py          Download verificado e instalação opcional
scripts/audit-history.py         Leitor opcional de históricos/exportações locais
scripts/paperclip-native.py      Controle de uma instalação npm já preparada
scripts/check-paperclip-source.py Verificação do submódulo e do catálogo
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
- [Paperclip no repositório e clone completo](docs/PAPERCLIP_REPOSITORIO.md)
- [Componentes e decisões](docs/COMPONENTES.md)
- [Operação, atualização e recuperação](docs/OPERACAO.md)
- [Orquestração e limites das sessões](docs/ORQUESTRACAO.md)
- [Auditoria de históricos fornecidos](docs/AUDITORIA_HISTORICOS.md)
- [Operação da instalação Paperclip via npm](docs/PAPERCLIP_NATIVO.md)
- [Resultado da validação](docs/VALIDACAO.md)

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
bash -n scripts/bootstrap-ubuntu.sh
```

O instalador foi preparado e testado localmente. Build e funcionamento dos upstreams na VM ainda precisam ser verificados durante a instalação. Os SHAs fixam o código; o Dockerfile Paperclip contém dependências mutáveis. O recibo registra a imagem realmente produzida.
