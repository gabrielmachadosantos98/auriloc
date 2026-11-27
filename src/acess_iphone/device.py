"""Descoberta do iPhone conectado e checagem de pré-requisitos."""

from dataclasses import dataclass
from typing import Optional

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.usbmux import list_devices


@dataclass(frozen=True)
class DeviceInfo:
    udid: str
    name: Optional[str]
    ios_version: str
    developer_mode: bool


class DeviceNotReadyError(RuntimeError):
    """O aparelho existe, mas falta algum pré-requisito (ex.: Modo de Desenvolvedor)."""


async def list_usb_udids() -> list[str]:
    """UDIDs dos aparelhos conectados por cabo USB."""
    return [device.serial for device in await list_devices() if device.is_usb]


async def get_device_info(udid: Optional[str] = None) -> DeviceInfo:
    """Lê nome, versão do iOS e status do Modo de Desenvolvedor via lockdown (USB)."""
    lockdown = await create_using_usbmux(serial=udid)
    try:
        info = lockdown.short_info
        return DeviceInfo(
            udid=info["UniqueDeviceID"],
            name=info.get("DeviceName"),
            ios_version=lockdown.product_version,
            developer_mode=await lockdown.get_developer_mode_status(),
        )
    finally:
        await lockdown.close()


async def ensure_ready(udid: Optional[str] = None) -> DeviceInfo:
    """Garante que o aparelho pode receber localização simulada; senão explica o que fazer."""
    info = await get_device_info(udid)
    major = int(info.ios_version.split(".")[0])
    if major < 17:
        raise DeviceNotReadyError(
            f"iOS {info.ios_version} não é suportado por esta ferramenta (precisa de iOS 17.4 ou superior)."
        )
    if not info.developer_mode:
        raise DeviceNotReadyError(
            "O Modo de Desenvolvedor está desligado. No iPhone, vá em "
            "Ajustes > Privacidade e Segurança > Modo de Desenvolvedor, ligue, "
            "reinicie quando pedir e confirme após desbloquear.\n"
            "Se a opção não aparecer, rode: iphone-gps reveal"
        )
    return info
