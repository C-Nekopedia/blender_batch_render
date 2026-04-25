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
- **Web 界面** — Vue 3 前端，包含终端控制台、进度追踪和系统状态面板
- **远程访问** — 通过 IPv6（直连）或 Tailscale（回退）从任意设备连接
- **Windows 服务** — 以后台服务运行，支持开机自启和崩溃恢复

## 环境要求

- Python 3.10+（实测支持 3.14）
- Blender 3.6+（任意安装方式均可：独立版、Steam、系统安装）
- Node.js 18+ 和 pnpm（仅首次构建前端时需要）

## 快速开始

```bash
# 一键安装 — 自动安装 Python 依赖、构建前端、注册系统服务
scripts\setup.bat
```

安装完成后会自动启动服务并打开 Web 界面 `http://localhost:34567`。

服务开机自启。在局域网内任意设备打开以下地址即可访问：

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

## 服务管理

```bat
scripts\install-service.bat     # 安装/重装 Windows 服务
scripts\remove-service.bat      # 卸载 Windows 服务
scripts\start.bat               # 启动服务
scripts\stop.bat                # 停止服务
scripts\restart.bat             # 重启服务
scripts\build-frontend.bat      # 重新构建前端（修改前端后执行）
scripts\setup.bat               # 一键安装：依赖 + 构建 + 注册服务
```

服务名称为 `BlenderBatchRender`，由 NSSM 管理。以 `python server/run_production.py` 命令运行，支持 IPv4/IPv6 双栈。

### 端口与防火墙

服务监听 `34567` 端口。安装脚本会自动添加 Windows 防火墙放行规则。如需手动添加：

```bat
netsh advfirewall firewall add rule name="Blender Batch Render" dir=in action=allow protocol=TCP localport=34567
```

## 项目结构

```
Blender_Bacth_Render_Tool/
├── server/                    # Python FastAPI 后端
│   ├── main.py                # HTTP/WebSocket 路由、系统检测、API 端点
│   ├── engine.py              # Blender 子进程管理、批量渲染引擎
│   └── run_production.py      # 双栈入口（IPv4 + IPv6）
├── apps/web/                  # Vue 3 + Vite 前端
│   └── src/
│       ├── App.vue            # 主布局，含侧边栏导航
│       ├── components/        # UI 组件
│       └── composables/       # 终端与设置状态管理
├── scripts/                   # 安装、服务管理、开发脚本
│   ├── setup.bat              # 一键安装
│   ├── install-service.bat    # NSSM 服务注册
│   ├── remove-service.bat     # 服务卸载
│   ├── start.bat / stop.bat / restart.bat  # 服务控制
│   ├── build-frontend.bat     # 前端构建
│   ├── dev.bat / dev.ps1 / dev.sh  # 开发服务器启动
│   └── nssm.exe               # NSSM 服务管理器（自动下载）
└── server/requirements.txt    # Python 依赖清单
```

渲染引擎以后台模式（`-b`）启动 Blender 子进程，解析标准输出中的帧/采样进度，并通过 WebSocket 向所有连接的客户端广播。每批次结束后检查系统内存，超过配置阈值则自动重启 Blender。

## API 概览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/ws` | WebSocket | 实时推送渲染进度和系统状态 |
| `/render/start` | POST | 开始渲染 |
| `/render/stop` | POST | 停止渲染 |
| `/api/settings` | GET/POST | 读写渲染设置 |
| `/api/system-stats` | GET | CPU/GPU/内存/显存使用率 |
| `/api/hardware-info` | GET | 硬件配置（CPU、GPU、主板、内存、OS） |
| `/api/network-info` | GET | 网络地址（IPv4、IPv6、Tailscale） |
| `/api/browse-file` | GET | 打开系统文件选择对话框（仅本地） |

## 常见问题

**渲染日志无输出？**
检查 WebSocket 连接状态。如断开，服务端可能重启中，等待数秒自动重连。

**手机端看不到文件浏览按钮？**
远程访问时文件浏览（本地文件对话框）自动隐藏，需手动输入路径。

**服务无法启动？**
检查 `logs\error.log` 查看详细错误信息。常见原因：Python 路径不正确、Blender 路径不存在。

## 许可证

MIT
