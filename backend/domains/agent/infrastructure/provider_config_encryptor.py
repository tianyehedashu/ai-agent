"""
Provider Config Encryptor - 用户提供商配置加解密

使用与 API Key 相同的派生密钥对用户配置的 LLM API Key 进行加密存储。
实现 LLMKeyService 所需的 EncryptorProtocol。
"""

from bootstrap.config import settings
from domains.agent.application.llm_key_service import EncryptorProtocol
from domains.identity.domain.services.api_key_service import ApiKeyGenerator


class ProviderConfigEncryptor:
    """用户提供商配置加解密器"""

    def __init__(self) -> None:
        secret = settings.secret_key.get_secret_value()
        self._encryption_key = ApiKeyGenerator.derive_encryption_key(secret)
        self._generator = ApiKeyGenerator(encryption_key=self._encryption_key)

    def encrypt(self, plaintext: str) -> str:
        """加密明文 API Key"""
        return self._generator.encrypt_key(plaintext, self._encryption_key)

    def decrypt(self, ciphertext: str) -> str:
        """解密密文 API Key"""
        return self._generator.decrypt_key(ciphertext, self._encryption_key)


def get_provider_config_encryptor() -> EncryptorProtocol:
    """获取提供商配置加解密器（用于依赖注入）"""
    return ProviderConfigEncryptor()
