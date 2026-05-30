# MultiMount

多协议统一文件挂载管理平台。支持 Local / FTP / SFTP / WebDAV / 阿里云 OSS / Amazon S3 六种协议的统一管理，并提供 WebDAV 服务暴露能力。

## 环境要求

- Python >= 3.11
- Node.js >= 18

## 开发启动

### Windows

后端:

```powershell
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate

# 安装依赖
pip install -e .

# 复制环境配置
copy .env.example .env

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8014 --reload
```

前端:

```powershell
cd frontend
npm install
npm run dev
```

### Linux / macOS

后端:

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -e .

# 复制环境配置
cp .env.example .env

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8014 --reload
```

后端启动后会自动:
- 创建 SQLite 数据库 (`data/multimount.db`)
- 初始化默认角色 (admin / user / readonly)
- 创建默认管理员账号

前端:

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 ，前端通过 `VITE_API_BASE_URL` 连接后端 `http://localhost:8014`。也可以使用 Vite 代理将 `/api` 请求转发到后端 `http://127.0.0.1:8014`。

### 默认管理员账号

| 账号 | 用户名 | 密码 |
|------|--------|------|
| `admin` | `admin` | `admin123` |

首次登录后建议在「个人设置」中修改密码。

## 环境配置

复制 `backend/.env.example` 为 `backend/.env`，按需修改:

```ini
# 应用
APP_HOST=0.0.0.0
APP_PORT=8014
DEBUG=true

# 数据库 (默认 SQLite，文件存储在 data/ 目录)
DATABASE_URL=sqlite+aiosqlite:///./data/multimount.db

# JWT 密钥 (生产环境务必更换!)
JWT_SECRET_KEY=CHANGE_ME_TO_A_RANDOM_SECRET_KEY
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS 允许的前端地址
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# Fernet 加密密钥 (用于加密挂载配置中的密码等敏感字段，生产环境务必设置固定值)
ENCRYPTION_KEY=
```

前端复制 `frontend/.env.example` 为 `frontend/.env`，默认 API 地址:

```ini
VITE_API_BASE_URL=http://localhost:8014
```

## 生产部署

生产环境建议使用 Nginx 托管前端构建产物，并将 `/api/` 反向代理到后端。项目内提供了 Nginx 模板:

```text
deploy/nginx/mounthub.conf.example
```

这个模板不会自动生效，需要复制到服务器的 Nginx 配置目录并按实际域名、路径修改。

### Windows 本机预览

Windows 更适合开发和本机预览。可以分别启动后端和前端:

```powershell
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8014
```

```powershell
cd frontend
npm run build
npm run preview
```

如需在 Windows 上用生产方式部署，也建议使用独立的 Web 服务器托管 `frontend/dist`，并把 `/api/` 代理到后端。

### Linux 单机生产部署

```bash
# 代码目录示例
sudo mkdir -p /opt/mounthub
sudo chown -R "$USER":"$USER" /opt/mounthub
cd /opt/mounthub

# 拉取或复制本项目代码后，安装后端依赖
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -e .
cp .env.example .env
```

修改 `backend/.env`，生产环境至少需要:

```ini
DEBUG=false
APP_HOST=127.0.0.1
APP_PORT=8014
DATABASE_URL=sqlite+aiosqlite:///./data/multimount.db
JWT_SECRET_KEY=请替换为随机长密钥
ENCRYPTION_KEY=请替换为固定的 Fernet 密钥
CORS_ORIGINS=["https://your-domain.example"]
```

生成 Fernet 密钥示例:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

构建前端:

```bash
cd /opt/mounthub/frontend
npm install
npm run build
```

启动后端:

```bash
cd /opt/mounthub/backend
source venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8014
```

### Nginx 配置

复制模板:

```bash
sudo cp /opt/mounthub/deploy/nginx/mounthub.conf.example /etc/nginx/sites-available/mounthub
sudo ln -s /etc/nginx/sites-available/mounthub /etc/nginx/sites-enabled/mounthub
```

编辑 `/etc/nginx/sites-available/mounthub`:

- 将 `server_name example.com;` 改为你的域名或服务器 IP
- 将 `root /opt/mounthub/frontend/dist;` 改为实际前端构建目录
- 如启用 HTTPS，使用模板中的 HTTPS 示例并配置证书路径

检查并重载 Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Nginx 模板包含:

- `try_files $uri $uri/ /index.html`，支持 Vue Router 刷新不 404
- `/api/` 反向代理到 `127.0.0.1:8014`
- WebSocket `Upgrade` / `Connection` 头
- 大文件上传的 `client_max_body_size` 和 `proxy_request_buffering off`

### systemd 后台运行示例

可以在服务器创建 `/etc/systemd/system/mounthub.service`:

```ini
[Unit]
Description=MountHub Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/mounthub/backend
Environment=PATH=/opt/mounthub/backend/venv/bin
ExecStart=/opt/mounthub/backend/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8014
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用服务:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mounthub
sudo systemctl status mounthub
```

## 功能说明

### 用户系统

- **账号体系**: 每个用户拥有唯一账号 (`account`)、用户名、邮箱，均用于登录
- **多方式登录**: 支持使用账号、用户名或邮箱登录
- **角色权限**: 基于角色的访问控制 (admin / user / readonly)
- **个人设置**: 修改用户名、邮箱、密码（自动唯一性校验）

### 挂载管理

支持六种存储协议，每个挂载点独立配置:

| 协议 | 说明 |
|------|------|
| Local | 本地文件系统目录 |
| FTP | FTP 服务器 |
| SFTP | SSH 文件传输 |
| WebDAV | WebDAV 服务 |
| OSS | 阿里云对象存储 |
| S3 | Amazon S3 兼容存储 |

- 挂载点级别的权限管理 (不可见 / 只读 / 读写)
- 普通用户可创建和管理自己的挂载点 (需 `can_manage_mounts` 权限)

### 文件浏览器

- 列表/网格双视图切换
- 文件上传 (支持拖拽)、下载、删除、移动、复制
- 创建文件夹
- 批量选择操作
- 文件预览 (图片、文本、视频等)
- 生成分享链接

### 文件搜索

- 跨挂载点文件名搜索
- 支持正则表达式匹配
- 按挂载源、创建者过滤搜索结果

### WebDAV 服务

将所有挂载点以 WebDAV 协议对外暴露，支持:
- Windows 资源管理器 / macOS Finder 原生挂载
- Basic Auth 认证 (复用平台用户账号)
- 通过侧边栏开关一键启停

### 通知系统

- 挂载状态变更通知
- 权限变更通知
- 权限申请审批 (同意/拒绝)

### 传输任务

- 传输队列管理
- 传输进度和状态跟踪

### 系统管理 (管理员)

- 用户与角色管理
- 请求监控
- 系统设置 (HTTPS 证书、日志查看等)
- 深色/浅色主题切换

## 项目结构

```
MountHub/
├── deploy/
│   └── nginx/
│       └── mounthub.conf.example # Nginx 生产部署模板
├── backend/
│   ├── app/
│   │   ├── adapters/          # 存储协议适配器 (local/ftp/sftp/webdav/oss/s3)
│   │   ├── api/v1/            # REST API 路由
│   │   ├── core/              # 安全、中间件、权限、日志
│   │   ├── models/            # SQLAlchemy 数据库模型
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── services/          # 业务逻辑
│   │   ├── utils/             # 工具函数
│   │   └── webdav_server/     # WebDAV 服务端 (wsgidav)
│   ├── data/                  # SQLite 数据库 (git 忽略)
│   ├── certs/                 # SSL 证书 (git 忽略)
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/               # 后端 API 调用
│   │   ├── components/        # 通用组件 (布局、文件操作等)
│   │   ├── composables/       # 组合式函数 (WebSocket 等)
│   │   ├── router/            # Vue Router 路由配置
│   │   ├── stores/            # Pinia 状态管理
│   │   ├── utils/             # 工具函数 (axios 封装等)
│   │   └── views/             # 页面视图
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## 页面导航

| 路径 | 页面 | 权限 |
|------|------|------|
| `/files` | 文件浏览器 | 所有用户 |
| `/mounts` | 挂载管理 | 所有用户 |
| `/transfers` | 传输任务 | 所有用户 |
| `/profile` | 个人设置 | 所有用户 |
| `/users` | 用户与权限 | 管理员 |
| `/settings` | 系统设置 | 管理员 |
| `/monitor` | 请求监控 | 管理员 |
