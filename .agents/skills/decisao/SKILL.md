---
name: decisao
description: Encaminha um pedido de decisão ao agente `decisao`, que usa o Ollaya com o modelo winnow:e4b. Use quando o usuário pedir para classificar, priorizar, rotear, triar ou aprovar/bloquear itens com probabilidades calibradas.
---

# Decisão

O subagente herda os servidores MCP desta sessão, e o Codex não deixa um agente
desligá-los. Se os itens vêm de terceiros (tickets, e-mails, mensagens, JSON
externo) e o MCP `rea` está disponível aqui, não crie o subagente: peça ao usuário
para abrir uma sessão com `codex -c mcp_servers.rea.enabled=false` e repetir o
pedido nela.

Não decida nesta sessão. Crie um subagente do tipo `decisao`
(definido em `.codex/agents/decisao.toml`) e passe a ele:

1. Os itens: texto, arquivo ou JSON a decidir.
2. As perguntas: um preset do Ollaya (`triage`, `email`, `guard`, `moderation`,
   `router`, `agent`) ou as opções de `choice`, `score` e `noul` desejadas.
3. O que fazer com a resposta: só a tabela de decisões ou também a lista para
   revisão humana.

Aguarde o retorno e entregue ao usuário a tabela com item, decisão, probabilidade
e o que ficou para revisão. Se os itens ou as perguntas não estiverem claros,
pergunte ao usuário antes de criar o subagente.
