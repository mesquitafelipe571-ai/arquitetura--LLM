# Validação da entrega

Data: 2026-11-05.

## Executado

- 23 testes unittest passaram usando Python 3.12.14 e Git 2.52.0.
- `bash -n scripts/bootstrap-ubuntu.sh` passou.
- `scripts/setup.py plan` retornou os cinco componentes e não criou runtime.
- Duas revisões independentes examinaram implantação/backup e sincronização/skills.

Os testes cobrem preservação de segredos, configuração ausente com dados existentes, locks, checkouts alterados, origens divergentes, arquivos extras/ignorados, falhas parciais em paralelo, colisões de skills/licenças, symlinks, isolamento Compose por runtime, sudo sem segredos no argv, readiness e backup sem recriação do container.

## Ainda não executado

- Instalação em VM Google real ou validação de sua distribuição/arquitetura.
- Build/runtime Docker do Paperclip e fluxo real de onboarding.
- Instalação .deb e runtime remoto Orca.
- Ativação de plugins completos, hooks ou chamadas a provedores.
- Restauração completa do banco em uma VM.

A configuração Paperclip foi conferida contra o código/documentação upstream fixados. Chamadas Docker e saúde são simuladas nos testes de comportamento; isso não comprova funcionamento ponta a ponta.

## Reprodução local

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
bash -n scripts/bootstrap-ubuntu.sh
python3 scripts/setup.py plan
```

A validação GitHub Actions repete esses checks sem instalar os upstreams, usar secrets ou criar recursos cloud.
