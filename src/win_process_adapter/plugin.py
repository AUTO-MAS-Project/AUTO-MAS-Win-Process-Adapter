"""通用进程适配。"""

from __future__ import annotations

import sys
from typing import ClassVar

from auto_mas_core import GameAdapterPlugin, GameTypeDecl, PluginPrecheckError
from auto_mas_core.utils import ProcessManager, process

from .control import WinProcessControl, search_installed
from .schema import WinProcessDevice, WinProcessGame


class Plugin(GameAdapterPlugin):
    """登记通用进程游戏配置类。展示名在包内 i18n。"""

    game_type_key = "win_process"
    provides_services: ClassVar[dict[str, str]] = {
        "win_process.desktop_scope": "check_desktop_scope"
    }
    decl = GameTypeDecl(
        game_class=WinProcessGame,
        device_class=WinProcessDevice,
        control_class=WinProcessControl,
        search=search_installed,
    )

    def check_desktop_scope(self) -> None:
        if not callable(getattr(ProcessManager, "maximize_window", None)) or not all(
            callable(getattr(process, name, None))
            for name in ("desktop_process_session_id", "iter_processes")
        ):
            raise PluginPrecheckError("当前宿主未提供桌面分身进程范围接口")

    async def pre_enable(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Windows 通用进程适配仅支持 Windows")

    async def on_enable(self) -> None:
        for entry in self.instances():
            if isinstance(entry, WinProcessGame):
                await entry._control.refresh()

    async def on_disable(self) -> None:
        await self.on_teardown()

    async def on_teardown(self) -> None:
        for entry in self.instances():
            if isinstance(entry, WinProcessGame):
                await entry._control.teardown()
