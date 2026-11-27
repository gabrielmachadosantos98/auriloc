"""Discovery of the connected iPhone and prerequisite checks."""

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
    """The device is there, but a prerequisite is missing (e.g. Developer Mode)."""


async def list_usb_udids() -> list[str]:
    """UDIDs of the devices connected by USB cable."""
    return [device.serial for device in await list_devices() if device.is_usb]


async def get_device_info(udid: Optional[str] = None) -> DeviceInfo:
    """Read name, iOS version and Developer Mode status over lockdown (USB)."""
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
    """Make sure the device can receive a simulated location; otherwise explain what to do."""
    info = await get_device_info(udid)
    major = int(info.ios_version.split(".")[0])
    if major < 17:
        raise DeviceNotReadyError(f"iOS {info.ios_version} is not supported (iOS 17.4 or later is required).")
    if not info.developer_mode:
        raise DeviceNotReadyError(
            "Developer Mode is off. On the iPhone, open "
            "Settings > Privacy & Security > Developer Mode, turn it on, "
            "restart when asked and confirm after unlocking.\n"
            "If the option is missing, run: auriloc reveal"
        )
    return info
