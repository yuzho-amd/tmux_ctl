# Agent Control

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
- **SQLite**（`data/sessions.db`）：保存 session 元数据（id、标题、端口）
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
python app.py
```

浏览器打开 http://127.0.0.1:5000

## 使用

1. 点击右下角 **+** 创建 session（默认名 `session-1`、`session-2`…）
2. 点击标题可编辑备注（存 SQLite）
3. 多个 session 自动矩阵排列
4. **双击** 格子进入全屏，**Esc** 退出
5. 格子右上角 **×** 关闭 session（同时结束对应 tmux）

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
| `HOST` | `0.0.0.0` | Flask 监听地址 |
| `PORT` | `5000` | Flask 端口 |
| `DEBUG` | `1` | 调试模式（改代码自动重载） |
| `TTYD_BASE_PORT` | `7681` | ttyd 起始端口 |
| `TTYD_BIN` | 自动查找 | ttyd 可执行文件路径 |
