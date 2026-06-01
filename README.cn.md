# TMUX Ctl

[English](README.md)

最简单的群控终端 Web 面板。

![TMUX Ctl](images/image.jpg)

## 为什么需要 TMUX Ctl？

在一个终端里跑一个 AI 编码 agent 很轻松，但同时跑十个就成了一团乱麻。

当你开始让多个 agent 并行干活——一个修 bug、一个写测试、一个重构模块——你很快就看不清全局了：在一堆终端标签、SSH 会话、tmux 窗格之间来回切换，只为确认「它还在跑吗？是不是卡住了？做完了没？」。

**TMUX Ctl 把它们全部收进同一块屏幕。** 每个 agent 都拥有自己独立的实时终端格子，在浏览器里排成网格。一眼望去，你就能看到哪些 agent 在推进、哪些在等你回复、哪些需要你搭把手——而且每个格子都仍然是完整、可交互的终端。

- **一屏掌握全局**——所有正在运行的 agent 都在同一个面板上，无需来回切标签。
- **始终掌控**——每个格子都是真正可交互的终端，随时点进去敲命令。
- **不丢进度**——会话跑在 tmux 里，刷新或重启都不会中断你的工作。
- **随处可达**——它就是一个网页，用电脑、平板甚至手机都能查看你的 agent。

如果你要同时盯着多个 agent，或者只是想给几个长时间运行的终端找一个清爽的指挥中心，它能把混乱变成一目了然的平静视图。

## 依赖

- Python 3.10+
- [ttyd](https://github.com/tsl0922/ttyd)
- [tmux](https://github.com/tmux/tmux)（推荐，刷新/重启后保留工作区）

## 安装

```bash
# Ubuntu / Debian
sudo apt install ttyd tmux

# 或下载 ttyd 到项目目录（无 sudo 时）
bash setup_ttyd.sh

pip install -r requirements.txt
```

## 运行

```bash
# 必须提供 token（命令行或环境变量二选一）
python app.py --token your-secret-token

# 指定端口（默认 5000）
python app.py --token your-secret-token -p 8080

# 或用环境变量
export AGENT_CTL_TOKEN=your-secret-token
python app.py -p 5000
```

浏览器打开 http://127.0.0.1:5000 ，首次访问会进入登录页，输入启动时配置的 **token**。

也可使用一次性链接（写入 cookie 后跳转主页）：

```
http://127.0.0.1:5000/auth?token=your-secret-token
```

## 启动参数

| 参数 | 环境变量 | 默认值 | 说明 |
|------|----------|--------|------|
| `--token` | `AGENT_CTL_TOKEN` | （必填） | 访问令牌，无 token 无法启动 |
| `-p` / `--port` | `PORT` | `5000` | 监听端口 |
| `--host` | `HOST` | `0.0.0.0` | 绑定地址 |
| `--debug` | `DEBUG=1` | 开启 | 调试模式 |
| `--no-debug` | — | — | 关闭调试模式 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AGENT_CTL_TOKEN` | （必填） | 访问令牌，也可通过 `--token` 传入 |
| `HOST` | `0.0.0.0` | 绑定地址 |
| `PORT` | `5000` | 监听端口 |
| `DEBUG` | `1` | 调试模式（改代码自动重载） |
| `TTYD_BASE_PORT` | `7681` | ttyd 起始端口 |
| `TTYD_BIN` | 自动查找 | ttyd 可执行文件路径 |

## 鉴权

| 方式 | 说明 |
|------|------|
| 登录页 | 访问 `/` 跳转 `/login`，输入 token 后写入 HttpOnly cookie |
| URL | `GET /auth?token=...` 验证通过后写入 cookie |
| 请求头 | `Authorization: Bearer <token>` 或 `X-Agent-Token: <token>` |

## 使用

1. 点击右下角 **+** 创建 session
2. 点击标题可编辑备注
3. 拖动 **⠿** 调整格子顺序；拖动 **右下角** 调整窗口大小
4. 点击 **⤢** 全屏放大，**Esc** /「最小化」回到网格
5. 右上角 **重置窗口** 将所有格子恢复为默认大小
6. 格子右上角 **×** 关闭 session
