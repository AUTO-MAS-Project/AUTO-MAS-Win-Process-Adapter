"""通用进程适配。"""

from __future__ import annotations

import sys

from auto_mas_core import GameAdapterPlugin, GameTypeDecl

from .control import WinProcessControl, search_installed
from .schema import WinProcessDevice, WinProcessGame


class Plugin(GameAdapterPlugin):
    """登记通用进程游戏配置类。展示名在包内 i18n。"""

    game_type_key = "win_process"
    decl = GameTypeDecl(
        game_class=WinProcessGame,
        device_class=WinProcessDevice,
        control_class=WinProcessControl,
        search=search_installed,
    )

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
