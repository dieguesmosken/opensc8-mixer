# Hardware da Fifine SC8

Dados levantados no Linux com `lsusb -v`, `amixer` e `/proc/asound`, numa SC8 com firmware de fábrica. Nada aqui foi obtido escrevendo na mesa.

## Identificação

| Campo | Valor |
| --- | --- |
| Vendor:Product | `3142:0c88` |
| Fabricante (string USB) | `MV-SILICON` |
| Produto (string USB) | `fifine SC8 Chat` |
| Serial | `20190808` (padrão do firmware MV-Silicon, repetido em outros aparelhos Fifine) |
| USB | 1.10, full speed, 100 mA |
| Interfaces | 8 |

Outros aparelhos Fifine usam o mesmo vendor `3142` e o mesmo serial. Por exemplo, o microfone AM8 aparece como `3142:a010`. Sempre identifique a SC8 pelo product ID `0c88`.

## Interfaces

| # | Classe | Nome | Função |
| --- | --- | --- | --- |
| 0 | Audio Control | fifine SC8 Chat | IT1 USB Streaming → FU2 (mute, volume L/R) → OT3 Speaker |
| 1 | Audio Streaming | | Saída "Chat": estéreo, S16 ou S24_3LE, 44,1 ou 48 kHz, EP 0x02 OUT isócrono |
| 2 | Audio Control | fifine SC8 Mic | IT4 Microfone → FU5 (mute, volume) → SU6 → OT7 USB Streaming |
| 3 | Audio Streaming | | Entrada do mic: mono, S16 ou S24, EP 0x82 IN isócrono |
| 4 | HID | | Teclas de mídia, EP 0x81 IN interrupt, 64 bytes, 1 ms |
| 5 | HID | | Canal de configuração do fabricante, sem endpoint |
| 6 | Audio Control | fifine SC8 Game | IT9 USB Streaming → FU10 (mute, volume L/R) → OT11 Headphones |
| 7 | Audio Streaming | | Saída "Game": estéreo, S16 ou S24, EP 0x01 OUT isócrono |

No ALSA (driver `snd-usb-audio`):

| Controle | Interface | Faixa |
| --- | --- | --- |
| `PCM Playback Volume` índice 0 | Saída Chat (unidade 2) | 0 a 4096, 0 a 16 dB |
| `PCM Playback Volume` índice 1 | Saída Game (unidade 10) | 0 a 4096, 0 a 16 dB |
| `Mic Capture Volume` | Mic (unidade 5) | 0 a 4096 |

Com o perfil padrão, o PipeWire cria só o sink da saída Chat. A saída Game fica escondida e, de fábrica, pode estar com volume baixo (409 de 4096 na unidade testada).

## HID interface 4: teclas de mídia

Report descriptor de 33 bytes:

```
05 0c 09 01 a1 01 15 00 25 01 09 e9 09 ea 09 b5 09 b6 09 e2 09 b3 09 cd 09 b7 75 01 95 08 81 42 c0
```

Consumer Control, um byte de input sem report ID:

| Bit | Usage | Tecla |
| --- | --- | --- |
| 0 | 0xE9 | Volume + |
| 1 | 0xEA | Volume − |
| 2 | 0xB5 | Próxima |
| 3 | 0xB6 | Anterior |
| 4 | 0xE2 | Mute |
| 5 | 0xB3 | Avançar |
| 6 | 0xCD | Play/Pause |
| 7 | 0xB7 | Stop |

Ainda não se sabe quais botões físicos geram cada bit, nem se o botão CUSTOM gera algum.

## HID interface 5: canal de configuração

Report descriptor de 36 bytes:

```
06 00 ff 0a aa 55 a1 01 15 00 26 ff 00 75 08 96 00 01 09 01 81 02 96 00 01 09 01 91 02 95 08 09 01 b1 02 c0
```

| Item | Valor |
| --- | --- |
| Usage Page | 0xFF00 (definida pelo fabricante) |
| Usage | 0x55AA |
| Report ID | nenhum |
| Input | 256 bytes |
| Output | 256 bytes |
| Feature | 8 bytes |

A interface não tem endpoints, então toda a comunicação é por control transfer:

- Output: `SET_REPORT` (bmRequestType 0x21, bRequest 0x09, wValue 0x0200, wIndex 5)
- Input: `GET_REPORT` (bmRequestType 0xA1, bRequest 0x01, wValue 0x0100, wIndex 5)
- Feature: wValue 0x0300

O Linux não associa driver a ela. É quase certamente por aqui que o FIFINE Genie configura EQ, voice changer, surround e luzes. **O formato dos comandos ainda é desconhecido.**

### Regra de segurança

Não mande `SET_REPORT` para a interface 5 com dados inventados. Comandos errados podem alterar configurações salvas na mesa. Só reproduza comandos que foram capturados do próprio Genie.

### Como capturar o protocolo

O passo a passo completo, com comandos e a lista de capturas por função, está em [diagnostico.md](diagnostico.md). Resumo:

1. No Windows, instale o [USBPcap](https://desowin.org/usbpcap/) e o [Wireshark](https://www.wireshark.org/).
2. Abra o FIFINE Genie com a SC8 conectada e comece a captura no hub da mesa.
3. Mude **uma** opção por vez (um preset de EQ, um modo de voz, uma cor) e anote a hora de cada mudança.
4. Filtre por `usb.idProduct == 0x0c88` e pelos `SET_REPORT` com wIndex 5.
5. Salve o `.pcapng` e abra uma issue com o arquivo e a lista do que você mudou.

## Fontes

- [Página da SC8](https://fifinemicrophone.com/products/fifine-ampligame-sc8-audio-mixer) e [FAQ](https://fifinemicrophone.com/blogs/news/sc8-faqs)
- [FIFINE Genie](https://fifinemicrophone.com/pages/fifine-genie-software) e o [guia de primeiros passos](https://intercom.help/fifine/en/articles/13365012-how-to-get-started-with-fifine-genie-software)
- [fifine-sc8-linux](https://github.com/brcly/fifine-sc8-linux), scripts anteriores para nomear as saídas
