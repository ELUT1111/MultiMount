"""Role identity helpers.

Role names are the stable identity for built-in privileged roles. Usernames are
not used for authorization decisions.
"""

ROLE_ADMIN = "admin"
ROLE_SUPER_ADMIN = "super_admin"
ADMIN_ROLE_NAMES = {ROLE_ADMIN, ROLE_SUPER_ADMIN}
PROTECTED_ROLE_NAMES = {ROLE_ADMIN, ROLE_SUPER_ADMIN}


def role_name(user) -> str | None:
    # 只读取关联角色的稳定 name 字段，不使用用户名、昵称等可变信息做授权依据。
    return getattr(getattr(user, "role", None), "name", None)


def is_super_admin(user) -> bool:
    # 当前设计中超级管理员唯一，用于授予/取消普通管理员身份。
    return role_name(user) == ROLE_SUPER_ADMIN


def is_admin(user) -> bool:
    # 超级管理员继承管理员能力，因此所有管理员判断都包含 super_admin。
    return role_name(user) in ADMIN_ROLE_NAMES


def is_protected_role_name(name: str | None) -> bool:
    # 受保护角色不能被普通管理员编辑或删除。
    return name in PROTECTED_ROLE_NAMES
