# Uso do OpenSC8 Mixer

## Instalar

```bash
./install.sh
```

Não precisa de sudo. O script:

1. salva o estado atual do áudio em `$XDG_STATE_HOME/opensc8-mixer/backup/` (só na primeira vez);
2. copia o app para `$XDG_DATA_HOME/opensc8-mixer/` e cria `~/.local/bin/opensc8-mixer`;
3. instala a regra do WirePlumber (`90-opensc8-mixer.conf`) que põe a SC8 no perfil **pro-audio** e dá nomes às portas: **SC8 Chat**, **SC8 Game** e **SC8 Mic**;
4. gera a configuração do PipeWire com os canais virtuais e liga o serviço de usuário `opensc8-router`;
5. cria o atalho "OpenSC8 Mixer" no menu.

Requisitos: PipeWire + WirePlumber, `python3-gi` com GTK 3 (`gir1.2-gtk-3.0`). Com `gir1.2-gtk-4.0` instalado, a migração para GTK 4 fica possível (ainda não feita).

## Como o áudio passa

```
programa ─► OpenSC8 <canal> ─┬─► (slider Fone) ─► barramento ─► SC8 Chat ou SC8 Game ─► fone
                             └─► (slider Live) ─► Mix da Live ─► SC8 Stream ─► OBS
SC8 Mic ─► (slider Live do Mic) ─► Mix da Live
```

- Canais padrão: **Game, Navegador, Chat, Música, Sistema e Efeitos** (a soundboard). Dá para criar até 3 canais extras pelo botão **+**.
- O canal Chat sai pela saída **SC8 Chat**; os outros saem pela **SC8 Game**. Assim o botão Game/Chat da própria mesa continua equilibrando os dois lados.
- **MASTER Fone** controla os dois barramentos de saída; **MASTER Live** controla a fonte SC8 Stream.
- **Mudo** num canal cala os dois caminhos dele (fone e live).

## OBS

Adicione uma fonte **Captura de entrada de áudio** e escolha **SC8 Stream**. Ela já traz o mix da live (canais + mic, cada um com seu volume).

## Regras por programa

Ficam em `$XDG_CONFIG_HOME/opensc8-mixer/config.json`, campo `rules`. A primeira regra cujo texto aparece no nome do programa (`application.process.binary`, `application.name` ou `application.id`) decide o canal. Padrão:

| Programa | Canal |
|---|---|
| steam, gamescope, wine, proton, *.exe | Game |
| discord, vesktop, webcord | Chat |
| spotify | Música |
| firefox, chrome, chromium, brave | Navegador |
| o resto | Sistema (sink padrão) |

Na janela, cada programa tocando aparece no seu canal. Clique nele para **Mover** (só agora) ou **Mover e lembrar** (cria uma regra).

## Soundboard

Aba **Soundboard** → **Adicionar som**: escolha um arquivo (wav, ogg, mp3, flac…), dê um nome, ajuste o volume e, se quiser, um atalho de teclado. Os sons tocam no canal **Efeitos**, que vai para o fone e para a live.

- Os atalhos funcionam com a janela em foco.
- Para atalho global, crie um atalho no sistema que rode `opensc8-mixer --play 1` (número do som, ou o nome).

## Linha de comando

```bash
opensc8-mixer              # abre a janela
opensc8-mixer --play 2     # toca o som 2 da soundboard
opensc8-mixer --apply      # regenera a config do PipeWire e reaplica volumes
opensc8-mixer --router     # roteador (normalmente roda como serviço)
```

## Reconexão da SC8

O roteador religa as saídas e o mic sozinho quando a SC8 é reconectada. Se uma das saídas da mesa ficar travada (acontece às vezes ao abrir as duas saídas juntas), ele reabre o dispositivo; se não resolver, reinicia o PipeWire (1–2 s sem áudio).

## Desfazer

```bash
~/.local/share/opensc8-mixer/rollback.sh    # volta o áudio ao estado anterior (app continua instalado)
~/.local/share/opensc8-mixer/uninstall.sh   # volta o áudio e remove o app (--purge apaga config e backup)
```

## Testes

```bash
python3 tests/test_audio.py      # tom de -30 dBFS em cada canal; confere fone/live e os sliders
python3 tests/test_latency.py    # latência extra dos caminhos virtuais
```
