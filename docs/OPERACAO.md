# Operação e recuperação

Todos os comandos abaixo são executados no checkout do instalador, como usuário normal. O runtime padrão fica em `~/.local/share/arquitetura-llm`; repita o mesmo `--root` em todos os comandos se escolher outro caminho.

## Diagnóstico e parada

```bash
python3 scripts/setup.py --sudo-docker doctor
python3 scripts/setup.py --sudo-docker paperclip status
python3 scripts/setup.py --sudo-docker paperclip logs
python3 scripts/setup.py --sudo-docker paperclip stop
```

Parar preserva dados e container. Não há comando de remoção de volumes. Logs podem conter dados das tarefas; revise-os antes de compartilhar.

Cada root gera um nome Compose próprio. A porta 3100 continua fixa: uma segunda instância exige uma configuração de porta/public URL específica, não iniciar duas cópias com os defaults.

## Backup consistente

Antes de alterar imagens, configuração ou versões:

```bash
python3 scripts/setup.py --sudo-docker paperclip backup
```

O comando confirma que o container monta o diretório esperado, registra sua imagem/revisão, para esse container, arquiva o volume somente leitura e retoma **o mesmo container** se estava rodando. Não executa `compose up` para retomada nem troca a imagem durante o backup.

O diretório retornado contém `data.tar`, `paperclip.env`, catálogo e `manifest.json`. Somente um manifesto `complete=true` indica cópia concluída. Há indisponibilidade durante a cópia. O diretório tem modo 700, mas não há criptografia adicionada pelo script. Armazene cópias fora da VM usando seu armazenamento privado e política de acesso; backups incluem segredos.

O backup não inclui a imagem Docker. Para recuperação binária exata, salve a imagem identificada em `manifest.json` com `docker image save` e armazene-a junto do backup. A reconstrução upstream pode variar.

## Recuperação

1. Preserve a instalação original e escolha um **novo** diretório de runtime.
2. Use a mesma revisão deste instalador e o catálogo do backup; confirme o SHA Paperclip em `manifest.json`.
3. Execute `init` no novo runtime vazio e `sync`.
4. Copie `paperclip.env` do backup para `config/paperclip.env` do novo runtime, mantendo modo 600. Não regenere os segredos sobre dados existentes.
5. Carregue a imagem salva com `docker image load`. Confirme que seu ID corresponde a `image_id` do manifesto; marque-a com a tag Paperclip esperada pelo Compose.
6. Com a aplicação parada, extraia `data.tar` em `data/paperclip` do **novo runtime**, preservando proprietários/permissões. Use tar como root ou um container auxiliar com esse diretório montado.
7. Crie `state/paperclip-build.json` com `source_commit` e `image_id` copiados do manifesto; mantenha modo 600. O recibo deve descrever a imagem recuperada, não uma nova compilação.
8. Pare a instância original para liberar 3100. Execute `paperclip up` com o novo root e confirme healthcheck, login, dados e uploads antes de considerar a recuperação concluída.

A recuperação exige valores reais do manifesto, por isso não existe comando automático que sobrescreve uma instalação. Caso prefira reconstruir a imagem, execute `paperclip build` no novo runtime e trate a migração como atualização; o resultado binário pode diferir.

## Atualização

Faça backup **antes** de editar `paperclip.env` ou trocar o instalador. Atualize um componente por vez, com revisão do upstream, catálogo e Compose consistentes. Faça novo build e valide o recibo. `up` recusa uma imagem cujo ID difere do build registrado.

Mantenha o checkout antigo, backup e imagem anterior até validar a atualização. Migrações de banco podem impedir downgrade só da imagem; nesse caso recupere o backup correspondente em um novo runtime.

## Limitações de validação

Os testes locais verificam o instalador e suas proteções. Não houve criação/SSH em VM Google, build do Paperclip, instalação real do .deb Orca nem execução de provedores. O `doctor` testa presença e acesso a Git, Python, Docker, Compose e Buildx, mas não substitui o primeiro build e healthcheck.
