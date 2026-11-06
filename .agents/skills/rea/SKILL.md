---
name: rea
description: Encaminha um pedido de engenharia reversa ao agente `rea`, que já traz o servidor MCP do REA configurado. Use quando o usuário pedir para investigar um binário, app, pacote ou site sem o código-fonte, comparar versões ou decompilar.
---

# REA

Não faça a análise nesta sessão. Crie um subagente do tipo `rea`
(definido em `.codex/agents/rea.toml`) e passe a ele:

1. O alvo: caminho do arquivo, nome do app, pacote ou URL.
2. A pergunta: qual recurso ou comportamento deve ser explicado.
3. O resultado esperado: explicação, comparação, código recuperado ou plano para
   reproduzir o recurso neste projeto.

Aguarde o retorno e entregue ao usuário a conclusão, as evidências e os limites
informados pelo agente. Se o alvo ou a pergunta não estiverem claros, pergunte
ao usuário antes de criar o subagente.
