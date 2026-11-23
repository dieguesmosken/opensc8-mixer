# Como contribuir

Obrigado por querer ajudar. O OpenSC8 Mixer é um projeto pequeno e toda ajuda conta: código, testes em outras distros, capturas do protocolo e tradução.

## Formas de ajudar

- **Testar em outra distro** e abrir uma issue dizendo o que funcionou e o que não funcionou. Inclua a saída de `pipewire --version`, `wpctl status` e `lsusb -d 3142:0c88`.
- **Capturar o protocolo do FIFINE Genie** no Windows. É o que destrava a fase 3. O passo a passo está em [docs/hardware.md](docs/hardware.md#como-capturar-o-protocolo).
- **Código**: veja as issues abertas ou proponha uma melhoria numa issue antes de começar algo grande.

## Ambiente de desenvolvimento

```bash
git clone https://github.com/dieguesmosken/opensc8-mixer.git
cd opensc8-mixer
python3 -m venv --system-site-packages .venv   # usa o PyGObject do sistema
. .venv/bin/activate
```

Dependências do sistema (nomes do Debian/Ubuntu/Pop!_OS):

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 pipewire wireplumber pipewire-pulse
```

Antes de mexer no áudio, salve o estado atual e saiba como voltar: `./rollback.sh` desfaz o que a instalação mudou.

## Regras do projeto

- **Nunca escreva na interface HID 5 da mesa com dados inventados.** Só reproduza comandos capturados do Genie. Veja [docs/hardware.md](docs/hardware.md#regra-de-segurança).
- **Nada de sudo na instalação.** Tudo roda como usuário, com arquivos em `$XDG_CONFIG_HOME` e `~/.local`.
- **Tudo reversível.** Cada mudança no PipeWire ou no WirePlumber precisa ser desfeita por `uninstall.sh` ou `rollback.sh`.
- **Interface em português do Brasil.** Textos da interface ficam em PT-BR. Código, nomes de variáveis e commits podem ser em inglês ou português, desde que o arquivo seja consistente.
- **Sem caminhos fixos.** Use `$HOME` e as variáveis XDG, nunca `/home/<usuário>`.
- **Teste com volume baixo.** Tons de teste curtos e baixos; quem testa pode estar de fone.

## Pull requests

1. Crie um branch a partir de `main`.
2. Faça mudanças pequenas e focadas, com uma descrição do que muda e de como você testou.
3. Rode `python3 -m compileall -q .` para pegar erros de sintaxe.
4. Se a mudança mexe no áudio, diga em que distro e versão do PipeWire você testou.
5. Abra o PR. Ele vai ser revisado antes do merge.

## Versões

As versões seguem [SemVer](https://semver.org/lang/pt-BR/). Uma tag `vX.Y.Z` em `main` dispara a action de release, que gera o pacote e publica a release com as notas automáticas.

## Licença

Ao contribuir, você concorda que sua contribuição é licenciada sob a [GPL-3.0](LICENSE).
