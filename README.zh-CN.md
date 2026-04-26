# Blender Batch Render Tool

基于浏览器的 Blender 批量渲染工具。将多帧分批排队渲染，内存过高时自动重启 Blender，并通过 WebSocket 向任意设备实时推送进度。

**English** | [**中文**](README.zh-CN.md)

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://cdn.jsdelivr.net/gh/C-Nekopedia/blender_batch_render@master/ui_preview/pc_preview.png">
    <img src="https://cdn.jsdelivr.net/gh/C-Nekopedia/blender_batch_render@master/ui_preview/pc_preview.png" alt="任务界面" width="720">
  </picture>
</div>

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://cdn.jsdelivr.net/gh/C-Nekopedia/blender_batch_render@master/ui_preview/phone_preview.jpg">
    <img src="https://cdn.jsdelivr.net/gh/C-Nekopedia/blender_batch_render@master/ui_preview/phone_preview.jpg" alt="手机预览" width="360">
  </picture>
</div>

## 功能特性

- **批量渲染** — 按可配置的批次大小渲染帧，批次间重启 Blender 以释放内存
- **内存感知** — 监控系统内存使用率，超过阈值自动重启
- **预览面板** — 实时栅格预览渲染输出帧；支持 EXR（ACES 色调映射）
- **Web 界面** — Vue 3 前端，包含终端控制台、错误日志分页、系统状态和实时预览
- **远程访问** — 通过 IPv6（直连）或 Tailscale（回退）从任意设备连接
- **移动端适配** — 响应式布局，汉堡菜单导航
- **后台进程** — 以后台窗口运行，无需安装，即开即用

## 环境要求

- Python 3.10+（实测支持 3.14）
- Blender 3.6+（任意安装方式均可：独立版、Steam、系统安装）
- Node.js 18+ 和 pnpm（仅首次构建前端时需要）

## 快速开始

```bash
# 一键安装 — 自动安装 Python 依赖、构建前端、启动服务器
scripts\setup.bat
```

安装完成后自动打开 Web 界面 `http://localhost:34567`。

在局域网内任意设备打开以下地址即可访问：

- **本机**: `http://localhost:34567`
- **局域网**: `http://<你的局域网IP>:34567`
- **远程 (IPv6)**: `http://[你的IPv6地址]:34567`
- **远程 (Tailscale)**: `http://<tailscale-IP>:34567`

系统信息面板中会列出所有可用的远程访问地址。

### 手动安装

```bash
# 安装 Python 依赖
cd server
pip install -r requirements.txt
cd ..

# 构建前端（一次性）
cd apps/web
pnpm install && pnpm build
cd ../..

# 启动生产服务器
python server/run_production.py
```

### 开发模式（前端热重载）

```bash
# 方式一：批处理脚本
scripts\dev.bat

# 方式二：PowerShell
powershell scripts\dev.ps1

# 方式三：Git Bash
bash scripts/dev.sh

# 方式四：pnpm（需安装 Node.js/pnpm）
pnpm dev
```

上述方式分别启动后端（端口 34567）和前端开发服务器（端口 5173），前端自动代理 API 和 WebSocket 请求到后端。

## 服务器管理

```bat
scripts\setup.bat               # 一键安装：依赖 + 构建 + 启动
scripts\start.bat               # 启动服务器（后台窗口）
scripts\stop.bat                # 停止服务器
scripts\restart.bat             # 重启服务器
scripts\build-frontend.bat      # 重新构建前端（修改前端后执行）
```

服务器以 `python server/run_production.py` 命令运行，支持 IPv4/IPv6 双栈。

### 端口与防火墙

服务监听 `34567` 端口。如需手动添加防火墙放行规则：

```bat
netsh advfirewall firewall add rule name="Blender Batch Render" dir=in action=allow protocol=TCP localport=34567
```

## 项目结构

```
Blender_Bacth_Render_Tool/
├── server/                    # Python FastAPI 后端
│   ├── main.py                # HTTP/WebSocket 路由、系统检测、API 端点
│   ├── engine.py              # Blender 子进程管理、批量渲染引擎
│   ├── preview.py             # 基于 watchdog 的输出目录监控
│   └── run_production.py      # 双栈入口（IPv4 + IPv6）
├── apps/web/                  # Vue 3 + Vite 前端
│   └── src/
│       ├── App.vue            # 主布局，含侧边栏导航
│       ├── components/
│       │   ├── PreviewPanel.vue      # 栅格预览、分页、放大查看
│       │   ├── TerminalConsole.vue   # 分页终端（Console / Errors）
│       │   ├── SettingsPanel.vue     # 渲染设置 + 崩溃恢复配置
│       │   ├── StatsBar.vue          # 用时 + 进度条
│       │   └── SystemInfo.vue        # 硬件信息、使用率图表、远程访问指南
│       └── composables/       # 终端与设置状态管理
├── scripts/                   # 安装、控制、开发脚本
│   ├── setup.bat              # 一键安装
│   ├── start.bat / stop.bat / restart.bat  # 服务器控制
│   ├── build-frontend.bat     # 前端构建
│   └── dev.bat / dev.ps1 / dev.sh  # 开发服务器启动
└── server/requirements.txt    # Python 依赖清单
```

渲染引擎以后台模式（`-b`）启动 Blender 子进程，解析标准输出中的帧/采样进度，并通过 WebSocket 向所有连接的客户端广播。每批次结束后检查系统内存，超过配置阈值则自动重启 Blender。

## API 概览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/ws` | WebSocket | 实时推送渲染进度、系统状态、预览更新 |
| `/render/start` | POST | 开始渲染 |
| `/render/stop` | POST | 停止渲染 |
| `/api/settings` | GET/POST | 读写渲染设置 |
| `/api/system-stats` | GET | CPU/GPU/内存/显存使用率 |
| `/api/hardware-info` | GET | 硬件配置（CPU、GPU、主板、内存、OS） |
| `/api/network-info` | GET | 网络地址（IPv4、IPv6、Tailscale） |
| `/api/browse-file` | GET | 打开系统文件选择对话框（仅本地） |
| `/api/preview-file` | GET | 提供渲染输出图像；`?thumb=true` 返回 320px WebP 缩略图 |

## 常见问题

**渲染日志无输出？**
检查 WebSocket 连接状态。如断开，服务端可能重启中，等待数秒自动重连。

**手机端看不到文件浏览按钮？**
远程访问时文件浏览（本地文件对话框）自动隐藏，需手动输入路径。

**服务器无法启动？**
检查 `logs\error.log` 查看详细错误信息。常见原因：Python 路径不正确、Blender 路径不存在。

**EXR 预览颜色与 Photoshop 不同？**
EXR 为 HDR 浮点格式，浏览器无法直接显示。工具使用 ACES Filmic 色调映射（与 Blender 视口相同的算法）将其转为 WebP，可能与 Photoshop 的显示设置有差异。原始 EXR 文件不受影响。

**预览页手动增删文件后没有刷新？**
目录监控覆盖了 on_created、on_modified、on_moved、on_deleted 四种事件。切换到预览页时会触发 re-scan（preview_init 消息）。如果服务停止期间添加的文件，首次扫描时会自动出现。

## 许可证

MIT
