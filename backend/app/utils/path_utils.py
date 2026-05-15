def normalize_path(path: str) -> str:
    """规范化路径: 统一使用 /, 去除多余分隔符"""
    if not path:
        return "/"
    parts = [p for p in path.replace("\\", "/").split("/") if p and p != "."]
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