<!-- auto-mas:i18n
{
  "display_name_i18n": {
    "zh_CN": "通用 Windows 进程适配",
    "en": "Windows Process Adapter",
    "ja": "Windows プロセスアダプター"
  },
  "description_i18n": {
    "zh_CN": "通用 Windows 进程适配",
    "en": "Windows Process Adapter",
    "ja": "Windows プロセスアダプター"
  },
  "tags_i18n": {
    "zh_CN": [
      "游戏",
      "进程"
    ],
    "en": [
      "game",
      "process"
    ],
    "ja": [
      "ゲーム",
      "プロセス"
    ]
  }
}
-->

# Windows 通用进程游戏适配

将一个游戏可执行文件登记为稳定游戏目标，集中管理启动、关闭、窗口操作和设备占用。
可单独指定启动器、启动参数及工作目录；按完整目标路径控制进程。
游戏离线时仍保留设备身份。插件不会执行游戏内任务或判断代理结果。

## 安装与发布

发行包为 `auto-mas-win-process-adapter`，插件 ID 为 `win_process_adapter`。
适用于 Python 3.12 和已接入游戏适配插件的 AUTO-MAS 宿主，要求 `auto-mas-core>=5.9.0b1,<6`。
通过插件市场安装时由宿主提供 core，独立安装时需要提供兼容的 SDK wheel。

首次发布前，在 [PyPI 账户的 Publishing 页面](https://pypi.org/manage/account/publishing/) 登记待定发布者。
项目名填 `auto-mas-win-process-adapter`，仓库所有者填 `AUTO-MAS-Project`，仓库名填 `AUTO-MAS-Win-Process-Adapter`，工作流文件名填 `publish.yml`，环境名填 `pypi`。

分支和 PR 会构建并校验 wheel 与源码包。发布时，在默认分支的提交上打与 `pyproject.toml` 版本一致的 `v` 标签并推送；GitHub Actions 通过 Trusted Publishing 上传分发包。
