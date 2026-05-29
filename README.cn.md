# Agent Control

[English](README.en.md)

最简单的群控终端：Flask 提供 Web 界面，每个 session 由 [ttyd](https://github.com/tsl0922/ttyd) 映射为一个格子，底层用 [tmux](https://github.com/tmux/tmux) 持久化终端工作区。

## 架构

```
浏览器格子 (iframe)
    ↓ HTTP / WebSocket
  ttyd（每个 session 一个端口）
    ↓
  tmux session（agent-{id}）
    ↓
  bash / 你跑的程序
```

- **Flask**：Web UI、API、session 管理
- **SQLite**（`data/sessions.db`）：保存 session 元数据（id、标题、端口、排序、窗口大小、tmux 绑定）
- **ttyd**：把终端暴露到浏览器
- **tmux**：真正持有终端状态（目录、进程、历史）

## 依赖

- Python 3.10+
- [ttyd](https://github.com/tsl0922/ttyd)（Web 终端）
- [tmux](https://github.com/tmux/tmux)（**推荐**，刷新/重启后保留工作区）

### 安装

```bash
# Ubuntu / Debian
sudo apt install ttyd tmux

# 或下载 ttyd 到项目目录（无 sudo 时）
bash setup_ttyd.sh
```

## 运行

```bash
pip install -r requirements.txt

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

### 启动参数

| 参数 | 环境变量 | 默认值 | 说明 |
|------|----------|--------|------|
| `--token` | `AGENT_CTL_TOKEN` | （必填） | 访问令牌，无 token 无法启动 |
| `-p` / `--port` | `PORT` | `5000` | Flask 监听端口 |
| `--host` | `HOST` | `0.0.0.0` | 绑定地址 |
| `--debug` | `DEBUG=1` | 开启 | Flask 调试模式 |
| `--no-debug` | — | — | 关闭调试模式 |

## 鉴权

启动时 **必须** 配置 token，所有 Web 页面与 `/api/*` 接口均受保护，未授权请求会被拒绝。

| 方式 | 说明 |
|------|------|
| 登录页 | 访问 `/` 跳转 `/login`，输入 token 后写入 HttpOnly cookie |
| URL | `GET /auth?token=...` 验证通过后写入 cookie |
| 请求头 | `Authorization: Bearer <token>` 或 `X-Agent-Token: <token>` |
| API | 无有效 token 返回 `401` |

> 说明：ttyd 终端 iframe 仍直连各自端口（7681+），不经过 Flask 鉴权。控制面板 UI 与 API 已受 token 保护。

## 使用

1. 点击右下角 **+** 创建 session（可选复用已有 tmux session，或新建）
2. 点击标题可编辑备注（存 SQLite）
3. 拖动 **⠿** 调整格子顺序；拖动 **右下角** 调整窗口大小（流式排列）
4. 点击 **⤢** 全屏放大，**Esc** /「最小化」回到网格；最小化后点击终端区域「重绘」可继续在小窗编辑
5. 右上角 **重置窗口** 将所有格子恢复为默认大小（320×240）
6. 格子右上角 **×** 关闭 session（同时结束对应 tmux，若未被其他格子复用）

## tmux 联动原理

每个 session 创建时，后端启动的命令是：

```bash
ttyd -p <port> -W -I ttyd/index.html \
  tmux new-session -A -s agent-<session_id>
```

含义：

| 部分 | 作用 |
|------|------|
| `tmux new-session -A -s agent-xxx` | 若 tmux 会话已存在则 **attach**，否则 **新建** |
| `agent-<session_id>` | 与 SQLite 里的 session id 一一对应，保证可恢复 |
| ttyd | 仅负责 Web 展示；挂了可以再起，重新 attach 同一个 tmux |

因此：

- **刷新浏览器**：iframe 重连 ttyd，ttyd 仍 attach 同一个 tmux → 工作区不丢
- **重启 Flask 服务器**：从 SQLite 恢复 session 列表，重新拉起 ttyd，再 attach 已有 tmux → 工作区不丢
- **关闭 session（×）**：停止 ttyd，并执行 `tmux kill-session -t agent-xxx` → 彻底清理

若系统未安装 tmux，会回退为 `bash`，刷新/重启后终端状态**不会**保留。

### 手动查看 tmux 会话

```bash
tmux ls                  # 列出所有 agent-* 会话
tmux attach -t agent-xxx # 在本地终端 attach 同一个 session
```

## 持久化说明

| 内容 | 刷新页面 | 重启服务器 | 关闭 session |
|------|----------|------------|--------------|
| 格子 / 标题 | ✅ SQLite | ✅ SQLite | ❌ 删除 |
| 终端工作区（tmux） | ✅ | ✅ | ❌ kill tmux |
| ttyd 进程 | 重连即可 | 自动重建 | 停止 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AGENT_CTL_TOKEN` | （必填） | 访问令牌，也可通过 `--token` 传入 |
| `HOST` | `0.0.0.0` | Flask 监听地址 |
| `PORT` | `5000` | Flask 端口 |
| `DEBUG` | `1` | 调试模式（改代码自动重载） |
| `TTYD_BASE_PORT` | `7681` | ttyd 起始端口 |
| `TTYD_BIN` | 自动查找 | ttyd 可执行文件路径 |

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/sessions` | 列出 session |
| `POST` | `/api/sessions` | 创建（可选 body `{ "tmuxSession": "..." }` 复用 tmux） |
| `PATCH` | `/api/sessions/<id>` | 更新标题或窗口尺寸 `{ "width", "height" }` |
| `DELETE` | `/api/sessions/<id>` | 删除 session |
| `PUT` | `/api/sessions/order` | 更新排序 `{ "order": ["id", ...] }` |
| `POST` | `/api/sessions/reset-layout` | 重置所有窗口为默认大小 |
| `GET` | `/api/tmux/sessions` | 列出可复用的 tmux session |
