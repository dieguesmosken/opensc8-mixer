# AGENTS.md

Instruções para agentes de IA (Claude Code, Codex, Copilot e similares) que trabalham neste repositório. Leia também o [CONTRIBUTING.md](CONTRIBUTING.md); as regras dele valem aqui.

## O projeto

OpenSC8 Mixer é um mixer para a mesa de som Fifine AmpliGame SC8 (USB `3142:0c88`) no Linux. Ele substitui o FIFINE Genie, que só existe para Windows.

- Fases 0 e 1 são **só software** sobre o PipeWire: canais virtuais, mix do fone, mix da live ("SC8 Stream"), regras por programa, app GTK4 e soundboard. Não falam com a mesa por HID.
- Fase 2: EQ e redução de ruído com filtros do PipeWire.
- Fase 3: funções internas da mesa pela interface HID 5, que depende de capturas do Genie.

Detalhes do hardware: [docs/hardware.md](docs/hardware.md).

## Stack

- Python 3.10+, PyGObject, GTK 4 (libadwaita opcional, com fallback para GTK puro)
- PipeWire 1.0+ e WirePlumber. Configurações geradas em `$XDG_CONFIG_HOME/pipewire/pipewire.conf.d/` e `$XDG_CONFIG_HOME/wireplumber/wireplumber.conf.d/`
- Configuração do app em `$XDG_CONFIG_HOME/opensc8-mixer/config.json`
- Ferramentas usadas em tempo de execução: `pw-cli`, `pw-dump`, `pw-link`, `wpctl`, `pw-play`, `amixer`
- Site estático em `site/`, publicado no GitHub Pages pela action `pages.yml`

## Regras obrigatórias

1. **Nunca mande `SET_REPORT` para a interface HID 5 com bytes que não vieram de uma captura do Genie.** Isso pode alterar configurações salvas na mesa. Ler (`GET_REPORT`) é permitido.
2. **Nunca use sudo** em scripts de instalação ou no app. Se algo precisar de root (por exemplo uma regra udev), documente e deixe o usuário rodar.
3. **Toda mudança no sistema precisa ter volta.** Atualize `uninstall.sh` e `rollback.sh` junto com qualquer arquivo novo que a instalação crie.
4. **Textos da interface em PT-BR.**
5. **Sem caminhos fixos de usuário** e sem dados pessoais (nomes, IPs, seriais além do `20190808` público do firmware).
6. **Identifique a SC8 pelo product ID `0c88`.** Outros aparelhos Fifine usam o mesmo vendor e o mesmo serial.
7. **Testes de áudio com volume baixo** e curtos.
8. Não invente resultados de testes. Se não deu para testar no hardware, diga isso no PR.

## Verificação

```bash
python3 -m compileall -q .          # sintaxe
wpctl status                        # nós "OpenSC8 *", "SC8 Chat", "SC8 Game", "SC8 Stream"
pw-link -l                          # links entre canais, mixes e saídas
```

## Commits e PRs

- Mudanças pequenas e focadas, um assunto por PR.
- A descrição do PR diz o que mudou e como foi testado (distro, versão do PipeWire, com ou sem a SC8 conectada).
- Releases saem por tag `vX.Y.Z` em `main`; não crie tags sem pedido do mantenedor.
