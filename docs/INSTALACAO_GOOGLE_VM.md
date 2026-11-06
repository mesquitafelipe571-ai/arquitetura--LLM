# Instalação na VM Google

## Alvo e capacidade

A VM informada usa **Ubuntu 24.04 x86_64 (amd64)**. O bootstrap foi escrito para esse alvo e também aceita arm64. A capacidade de CPU, RAM e disco ainda não foi informada. Para o primeiro build, uma base prática é 4 vCPUs, 16 GiB de RAM e 80 GiB de disco; isso é recomendação, não dimensionamento medido. Usar uma VM existente evita criar recursos ou custos por este instalador.

Debian pode executar o gerenciador Python, mas precisa Git, Python >=3.10, Docker Engine, Compose v2 e Buildx instalados conforme a documentação Docker para sua distribuição. O bootstrap recusa outros sistemas.

Conecte-se com seu usuário normal e sudo. Não rode o gerenciador inteiro como root: ele usa o diretório pessoal para manter o runtime.

## Obter o código

Após merge na branch principal:

```bash
git clone https://github.com/mesquitafelipe571-ai/arquitetura--LLM.git
cd arquitetura--LLM
```

Enquanto a entrega estiver em revisão, use a branch completa:

```bash
git clone --branch setup/google-vm-organizado https://github.com/mesquitafelipe571-ai/arquitetura--LLM.git
cd arquitetura--LLM
```

Guarde o SHA retornado por `git rev-parse HEAD` junto do inventário da VM.

## Preparar e instalar

```bash
sudo bash scripts/bootstrap-ubuntu.sh
python3 scripts/setup.py --sudo-docker doctor
python3 scripts/setup.py plan
python3 scripts/setup.py init
python3 scripts/setup.py sync --jobs 3
python3 scripts/setup.py --sudo-docker paperclip pull
python3 scripts/setup.py --sudo-docker paperclip up
```

O bootstrap instala pacotes Ubuntu e habilita o daemon Docker. O gerenciador usa sudo somente para Docker; não adiciona automaticamente seu usuário ao grupo docker.

`sync` baixa quatro origens verificadas, cada uma em seu diretório. Ele não executa scripts desses repositórios. O candidato UI UX Pro Max exige seleção explícita:

```bash
python3 scripts/setup.py sync --component ui-ux-pro-max
```

Se um download falhar, os que terminaram ficam preservados. Corrija a conexão e repita o comando. Checkouts alterados são recusados; não são limpos automaticamente.

O comando pull verifica a revisão da imagem oficial e registra seu digest e image ID. Se a imagem não estiver publicada para o SHA, use paperclip build para executar o Dockerfile upstream. `up` exige o recibo e aguarda o healthcheck.

## Acesso pelo computador

A porta 3100 fica somente no loopback da VM. Em seu computador, substitua PROJETO, NOME_VM e ZONA por valores reais:

```bash
gcloud compute ssh NOME_VM --project PROJETO --zone ZONA -- -N -L 3100:127.0.0.1:3100
```

Abra `http://localhost:3100` no computador. Para VM sem IP público, seu ambiente Google pode exigir `--tunnel-through-iap`, permissões IAP e regras SSH correspondentes. O instalador não altera essas regras.

Conclua o onboarding do Paperclip. `bootstrap_pending` pode coexistir com serviço saudável e significa cadastro inicial pendente. Não exponha a porta sem configurar autenticação, domínio e TLS adequados.

## Credenciais e agentes

`init` gera duas chaves independentes de sessão/assinatura e as preserva em `~/.local/share/arquitetura-llm/config/paperclip.env`, com modo 600.

Para configurar um provedor, edite esse arquivo diretamente na VM; não cole chaves em commits ou comandos de chat. O Compose aceita OPENAI_API_KEY, ANTHROPIC_API_KEY e GEMINI_API_KEY. Gemini pode exigir chave restrita à sua API ou autenticação suportada pelo adaptador.

As CLIs dos adaptadores Paperclip ficam dentro do container. Um login feito no host não é automaticamente compartilhado com o container. Configure cada adaptador no seu runtime, com limite de gasto e validação próprios; nenhuma execução paga é iniciada pelo setup.

## Skills no seu projeto

O projeto de destino precisa existir. Exemplo:

```bash
python3 scripts/setup.py skills ecc --project /caminho/do/projeto
python3 scripts/setup.py skills ponytail --project /caminho/do/projeto
```

Isso copia apenas o catálogo curado para `.agents/skills/`, registra origem/commit e preserva as licenças. Arquivos diferentes já existentes causam recusa. Seu AGENTS.md e suas configurações globais são preservados.

Orca e UI UX Pro Max têm procedimentos opcionais em [Componentes](COMPONENTES.md).
