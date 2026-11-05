# Validação da entrega

Data: 2026-11-05.

## Executado

- 50 testes unittest passaram usando Python 3.12.14 e Git 2.52.0: 28 do instalador e 22 do leitor opcional de históricos.
- `bash -n scripts/bootstrap-ubuntu.sh` passou.
- `scripts/setup.py plan` retornou os cinco componentes e não criou runtime.
- Duas revisões independentes examinaram implantação/backup e sincronização/skills.
- GitHub Actions passou no commit 164fda4f44d449e6a82dd4cd60ddabb0051e684a: [execução 42096473662](https://github.com/mesquitafelipe571-ai/arquitetura--LLM/actions/runs/42096473662).
- Alvo confirmado pelo usuário: Ubuntu 24.04 x86_64.

Os testes cobrem preservação de segredos, configuração ausente com dados existentes, locks, checkouts alterados, origens divergentes, arquivos extras/ignorados, falhas parciais em paralelo, colisões de skills/licenças, symlinks, isolamento Compose por runtime, sudo sem segredos no argv, readiness e backup sem recriação do container.

O leitor de históricos usa fixtures sintéticas. Foram verificados JSON/JSONL, páginas incompletas, arquivos inválidos ou grandes, symlinks, recusa de credenciais/configurações e ausência de transcrição no relatório. Nenhuma sessão real da conta foi acessada.

## Ainda não executado

- Instalação e verificação de funcionamento na VM Google real.
- Build/runtime Docker do Paperclip e fluxo real de onboarding.
- Instalação .deb e runtime remoto Orca.
- Ativação de plugins completos, hooks ou chamadas a provedores.
- Restauração completa do banco em uma VM.

A configuração Paperclip foi conferida contra o código/documentação upstream fixados. Chamadas Docker e saúde são simuladas nos testes de comportamento; isso não comprova funcionamento ponta a ponta.

## Instalação real no ambiente desta conversa

Paperclip 2026.1023.0 foi instalado via npm com Node 24.22.2, configuração autenticada e banco local. CLI, esquema de configuração, API, HTML e JavaScript responderam; a rota de empresas sem login retornou 403. Parada e reinicialização foram verificadas com os segredos e o banco preservados. O cadastro inicial do administrador permanece pendente.

A imagem oficial Docker foi tentada e excedeu o disco disponível do ambiente VFS; não foi considerada instalada. Esses resultados são do ambiente gerenciado, sem instalação ou validação na VM Google. Veja [operação nativa](PAPERCLIP_NATIVO.md).

## Reprodução local

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
bash -n scripts/bootstrap-ubuntu.sh
python3 scripts/setup.py plan
```

A validação GitHub Actions repete esses checks sem instalar os upstreams, usar secrets ou criar recursos cloud.
