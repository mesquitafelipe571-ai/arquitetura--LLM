# Origem do Superpowers

- Projeto: [obra/superpowers](https://github.com/obra/superpowers).
- Versão do plugin na origem: `7.0.2`.
- Commit de origem: `22f0b463e7a5e579904dd6211a520321035526f7`.
- Diretório original: [skills](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills).
- Licença: MIT, copyright (c) 2025 Jesse Vincent; texto integral em [LICENSE](LICENSE).

As 15 skills de `skills/` foram copiadas sem alterações para `.agents/skills/<nome>/`.
As skills citam umas às outras como `superpowers:<nome>`; nesta instalação de projeto
os nomes não têm prefixo (por exemplo, `$writing-plans`).

Os hooks (`hooks/session-start`) e os adaptadores de outros assistentes não fazem
parte desta instalação. Sem o hook, `using-superpowers` não é carregada no início da
sessão: invoque `$using-superpowers` ou a skill desejada manualmente.

Para atualizar, substitua as pastas pelas de um novo commit e registre-o aqui.
