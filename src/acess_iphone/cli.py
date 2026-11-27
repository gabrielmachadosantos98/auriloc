"""CLI `iphone-gps`.

Exemplos (coordenadas negativas funcionam direto):
    iphone-gps devices
    iphone-gps set -23.5505 -46.6333
    iphone-gps route caminho.gpx
    iphone-gps clear
    iphone-gps web
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, Optional

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.amfi import AmfiService

from acess_iphone.device import DeviceNotReadyError, ensure_ready, get_device_info, list_usb_udids
from acess_iphone.location import LocationSession, validate_coordinates


async def _wait_forever() -> None:
    await asyncio.Event().wait()


async def cmd_devices(_: argparse.Namespace) -> None:
    udids = await list_usb_udids()
    if not udids:
        print("Nenhum iPhone conectado via USB. Confira o cabo e se o app Dispositivos Apple está instalado.")
        return
    for udid in udids:
        info = await get_device_info(udid)
        dev = "ligado" if info.developer_mode else "DESLIGADO"
        print(f"{info.name}  |  iOS {info.ios_version}  |  Modo Desenvolvedor: {dev}  |  {info.udid}")


async def cmd_reveal(args: argparse.Namespace) -> None:
    lockdown = await create_using_usbmux(serial=args.udid)
    try:
        await AmfiService(lockdown).reveal_developer_mode_option_in_ui()
    finally:
        await lockdown.close()
    print("Pronto: a opção deve aparecer em Ajustes > Privacidade e Segurança > Modo de Desenvolvedor.")


async def cmd_set(args: argparse.Namespace) -> None:
    validate_coordinates(args.latitude, args.longitude)
    info = await ensure_ready(args.udid)
    async with LocationSession(info.udid) as session:
        await session.set(args.latitude, args.longitude)
        print(f"Localização de '{info.name}' definida para {args.latitude}, {args.longitude}.")
        print("Mantenha este terminal aberto. Ctrl+C para encerrar e voltar ao GPS real.")
        try:
            await _wait_forever()
        finally:
            await session.clear()


async def cmd_clear(args: argparse.Namespace) -> None:
    info = await ensure_ready(args.udid)
    async with LocationSession(info.udid) as session:
        await session.clear()
    print("Simulação removida; o iPhone voltou a usar o GPS real.")


async def cmd_route(args: argparse.Namespace) -> None:
    if not args.gpx.is_file():
        raise FileNotFoundError(f"Arquivo GPX não encontrado: {args.gpx}")
    info = await ensure_ready(args.udid)
    async with LocationSession(info.udid) as session:
        print(f"Reproduzindo {args.gpx.name} em '{info.name}'... (Ctrl+C para parar)")
        try:
            await session.play_gpx(args.gpx, no_wait=args.no_wait, jitter_ms=args.jitter_ms)
            print("Rota concluída; mantendo o último ponto. Ctrl+C para encerrar.")
            await _wait_forever()
        finally:
            await session.clear()


async def cmd_web(args: argparse.Namespace) -> None:
    from acess_iphone.server import serve  # importa FastAPI/uvicorn só quando necessário

    await serve(host=args.host, port=args.port, udid=args.udid, open_browser=not args.no_browser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="iphone-gps", description="Simula a localização do iPhone via USB.")
    parser.add_argument("--udid", help="UDID do aparelho (padrão: o primeiro conectado via USB)")
    parser.add_argument("-v", "--verbose", action="store_true", help="mostra logs detalhados")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("devices", help="lista iPhones conectados e pré-requisitos").set_defaults(func=cmd_devices)
    sub.add_parser("reveal", help="faz a opção Modo de Desenvolvedor aparecer nos Ajustes").set_defaults(
        func=cmd_reveal
    )

    p_set = sub.add_parser("set", help="define uma localização fixa (mantém até Ctrl+C)")
    p_set.add_argument("latitude", type=float)
    p_set.add_argument("longitude", type=float)
    p_set.set_defaults(func=cmd_set)

    sub.add_parser("clear", help="remove a localização simulada").set_defaults(func=cmd_clear)

    p_route = sub.add_parser("route", help="reproduz uma rota de um arquivo GPX")
    p_route.add_argument("gpx", type=Path)
    p_route.add_argument("--no-wait", action="store_true", help="ignora os horários do GPX e pula ponto a ponto")
    p_route.add_argument("--jitter-ms", type=int, default=0, help="variação aleatória no tempo entre pontos (ms)")
    p_route.set_defaults(func=cmd_route)

    p_web = sub.add_parser("web", help="abre o mapa no navegador para clicar/desenhar rotas")
    p_web.add_argument("--port", type=int, default=8765)
    p_web.add_argument(
        "--host", default="127.0.0.1", help="endereço do servidor (padrão: só este computador)"
    )
    p_web.add_argument("--no-browser", action="store_true", help="não abre o navegador automaticamente")
    p_web.set_defaults(func=cmd_web)
    return parser


def _run(coro: Coroutine[Any, Any, None]) -> None:
    # O pymobiledevice3 usa SelectorEventLoop no Windows (o Proactor tem problemas com seus sockets).
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(coro, loop_factory=loop_factory)


def main(argv: Optional[list[str]] = None) -> int:
    # Mensagens como "Localização definida" precisam sair na hora, mesmo com saída redirecionada.
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        _run(args.func(args))
    except KeyboardInterrupt:
        print("\nEncerrado.")
    except (DeviceNotReadyError, ValueError, FileNotFoundError) as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
