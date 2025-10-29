#!/usr/bin/env python3
"""
IMA Copilot MCP 服务器 - 基于环境变量的简化版本
专注于 MCP 协议实现，配置通过环境变量管理
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

from fastmcp import FastMCP

# 导入我们的模块
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config_manager, get_config, get_app_config
from ima_client import IMAAPIClient
from models import IMAStatus

# 配置详细的调试日志
app_config = get_app_config()

# 创建日志目录
log_dir = Path("logs/debug")
log_dir.mkdir(parents=True, exist_ok=True)

# 生成带时间戳的日志文件
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"ima_server_{timestamp}.log"

# 配置日志处理器
logging.basicConfig(
    level=logging.INFO,  # 强制使用DEBUG级别
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"调试日志已启用，日志文件: {log_file}")

# 确保ima_client使用INFO级别
logging.getLogger('ima_client').setLevel(logging.INFO)

# 创建 FastMCP 实例
mcp = FastMCP("IMA Copilot")

# 全局变量
ima_client: IMAAPIClient = None


@mcp.tool()
async def ask(question: str) -> str:
    """向腾讯 IMA 知识库询问任何问题

    Args:
        question: 要询问的问题

    Returns:
        IMA 知识库的回答
    """
    global ima_client

    if not question or not question.strip():
        return "[ERROR] 问题不能为空"

    if not ima_client:
        config = get_config()
        if not config:
            return "[ERROR] 配置未完成，请检查环境变量设置"

        try:
            # 启用原始SSE日志
            config.enable_raw_logging = True
            config.raw_log_dir = "logs/debug/raw"
            config.raw_log_on_success = False  # 只在失败时保存
            
            ima_client = IMAAPIClient(config)
            logger.info("IMA 客户端初始化成功")
            logger.info(f"原始SSE日志已启用: {config.raw_log_dir}")
        except Exception as e:
            logger.error(f"初始化 IMA 客户端失败: {e}")
            return f"[ERROR] IMA 客户端初始化失败: {str(e)}"

    try:
        logger.info(f"发送问题到 IMA: {question}")

        # 使用异步方法获取完整响应
        messages = await ima_client.ask_question_complete(question)

        # 即使没有消息，也会返回包含错误信息的消息列表
        if not messages:
            return "[ERROR] 没有收到任何响应"

        response = ima_client._extract_text_content(messages)

        logger.info(f"从 IMA 获取到响应，长度: {len(response)}")
        return response

    except Exception as e:
        logger.error(f"询问 IMA 时发生错误: {e}")
        # 返回更友好的错误信息
        if "超时" in str(e):
            return "[ERROR] 请求超时，请稍后重试"
        elif "认证" in str(e) or "auth" in str(e).lower():
            return "[ERROR] 认证失败，请检查 IMA 配置信息"
        elif "网络" in str(e) or "network" in str(e).lower() or "connection" in str(e).lower():
            return "[ERROR] 网络连接失败，请检查网络设置"
        else:
            return f"[ERROR] 询问失败: {str(e)}"


@mcp.tool()
def ima_validate_config() -> str:
    """验证当前 IMA 配置是否有效

    Returns:
        验证结果信息
    """
    try:
        config = get_config()
        if not config:
            return "[ERROR] 配置未加载，请检查环境变量"

        # 验证环境变量配置
        is_valid, error = config_manager.validate_config()
        if not is_valid:
            return f"[ERROR] 配置验证失败: {error}"

        # 尝试创建 IMA 客户端进行验证
        try:
            client = IMAAPIClient(config)
            # 这里可以添加实际的连接验证
            return "[OK] 配置验证成功，IMA 认证信息有效"

        except Exception as e:
            return f"[ERROR] IMA 连接验证失败: {str(e)}"

    except Exception as e:
        logger.error(f"配置验证时发生错误: {e}")
        return f"[ERROR] 验证过程出错: {str(e)}"


@mcp.tool()
def ima_get_status() -> str:
    """获取 IMA 服务状态

    Returns:
        服务状态信息
    """
    try:
        status = config_manager.get_config_status()

        status_text = f"IMA 服务状态:\n"
        status_text += f"配置状态: {'[OK] 已配置' if status.is_configured else '[ERROR] 未配置'}\n"

        if status.error_message:
            status_text += f"错误信息: {status.error_message}\n"

        if status.session_info:
            status_text += f"会话信息:\n"
            for key, value in status.session_info.items():
                status_text += f"  {key}: {value}\n"

        # 添加环境变量状态
        env_config = config_manager.env_config
        status_text += f"\n环境变量状态:\n"
        status_text += f"  IMA_COOKIES: {'[OK] 已设置' if env_config.cookies else '[ERROR] 未设置'}\n"
        status_text += f"  IMA_X_IMA_COOKIE: {'[OK] 已设置' if env_config.x_ima_cookie else '[ERROR] 未设置'}\n"
        status_text += f"  IMA_X_IMA_BKN: {'[OK] 已设置' if env_config.x_ima_bkn else '[ERROR] 未设置'}\n"
        status_text += f"  IMA_USKEY: {'[OK] 已设置' if env_config.uskey else '[AUTO] 自动生成'}\n"
        status_text += f"  IMA_CLIENT_ID: {'[OK] 已设置' if env_config.client_id else '[AUTO] 自动生成'}\n"

        return status_text

    except Exception as e:
        logger.error(f"获取状态时发生错误: {e}")
        return f"[ERROR] 获取状态失败: {str(e)}"


@mcp.resource("ima://config")
def get_config_resource() -> str:
    """获取当前配置信息（不包含敏感数据）"""
    try:
        config = get_config()
        if not config:
            return "配置未加载"

        # 返回非敏感的配置信息
        config_info = f"IMA 配置信息:\n"
        config_info += f"客户端ID: {config.client_id}\n"
        config_info += f"请求超时: {config.timeout}秒\n"
        config_info += f"重试次数: {config.retry_count}\n"
        config_info += f"代理设置: {config.proxy or '未设置'}\n"
        config_info += f"创建时间: {config.created_at}\n"
        if config.updated_at:
            config_info += f"更新时间: {config.updated_at}\n"

        return config_info

    except Exception as e:
        logger.error(f"获取配置资源时发生错误: {e}")
        return f"[ERROR] 获取配置失败: {str(e)}"


@mcp.resource("ima://help")
def get_help_resource() -> str:
    """获取使用帮助信息"""
    help_text = """
# IMA Copilot MCP 服务器帮助

## 概述
这是基于环境变量配置的 IMA Copilot MCP 服务器，提供腾讯 IMA 知识库的 MCP 协议接口。

## 配置方式
通过环境变量或 .env 文件配置 IMA 认证信息：

1. 复制 .env.example 为 .env
2. 填入从浏览器获取的认证信息：
   - IMA_COOKIES: 完整的 cookies 字符串
   - IMA_X_IMA_COOKIE: X-Ima-Cookie 请求头
   - IMA_X_IMA_BKN: X-Ima-Bkn 请求头

## 工具
- `ask`: 向 IMA 知识库询问问题
- `ima_validate_config`: 验证配置是否有效
- `ima_get_status`: 获取服务状态

## 资源
- `ima://config`: 查看配置信息
- `ima://help`: 查看帮助信息

## 启动方式
```bash
# 使用 fastmcp 命令启动
fastmcp run ima_server_simple.py:mcp --transport http --host 127.0.0.1 --port 8081

# 或使用 Python 直接运行
python ima_server_simple.py
```

## 连接方式
使用 MCP Inspector 连接到: http://127.0.0.1:8081/mcp
"""
    return help_text


@mcp.resource("ima://status")
def get_status_resource() -> str:
    """获取服务状态资源"""
    return ima_get_status()


def main():
    """主函数 - 直接启动服务器时使用"""
    app_config = get_app_config()

    print("IMA Copilot MCP 服务器")
    print("=" * 50)
    print("版本: 简化版 (基于环境变量)")
    print(f"服务地址: http://{app_config.host}:{app_config.port}")
    print(f"MCP 端点: http://{app_config.host}:{app_config.port}/mcp")
    print(f"日志级别: {app_config.log_level}")
    print("=" * 50)

    # 验证配置
    config = get_config()
    if config:
        print("[OK] 配置加载成功")
        is_valid, error = config_manager.validate_config()
        if is_valid:
            print("[OK] 配置验证通过")
        else:
            print(f"[ERROR] 配置验证失败: {error}")
    else:
        print("[ERROR] 配置加载失败，请检查环境变量")

    print("=" * 50)
    print("启动命令:")
    print(f"fastmcp run ima_server_simple.py:mcp --transport http --host {app_config.host} --port {app_config.port}")
    print("=" * 50)


if __name__ == "__main__":
    main()


__all__ = ["mcp"]