# acess-iphone

Simula a localização de um iPhone conectado via USB no Windows, usando
[pymobiledevice3](https://github.com/doronz88/pymobiledevice3).

## Requisitos

- Windows com o app **Dispositivos Apple** (ou iTunes) instalado
- iPhone com **iOS 17.4+**, pareado ("Confiar neste computador")
- **Modo de Desenvolvedor** ligado no iPhone (Ajustes > Privacidade e Segurança)
- [uv](https://docs.astral.sh/uv/)

Não precisa de terminal como administrador: o túnel iOS 17+ roda em userspace.

## Instalação

```powershell
uv sync
```

## Uso

### Mapa no navegador

```powershell
uv run iphone-gps web
```

Abre `http://localhost:8765`. No modo **Ponto fixo**, clique no mapa para mover o
iPhone. No modo **Rota**, clique para desenhar o trajeto, escolha a velocidade e
inicie. Ao encerrar o servidor (Ctrl+C), o iPhone volta ao GPS real. O servidor só
aceita conexões deste computador.

### Linha de comando

```powershell
uv run iphone-gps devices                  # lista aparelhos e pré-requisitos
uv run iphone-gps reveal                   # mostra a opção Modo de Desenvolvedor nos Ajustes
uv run iphone-gps set -23.5505 -46.6333    # fixa a localização (até Ctrl+C)
uv run iphone-gps route caminho.gpx        # reproduz uma rota GPX
uv run iphone-gps clear                    # volta ao GPS real
```

A localização simulada vale enquanto o comando estiver rodando. Ao encerrar com
Ctrl+C, a simulação é removida.
