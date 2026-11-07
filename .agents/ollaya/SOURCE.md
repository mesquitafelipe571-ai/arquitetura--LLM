# Origem da skill do Ollaya

- Projeto: [ollaya-dev/ollaya](https://github.com/ollaya-dev/ollaya).
- Versão: `0.18.0`, a mesma que `scripts/ollaya.sh` instala.
- Commit de origem: `a8bce962dc8219e696604403a5c2a30e6c9523f0` (tag `v0.18.0`).
- Diretório original: [skills/ollaya-decisions](https://github.com/ollaya-dev/ollaya/tree/a8bce962dc8219e696604403a5c2a30e6c9523f0/skills/ollaya-decisions).
- Licença: Apache-2.0; texto integral em [LICENSE](LICENSE).

A skill foi copiada com uma única alteração: quando nenhuma interface do Ollaya está
disponível, ela indica `npm run ollaya:install` (instalador fixado por commit e SHA-256,
com confirmação) em vez de `curl -fsSL https://ollaya.dev/install.sh | sh`, que não é
fixado. Ao trocar a versão do Ollaya, atualize a skill (refazendo essa troca),
`VERSION` e `SOURCE_SHA` em `scripts/ollaya.sh`.

O instalador (`scripts/install.sh` do mesmo commit) é baixado por SHA completo,
conferido pelo SHA-256 fixado em `scripts/ollaya.sh` (`INSTALLER_SHA256`) e só
roda com confirmação humana; ele confere os binários da release pelo
`sha256sum.txt` dela, que também é fixado (`SUMS_SHA256`): o `scripts/ollaya.sh` baixa e confere
essa lista antes e a entrega ao instalador, porque assets de release podem ser reenviados.
Ao trocar a versão, atualize também `INSTALLER_SHA256` e `SUMS_SHA256`. Os pesos dos modelos vêm
dos repositórios dos autores no Hugging Face, fixados por commit e conferidos por
sha256 pelo próprio Ollaya.
