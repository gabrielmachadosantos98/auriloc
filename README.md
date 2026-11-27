# Auriloc

**Simulate the location of a real iPhone, no Mac required.**

Auriloc lets developers and QA teams on Windows set a fixed location or play a route on a
physical iPhone connected over USB. Click a point on a map, draw a route, or script it from
the command line.

> Status: early alpha. Tested on Windows 11 with iOS 27.

## Why

Testing location features on a real iPhone usually means owning a Mac and Xcode, and
repeating the same trip by hand. Auriloc runs on Windows and makes location scenarios
repeatable: delivery flows, geofences, ride tracking, fitness routes.

## Features

- **Fixed location:** click the map or paste coordinates.
- **Routes:** draw waypoints, pick a speed, and watch the iPhone move one update per second.
- **GPX playback:** replay recorded tracks at their original pace.
- **CLI and local HTTP API:** script anything you can do on the map.
- **No admin rights:** the iOS 17+ tunnel runs in userspace.

## Requirements

- Windows with the **Apple Devices** app (or iTunes) installed
- iPhone on **iOS 17.4 or later**, trusted by the computer
- **Developer Mode** enabled on the iPhone (Settings > Privacy & Security). If the option
  is missing, run `auriloc reveal`.
- Python 3.13 and [uv](https://docs.astral.sh/uv/)

## Install

```powershell
git clone https://github.com/gabrielmachadosantos98/auriloc.git
cd auriloc
uv sync
```

## Usage

### Map

```powershell
uv run auriloc web
```

Opens `http://localhost:8765`. In **Fixed point** mode, click the map to move the iPhone.
In **Route** mode, click to draw the path, choose a speed and start. Stopping the server
(Ctrl+C) returns the iPhone to its real GPS. The server only accepts connections from
this computer.

### Command line

```powershell
uv run auriloc devices                   # list iPhones and prerequisites
uv run auriloc set -23.5505 -46.6333     # fixed location (holds until Ctrl+C)
uv run auriloc route examples/paulista.gpx
uv run auriloc clear                     # back to real GPS
```

A simulated location lasts while the command runs. Ctrl+C clears it.

### HTTP API

While `auriloc web` is running:

| Method | Path | Body |
|---|---|---|
| `GET` | `/api/status` | |
| `POST` | `/api/location` | `{"lat": -23.55, "lon": -46.63}` |
| `POST` | `/api/route` | `{"points": [{"lat": ..., "lon": ...}, ...], "speed_kmh": 40}` |
| `POST` | `/api/stop` | `{}` |
| `POST` | `/api/clear` | `{}` |

Interactive docs at `http://localhost:8765/docs`.

## Development

```powershell
uv sync
uv run pytest
```

The landing page lives in `site/`. See [docs/website.md](docs/website.md) to preview and deploy it.

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
