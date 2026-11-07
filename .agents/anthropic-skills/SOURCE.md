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
| `skill-creator/scripts/run_loop.py` | Com 1 consulta positiva e 1 negativa, o holdout reservava as duas para teste; com o treino vazio o loop dizia `all_passed` sem otimizar | Nunca reserva o último caso de um grupo; treino vazio vira erro explícito |
| `skill-creator/eval-viewer/generate_review.py` (segurança) | Um link simbólico em `outputs/` fazia o visualizador embutir no HTML qualquer arquivo legível (ex.: `secret.env`) | Links e caminhos que saem de `outputs/` aparecem como "(symbolic link not shown)", sem conteúdo |
| `pdf/scripts/fill_pdf_form_with_annotations.py` | Em páginas com `/Rotate` 90/270, as coordenadas medidas na página exibida eram convertidas com o MediaBox original e o texto caía no lugar errado | A rotação é aplicada ao conteúdo (`transfer_rotation_to_content`) antes da conversão |
| `skill-creator/eval-viewer/viewer.html` (segurança) | `summary.passed/failed/total` do `grading.json` iam sem escape para `innerHTML`; um valor com HTML executava JavaScript no visualizador | Só números finitos chegam ao HTML |
| `skill-creator/eval-viewer/generate_review.py` (segurança) | Com `outputs/` (ou uma pasta acima) sendo um link, o destino externo virava a raiz confiável e seus arquivos eram embutidos | A raiz confiável é o caminho real do workspace mais o caminho relativo de `outputs/`; qualquer link no meio é recusado |
| `{docx,pptx,xlsx}/scripts/office/validators/base.py` | Sem o `.rels` da parte, pulava a checagem de `r:id`/`r:embed`/`r:link` e aprovava referências quebradas | `.rels` ausente vale como mapa vazio; as referências são conferidas |
| `{docx,pptx,xlsx}/scripts/office/validators/base.py` | Exigia `authorId` único por comentário (`p:cm`) e reprovava dois comentários do mesmo autor | Regra removida; `authorId` referencia o autor, não identifica o comentário |
| `skill-creator/eval-viewer/generate_review.py` (segurança) | `grading.json`, `eval_metadata.json` e `transcript.md` eram lidos seguindo links e o conteúdo ia para o HTML | Só lê arquivos regulares realmente dentro do workspace |
| `pptx/scripts/clean.py` | Sem `ppt/presentation.xml` (ou o `.rels` dele), tratava a apresentação como vazia e apagava todos os slides | Recusa a limpeza (`RefusedToClean`) quando o índice está ausente e há slides no disco |
| `skill-creator/eval-viewer/generate_review.py` (segurança) | Um `feedback.json` que fosse link fazia o salvamento sobrescrever o arquivo de destino (e o GET servi-lo à página) | Grava em temporário e substitui a entrada sem seguir o link; o GET só lê arquivo regular |
| `skill-creator/eval-viewer/viewer.html` (segurança) | No benchmark, o nome da configuração e outros valores do `benchmark.json` (data, evals, deltas, contagens) iam sem escape para `innerHTML` | Todos os valores passam por `escapeHtml()` |
| `pptx/SKILL.md`, `docx/SKILL.md` (segurança) | O fluxo de edição extraía com `extractall()`/`unzip`, sem os limites do `safe_extract()` (zip bomb, links, travessia) | O comando documentado usa `office.helpers.safe_extract` |
| `pptx/scripts/clean.py` | Um `r:id` listado em `<p:sldIdLst>` sem relacionamento no `.rels` era descartado e o slide correspondente apagado como órfão | Recusa a limpeza enquanto algum ID listado não tiver relacionamento de slide |
| `skill-creator/eval-viewer/viewer.html` | Fechar o diálogo de conclusão salvava de novo com `status: in_progress`, desfazendo o envio final | O diálogo só fecha; uma edição posterior salva pelo auto-save |
| `pptx/scripts/thumbnail.py` + `office/helpers` (segurança) | `get_slide_info()` lia o PPTX com `ZipFile.read()` sem os limites do `safe_extract()`; um deck de 33 KB alocava 32 MiB | Os limites viraram `check_archive_limits()`, usado pelo `safe_extract()` e chamado antes de ler o deck |
| `skill-creator/scripts/run_loop.py` (segurança) | O relatório `--report auto` ia para um nome previsível no tmp compartilhado; um link plantado ali tinha o alvo sobrescrito | Arquivo criado com `mkstemp()` (nome aleatório, criação exclusiva) e reutilizado nas atualizações |
| `skill-creator/scripts/package_skill.py` (segurança) | Seguia links simbólicos e podia empacotar arquivos de fora da skill, como credenciais | Recusa links e caminhos fora da pasta da skill e apaga o pacote parcial; as exclusões (`node_modules` etc.) são aplicadas antes, então links nelas não bloqueiam; o pacote é gravado em arquivo temporário e movido para o destino, sem seguir um link plantado no caminho de saída |
| `pptx/scripts/thumbnail.py` + `office/helpers` | Procurava `p:sldId`, `r:id` e `Relationship` pelo prefixo; com outro prefixo não achava slides e as miniaturas falhavam | Usa o mesmo leitor por namespace de `clean.py`, movido para `office.helpers.listed_slide_rids` |
| `skill-creator/eval-viewer/viewer.html` (segurança) | `escapeHtml()` não escapava aspas; uma evidência com `"` saía do atributo `title` e injetava JavaScript no visualizador | `escapeHtml()` escapa `"` e `'`; `run_number` também passa por ela |
| `skill-creator/eval-viewer/generate_review.py` + `viewer.html` (segurança) | O servidor local (porta 3117) entregava saídas e aceitava feedback sem autenticação; outro usuário da máquina podia ler e adulterar | Token aleatório por execução exigido em todas as rotas; a URL aberta no navegador já o contém |
| `skill-creator/eval-viewer/viewer.html` (segurança) | Planilhas eram mostradas com `sheet_to_html()` via `innerHTML`; um hyperlink `javascript:` numa célula virava `<a href>` e executava no visualizador | A tabela é montada pelo DOM com `textContent` (`sheet_to_json`), sem links |
| `docx/scripts/comment.py` | Usava sempre `word/comments.xml`; num documento cuja relação aponta para outra parte (ex.: `comments1.xml`), repetia o ID 0, criava uma segunda relação de comentários e não achava o comentário-pai | Resolve as quatro partes de comentários pela relação existente antes de calcular IDs, achar o pai e registrar tipos de conteúdo |
| `claude-api/shared/evals/report/build-report-lite.mjs` | Uma variante em que todas as tentativas falharam (só `errors.jsonl`) era descartada; o relatório e o `scores.tsv` omitiam a rodada e as falhas | Só descarta a variante sem resultados e sem erros; a pontuação fica em branco e as falhas aparecem |
| `skill-creator/eval-viewer/generate_review.py` (segurança) | `--benchmark` passava por `resolve()` e seguia um `benchmark.json` que fosse link, embutindo qualquer JSON legível no HTML | O benchmark só é lido como arquivo regular dentro do workspace (`_workspace_file`); um link é recusado com erro |
| `claude-api/shared/evals/report/runner-scaffold.mjs` | IDs como `invoice` e `invoice.txt` passavam na checagem de unicidade, mas dividiam `baseline/ref/invoice.txt`; um caso era avaliado contra a saída do outro | O runner recusa, antes de rodar, um ID igual a outro mais uma extensão de `REF_EXTS` |
| `skill-creator/eval-viewer/generate_review.py` (segurança) | Com `--previous-workspace`, o `feedback.json` da iteração anterior era lido mesmo sendo link; o feedback de outro lugar ia para o HTML | Só é lido como arquivo regular dentro do workspace anterior (`_workspace_file`) |
| `pdf/scripts/check_bounding_boxes.py` | Em páginas com `/Rotate` 90 ou 270, convertia pixels em pontos pela altura do MediaBox, não pela altura exibida; aprovava caixas baixas demais para a fonte | Usa a largura do MediaBox como altura nessas rotações |
| `office/validators/base.py` em docx/pptx/xlsx | `validate_file_references()` aceitava um destino como `../../outside.png` que saía da extração, se o arquivo existisse na máquina; aprovava recursos que não vão no ZIP | Destino fora do pacote extraído conta como referência quebrada |
| `office/helpers/pptx_chart.py` em docx/pptx/xlsx | Aprovava qualquer grupo de gráfico com 2 eixos válidos, embora `line3DChart` e `surface3DChart` exijam 3; um eixo de série inexistente passava | Compara com `AXID_MINIMUM` do tipo do gráfico |
| `skill-creator/eval-viewer/generate_review.py` (segurança) | `--static` gravava com `write_text()`; um `review.html` que fosse link tinha o alvo sobrescrito pelo HTML | Grava em arquivo temporário e substitui com `os.replace()` |
| `xlsx/scripts/recalc.py` (segurança) | Recalculava fórmulas `WEBSERVICE`/`DDE` de planilhas de terceiros; o LibreOffice buscava URLs locais/internas e gravava a resposta no arquivo | Recusa recalcular (também com `--force`) quando uma fórmula, nome definido ou formatação condicional chama essas funções; o XML é interpretado (`defusedxml`) antes da busca, então referências como `&#73;` não escondem a chamada, e uma parte que não pode ser lida com segurança também bloqueia |
| `office/helpers` `safe_extract()` em docx/pptx/xlsx (segurança) | `dest.resolve()` seguia um destino que fosse link (`unpacked -> victim`), e a extração gravava ou sobrescrevia arquivos fora do workspace | Recusa o destino, e pastas acima dele dentro do diretório de trabalho, quando são links |
| `skill-creator/eval-viewer/generate_review.py` | `eval-a/b-c` e `eval-a-b/c` recebiam o mesmo id (`eval-a-b-c`); o feedback de um sobrescrevia o do outro | IDs únicos ficam como antes; os que colidem passam a ser o caminho relativo |
| `skill-creator/scripts/run_eval.py` | Um evento `result` com erro (`is_error`, `error_during_execution`) virava "não acionou"; consultas com `should_trigger: false` passavam numa execução que falhou | O erro levanta exceção e entra na contagem de erros |
| `pdf/scripts/fill_pdf_form_with_annotations.py` | Ignorava a origem do MediaBox; com `[100 200 700 1000]`, as anotações caíam fora do campo (ou da página) | Soma a origem (`left`, `bottom`) ao retângulo convertido |
| `pptx/scripts/add_slide.py` | Procurava `<p:sldIdLst>`, `<p:sldId>` e `r:id` com prefixos fixos; um `presentation.xml` com outros prefixos para os mesmos namespaces era recusado | Usa os prefixos que o `presentation.xml` declara para PresentationML e relacionamentos |
| `pptx/scripts/add_slide.py` | `Type = "…/notesSlide"` (espaços em volta do `=`, XML válido) não era reconhecido; o slide duplicado continuava compartilhando as notas do original | A expressão aceita espaços em volta do `=` |
| `claude-api/shared/evals/report/runner-scaffold.mjs` | Se uma gravação falhava depois do juiz, a linha de `errors.jsonl` perdia `judge_model`/`judge_usage` e o gasto do juiz sumia da contabilidade | Guarda o retorno do juiz e o usa na linha de erro |
| `office/helpers` `check_archive_limits()` em docx/pptx/xlsx (segurança) | A razão de compressão só valia para entradas acima de 1 MiB; uma bomba dividida em milhares de entradas de 1 MiB expandia ~2 GiB a partir de ~2 MiB | Também recusa quando a razão do arquivo inteiro passa de 200x |
| `pptx/scripts/add_slide.py` | Atributos com espaços em volta do `=` (`id = "256"`, XML válido) eram ignorados; o slide duplicado repetia o id 256 | Todas as buscas de atributo aceitam espaços em volta do `=` |
| `pdf/scripts/fill_fillable_fields.py` | Um campo com widgets em várias páginas só era preenchido na última; as outras ocorrências ficavam com a aparência antiga | Atualiza o campo em todas as páginas que têm widgets dele |
| `office/helpers` `safe_extract()`/`rezip()` em docx/pptx/xlsx + `docx`/`pptx` `SKILL.md` (segurança) | Um `unpacked/leak.txt` já existente como link sobrevivia à extração e o `zip -Xr` documentado (ou `rezip()`) empacotava o arquivo local apontado | A extração exige diretório novo ou vazio, `rezip()` recusa links e o comando documentado usa `zip -Xry`, que não segue links |

Ao atualizar as skills, confira se a origem já corrigiu cada item antes de
sobrescrever esses arquivos, e reporte os que continuarem pendentes.

`doc-coauthoring` ficou de fora: não tem arquivo de licença nem campo `license`,
e o repositório não declara licença na raiz.

Algumas skills usam ferramentas externas (por exemplo Python com bibliotecas de
documentos, Node ou Playwright), conforme as instruções de cada `SKILL.md`. Copiar
as skills não instala essas dependências.

Para atualizar, substitua as pastas pelas de um novo commit e registre-o aqui.
