"""
配置管理系统 - 基于环境变量的简化版本
"""
import logging
import os
import uuid
import base64
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from models import IMAConfig, IMAStatus

logger = logging.getLogger(__name__)


class AppConfig(BaseSettings):
    """应用配置 - 从环境变量读取"""
    # 服务配置
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8081
    mcp_debug: bool = False
    mcp_log_level: str = "INFO"
    mcp_log_file: Optional[str] = None
    mcp_secret_key: str = "default-secret-key-change-in-production"
    mcp_server_name: str = "ima-copilot"
    mcp_server_version: str = "0.2.0"

    # IMA API 配置
    api_endpoint: str = "https://ima.qq.com/cgi-bin/assistant/qa"
    request_timeout: int = 30
    retry_count: int = 3
    proxy: Optional[str] = None

    model_config = SettingsConfigDict(
        env_prefix="IMA_",
        env_file=".env",
        extra="ignore"  # 忽略额外的字段
    )

    @property
    def host(self) -> str:
        return self.mcp_host

    @property
    def port(self) -> int:
        return self.mcp_port

    @property
    def debug(self) -> bool:
        return self.mcp_debug

    @property
    def log_level(self) -> str:
        return self.mcp_log_level

    @property
    def log_file(self) -> Optional[str]:
        return self.mcp_log_file

    @property
    def secret_key(self) -> str:
        return self.mcp_secret_key


class IMAEnvironmentConfig(BaseSettings):
    """IMA 认证配置 - 从环境变量读取"""
    # IMA 认证信息
    cookies: str = ""
    x_ima_cookie: str = ""
    x_ima_bkn: str = ""
    knowledge_base_id: str = "7305806844290061"  # 默认值
    uskey: Optional[str] = None
    client_id: Optional[str] = None

    model_config = SettingsConfigDict(
        env_prefix="IMA_",
        env_file=".env",
        extra="ignore"  # 忽略额外的字段
    )


class ConfigManager:
    """简化的配置管理器 - 基于环境变量"""

    def __init__(self):
        self.app_config = AppConfig()
        self.env_config = IMAEnvironmentConfig()
        self._ima_config: Optional[IMAConfig] = None

    def _generate_missing_params(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """自动生成缺失的参数"""
        # 生成client_id（如果缺失）
        if not config_data.get('client_id'):
            config_data['client_id'] = str(uuid.uuid4())
            logger.info(f"Generated client_id: {config_data['client_id']}")

        # 生成uskey（如果缺失）
        if not config_data.get('uskey'):
            random_bytes = secrets.token_bytes(32)
            config_data['uskey'] = base64.b64encode(random_bytes).decode('utf-8')
            logger.info("Generated uskey: 32-byte random string")

        # 确保created_at存在
        if not config_data.get('created_at'):
            config_data['created_at'] = datetime.now()
            logger.info("Set created_at to current time")

        return config_data

    def load_config(self, auto_generate: bool = True) -> Optional[IMAConfig]:
        """从环境变量加载配置"""
        try:
            # 从环境变量获取配置数据
            config_data = {
                'cookies': self.env_config.cookies,
                'x_ima_cookie': self.env_config.x_ima_cookie,
                'x_ima_bkn': self.env_config.x_ima_bkn,
                'knowledge_base_id': self.env_config.knowledge_base_id,
                'uskey': self.env_config.uskey,
                'client_id': self.env_config.client_id,
                'timeout': self.app_config.request_timeout,
                'retry_count': self.app_config.retry_count,
                'proxy': self.app_config.proxy,
                'created_at': datetime.now()
            }

            # 自动生成缺失的参数
            if auto_generate:
                config_data = self._generate_missing_params(config_data)

            # 验证并创建配置对象
            self._ima_config = IMAConfig(**config_data)
            logger.info("Configuration loaded from environment variables successfully")
            return self._ima_config

        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading config: {e}")
            return None

    def get_config(self) -> Optional[IMAConfig]:
        """获取当前配置"""
        if self._ima_config is None:
            self._ima_config = self.load_config()
        return self._ima_config

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """验证环境变量配置"""
        # 只需要 X-Ima-Cookie 和 X-Ima-Bkn，COOKIES 是可选的
        required_fields = [
            (self.env_config.x_ima_cookie, "IMA_X_IMA_COOKIE"),
            (self.env_config.x_ima_bkn, "IMA_X_IMA_BKN")
        ]

        for value, name in required_fields:
            if not value or value.strip() == "":
                return False, f"Missing required environment variable: {name}"

        return True, None

    def get_config_status(self) -> IMAStatus:
        """获取配置状态"""
        status = IMAStatus()

        # 验证环境变量配置
        is_valid, error = self.validate_config()
        if is_valid:
            config = self.get_config()
            if config:
                status.is_configured = True
                status.session_info = {
                    'client_id': config.client_id,
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat() if config.updated_at else None,
                }
        else:
            status.error_message = error or "环境变量配置不完整"

        return status


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config() -> Optional[IMAConfig]:
    """获取全局配置"""
    return config_manager.get_config()


def get_app_config() -> AppConfig:
    """获取应用配置"""
    return config_manager.app_config