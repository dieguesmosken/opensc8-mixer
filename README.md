# OpenSC8 Mixer

Mixer open source para a mesa de som **Fifine AmpliGame SC8** no Linux.

O app oficial da Fifine, o FIFINE Genie, só existe para Windows. No Linux a SC8 funciona como placa de som USB, mas perde as funções do Genie: os canais separados por programa, o mix de stream para a live, o EQ, os efeitos e as luzes. O OpenSC8 Mixer recupera essas funções usando o PipeWire.

> Projeto independente, sem ligação com a Fifine. "Fifine", "AmpliGame" e "FIFINE Genie" são marcas dos seus donos.

## Status

Em desenvolvimento. Ainda não há uma versão pronta para uso.

| Fase | O que entrega | Situação |
| --- | --- | --- |
| 0 | As duas saídas da SC8 ("SC8 Chat" e "SC8 Game") visíveis e com volume certo | Em andamento |
| 1 | Canais virtuais por programa, mix do fone, mix da live ("SC8 Stream"), app gráfico e soundboard | Em andamento |
| 2 | EQ de até 10 pontos e redução de ruído no PC | Planejada |
| 3 | Funções internas da mesa (presets de EQ, voice changer, surround, luzes) | Depende de engenharia reversa |

## Como funciona

A porta USB da SC8 só recebe o áudio já mixado. Por isso os canais do Genie são aparelhos virtuais criados no PC, e não algo dentro da mesa. O OpenSC8 Mixer faz o mesmo no PipeWire:

```
Programas            Canais virtuais        Mixes                 Saídas
Jogo       ───────►  OpenSC8 Game     ──┬─► Mix do fone   ──────► SC8 (fone)
Navegador  ───────►  OpenSC8 Navegador ─┤
Discord    ───────►  OpenSC8 Chat     ──┤
Spotify    ───────►  OpenSC8 Música   ──┼─► Mix da live   ──────► SC8 Stream (OBS)
Efeitos    ───────►  OpenSC8 Efeitos  ──┘        ▲
Microfone SC8 ───────────────────────────────────┘
```

- Cada canal tem dois volumes independentes: o do fone e o da live.
- O canal Chat sai pela saída "SC8 Chat" e os outros pela "SC8 Game", então o botão Game/Chat da mesa continua funcionando.
- O OBS captura a fonte "SC8 Stream" como se fosse um microfone.
- Regras salvas decidem em qual canal cada programa toca.
- A soundboard toca seus próprios arquivos (aplausos, risos etc.) no canal Efeitos.

## Requisitos

- Linux com PipeWire 1.0 ou mais novo e WirePlumber (testado no Pop!_OS com PipeWire 1.6.8)
- Python 3.10 ou mais novo, com PyGObject e GTK 4 (libadwaita é opcional)
- A chave traseira da SC8 na posição **PC**

## Instalação

As instruções completas entram aqui com a primeira versão. O fluxo previsto:

```bash
git clone https://github.com/dieguesmosken/opensc8-mixer.git
cd opensc8-mixer
./install.sh      # instala para o seu usuário, sem sudo
```

Para remover: `./uninstall.sh`. Para voltar o áudio ao estado anterior à instalação: `./rollback.sh`.

## Documentação

- [Hardware da SC8](docs/hardware.md): descritores USB, interfaces e o que já se sabe do protocolo
- [Como contribuir](CONTRIBUTING.md)
- [Instruções para agentes de IA](AGENTS.md)

## Licença

[GPL-3.0](LICENSE).
