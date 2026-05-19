from pathlib import PurePosixPath

from app.core.exceptions import BadRequestException


def normalize_path(path: str) -> str:
    """规范化虚拟路径: 统一使用 /, 并拒绝目录穿越。"""
    if not path:
        return "/"
    if "\x00" in path:
        raise BadRequestException("路径包含非法字符")

    parts = []
    for part in path.replace("\\", "/").split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            raise BadRequestException("路径不能包含上级目录引用")
        parts.append(part)
    return "/" + "/".join(parts) if parts else "/"


def is_safe_path(base: str, target: str) -> bool:
    """检查目标路径是否在基础路径内 (防止目录遍历)"""
    base_parts = normalize_path(base).strip("/").split("/")
    target_parts = normalize_path(target).strip("/").split("/")
    if not base_parts or base_parts == [""]:
        return True
    return target_parts[:len(base_parts)] == base_parts


def parent_path(path: str) -> str:
    """获取父目录路径"""
    normalized = normalize_path(path)
    if normalized == "/":
        return "/"
    parts = normalized.strip("/").split("/")
    return "/" + "/".join(parts[:-1]) if len(parts) > 1 else "/"


def safe_upload_filename(filename: str | None) -> str:
    """校验上传文件名, 禁止客户端通过文件名携带路径。"""
    if not filename or "\x00" in filename:
        raise BadRequestException("文件名无效")

    normalized = filename.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.name != normalized or path.name in ("", ".", ".."):
        raise BadRequestException("文件名不能包含路径")
    return path.name
