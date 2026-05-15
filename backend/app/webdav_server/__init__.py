"""
WebDAV 服务端模块 — 使用 wsgidav + cheroot 对外暴露 WebDAV 协议。

核心组件:
  - provider.py: 自定义 DAVProvider, 桥接 Adapter 层
  - domain_controller.py: 复用 User 模型的 Basic Auth 认证
  - manager.py: 服务生命周期管理 (启停/配置热更新)
  - middleware.py: 访问日志中间件
"""
