---
name: decisao
description: Encaminha um pedido de decisão ao agente `decisao`, que usa o Ollaya com o modelo winnow:e4b. Use quando o usuário pedir para classificar, priorizar, rotear, triar ou aprovar/bloquear itens com probabilidades calibradas.
context: fork
agent: decisao
---

Decida com o Ollaya (winnow:e4b): $ARGUMENTS

Entregue uma tabela com item, decisão, probabilidade e o que foi para revisão
humana. Se os itens ou as perguntas não estiverem claros, diga exatamente o que
falta em vez de adivinhar.
