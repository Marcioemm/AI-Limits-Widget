"""Windows notification-area control for the Tk-free integration collector."""

from __future__ import annotations

import ctypes
import os
import struct
import threading
from ctypes import wintypes as wt


def _icon_data() -> bytes:
    """A small AI Limits meter icon, encoded as a Windows icon resource."""
    pixels = bytearray()
    for y in range(31, -1, -1):
        for x in range(32):
            inside = (x - 15.5) ** 2 + (y - 15.5) ** 2 <= 15**2
            bar = any(left <= x < left + 4 and top <= y <= 23 for left, top in ((7, 17), (14, 11), (21, 6)))
            pixels.extend((110, 220, 160, 255) if inside and bar else (38, 32, 26, 255 if inside else 0))
    mask = b"".join(
        sum((1 << (31 - x)) for x in range(32) if pixels[(y * 32 + x) * 4 + 3] == 0).to_bytes(4, "big")
        for y in range(32)
    )
    return struct.pack("<IiiHHIIiiII", 40, 32, 64, 1, 32, 0, len(pixels), 0, 0, 0, 0) + pixels + mask


class IntegrationTray:
    """Owns a native message loop; communicates only through thread-safe events."""

    def __init__(self, stop: threading.Event, show_widget: threading.Event) -> None:
        self.stop = stop
        self.show_widget = show_widget
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, name="ai-limits-tray", daemon=True)
        self.hwnd = None
        self.error: BaseException | None = None

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(10):
            raise RuntimeError("A bandeja do Windows não respondeu.")
        if self.error:
            raise RuntimeError("Não foi possível criar o ícone na bandeja do Windows.") from self.error

    def close(self) -> None:
        if self.hwnd:
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
            user.PostMessageW(self.hwnd, 0x0010, 0, 0)  # WM_CLOSE
        if self.thread.is_alive():
            self.thread.join(timeout=10)

    def _run(self) -> None:
        try:
            self._message_loop()
        except BaseException as exc:
            self.error = exc
            self.stop.set()
        finally:
            self.ready.set()

    def _message_loop(self) -> None:
        user = ctypes.WinDLL("user32", use_last_error=True)
        shell = ctypes.WinDLL("shell32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

        class WindowClass(ctypes.Structure):
            _fields_ = [
                ("style", wt.UINT),
                ("callback", callback_type),
                ("class_extra", ctypes.c_int),
                ("window_extra", ctypes.c_int),
                ("instance", wt.HINSTANCE),
                ("icon", wt.HICON),
                ("cursor", wt.HANDLE),
                ("background", wt.HBRUSH),
                ("menu", wt.LPCWSTR),
                ("name", wt.LPCWSTR),
            ]

        class Guid(ctypes.Structure):
            _fields_ = [("a", wt.DWORD), ("b", wt.WORD), ("c", wt.WORD), ("d", ctypes.c_byte * 8)]

        class NotifyIcon(ctypes.Structure):
            _fields_ = [
                ("size", wt.DWORD),
                ("hwnd", wt.HWND),
                ("id", wt.UINT),
                ("flags", wt.UINT),
                ("callback", wt.UINT),
                ("icon", wt.HICON),
                ("tip", wt.WCHAR * 128),
                ("state", wt.DWORD),
                ("state_mask", wt.DWORD),
                ("info", wt.WCHAR * 256),
                ("version", wt.UINT),
                ("info_title", wt.WCHAR * 64),
                ("info_flags", wt.DWORD),
                ("guid", Guid),
                ("balloon", wt.HICON),
            ]

        # Explicit signatures keep handles pointer-sized on 64-bit Windows.
        signatures = [
            (kernel.GetModuleHandleW, [wt.LPCWSTR], wt.HMODULE),
            (user.RegisterClassW, [ctypes.POINTER(WindowClass)], wt.ATOM),
            (user.UnregisterClassW, [wt.LPCWSTR, wt.HINSTANCE], wt.BOOL),
            (
                user.CreateWindowExW,
                [
                    wt.DWORD,
                    wt.LPCWSTR,
                    wt.LPCWSTR,
                    wt.DWORD,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                    wt.HWND,
                    wt.HMENU,
                    wt.HINSTANCE,
                    wt.LPVOID,
                ],
                wt.HWND,
            ),
            (user.DefWindowProcW, [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM], ctypes.c_ssize_t),
            (user.DestroyWindow, [wt.HWND], wt.BOOL),
            (
                user.CreateIconFromResourceEx,
                [wt.LPVOID, wt.DWORD, wt.BOOL, wt.DWORD, ctypes.c_int, ctypes.c_int, wt.UINT],
                wt.HICON,
            ),
            (user.DestroyIcon, [wt.HICON], wt.BOOL),
            (user.RegisterWindowMessageW, [wt.LPCWSTR], wt.UINT),
            (user.CreatePopupMenu, [], wt.HMENU),
            (user.AppendMenuW, [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR], wt.BOOL),
            (user.SetForegroundWindow, [wt.HWND], wt.BOOL),
            (
                user.TrackPopupMenu,
                [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.LPVOID],
                wt.UINT,
            ),
            (user.DestroyMenu, [wt.HMENU], wt.BOOL),
            (user.GetCursorPos, [ctypes.POINTER(wt.POINT)], wt.BOOL),
            (user.PostMessageW, [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM], wt.BOOL),
            (user.PostQuitMessage, [ctypes.c_int], None),
            (user.GetMessageW, [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT], wt.BOOL),
            (user.TranslateMessage, [ctypes.POINTER(wt.MSG)], wt.BOOL),
            (user.DispatchMessageW, [ctypes.POINTER(wt.MSG)], ctypes.c_ssize_t),
            (shell.Shell_NotifyIconW, [wt.DWORD, ctypes.POINTER(NotifyIcon)], wt.BOOL),
        ]
        for function, args, result in signatures:
            function.argtypes = args
            function.restype = result

        instance = kernel.GetModuleHandleW(None)
        name = f"AILimitsIntegrationTray-{os.getpid()}"
        taskbar_created = user.RegisterWindowMessageW("TaskbarCreated")
        notice = NotifyIcon()
        icon = None

        def select(command: int) -> None:
            if command == 1:
                self.show_widget.set()
                self.stop.set()
            elif command == 2:
                self.stop.set()

        @callback_type
        def window_proc(hwnd, message, wparam, lparam):
            if message == 0x8001:
                if lparam == 0x0203:  # WM_LBUTTONDBLCLK
                    select(1)
                elif lparam == 0x0205:  # WM_RBUTTONUP
                    menu = user.CreatePopupMenu()
                    try:
                        user.AppendMenuW(menu, 0, 1, "Abrir widget")
                        user.AppendMenuW(menu, 0, 2, "Sair")
                        point = wt.POINT()
                        user.GetCursorPos(ctypes.byref(point))
                        user.SetForegroundWindow(hwnd)
                        select(user.TrackPopupMenu(menu, 0x0102, point.x, point.y, 0, hwnd, None))
                        user.PostMessageW(hwnd, 0, 0, 0)
                    finally:
                        user.DestroyMenu(menu)
                return 0
            if message == taskbar_created:
                shell.Shell_NotifyIconW(0, ctypes.byref(notice))
                return 0
            if message == 0x0010:  # WM_CLOSE
                user.DestroyWindow(hwnd)
                return 0
            if message == 0x0002:  # WM_DESTROY
                self.stop.set()
                user.PostQuitMessage(0)
                return 0
            return user.DefWindowProcW(hwnd, message, wparam, lparam)

        window_class = WindowClass(instance=instance, callback=window_proc, name=name)
        if not user.RegisterClassW(ctypes.byref(window_class)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            self.hwnd = user.CreateWindowExW(0, name, "AI Limits", 0, 0, 0, 0, 0, None, None, instance, None)
            if not self.hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            data = _icon_data()
            buffer = ctypes.create_string_buffer(data)
            icon = user.CreateIconFromResourceEx(buffer, len(data), True, 0x00030000, 32, 32, 0)
            if not icon:
                raise ctypes.WinError(ctypes.get_last_error())
            notice = NotifyIcon(
                size=ctypes.sizeof(NotifyIcon),
                hwnd=self.hwnd,
                id=1,
                flags=7,
                callback=0x8001,
                icon=icon,
                tip="AI Limits — funcionando em segundo plano",
            )
            if not shell.Shell_NotifyIconW(0, ctypes.byref(notice)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.ready.set()
            message = wt.MSG()
            while True:
                result = user.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result == -1:
                    raise ctypes.WinError(ctypes.get_last_error())
                if result == 0:
                    break
                user.TranslateMessage(ctypes.byref(message))
                user.DispatchMessageW(ctypes.byref(message))
        finally:
            shell.Shell_NotifyIconW(2, ctypes.byref(notice))
            if self.hwnd:
                user.DestroyWindow(self.hwnd)
                self.hwnd = None
            if icon:
                user.DestroyIcon(icon)
            user.UnregisterClassW(name, instance)
