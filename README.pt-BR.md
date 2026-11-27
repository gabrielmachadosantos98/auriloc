# Auriloc

[English](README.md) | **Português (Brasil)**

**Simule a localização de um iPhone de verdade, sem precisar de Mac.**

O Auriloc permite que desenvolvedores e times de QA no Windows definam uma localização fixa
ou reproduzam uma rota num iPhone físico conectado por USB. Clique num ponto do mapa,
desenhe uma rota que segue as ruas de verdade ou automatize tudo pela linha de comando e
por uma API HTTP.

> Status: alfa inicial. Testado no Windows 11 com iOS 27.

## Por quê

Testar recursos de localização num iPhone de verdade normalmente exige um Mac com Xcode e
refazer o mesmo trajeto na mão. O Auriloc roda no Windows e torna os cenários de localização
repetíveis: fluxos de entrega, geofences, acompanhamento de corridas, rotas de atividade
física.

## Recursos

- **Localização fixa:** clique no mapa ou cole coordenadas.
- **Rotas pelas ruas de verdade:** marque alguns pontos e o Auriloc encaixa o trajeto nas
  vias para caminhada, bicicleta ou carro.
- **Movimento realista:** cada modo de deslocamento acelera, reduz antes das curvas, freia
  no fim e varia a velocidade naturalmente, com uma atualização de posição por segundo.
- **Visualização ao vivo:** um pedestre, corredor, ciclista ou carro acompanha a posição
  simulada no mapa.
- **Reprodução de GPX:** repete trajetos gravados no ritmo original.
- **CLI e API HTTP local:** automatize tudo o que dá para fazer no mapa.
- **Sem jailbreak e sem administrador:** usa a interface de desenvolvedor da Apple; o túnel
  do iOS 17+ roda em espaço de usuário.

## Requisitos

- Windows com o app **Dispositivos Apple** (Microsoft Store) ou o iTunes instalado
- Um iPhone com **iOS 17.4 ou superior**
- [uv](https://docs.astral.sh/uv/) e [Git](https://git-scm.com/). O uv baixa o Python 3.13
  sozinho, se precisar.

Instale os dois com o winget:

```powershell
winget install --id=astral-sh.uv -e
```

```powershell
winget install --id=Git.Git -e
```

## Instalação

```powershell
uv tool install git+https://github.com/gabrielmachadosantos98/auriloc.git
```

Isso adiciona o comando `auriloc` ao sistema. Se o terminal avisar que ele não está no
`PATH`, rode `uv tool update-shell` e abra um terminal novo.

Para atualizar ou remover depois:

```powershell
uv tool upgrade auriloc
```

```powershell
uv tool uninstall auriloc
```

## Primeiros passos

1. **Conecte o iPhone** com o cabo, desbloqueie e toque em **Confiar** quando ele pedir.
2. **Ligue o Modo de Desenvolvedor** no iPhone: Ajustes > Privacidade e Segurança > Modo de
   Desenvolvedor, depois reinicie e confirme. Se a opção não aparecer, rode `auriloc reveal`
   para ela aparecer.
3. **Confira o aparelho:**

   ```powershell
   auriloc devices
   ```

   O seu iPhone deve aparecer com `Developer Mode: on`.
4. **Abra o mapa:**

   ```powershell
   auriloc web
   ```

   O mapa abre em `http://localhost:8765`. Ao encerrar o servidor (Ctrl+C), o iPhone volta
   ao GPS real.

## Usando o mapa

A interface está em inglês; abaixo, o nome de cada botão vem com a tradução.

**Fixed point** (ponto fixo): clique em qualquer lugar do mapa, ou cole coordenadas como
`-23.5505, -46.6333` e aperte **Go** (ir).

**Route** (rota):

1. Clique no mapa para adicionar pontos, na ordem do trajeto.
2. Escolha o **Travel mode** (modo de deslocamento): Walk (caminhada, 5 km/h), Run (corrida,
   10 km/h), Bike (bicicleta, 18 km/h) ou Car (carro, 40 km/h). Dá para mudar a velocidade de
   cruzeiro.
3. Deixe **Follow real streets** (seguir as ruas) ligado para encaixar o trajeto nas vias, ou
   desligue para andar em linha reta entre os pontos.
4. Confira a linha de prévia, a distância e o tempo estimado, e aperte **Start route**
   (iniciar rota). **Stop** (parar) mantém o iPhone onde está; **Back to real GPS** (voltar
   ao GPS real) encerra a simulação.

O servidor só aceita conexões deste computador.

## Linha de comando

```powershell
auriloc devices                     # lista iPhones e pré-requisitos
auriloc set -23.5505 -46.6333       # localização fixa, mantida até o Ctrl+C
auriloc route examples/paulista.gpx # reproduz um trajeto GPX
auriloc clear                       # volta ao GPS real
auriloc web --port 9000             # mapa em outra porta
```

A localização simulada vale enquanto o comando estiver rodando. O Ctrl+C remove a
simulação. Rode `auriloc --help` ou `auriloc <comando> --help` para ver todas as opções.

## API HTTP

Com o `auriloc web` rodando, tudo o que existe no mapa está disponível por HTTP:

| Método | Caminho | O que faz |
|---|---|---|
| `GET` | `/api/status` | Aparelho, modo, posição atual e progresso da rota |
| `POST` | `/api/location` | Define um ponto fixo: `{"lat": -23.55, "lon": -46.63}` |
| `POST` | `/api/route/plan` | Prévia da rota (trajeto, distância, duração) sem mover o iPhone |
| `POST` | `/api/route` | Inicia uma rota |
| `POST` | `/api/stop` | Para a rota e mantém o ponto atual |
| `POST` | `/api/clear` | Volta ao GPS real |

Corpo da rota:

```json
{
  "points": [{"lat": -23.5552, "lon": -46.6621}, {"lat": -23.5713, "lon": -46.6449}],
  "travel_mode": "driving",
  "follow_streets": true,
  "speed_kmh": 40
}
```

- `travel_mode`: `walking`, `running`, `cycling` ou `driving`. Faz o movimento como esse modo.
- `follow_streets`: encaixa o trajeto nas vias (exige `travel_mode` e conexão com a internet).
- `speed_kmh`: velocidade de cruzeiro. Opcional quando há `travel_mode`; sem modo de
  deslocamento, a rota anda em linha reta nessa velocidade constante.

Exemplo no PowerShell:

```powershell
$body = @{
  travel_mode    = "driving"
  follow_streets = $true
  points         = @(@{ lat = -23.5552; lon = -46.6621 }, @{ lat = -23.5713; lon = -46.6449 })
} | ConvertTo-Json -Depth 3
Invoke-RestMethod http://localhost:8765/api/route -Method Post -ContentType "application/json" -Body $body
```

Documentação interativa em `http://localhost:8765/docs`.

## Roteamento pelas ruas e privacidade

Com **Follow real streets** ligado, os pontos da sua rota são enviados a um servidor de
roteamento para obter o trajeto pelas vias. Por padrão, é o servidor público do
OpenStreetMap mantido pela FOSSGIS (`routing.openstreetmap.de`), feito para uso leve. Para
uso intenso ou privado, rode o seu próprio servidor [OSRM](https://project-osrm.org/) e
aponte o Auriloc para ele:

```powershell
auriloc web --routing-url http://localhost:5000/route/v1/driving
```

Nada mais sai do seu computador. Pontos fixos, rotas em linha reta e reprodução de GPX
funcionam sem internet (só os blocos do mapa continuam vindo do OpenStreetMap).

## Solução de problemas

| Problema | O que fazer |
|---|---|
| `No iPhone connected over USB` | Confira o cabo, desbloqueie o iPhone, toque em **Confiar** e verifique se o Dispositivos Apple ou o iTunes está instalado. |
| `Developer Mode is off` | Ligue em Ajustes > Privacidade e Segurança > Modo de Desenvolvedor. Rode `auriloc reveal` se a opção não aparecer. |
| O iPhone continua numa localização falsa | Rode `auriloc clear`. Isso acontece quando o Auriloc é fechado de forma abrupta em vez de com Ctrl+C. |
| `Could not reach the routing server` | Confira a conexão com a internet ou desligue **Follow real streets**. |

## Desenvolvimento

```powershell
git clone https://github.com/gabrielmachadosantos98/auriloc.git
cd auriloc
uv sync
uv run pytest
uv run auriloc web
```

Numa cópia do código-fonte, coloque `uv run` antes dos comandos. A landing page fica em
`site/`; veja [docs/website.md](docs/website.md).

## Uso aceitável

O Auriloc é para desenvolvimento, testes e demonstrações. É proibido usá-lo para falsificar
presença, check-ins, entregas ou qualquer coisa que engane pessoas ou serviços. Veja
[ACCEPTABLE_USE.md](ACCEPTABLE_USE.md) (em inglês).

## Licença

Copyright (C) 2026 Gabriel Machado

O Auriloc é software livre: você pode redistribuí-lo e/ou modificá-lo sob os termos da
Licença Pública Geral GNU, publicada pela Free Software Foundation, na versão 3 da licença
ou (a seu critério) qualquer versão posterior. Veja [LICENSE](LICENSE) (texto oficial em
inglês).

Feito sobre o [pymobiledevice3](https://github.com/doronz88/pymobiledevice3)
(GPL-3.0-or-later). Sem vínculo com a Apple Inc. nem endosso dela. iPhone é marca registrada
da Apple Inc.
