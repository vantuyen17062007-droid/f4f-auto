"""
adbcontrol.py — Proxy tương thích ngược.
Toàn bộ mã nguồn cốt lõi đã được chuyển sang core/adb.py
"""
import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.adb import AdbController
from core.helpers import get_connected_devices as get_connected_adb_devices, resolve_device as resolve_active_device

__all__ = ["AdbController", "resolve_active_device", "get_connected_adb_devices"]
