# Guia de diagnóstico e captura

Este guia mostra como juntar as informações que o projeto precisa: no Windows, para descobrir os comandos que o FIFINE Genie manda para a SC8 (fase 3), e no Linux, para investigar problemas do OpenSC8 Mixer.

Antes de começar, leia a [regra de segurança](hardware.md#regra-de-segurança): neste guia só se **observa** o que o Genie faz. Nada aqui envia comandos novos para a mesa.

## Sumário

1. [Windows: preparar o ambiente](#1-windows-preparar-o-ambiente)
2. [Windows: informações do aparelho e do Genie](#2-windows-informações-do-aparelho-e-do-genie)
3. [Windows: capturar o tráfego USB do Genie](#3-windows-capturar-o-tráfego-usb-do-genie)
4. [Windows: o que capturar, uma função por arquivo](#4-windows-o-que-capturar-uma-função-por-arquivo)
5. [Gravar a tela: vídeo ou Gravador de Passos](#5-gravar-a-tela-vídeo-ou-gravador-de-passos)
6. [Sem Windows: máquina virtual com captura no Linux](#6-sem-windows-máquina-virtual-com-captura-no-linux)
7. [Linux: diagnóstico do OpenSC8 Mixer](#7-linux-diagnóstico-do-opensc8-mixer)
8. [Como enviar os arquivos](#8-como-enviar-os-arquivos)

---

## 1. Windows: preparar o ambiente

Você precisa de:

- Windows 10 ou 11 com o [FIFINE Genie](https://fifinemicrophone.com/pages/fifine-genie-software) instalado
- A SC8 ligada por USB, com a chave traseira em **PC**
- [Wireshark](https://www.wireshark.org/) e [USBPcap](https://desowin.org/usbpcap/)

Instale pelo PowerShell (como administrador):

```powershell
winget install --id WiresharkFoundation.Wireshark -e
winget install --id desowin.USBPcap -e
```

Se o `winget` não encontrar algum dos dois, baixe pelos sites acima. O instalador do Wireshark também oferece instalar o USBPcap; marque essa opção se aparecer. **Reinicie o Windows depois de instalar o USBPcap**, senão as interfaces de captura não aparecem.

Crie uma pasta para tudo deste guia:

```powershell
mkdir $HOME\Desktop\sc8-capturas
cd $HOME\Desktop\sc8-capturas
```

### Marcador de tempo

Cada captura precisa de uma lista do que você mudou e quando. Cole esta função no PowerShell. Ela grava cada ação com a hora exata em `marcas.txt`:

```powershell
function marca([string]$texto) {
  $linha = "$(Get-Date -Format 'HH:mm:ss.fff')  $texto"
  Add-Content -Path "$HOME\Desktop\sc8-capturas\marcas.txt" -Value $linha
  Write-Host $linha
}
```

Uso: `marca "EQ preset Game"` logo **depois** de clicar na opção do Genie.

---

## 2. Windows: informações do aparelho e do Genie

Rode uma vez. Isso ajuda a comparar o firmware da sua mesa com o de outras pessoas.

```powershell
cd $HOME\Desktop\sc8-capturas

# Aparelhos Fifine conectados (a SC8 é VID_3142 & PID_0C88)
Get-PnpDevice -PresentOnly | Where-Object InstanceId -match 'VID_3142' |
  Format-List FriendlyName, Class, Status, InstanceId | Out-File aparelhos.txt

pnputil /enum-devices /connected /ids | Select-String -Context 0,6 'VID_3142' | Out-File -Append aparelhos.txt

# Versão do Windows
Get-ComputerInfo -Property WindowsProductName, WindowsVersion, OsBuildNumber | Out-File windows.txt

# Onde o Genie está instalado e onde guarda configurações e logs (só lista, não copia)
$locais = $env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:APPDATA, $env:LOCALAPPDATA, $env:ProgramData
Get-ChildItem $locais -Directory -Recurse -Depth 2 -ErrorAction SilentlyContinue |
  Where-Object Name -match 'genie|fifine' | Select-Object FullName | Out-File genie-pastas.txt
```

Abra `genie-pastas.txt`. Para cada pasta de configuração ou log (não a pasta do programa), liste os arquivos:

```powershell
Get-ChildItem "<pasta>" -Recurse | Select-Object FullName, Length, LastWriteTime | Out-File -Append genie-arquivos.txt
```

Anote também a versão do Genie (normalmente em Configurações ou Sobre).

### Descritores USB completos

Baixe o [USB Device Tree Viewer](https://www.uwe-sieber.de/usbtreeview_e.html) (portátil, não precisa instalar). Abra, encontre **fifine SC8 Chat** na árvore, clique com o botão direito e salve o relatório em texto como `sc8-usbtreeview.txt`.

---

## 3. Windows: capturar o tráfego USB do Genie

### Descobrir em qual interface a SC8 está

O USBPcap cria uma interface de captura por controlador USB (`USBPcap1`, `USBPcap2`...). Para saber qual tem a SC8:

```powershell
& "C:\Program Files\USBPcap\USBPcapCMD.exe"
```

Ele lista os controladores e os aparelhos ligados em cada um. Anote o número do que mostra **fifine SC8** (por exemplo, `\\.\USBPcap2` corresponde à interface `USBPcap2`). Feche com Ctrl+C.

Liste as interfaces do Wireshark para achar o número da `USBPcapN`:

```powershell
& "C:\Program Files\Wireshark\dumpcap.exe" -D
```

### Fazer uma captura

Uma captura por função (seção 4). Para cada uma:

1. Feche o Genie.
2. Inicie a captura, trocando `3` pelo número da interface `USBPcapN` mostrado no `-D`:

   ```powershell
   cd $HOME\Desktop\sc8-capturas
   & "C:\Program Files\Wireshark\dumpcap.exe" -i 3 -w sc8-01-abrir-genie.pcapng
   ```

3. `marca "inicio captura 01"`
4. Abra o Genie, faça **uma** mudança, espere 3 segundos e rode `marca "<o que você fez>"`. Repita para cada opção da função, sempre com 3 segundos entre elas.
5. Pare a captura com Ctrl+C no PowerShell.

Se preferir a interface gráfica, abra o Wireshark, dê dois cliques em `USBPcapN` e salve com Arquivo → Salvar como, no formato `.pcapng`.

### Conferir se pegou algo

No Wireshark, abra o arquivo e use este filtro. Ele mostra os pedidos de controle mandados para a interface 5 da mesa (o canal do Genie):

```
usb.setup.wIndex == 5
```

Se não aparecer nada, tente `usbhid` ou `usb.transfer_type == 0x02`. Se mesmo assim estiver vazio, você provavelmente capturou o controlador errado.

---

## 4. Windows: o que capturar, uma função por arquivo

Siga a ordem. Cada linha é um arquivo `.pcapng` separado, com as marcas no mesmo `marcas.txt`.

| # | Arquivo | O que fazer durante a captura |
| --- | --- | --- |
| 01 | `sc8-01-abrir-genie.pcapng` | Com o Genie fechado, iniciar a captura, abrir o Genie, esperar 10 s, fechar o Genie |
| 02 | `sc8-02-replug.pcapng` | Com o Genie aberto, desconectar a SC8, esperar 5 s, reconectar, esperar 10 s |
| 03 | `sc8-03-eq-presets.pcapng` | Trocar entre os presets de EQ (Game, Music, Movie e os outros da lista), um por vez |
| 04 | `sc8-04-eq-custom.pcapng` | No EQ personalizado: mexer um ponto de cada vez até o máximo, depois até o mínimo; usar Reset |
| 05 | `sc8-05-voz.pcapng` | Ligar o voice changer e passar pelos 8 modos, um por vez; depois desligar |
| 06 | `sc8-06-ruido.pcapng` | Ligar e desligar a redução de ruído (e os níveis, se houver) |
| 07 | `sc8-07-surround.pcapng` | Ligar o surround 7.1 e trocar entre Surround, Music e Game; depois desligar |
| 08 | `sc8-08-luz-modos.pcapng` | Passar por cada modo de luz |
| 09 | `sc8-09-luz-cor.pcapng` | Em um modo fixo: trocar a cor para vermelho, verde, azul, branco; mexer no brilho do mínimo ao máximo; mexer na velocidade |
| 10 | `sc8-10-mixer.pcapng` | Mexer nos sliders dos canais e no slider Game/Chat do Genie |
| 11 | `sc8-11-botoes.pcapng` | Sem mexer no Genie: apertar cada botão físico da mesa (CUSTOM, mutes, monitor, 48V), um por vez |
| 12 | `sc8-12-presets.pcapng` | Salvar um preset, trocar de preset, apagar um preset |

Dicas:

- Anote os valores exatos (por exemplo, `marca "EQ ponto 3 = +6 dB"`). É comparando valores conhecidos que se descobre o formato dos bytes.
- Se uma função não existir no seu Genie, pule e anote isso.
- **Não atualize o firmware durante as capturas.** Se o Genie oferecer uma atualização, recuse e avise na issue.

---

## 5. Gravar a tela: vídeo ou Gravador de Passos

A captura USB mostra os bytes, mas não o que estava na tela. Grave a tela junto com as capturas 03 a 12. Use a ferramenta certa para cada caso.

### Quando usar vídeo

Use vídeo quando a informação muda de forma contínua ou visual:

- sliders (EQ, brilho, velocidade, volumes), para ver o valor em cada momento
- luzes da mesa: grave **a mesa com o celular** ao mesmo tempo, porque a gravação de tela não mostra os LEDs
- qualquer coisa animada ou que dependa do tempo

Opções no Windows:

- **Ferramenta de Captura** (Windows 11): Win + Shift + R, escolha a área e grave
- **Xbox Game Bar**: Win + Alt + R grava a janela ativa (não grava a área de trabalho)
- **OBS Studio** para gravar a tela inteira com áudio

Deixe o relógio do Windows visível na gravação, para alinhar o vídeo com o `marcas.txt` e com a captura.

### Quando usar o Gravador de Passos

Use o Gravador de Passos para documentar menus e telas: ele tira uma captura a cada clique e escreve o que foi clicado. Serve para:

- mostrar todas as telas e opções do Genie (nomes exatos de menus, presets e modos)
- mostrar o caminho até cada função

Para abrir: Win + R, digite `psr` e Enter. Clique em **Iniciar gravação**, navegue pelo Genie e clique em **Parar gravação**. Salve o `.zip`.

O Gravador de Passos foi descontinuado nas versões mais novas do Windows 11. Se ele não abrir, use a Ferramenta de Captura em modo vídeo ou tire capturas de tela (Win + Shift + S) de cada menu.

### Antes de enviar

O Gravador de Passos e os vídeos podem mostrar o seu nome de usuário, outras janelas e notificações. Feche o que não for o Genie e confira o arquivo antes de publicar.

---

## 6. Sem Windows: máquina virtual com captura no Linux

Se você só tem Linux, rode o Windows numa máquina virtual (VirtualBox, VMware ou virt-manager), instale o Genie nela e passe a SC8 para a VM pelo menu de USB. Aí a captura pode ser feita no Linux, fora da VM:

```bash
sudo modprobe usbmon
lsusb -d 3142:0c88          # anote o número do Bus, por exemplo 003
sudo wireshark              # escolha a interface usbmon3 (o número do Bus)
```

Ou pela linha de comando:

```bash
sudo dumpcap -i usbmon3 -w sc8-03-eq-presets.pcapng
```

Siga a tabela da seção 4. Para tirar o módulo depois: `sudo modprobe -r usbmon`.

---

## 7. Linux: diagnóstico do OpenSC8 Mixer

### Relatório geral

Rode e anexe a saída numa issue:

```bash
{
  echo "== sistema";   uname -r; cat /etc/os-release | head -3
  echo "== pipewire";  pipewire --version; wireplumber --version 2>/dev/null
  echo "== usb";       lsusb -d 3142:0c88
  echo "== alsa";      cat /proc/asound/cards
  echo "== wpctl";     wpctl status
  echo "== links";     pw-link -l | grep -iE 'opensc8|sc8' 
  echo "== router";    systemctl --user status opensc8-router --no-pager
  echo "== log";       journalctl --user -u opensc8-router -n 200 --no-pager
} > opensc8-diagnostico.txt 2>&1
```

O arquivo pode conter nomes de outros aparelhos de áudio. Confira antes de publicar.

### Uma saída da SC8 ficou muda

Rode enquanto o problema acontece:

```bash
for f in /proc/asound/card*/pcm*p/sub0/status; do echo "$f"; cat "$f"; done
```

Se aparecer `state: PREPARED` com `hw_ptr: 0`, é o problema conhecido de inicialização da saída. Anexe a saída e o log do roteador.

### O botão CUSTOM manda algo para o PC?

Este comando só **lê** o que a mesa manda pela interface das teclas de mídia. Durante 60 segundos, aperte o CUSTOM e depois cada botão da mesa, um por vez, com 2 segundos entre eles. Anote a ordem.

```bash
H=$(grep -l 'HID_ID=0003:00003142:00000C88' /sys/class/hidraw/hidraw*/device/uevent | head -1 | cut -d/ -f5)
echo "Lendo /dev/$H por 60 s"
sudo timeout 60 xxd -c 1 /dev/$H
```

Cada linha é um byte (bit 0 Vol+, 1 Vol−, 2 Próxima, 3 Anterior, 4 Mudo, 5 Avançar, 6 Play/Pause, 7 Stop), seguido de `00` ao soltar. Se o CUSTOM não gerar nenhuma linha, ele funciona só dentro da mesa.

### Descritores USB completos

```bash
sudo lsusb -v -d 3142:0c88 > sc8-lsusb.txt 2>&1
```

---

## 8. Como enviar os arquivos

1. Compacte a pasta `sc8-capturas` (com os `.pcapng`, o `marcas.txt`, os relatórios e as gravações) num `.zip`.
2. Abra ou responda a issue correspondente e anexe o `.zip`. Se passar do limite de anexo do GitHub (25 MB por arquivo), envie os vídeos por um link e anexe o resto.
3. Diga no texto: versão do Genie, versão do Windows e o que não deu para capturar.

As capturas USB só contêm o tráfego do controlador escolhido. Se outro aparelho seu (teclado, por exemplo) estiver no mesmo controlador, o que você digitou durante a captura pode aparecer nela. Durante as capturas, evite digitar senhas.
