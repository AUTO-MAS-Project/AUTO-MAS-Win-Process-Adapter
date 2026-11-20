"""Windows 客户端的设备身份、进程占用及窗口控制。"""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid5

import psutil
from auto_mas_core import ClientControl, DeviceStatus, DeviceSubscribeError, LockTicket
from auto_mas_core.utils import ProcessInfo, ProcessManager, file_lock, process

from .schema import WinProcessDevice, WinProcessGame


class WinProcessControl(ClientControl[WinProcessGame, WinProcessDevice]):
    """配置保存目标身份，控制器在运行期跟踪真实进程。"""

    capabilities = ("open", "close", "show", "hide", "minimize", "maximize")

    def __init__(self, config: WinProcessGame | None = None) -> None:
        super().__init__(config=config)
        self._processes: dict[int | None, ProcessManager] = {}
        self._operation = asyncio.Lock()
        self._resource_file: BinaryIO | None = None

    @property
    def _process(self) -> ProcessManager:
        # 支持尚未提供桌面分身会话接口的 SDK。
        scope = getattr(process, "desktop_process_session_id", None)
        session_id = scope() if scope is not None else None
        if session_id not in self._processes:
            self._processes[session_id] = ProcessManager()
        return self._processes[session_id]

    @property
    def busy(self) -> bool:
        return self._operation.locked()

    @property
    def executable_path(self):
        return self.config.info.path

    @property
    def launcher_path(self):
        return self.config.info.launch_path

    async def initialize_devices(self) -> None:
        entry = self.config
        if not entry.devices:
            entry.devices.add(
                WinProcessDevice,
                uid=uuid5(entry.uid, "client"),
                payload={"info": {"name": entry.info.name}},
            )
            await entry.devices.commit()

    async def _refresh(self) -> None:
        await self.initialize_devices()
        entry = self.config
        running = await self._process.is_running()
        if not running and entry.info.path is not None:
            path = os.path.normcase(str(entry.executable.resolve()))

            def matching_pids() -> list[int]:
                scan = getattr(process, "iter_processes", psutil.process_iter)
                return [
                    proc.pid
                    for proc in scan(["exe"])
                    if proc.info["exe"]
                    and os.path.normcase(str(Path(proc.info["exe"]).resolve())) == path
                ]

            pids = await asyncio.to_thread(matching_pids)
            if len(pids) > 1:
                raise RuntimeError("同一游戏路径存在多个进程，无法确定应控制的目标")
            if pids:
                await self._process.search_process(
                    ProcessInfo(pid=pids[0]),
                    timeout_seconds=1,
                    owned=False,
                )
                running = await self._process.is_running()
        status = DeviceStatus.ONLINE if running else DeviceStatus.OFFLINE
        for device in entry.devices.values():
            device.info.status = status
            await device.commit()

    async def refresh(self) -> None:
        async with self.operation_scope(self._operation):
            await self._refresh()

    async def _on_device_subscribed(
        self, device_uid: UUID, expect: object | None
    ) -> None:
        if device_uid not in self.config.devices:
            raise KeyError("游戏设备不存在")
        if expect is not None:
            raise TypeError("Windows 进程设备不接受模拟器设置")
        identity = os.path.normcase(str(self.config.executable.resolve()))
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        directory = Path(tempfile.gettempdir()) / "AUTO-MAS" / "win-process-locks"
        directory.mkdir(parents=True, exist_ok=True)
        handle = (directory / digest).open("a+b")
        try:
            file_lock.acquire(handle)
        except OSError as error:
            handle.close()
            raise DeviceSubscribeError("该游戏已被其他托管或 MAS 进程占用") from error
        self._resource_file = handle

    async def _on_device_unsubscribed(self, device_uid: UUID) -> None:
        handle = self._resource_file
        if handle is not None:
            try:
                file_lock.release(handle)
            finally:
                handle.close()
                self._resource_file = None

    def _check_device(self, device_uid: UUID, ticket: LockTicket) -> None:
        self.check_subscription(device_uid, ticket)
        if device_uid not in self.config.devices:
            raise KeyError("游戏设备不存在")

    def checked_process(self, uid, *, ticket):
        self._check_device(uid, ticket)
        return self._process

    def _target(self, target: ProcessInfo) -> ProcessInfo:
        executable = self.config.executable.resolve()
        if target.exe is not None and Path(target.exe).resolve() != executable:
            raise ValueError("专项请求的游戏进程与所选游戏目标不一致")
        return ProcessInfo(pid=target.pid, exe=str(executable), cmdline=target.cmdline)

    async def start_process(self, uid, program, *args, ticket, **options):
        self._check_device(uid, ticket)
        async with self.operation_scope(self._operation):
            await self._refresh()
            executable = self.config.executable
            program = Path(program)
            target = options.get("target_process")
            if target is not None:
                options["target_process"] = self._target(target)
            elif program != executable:
                options["target_process"] = ProcessInfo(exe=str(executable))
            options["breakaway"] = True
            try:
                async with asyncio.timeout(self.config.info.wait_time):
                    await self._process.open_process(program, *args, **options)
                    if not await self._process.is_running():
                        raise RuntimeError("游戏启动后已经退出")
            finally:
                await self._refresh()

    async def track_process(self, uid, target, *args, ticket, **options):
        self._check_device(uid, ticket)
        async with self.operation_scope(self._operation):
            return await self._process.search_process(
                self._target(target), *args, **options
            )

    async def stop_process(self, uid, *, ticket):
        self._check_device(uid, ticket)
        async with self.operation_scope(self._operation):
            await self._refresh()
            await self._process.kill()
            await self._refresh()
            if await self._process.is_running():
                raise RuntimeError("无法确认游戏进程已经关闭")

    async def start_protocol(self, uid, url, target, *, ticket):
        self._check_device(uid, ticket)
        async with self.operation_scope(self._operation):
            try:
                async with asyncio.timeout(self.config.info.wait_time):
                    await self._process.open_protocol(url, self._target(target))
            finally:
                await self._refresh()

    async def open(self, device_uid: UUID, *, ticket: LockTicket) -> None:
        self._check_device(device_uid, ticket)
        async with self.operation_scope(self._operation):
            await self._refresh()
            if await self._process.is_running():
                return
            entry = self.config
            executable = entry.executable
            launch = (
                entry.info.launch_path if entry.info.launch_with_launcher else None
            ) or executable
            try:
                async with asyncio.timeout(entry.info.wait_time):
                    await self._process.open_process(
                        launch,
                        *entry.info.arguments,
                        cwd=entry.info.working_directory or launch.parent,
                        target_process=(
                            ProcessInfo(exe=str(executable))
                            if launch != executable
                            else None
                        ),
                        breakaway=True,
                    )
                    if not await self._process.is_running():
                        raise RuntimeError("游戏启动后已经退出")
            finally:
                await self._refresh()

    async def close(self, device_uid: UUID, *, ticket: LockTicket) -> None:
        self._check_device(device_uid, ticket)
        async with self.operation_scope(self._operation):
            await self._refresh()
            try:
                async with asyncio.timeout(self.config.info.wait_time):
                    if self.config.info.force_kill:
                        await self._process.kill()
                    else:
                        await self._process.close()
                    if await self._process.is_running():
                        raise RuntimeError("无法确认游戏进程已经关闭")
            finally:
                await self._refresh()

    async def _window_action(
        self, device_uid: UUID, ticket: LockTicket, action: str
    ) -> None:
        self._check_device(device_uid, ticket)
        async with self.operation_scope(self._operation):
            await self._refresh()
            operations = {
                "show": self._process.show_window,
                "hide": self._process.hide_window,
                "minimize": self._process.minimize_window,
            }
            if not await operations[action]():
                raise RuntimeError("游戏窗口不可用或窗口操作失败")

    async def show(self, device_uid: UUID, *, ticket: LockTicket) -> None:
        await self._window_action(device_uid, ticket, "show")

    async def hide(self, device_uid: UUID, *, ticket: LockTicket) -> None:
        await self._window_action(device_uid, ticket, "hide")

    async def minimize(self, device_uid: UUID, *, ticket: LockTicket) -> None:
        await self._window_action(device_uid, ticket, "minimize")

    async def maximize(self, device_uid: UUID, *, ticket: LockTicket) -> None:
        self._check_device(device_uid, ticket)
        async with self.operation_scope(self._operation):
            await self._refresh()
            manager = self._process
            maximize = getattr(manager, "maximize_window", None)
            if maximize is not None:
                if not await maximize():
                    raise RuntimeError("游戏窗口不可用或最大化失败")
                return
            # 旧 SDK 只支持通过主会话的窗口句柄操作。
            hwnd = manager.main_hwnd
            if hwnd is None:
                raise RuntimeError("游戏窗口不可用")
            import win32con
            import win32gui

            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            if win32gui.GetWindowPlacement(hwnd)[1] != win32con.SW_SHOWMAXIMIZED:
                raise RuntimeError("游戏窗口最大化失败")

    async def teardown(self) -> None:
        """解除进程观察，显式关闭由设备操作入口负责。"""
        async with self.operation_scope(self._operation):
            for manager in self._processes.values():
                await manager.clear()
            self._processes.clear()


async def search_installed() -> list[WinProcessGame]:
    """Windows 客户端由手动创建或主程序配置升级登记。"""
    return []
