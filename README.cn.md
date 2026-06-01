# Agent Control

[English](README.md)

最简单的群控终端 Web 面板。

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
