from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import psutil
import pytest
from app.models.config.game import TRIGGER_TICKET
from app.utils.common.process import operations, session
from auto_mas_core import DeviceStatus

from win_process_adapter.control import WinProcessControl
from win_process_adapter.schema import WinProcessGame


@pytest.mark.asyncio
async def test_refresh_tracks_the_same_executable_independently_in_each_session(
    monkeypatch, tmp_path
):
    executable = tmp_path / "game.exe"
    executable.touch()
    entry = WinProcessGame.build(
        uid=uuid4(), payload={"info": {"path": str(executable)}}
    )
    await entry.activate()
    control = WinProcessControl(entry)
    processes = []
    for pid in (101, 102):
        candidate = Mock(spec=psutil.Process)
        candidate.pid = pid
        candidate.info = {
            "pid": pid,
            "exe": str(executable),
            "name": executable.name,
            "create_time": 1.0,
        }
        candidate.exe.return_value = str(executable)
        candidate.is_running.return_value = True
        processes.append(candidate)

    monkeypatch.setattr(psutil, "process_iter", lambda _: iter(processes))
    monkeypatch.setattr(
        operations, "matches_session", lambda pid, scope: pid - 100 == scope
    )
    monkeypatch.setattr(
        session, "matches_session", lambda pid, scope: pid - 100 == scope
    )
    monkeypatch.setattr(session, "_parent_scope", lambda: 1)

    def tracked_pid() -> int | None:
        device = next(iter(entry.devices.values()))
        assert device.info.status == DeviceStatus.ONLINE
        return control.checked_process(device.uid, ticket=TRIGGER_TICKET).main_pid

    await control.refresh()
    assert tracked_pid() == 101
    target = session.DesktopProcessTarget(2, Path.cwd(), tmp_path)
    token = session.desktop_process_target.set(target)
    try:
        await control.refresh()
        assert tracked_pid() == 102
    finally:
        session.desktop_process_target.reset(token)
    await control.refresh()
    assert tracked_pid() == 101
    await control.teardown()
