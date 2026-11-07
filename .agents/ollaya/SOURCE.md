# Origem da skill do Ollaya

- Projeto: [ollaya-dev/ollaya](https://github.com/ollaya-dev/ollaya).
- Versão: `0.18.0`, a mesma que `scripts/ollaya.sh` instala.
- Commit de origem: `a8bce962dc8219e696604403a5c2a30e6c9523f0` (tag `v0.18.0`).
- Diretório original: [skills/ollaya-decisions](https://github.com/ollaya-dev/ollaya/tree/a8bce962dc8219e696604403a5c2a30e6c9523f0/skills/ollaya-decisions).
- Licença: Apache-2.0; texto integral em [LICENSE](LICENSE).

A skill foi copiada sem alterações. Ao trocar a versão do Ollaya, atualize a skill,
`VERSION` e `SOURCE_SHA` em `scripts/ollaya.sh`.

O instalador (`scripts/install.sh` do mesmo commit) é baixado por SHA completo e
confere os binários da release pelo `sha256sum.txt` dela. Os pesos dos modelos vêm
dos repositórios dos autores no Hugging Face, fixados por commit e conferidos por
sha256 pelo próprio Ollaya.
