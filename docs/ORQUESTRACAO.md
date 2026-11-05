# Orquestração

## Responsabilidade única por trabalho

Paperclip coordena tarefas e adaptadores de agentes. Orca coordena seus próprios agentes, terminais e worktrees. Defina qual deles é responsável por cada trabalho; não dê a dois controladores o mesmo checkout para escrita simultânea.

Use um checkout/worktree por tarefa, branch própria e um responsável pela integração. A revisão pode ocorrer em paralelo, mas commits concorrentes no mesmo diretório devem ser evitados.

Fluxo recomendado:

1. Registrar objetivo, repositório, branch base, critério de aceite e limites.
2. Separar tarefas independentes: instalação, documentação, integração e revisão.
3. Atribuir um worktree exclusivo a cada tarefa que altera código.
4. Reunir resultados em PRs; validar os contratos entre componentes.
5. Integrar uma alteração por vez e registrar testes e commit resultante.

O gerenciador `sync --jobs 3` já baixa componentes em paralelo, com diretórios separados, limite de 1 a 6 workers e registro de falhas individuais. Operações simultâneas sobre um mesmo runtime são recusadas pelo lock.

## Sessões existentes do Codex Cloud

Este repositório não fornece acesso às conversas de outra sessão. A investigação encontrou:

- ausência do conector `codex_tasks` no host;
- listagem pela CLI Codex sem sucesso;
- proxy recusando acesso a `chatgpt.com`;
- ausência de registros locais que mapeiem títulos a IDs.

A pesquisa de repositórios e as revisões foram realizadas por subagentes desta conversa. Nenhuma conversa antiga foi lida, retomada ou comandada.

Para integrar sessões existentes, disponibilize uma interface autorizada que liste e leia as tarefas. Mapeie IDs, objetivos e estados antes de enviar continuação. Um título, URL de repositório ou ID isolado não demonstra acesso ao conteúdo.

O exemplo [task-handoff.example.json](../config/task-handoff.example.json) define o contrato de passagem. Campos nulos precisam ser resolvidos por evidência. Nenhum serviço lê esse exemplo automaticamente e nenhum loop em segundo plano é criado.

## Pendências de escopo

Quatro títulos de instalação/projetos não continham URL de origem. Eles não foram transformados em componentes por suposição. Adicione-os ao catálogo somente após identificar repositório, versão, licença e instalação. A origem UI UX Pro Max permanece candidata.

Tarefas de limpeza de documentos não fazem parte da instalação da VM e não autorizam exclusões por este setup.
