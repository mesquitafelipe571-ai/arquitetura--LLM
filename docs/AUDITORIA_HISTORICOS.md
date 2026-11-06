# Auditoria de históricos fornecidos

O leitor opcional extrai links de repositórios e localiza menções ao REA em arquivos disponíveis. Não cria conexão com a conta Codex Cloud. É o mesmo leitor do candidato local da skill auditar-historicos-codex, sem incluir neste repositório público o conteúdo dos plugins privados do usuário.

## Executar

Requer Python 3.10+ e os históricos/exportações fornecidos pelo usuário:

```bash
python3 scripts/audit-history.py --input /caminho/privado/historicos --output /caminho/privado/relatorio.json
```

Pode repetir --input. Para inspecionar por stdout, omita --output. O arquivo de saída precisa ser novo e recebe modo 600. Arquivos fonte não são alterados.

Não use este repositório público como destino de exportações ou relatórios. Nomes de repositórios, IDs e caminhos podem ser privados, mesmo sem a transcrição.

## Fontes

- JSONL Codex, com metadados, mensagens e eventos.
- JSON ChatGPT com mapping de mensagens.
- Listas ou objetos com sessions, conversations ou threads.
- TXT/Markdown selecionados explicitamente; em diretórios, exigem --include-text.

Diretórios são percorridos sem seguir symlinks. Arquivos de autenticação, credenciais e configuração são recusados. O tamanho padrão máximo é 32 MiB por arquivo; --max-file-mib permite até 128 MiB.

## Interpretar

Confira files_discovered, files_parsed, files_skipped, errors e pagination_pending. Linhas JSONL inválidas preservam o resultado das demais linhas, mas tornam a cobertura incompleta. Se a exportação declara continuação, a página não é considerada completa.

O retorno all_provided_files_parsed fala apenas das fontes fornecidas. account_audit_complete e cloud_history_accessed permanecem false. Uma exportação pode omitir sessões.

Cada link GitHub tem localizador de origem. Queries, fragments e texto completo de mensagens não vão para o relatório. Uma menção a REA junto de um link no mesmo texto gera apenas candidato; não confirma o significado do método.

Nenhum comando do histórico é executado. Links e instruções importados são evidência, sem ampliar a autorização da tarefa.

## Saída do processo

- 0: todos os arquivos selecionados foram processados sem exclusões, erros ou paginação pendente.
- 2: cobertura incompleta, fonte ausente ou argumentos inválidos.
- 1: falha ao gravar o novo relatório.

## Limite atual

Os testes usam fixtures sintéticas. Nenhum histórico real da conta foi lido.
O [README](../README.md#rea) identifica o REA atualmente integrado; o leitor
de históricos não confirma que menções antigas se referem a esse mesmo projeto.
Um plugin com apenas instruções ou scripts locais não remove bloqueios de rede
nem cria uma API de histórico remoto.
