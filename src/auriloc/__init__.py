"""Auriloc: simulate the location of a real iPhone connected over USB."""

from auriloc.device import DeviceInfo, DeviceNotReadyError, get_device_info, list_usb_udids
from auriloc.location import LocationSession

__all__ = ["DeviceInfo", "DeviceNotReadyError", "LocationSession", "get_device_info", "list_usb_udids"]
