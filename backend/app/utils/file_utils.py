import mimetypes


def format_size(size_bytes: int) -> str:  # noqa: E302
    """将字节数格式化为人类可读的大小"""
    if size_bytes < 0:
        return "未知"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} B"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def guess_mime(filename: str) -> str | None:
    """根据文件名猜测 MIME 类型"""
    return mimetypes.guess_type(filename)[0]
