# Operação do Paperclip instalado via npm

Este documento registra uma instalação anterior, de 05/11/2026, em outro ambiente
gerenciado. O caminho abaixo não é criado pelo merge nem por `npm run setup`.
O controlador requer os artefatos já preparados dessa instalação; para uma
instalação nova, escolha um dos perfis documentados no [README](../README.md).

O Paperclip foi instalado e iniciado no ambiente gerenciado desta conversa pelo pacote oficial **paperclipai 2026.1023.0**, com **Node 24.22.2** em um diretório isolado. Isso não representa instalação na VM Google do usuário.

O caminho Docker foi tentado, mas o armazenamento VFS do ambiente excedeu o disco disponível ao extrair a imagem oficial. A instalação npm foi concluída com todas as etapas de instalação habilitadas, após configurar os diretórios XDG dos adaptadores dentro do runtime.

## Estrutura e comandos deste ambiente

Runtime: `/workspace/runtime/arquitetura-llm`.

- `app/`: pacote npm e package-lock.json.
- `toolchain/`: Node com SHA256 conferido contra o manifesto oficial.
- `sources/paperclip/<commit>/`: fontes em checkouts separados.
- `data/paperclip/`: PostgreSQL, configuração, armazenamento e chave local.
- `config/paperclip.env`: segredos privados, preservados nas reinicializações.
- `state/`: recibos de artefatos, PID, logs e validações.
- `bin/paperclipctl`: atalho local para o controlador.

```bash
/workspace/runtime/arquitetura-llm/bin/paperclipctl status
/workspace/runtime/arquitetura-llm/bin/paperclipctl stop
/workspace/runtime/arquitetura-llm/bin/paperclipctl start
/workspace/runtime/arquitetura-llm/bin/paperclipctl logs
```

A API e a interface usam `http://127.0.0.1:3100` neste ambiente. Não há publicação externa. O cadastro inicial do administrador continua pendente; os registros de inicialização ficam em arquivo privado.

O controlador também pode ser chamado diretamente:

```bash
python3 scripts/paperclip-native.py --root /workspace/runtime/arquitetura-llm status
```

Ele controla uma instalação npm **já preparada**: requer o pacote em app/, o Node descrito por state/node-artifact.json, o config.json do Paperclip e o arquivo de segredos. Não é um comando de instalação do Node/npm.

O controlador verifica PID, tempo de início e linha de comando antes de sinalizar o grupo do serviço; a consulta ao executável em /proc não é necessária. Um lock impede controles concorrentes. Uma segunda chamada start reutiliza o processo saudável. A parada preserva os dados.

Não existe autostart de host configurado para esse processo nativo. Depois de reiniciar o ambiente, execute start. Use um root separado para outra instalação ou modo Docker.

## Configuração e integridade

O serviço usa modo authenticated/private, loopback, banco local e segredos com modo 600. Credenciais de provedores não foram preenchidas e não houve execução de agentes pagos.

Na instalação npm, configure XDG_DATA_HOME, XDG_STATE_HOME, XDG_CONFIG_HOME e XDG_CACHE_HOME para subdiretórios do runtime. Isso permite instalar/verificar OpenCode sem escrever no diretório pessoal protegido do host. HOME e CODEX_HOME permanecem os originais.

O package-lock.json foi conferido contra o campo integrity do registro npm para paperclipai e @paperclipai/server. A versão CLI/servidor é 2026.1023.0. O commit reportado no build-info/health do servidor é `1b4c803816e82b0265c8422e1a804327a7ed8c54`; a proveniência npm da CLI declara `ff835a3fc62fb50dd1c3cc2ff2246029adeb0d39`. Esses identificadores foram registrados separadamente; não se afirma que o build stamp do servidor corresponde ao commit da CLI nem ao SHA Docker do catálogo.

## Verificação real realizada

- CLI --version confirmou a versão instalada.
- O esquema oficial aceitou a configuração.
- Doctor: 12 checks aprovados.
- API /api/health: status ok, authenticated e bootstrap_pending.
- HTML e JavaScript da interface: HTTP 200.
- API /api/companies sem autenticação: HTTP 403.
- Parada e reinicialização reais concluídas, com PostgreSQL e segredos preservados.
- Start repetido manteve o mesmo processo.

Nenhuma conta de administrador, empresa ou agente foi criada. Para instalação em outra máquina, siga o [guia da VM](INSTALACAO_GOOGLE_VM.md) ou o [quickstart oficial npm](https://github.com/paperclipai/paperclip/blob/ff835a3fc62fb50dd1c3cc2ff2246029adeb0d39/docs/start/quickstart.md), conferindo o modo de acesso escolhido pelo onboarding.
