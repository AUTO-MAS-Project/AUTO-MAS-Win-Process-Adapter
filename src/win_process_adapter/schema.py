"""通用进程游戏配置与设备配置。"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from auto_mas_core import (
    ConfigCollection,
    ExecutablePath,
    FolderPath,
    GameDeviceEntry,
    GameEntry,
    UiVisibility,
    collection,
    ui,
)
from pydantic import Field


class WinProcessDevice(GameDeviceEntry):
    """一个配置目标的稳定设备身份，进程退出后仍保留。"""


class WinProcessGame(GameEntry):
    """通用进程 / 客户端配置。"""

    class Info(GameEntry.Info):
        type: Annotated[Literal["client"], ui(visibility=UiVisibility.HIDE)] = Field(  # pyright: ignore[reportIncompatibleVariableOverride]
            default="client", description="模拟器或客户端"
        )
        path: ExecutablePath = Field(default=None, description="游戏可执行文件")
        launch_path: ExecutablePath = Field(
            default=None, description="启动器路径，留空直接启动游戏"
        )
        launch_with_launcher: bool = Field(
            default=True, description="已设置启动器时通过启动器启动"
        )
        arguments: list[str] = Field(default_factory=list, description="启动参数")
        working_directory: FolderPath = Field(
            default=None, description="工作目录，留空使用启动程序所在目录"
        )
        wait_time: Annotated[int, Field(ge=1, le=9999)] = Field(
            default=60, description="操作最大等待时间（秒）"
        )
        force_kill: bool = Field(default=False, description="关闭时强制结束目标进程")

    info: Info = Field(default_factory=Info, description="游戏信息")  # pyright: ignore[reportIncompatibleVariableOverride]
    devices: ConfigCollection[WinProcessDevice] = collection(WinProcessDevice)  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def executable(self) -> Path:
        """取得配置的实际游戏路径，未配置时拒绝操作。"""
        if self.info.path is None:
            raise ValueError("尚未配置游戏可执行文件")
        return self.info.path
