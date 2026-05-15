# MultiMount

多协议统一文件挂载管理平台。支持 Local / FTP / SFTP / WebDAV / 阿里云 OSS / Amazon S3 六种协议的统一管理，并提供 WebDAV 服务暴露能力。

## 环境要求

- Python >= 3.11
- Node.js >= 18

## 快速启动

### 1. 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 安装依赖
pip install -e .

# 复制环境配置 (可按需修改)
cp .env.example .env

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

后端启动后会自动:
- 创建 SQLite 数据库
- 初始化默认角色 (admin / user / readonly)
- 创建默认管理员账号

### 2. 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 http://localhost:5173

### 3. 默认管理员账号

| 用户名 | 密码 |
|--------|------|
| `admin` | `admin123` |

首次登录后建议修改密码。

## 生产构建

```bash
# 构建前端
cd frontend && npm run build

# 将构建产物复制到后端静态目录
cp -r dist/* ../backend/static/

# 以生产模式启动后端 (自动托管前端)
cd ../backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 功能说明

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

### 文件浏览器

- 列表/网格双视图切换
- 文件上传 (支持拖拽)、下载、删除、移动、复制
- 创建文件夹
- 批量选择操作
- 生成分享链接

### WebDAV 服务

将所有挂载点以 WebDAV 协议对外暴露，支持:
- Windows 资源管理器 / macOS Finder 原生挂载
- Basic Auth 认证 (复用平台用户账号)
- 独立端口运行，可配置 SSL

### 用户与权限

- 基于角色的访问控制 (RBAC)
- 每个角色可独立配置对各挂载点的访问权限 (不可见 / 只读 / 读写)
- QoS 速率限制 (下载/上传速率、并发连接数)

### 系统设置

- 深色/浅色主题切换
- HTTPS 证书管理
- 日志查看 (系统日志 / 访问日志 / 传输日志)

## 项目结构

```
pan/
├── backend/
│   ├── app/
│   │   ├── adapters/          # 存储协议适配器
│   │   ├── api/v1/            # REST API 路由
│   │   ├── core/              # 安全、中间件、权限
│   │   ├── models/            # 数据库模型
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── services/          # 业务逻辑
│   │   └── webdav_server/     # WebDAV 服务端
│   ├── alembic/               # 数据库迁移
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/               # 后端 API 调用
│   │   ├── components/        # 通用组件
│   │   ├── composables/       # 组合式函数
│   │   ├── stores/            # Pinia 状态管理
│   │   ├── views/             # 页面视图
│   │   └── styles/            # 全局样式
│   ├── package.json
│   └── vite.config.js
└── README.md
```
