# Origem das skills da Anthropic

- Projeto: [anthropics/skills](https://github.com/anthropics/skills).
- Commit de origem: `2c5958ecac7cee2b583967a2c4981d0f4a75c579`.
- Diretório original: [skills](https://github.com/anthropics/skills/tree/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills).
- Licença: Apache 2.0, com o texto em `LICENSE.txt` dentro de cada skill.
  Avisos de componentes de terceiros em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

18 skills foram copiadas para `.agents/skills/<nome>/`:
`academy-guide`, `algorithmic-art`, `brand-guidelines`, `canvas-design`,
`claude-api`, `discernment-nudge`, `docx`, `frontend-design`, `internal-comms`,
`mcp-builder`, `pdf`, `pptx`, `skill-creator`, `slack-gif-creator`,
`theme-factory`, `web-artifacts-builder`, `webapp-testing` e `xlsx`.

## Alterações locais

A revisão do Codex no PR #15 apontou defeitos que também existem na origem; o item do `office/soffice.py` foi encontrado ao corrigir o do perfil LibreOffice. As 4 últimas linhas vieram da revisão dos commits de correção.
Eles foram corrigidos aqui e cobertos por `tests/test_anthropic_skill_fixes.py`
(todos os testes falham com os arquivos originais):

| Arquivo | Defeito | Correção |
| --- | --- | --- |
| `pptx/scripts/clean.py` | Lia `<p:sldId>` por regex; com outro prefixo de namespace, apagava slides válidos | Lê `sldId` e `r:id` pelo namespace XML, também na proteção contra exclusão |
| `docx/scripts/accept_changes.py` | Tempo esgotado do LibreOffice era informado como sucesso | Retorna erro (código de saída 1) |
| `docx/scripts/comment.py` | Sem `word/_rels/document.xml.rels`, os comentários ficavam desconectados | Cria o arquivo de relacionamentos vazio antes de registrar os comentários |
| `webapp-testing/scripts/with_server.py` | `terminate()` encerrava só o shell; o servidor filho continuava rodando | Cada servidor roda em um grupo de processos próprio, encerrado inteiro |
| `mcp-builder/scripts/evaluation.py` | Respondia só a primeira chamada de ferramenta de cada turno | Executa todas e envia todos os `tool_result` juntos |
| `docx/scripts/accept_changes.py` (segurança) | Perfil LibreOffice fixo em `/tmp/libreoffice_docx_profile`; outro usuário local podia plantar a macro executada | Perfil privado (`TemporaryDirectory`, modo 700) criado a cada execução |
| `{docx,pptx,xlsx}/scripts/office/soffice.py` (segurança) | Reutilizava `/tmp/lo_socket_shim.so` se já existisse e o carregava via `LD_PRELOAD` | Compila o shim em diretório privado (`mkdtemp`) e nunca carrega um arquivo preexistente |
| `skill-creator/eval-viewer/generate_review.py` | Saídas com `</script>` fechavam o script do visualizador e podiam injetar HTML | `<` escapado como `\u003c` no JSON embutido |
| `skill-creator/scripts/run_eval.py` | Execução que falhava contava como "não acionou" e podia virar aprovação | Falhas contadas em `errors`; consulta com falha nunca passa |
| `webapp-testing/scripts/with_server.py` | Saída do servidor em `PIPE` nunca lido travava servidores com muito log | O servidor herda stdout/stderr |
| `mcp-builder/scripts/evaluation.py` | Resultados do SDK MCP (modelos pydantic) quebravam o `json.dumps` | Serializa com `model_dump(mode="json")` |
| `skill-creator/scripts/aggregate_benchmark.py` | Com a duração já no `grading.json`, ignorava `total_tokens` do `timing.json` e usava `output_chars` | Lê a contagem real de tokens independentemente da duração |
| `skill-creator/scripts/run_eval.py` | A saída que chegava junto com o fim do processo era descartada sem passar pelo parser | Processa o restante da saída antes de sair do laço |
| `xlsx/scripts/recalc.py` | Texto que só mencionava `#VALUE!` era contado como erro e bloqueava a entrega | Conta só células de erro (`data_type == "e"`) com o código exato |
| `skill-creator/eval-viewer/generate_review.py` | Execução sem `eval_id` (`None`) quebrava a ordenação com `TypeError` | `None` vai para o fim da ordenação |
| `pdf/scripts/extract_form_field_info.py` | Opções simples (`"Red"`) viravam `R`/`e`; opções de 1 caractere davam `IndexError` | String vale como valor e texto; pares continuam indexados |
| `pptx/scripts/clean.py` | Relacionamentos e overrides lidos pelo nome literal; com o prefixo `r:` em um `.rels`, apagava mídia ainda usada | `Relationship` e `Override` lidos pelo nome local em qualquer namespace |
| `pdf/scripts/extract_form_field_info.py` | Campo com widgets separados em `/Kids` era descartado e depois recusado no preenchimento | Só pula contêineres (filhos com `/T`); campos terminais com widgets ficam |
| `slack-gif-creator/core/gif_builder.py` | Ao reduzir frames para emoji, mantinha o FPS e acelerava a animação | Duração de cada frame multiplicada pelo passo de amostragem; `duration_seconds` corrigido |
| `pdf/scripts/extract_form_field_info.py` | Checkbox com widget separado era tratado como grupo de rádio e não podia ser desmarcado | Só vira grupo de rádio com o flag de rádio em `/Ff`; estados do checkbox lidos do widget |
| `pdf/scripts/check_bounding_boxes.py` + `forms.md` | Comparava altura em pixels com fonte em pontos e podia aprovar caixas pequenas demais | Aceita o PDF como 2º argumento e converte para pontos; sem ele, avisa que a altura não foi conferida |
| `pdf/scripts/convert_pdf_to_images.py` | Falhava quando a pasta de saída não existia | Cria a pasta antes de salvar |
| `pptx/scripts/add_slide.py` | Inseria o slide nos `.rels` e em `[Content_Types].xml` trocando `</Relationships>`/`</Types>` literais; com prefixo (`pkg:`) não registrava nada, mas informava sucesso | Insere antes da tag de fechamento com o prefixo da raiz e falha se ela não existir; relacionamentos existentes achados com qualquer prefixo |
| `docx/scripts/comment.py` | Relacionamentos, overrides e IDs de comentário lidos e criados pelo prefixo; com `pkg:`/`ct:`/outro prefixo de `w`, criava elementos fora do namespace OPC e reutilizava `rId` e IDs | Lê pelo namespace e cria os elementos com o namespace e o prefixo da raiz |
| `docx/scripts/comment.py` | O comentário novo usava `w14:` sem declarar o namespace no `comments.xml` existente, que ficava malformado | Declara na raiz os namespaces do fragmento que faltarem |
| `mcp-builder/scripts/evaluation.py` + `reference/evaluation.md` | `-a`, `-e` e `-H` com `nargs="+"` engoliam o arquivo de avaliação dos exemplos e o `-e` repetido perdia valores | Opções repetíveis (`action="append"`), um valor por ocorrência |
| `skill-creator/scripts/aggregate_benchmark.py` | Ignorava o layout documentado (`with_skill/grading.json`, sem `run-*`) e devolvia `runs: []` | A configuração com `grading.json` vale como execução 1; `run-*` continua aceito |
| `skill-creator/scripts/run_eval.py` | Encerrava a avaliação na primeira ferramenta que não fosse a skill (ex.: `Read` de outro arquivo), reprovando consultas positivas | Continua lendo blocos e turnos até achar o acionamento ou o fim (`result`) |
| `skill-creator/scripts/package_skill.py` | Com a saída dentro da skill (`dist/` ou cwd), incluía o próprio `.skill` em crescimento no pacote | Ignora o arquivo que está sendo gravado |
| `skill-creator/eval-viewer/generate_review.py` | No layout `eval-N/<config>/run-K/` não achava `eval_metadata.json` e mostrava `(No prompt found)` | Procura também no diretório do teste, mantendo a precedência dos metadados mais próximos |
| `pptx/scripts/add_slide.py` | IDs (`Id`, `r:id`, `id`) e alvos lidos só entre aspas duplas; com aspas simples reutilizava `rId1` e duplicava relacionamentos | Aceita aspas simples e duplas em todas as leituras de atributos |
| `skill-creator/eval-viewer/viewer.html` | Com `--previous-workspace`, não carregava o feedback já salvo da iteração atual; o próximo salvamento apagava as avaliações anteriores | Sempre carrega o `feedback.json` do workspace atual; o da iteração anterior continua embutido à parte |
| `pptx/scripts/add_slide.py` | Na duplicação, só removia o relacionamento de notas sem prefixo; com `<pkg:Relationship>` original e cópia compartilhavam o mesmo `notesSlide` | Remove relacionamentos com qualquer prefixo |
| `webapp-testing/scripts/with_server.py` | Esperava só o shell: se ele saía com o SIGTERM e um filho o ignorava, o SIGKILL nunca chegava e o servidor ficava vivo | Espera o grupo inteiro e envia SIGKILL ao grupo que restar após o prazo |
| `skill-creator/scripts/run_eval.py` | Workers paralelos compartilham `.claude/commands`; escolher a cópia (idêntica) de outro worker contava como não acionado | Cópias da mesma execução levam um `run_tag` comum, e qualquer uma delas conta; execuções diferentes continuam separadas |
| `skill-creator/SKILL.md` (`assets/eval_review.html`) | A receita de substituição inseria o JSON e o nome/descrição sem escape; uma consulta com `</script>` quebrava a página e podia injetar HTML | Receita em Python que escreve `<` como `\u003c` no JSON e aplica `html.escape()` ao nome e à descrição |
| `skill-creator/eval-viewer/viewer.html` | Um salvamento automático pendente (800 ms) ou em andamento chegava depois do envio final e trocava `status: complete` por `in_progress` | "Submit" cancela o salvamento agendado e só envia depois do último em andamento |
| `skill-creator/scripts/run_eval.py` | `claude -p` que falhava ou esgotava o tempo sem acionar a skill virava `False`, e consultas negativas passavam sem terem sido avaliadas | Timeout ou código de saída diferente de zero sem `result` lançam erro, contado como falha por `run_eval()` |
| `skill-creator/eval-viewer/viewer.html` | `fetch()` resolve com HTTP 500; o envio final mostrava a confirmação sem salvar nem baixar o arquivo | Confere `response.ok`; erro HTTP cai no download de contingência (também no salvamento automático) |
| `webapp-testing/scripts/with_server.py` | Outro serviço já na porta respondia à checagem de prontidão; o servidor pedido falhava no bind e o teste rodava contra a aplicação errada | Recusa porta ocupada antes de iniciar e para a espera se o processo do servidor falhar |
| `mcp-builder/scripts/connections.py` | `list_tools()` ignorava `nextCursor` e entregava ao modelo só a primeira página de `tools/list` | Segue todas as páginas (aceita a API `params=` nova e `cursor=` antiga do `mcp`) |
| `claude-api/shared/evals/report/runner-scaffold.mjs` | A linha em `results.jsonl` era gravada antes do transcript e da referência; se essas gravações falhavam, a retomada pulava o caso e nunca os recuperava | Grava transcript e referência antes da linha que marca o caso como concluído |
| `skill-creator/scripts/aggregate_benchmark.py` | O delta era "primeira configuração menos a segunda" na ordem alfabética; com `with_skill`/`old_skill`, a melhoria aparecia como piora | As configurações de baseline (`without_skill`, `old_skill`) ficam sempre por último |
| `skill-creator/eval-viewer/generate_review.py` | Ao iniciar, enviava SIGTERM a qualquer processo na porta (via `lsof`), inclusive aplicações alheias do usuário | Não encerra nada: com a porta ocupada, usa uma porta livre e avisa |
| `pdf/forms.md` | O primeiro comando do fluxo chamava `scripts/check_fillable_fields`, sem `.py`, e falhava | Caminho corrigido para `scripts/check_fillable_fields.py` |
| `docx/scripts/merge_runs.py` | Ao unir runs, os filhos movidos perdiam os namespaces declarados no run removido (`unbound prefix`) | As declarações `xmlns` do run de origem acompanham os filhos movidos |
| `slack-gif-creator/core/gif_builder.py` | `remove_duplicates=True` eliminava quadros repetidos (pausas, poses) sem somar o tempo deles; a animação acelerava | Cada quadro mantido acumula a duração dos removidos; o GIF recebe duração por quadro (também na redução para emoji) |
| `skill-creator/eval-viewer/generate_review.py` | Só lia arquivos no primeiro nível de `outputs/`; `outputs/site/index.html` aparecia como "No output files" | Percorre as subpastas e mostra o caminho relativo |
| `skill-creator/scripts/aggregate_benchmark.py` | Só achava casos `eval-*`; com o nome descritivo que o `SKILL.md` pede, o benchmark saía vazio | Também aceita diretórios com `eval_metadata.json` |
| `{docx,pptx,xlsx}/scripts/office/helpers` `safe_extract()` (segurança) | Extraía sem limite de tamanho; um pacote de 16 KB gravava 16 MiB (zip bomb) e podia esgotar o disco | Recusa, antes de extrair, totais acima de 2 GiB e entradas acima de 1 MiB com taxa de compressão acima de 200x |
| `skill-creator/scripts/package_skill.py` (segurança) | Seguia links simbólicos e podia empacotar arquivos de fora da skill, como credenciais | Recusa links e caminhos fora da pasta da skill e apaga o pacote parcial; as exclusões (`node_modules` etc.) são aplicadas antes, então links nelas não bloqueiam; o pacote é gravado em arquivo temporário e movido para o destino, sem seguir um link plantado no caminho de saída |
| `pptx/scripts/thumbnail.py` + `office/helpers` | Procurava `p:sldId`, `r:id` e `Relationship` pelo prefixo; com outro prefixo não achava slides e as miniaturas falhavam | Usa o mesmo leitor por namespace de `clean.py`, movido para `office.helpers.listed_slide_rids` |
| `skill-creator/eval-viewer/viewer.html` (segurança) | `escapeHtml()` não escapava aspas; uma evidência com `"` saía do atributo `title` e injetava JavaScript no visualizador | `escapeHtml()` escapa `"` e `'`; `run_number` também passa por ela |
| `skill-creator/eval-viewer/generate_review.py` + `viewer.html` (segurança) | O servidor local (porta 3117) entregava saídas e aceitava feedback sem autenticação; outro usuário da máquina podia ler e adulterar | Token aleatório por execução exigido em todas as rotas; a URL aberta no navegador já o contém |

Ao atualizar as skills, confira se a origem já corrigiu cada item antes de
sobrescrever esses arquivos, e reporte os que continuarem pendentes.

`doc-coauthoring` ficou de fora: não tem arquivo de licença nem campo `license`,
e o repositório não declara licença na raiz.

Algumas skills usam ferramentas externas (por exemplo Python com bibliotecas de
documentos, Node ou Playwright), conforme as instruções de cada `SKILL.md`. Copiar
as skills não instala essas dependências.

Para atualizar, substitua as pastas pelas de um novo commit e registre-o aqui.
