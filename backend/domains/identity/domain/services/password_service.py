"""
Password Domain Service - 密码领域服务

包含密码哈希和验证的业务逻辑"""

from fastapi_users.password import PasswordHelper


class PasswordService:
    """密码领域服务

    处理密码的哈希和验证    """

    def __init__(self) -> None:
        self._helper = PasswordHelper()

    def hash(self, password: str) -> str:
        """哈希密码

        Args:
            password: 明文密码

        Returns:
            哈希后的密码
        """
        return self._helper.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        """验证密码

        Args:
            password: 明文密码
            hashed: 哈希后的密码

        Returns:
            密码是否正确
        """
        verified, _ = self._helper.verify_and_update(password, hashed)
        return verified
