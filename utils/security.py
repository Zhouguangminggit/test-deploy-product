"""安全相关辅助方法。

包含随机 token / 字符串生成、敏感信息掩码、密码策略校验、定长时间比较等。
所有随机值均使用 secrets 模块（密码学安全）。
"""

import secrets
import string


def generate_token(nbytes: int = 32) -> str:
    """生成 URL 安全的随机 token（用于重置链接、一次性校验等）。"""
    return secrets.token_urlsafe(nbytes)


def generate_random_string(
    length: int = 16,
    *,
    letters: bool = True,
    digits: bool = True,
    punctuation: bool = False,
) -> str:
    """生成指定长度的随机字符串，可选择字符集。"""
    alphabet = ""
    if letters:
        alphabet += string.ascii_letters
    if digits:
        alphabet += string.digits
    if punctuation:
        alphabet += string.punctuation
    if not alphabet:
        raise ValueError("至少需要启用一种字符类型")
    return "".join(secrets.choice(alphabet) for _ in range(max(1, length)))


def mask_sensitive(value: str, keep_start: int = 3, keep_end: int = 4, mask_char: str = "*") -> str:
    """对敏感信息（手机号、卡号等）做掩码，保留首尾若干位。"""
    if not value:
        return ""
    text = str(value)
    if len(text) <= keep_start + keep_end:
        return mask_char * len(text)
    masked_length = len(text) - keep_start - keep_end
    return f"{text[:keep_start]}{mask_char * masked_length}{text[-keep_end:]}"


def mask_email(email: str) -> str:
    """对邮箱做掩码，保留域名与首尾字符。"""
    if not email or "@" not in email:
        return mask_sensitive(email, 1, 1)
    local, domain = email.rsplit("@", 1)
    return f"{mask_sensitive(local, 1, 1)}@{domain}"


def password_meets_policy(password: str, min_length: int = 8) -> tuple[bool, list[str]]:
    """校验密码强度，返回 (是否通过, 错误提示列表)。"""
    errors: list[str] = []
    password = password or ""
    if len(password) < min_length:
        errors.append(f"密码长度至少 {min_length} 位")
    if not any(char.isalpha() for char in password):
        errors.append("密码需包含字母")
    if not any(char.isdigit() for char in password):
        errors.append("密码需包含数字")
    return (not errors, errors)


def constant_time_equals(value_a: str, value_b: str) -> bool:
    """定长时间字符串比较，避免通过响应时间推断内容（时序攻击）。"""
    return secrets.compare_digest(value_a or "", value_b or "")
