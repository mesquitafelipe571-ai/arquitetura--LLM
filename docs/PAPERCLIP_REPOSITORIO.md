# Paperclip incluído no repositório

O código oficial do Paperclip faz parte deste projeto em `vendor/paperclip`, como **submódulo Git**. O Git registra a origem e o commit completo `d361f920716ac3aeb5c771246071abe8f2672efe`, o mesmo de `config/components.lock.json`. A licença MIT e a estrutura upstream permanecem dentro do submódulo.

## Baixar o projeto completo

```bash
git clone --recurse-submodules https://github.com/mesquitafelipe571-ai/arquitetura--LLM.git
cd arquitetura--LLM
python3 scripts/check-paperclip-source.py --checkout
```

Para um clone existente, com suas alterações locais já preservadas:

```bash
git pull --ff-only
git submodule update --init --recursive
python3 scripts/check-paperclip-source.py --checkout
```

O download ZIP do GitHub não inclui o conteúdo dos submódulos. Use o clone recursivo para obter o código completo. No GitHub, `vendor/paperclip` abre o código upstream no commit registrado.

## Instalar a partir deste projeto

Na VM Ubuntu 24.04 x86_64, após o clone:

```bash
sudo bash scripts/bootstrap-ubuntu.sh
python3 scripts/setup.py --sudo-docker doctor
python3 scripts/setup.py init
python3 scripts/setup.py sync --component paperclip
python3 scripts/setup.py --sudo-docker paperclip pull
python3 scripts/setup.py --sudo-docker paperclip up
```

O submódulo disponibiliza a fonte para consulta e desenvolvimento. O instalador cria seu próprio checkout imutável do mesmo commit em `~/.local/share/arquitetura-llm/sources/paperclip/`, mantendo os dados de operação fora do projeto. Essa cópia permite preservar alterações de desenvolvimento feitas no submódulo. Para compilar a fonte fixada localmente, substitua `paperclip pull` por `paperclip build`.

O setup mantém autenticação e acesso em loopback. Acesso via SSH, cadastro inicial e credenciais estão no [guia da VM Google](INSTALACAO_GOOGLE_VM.md). Salvar o código no GitHub não inicia o servidor na VM.

## Atualizar a versão

Atualize o gitlink de `vendor/paperclip` e o commit do catálogo juntos, em uma alteração revisável. `git submodule update --init --recursive` mantém a versão registrada; não use `--remote` no procedimento de instalação.

O CI confere origem, gitlink, checkout e licença antes dos testes do instalador. A instalação npm realizada no ambiente da conversa usa uma release distinta, documentada em [operação nativa](PAPERCLIP_NATIVO.md).
