# Auriloc

**English** | [Português (Brasil)](README.pt-BR.md)

**Simulate the location of a real iPhone, no Mac required.**

Auriloc lets developers and QA teams on Windows set a fixed location or play a route on a
physical iPhone connected over USB. Click a point on a map, draw a route that follows real
streets, or script it from the command line and an HTTP API.

> Status: early alpha. Tested on Windows 11 with iOS 27.

## Why

Testing location features on a real iPhone usually means owning a Mac and Xcode, and
repeating the same trip by hand. Auriloc runs on Windows and makes location scenarios
repeatable: delivery flows, geofences, ride tracking, fitness routes.

## Features

- **Fixed location:** click the map or paste coordinates.
- **Routes along real streets:** draw a few points and Auriloc snaps the path to the road
  network for walking, cycling or driving.
- **Realistic movement:** each travel mode accelerates, slows down before turns, brakes at
  the end and varies its speed naturally, one position update per second.
- **Live view:** a walker, runner, cyclist or car follows the simulated position on the map.
- **GPX playback:** replay recorded tracks at their original pace.
- **CLI and local HTTP API:** script anything you can do on the map.
- **No jailbreak, no admin rights:** uses Apple's developer interface; the iOS 17+ tunnel
  runs in userspace.

## Requirements

- Windows with the **Apple Devices** app (Microsoft Store) or iTunes installed
- An iPhone on **iOS 17.4 or later**
- [uv](https://docs.astral.sh/uv/) and [Git](https://git-scm.com/). uv downloads Python
  3.13 for you if needed.

Install both with winget:

```powershell
winget install --id=astral-sh.uv -e
```

```powershell
winget install --id=Git.Git -e
```

## Install

```powershell
uv tool install git+https://github.com/gabrielmachadosantos98/auriloc.git
```

This adds the `auriloc` command to your system. If the terminal says it is not on your
`PATH`, run `uv tool update-shell` and open a new terminal.

Update or remove it later:

```powershell
uv tool upgrade auriloc
```

```powershell
uv tool uninstall auriloc
```

## Quick start

1. **Connect the iPhone** with a cable, unlock it and tap **Trust** when asked.
2. **Turn on Developer Mode** on the iPhone: Settings > Privacy & Security > Developer Mode,
   then restart and confirm. If the option is missing, run `auriloc reveal` to make it
   appear.
3. **Check the device:**

   ```powershell
   auriloc devices
   ```

   You should see your iPhone with `Developer Mode: on`.
4. **Open the map:**

   ```powershell
   auriloc web
   ```

   The map opens at `http://localhost:8765`. Stopping the server (Ctrl+C) returns the iPhone
   to its real GPS.

## Using the map

**Fixed point:** click anywhere on the map, or paste coordinates such as
`-23.5505, -46.6333` and press **Go**.

**Route:**

1. Click the map to add points, in travel order.
2. Pick a **travel mode**: Walk (5 km/h), Run (10 km/h), Bike (18 km/h) or Car (40 km/h).
   You can change the cruise speed.
3. Keep **Follow real streets** on to snap the path to roads, or turn it off to move in
   straight lines between your points.
4. Check the preview line, distance and estimated time, then press **Start route**.
   **Stop** keeps the iPhone where it is; **Back to real GPS** ends the simulation.

The server only accepts connections from this computer.

## Command line

```powershell
auriloc devices                     # list iPhones and prerequisites
auriloc set -23.5505 -46.6333       # fixed location, holds until Ctrl+C
auriloc route examples/paulista.gpx # replay a GPX track
auriloc clear                       # back to real GPS
auriloc web --port 9000             # map on another port
```

A simulated location lasts while the command runs. Ctrl+C clears it. Run `auriloc --help`
or `auriloc <command> --help` for all options.

## HTTP API

While `auriloc web` is running, everything on the map is available over HTTP:

| Method | Path | What it does |
|---|---|---|
| `GET` | `/api/status` | Device, mode, current position and route progress |
| `POST` | `/api/location` | Set a fixed point: `{"lat": -23.55, "lon": -46.63}` |
| `POST` | `/api/route/plan` | Preview a route (path, distance, duration) without moving the iPhone |
| `POST` | `/api/route` | Start a route |
| `POST` | `/api/stop` | Stop the route and hold the current point |
| `POST` | `/api/clear` | Back to real GPS |

Route body:

```json
{
  "points": [{"lat": -23.5552, "lon": -46.6621}, {"lat": -23.5713, "lon": -46.6449}],
  "travel_mode": "driving",
  "follow_streets": true,
  "speed_kmh": 40
}
```

- `travel_mode`: `walking`, `running`, `cycling` or `driving`. Moves like that mode.
- `follow_streets`: snap the path to roads (needs `travel_mode` and an internet connection).
- `speed_kmh`: cruise speed. Optional when `travel_mode` is set; without a travel mode the
  route moves in straight lines at this constant speed.

Example from PowerShell:

```powershell
$body = @{
  travel_mode    = "driving"
  follow_streets = $true
  points         = @(@{ lat = -23.5552; lon = -46.6621 }, @{ lat = -23.5713; lon = -46.6449 })
} | ConvertTo-Json -Depth 3
Invoke-RestMethod http://localhost:8765/api/route -Method Post -ContentType "application/json" -Body $body
```

Interactive docs at `http://localhost:8765/docs`.

## Street routing and privacy

When **Follow real streets** is on, the points of your route are sent to a routing server to
get the path along the roads. By default this is the public OpenStreetMap server run by
FOSSGIS (`routing.openstreetmap.de`), which is meant for light use. For heavy or private use,
run your own [OSRM](https://project-osrm.org/) server and point Auriloc to it:

```powershell
auriloc web --routing-url http://localhost:5000/route/v1/driving
```

Nothing else leaves your computer. Fixed points, straight-line routes and GPX playback work
offline (the map tiles still load from OpenStreetMap).

## Troubleshooting

| Problem | What to do |
|---|---|
| `No iPhone connected over USB` | Check the cable, unlock the iPhone, tap **Trust**, and make sure Apple Devices or iTunes is installed. |
| `Developer Mode is off` | Turn it on in Settings > Privacy & Security > Developer Mode. Run `auriloc reveal` if the option is missing. |
| The iPhone stays at a fake location | Run `auriloc clear`. This happens if Auriloc was closed abruptly instead of with Ctrl+C. |
| `Could not reach the routing server` | Check the internet connection, or turn off **Follow real streets**. |

## Development

```powershell
git clone https://github.com/gabrielmachadosantos98/auriloc.git
cd auriloc
uv sync
uv run pytest
uv run auriloc web
```

In a source checkout, prefix commands with `uv run`. The landing page lives in `site/`; see
[docs/website.md](docs/website.md).

## Acceptable use

Auriloc is for development, testing and demos. Using it to fake attendance, check-ins,
deliveries or anything else to deceive people or services is prohibited. See
[ACCEPTABLE_USE.md](ACCEPTABLE_USE.md).

## License

Copyright (C) 2026 Gabriel Machado

Auriloc is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version. See [LICENSE](LICENSE).

Built on [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) (GPL-3.0-or-later).
Not affiliated with or endorsed by Apple Inc. iPhone is a trademark of Apple Inc.
