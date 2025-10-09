#!/usr/bin/env python3
"""
IMA Copilot MCP 服务器启动脚本
基于环境变量的简化启动方式
"""

import sys
import os
import subprocess
from pathlib import Path

# 设置控制台编码
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def check_env_file():
    """检查 .env 文件是否存在"""
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ 未找到 .env 配置文件")
        print("请复制 .env.example 为 .env 并配置相应的环境变量")
        print("\n配置步骤:")
        print("1. cp .env.example .env")
        print("2. 编辑 .env 文件，填入 IMA 认证信息")
        print("3. 重新运行此脚本")
        return False

    print("✅ 找到 .env 配置文件")
    return True

def check_required_env_vars():
    """检查必需的环境变量"""
    try:
        # 导入配置类来加载 .env 文件
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from config import IMAEnvironmentConfig

        # 创建配置实例，这会自动加载 .env 文件
        env_config = IMAEnvironmentConfig()

        # 检查必需的配置
        missing_configs = []
        if not env_config.cookies or env_config.cookies.strip() == "":
            missing_configs.append("IMA_COOKIES")
        if not env_config.x_ima_cookie or env_config.x_ima_cookie.strip() == "":
            missing_configs.append("IMA_X_IMA_COOKIE")
        if not env_config.x_ima_bkn or env_config.x_ima_bkn.strip() == "":
            missing_configs.append("IMA_X_IMA_BKN")

        if missing_configs:
            print("❌ 以下必需的环境变量未正确配置:")
            for var in missing_configs:
                print(f"   - {var}")
            print("\n请在 .env 文件中配置这些变量")
            return False

        print("✅ 必需的环境变量已配置")
        return True

    except Exception as e:
        print(f"❌ 配置检查失败: {e}")
        return False

def show_startup_info():
    """显示启动信息"""
    host = os.getenv("IMA_MCP_HOST", "127.0.0.1")
    port = os.getenv("IMA_MCP_PORT", "8081")

    print("\n" + "=" * 60)
    print("🚀 IMA Copilot MCP 服务器")
    print("=" * 60)
    print("版本: 简化版 (基于环境变量)")
    print(f"服务地址: http://{host}:{port}")
    print(f"MCP 端点: http://{host}:{port}/mcp")
    print("=" * 60)
    print("\n📋 可用工具:")
    print("   • ask: 向 IMA 知识库询问问题")
    print("   • ima_validate_config: 验证配置")
    print("   • ima_get_status: 获取状态")
    print("\n📚 可用资源:")
    print("   • ima://config: 配置信息")
    print("   • ima://help: 帮助信息")
    print("   • ima://status: 服务状态")
    print("\n🔗 连接方式:")
    print("   MCP Inspector: http://{host}:{port}/mcp")
    print("=" * 60)

def start_with_fastmcp():
    """使用 fastmcp 命令启动"""
    host = os.getenv("IMA_MCP_HOST", "127.0.0.1")
    port = os.getenv("IMA_MCP_PORT", "8081")

    cmd = [
        "fastmcp", "run",
        "ima_server_simple.py:mcp",
        "--transport", "http",
        "--host", host,
        "--port", port
    ]

    print(f"启动命令: {' '.join(cmd)}")
    print("\n按 Ctrl+C 停止服务器")
    print("=" * 60)

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 启动失败: {e}")
        return False
    except FileNotFoundError:
        print("\n❌ 未找到 fastmcp 命令")
        print("请安装 fastmcp: pip install fastmcp")
        return False

    return True

def start_directly():
    """直接启动 Python 脚本"""
    print("直接启动 Python 脚本...")
    print("注意: 这种方式主要用于测试，建议使用 fastmcp 命令")
    print("\n按 Ctrl+C 停止服务器")
    print("=" * 60)

    try:
        # 导入并运行服务器
        from ima_server_simple import mcp
        print("✅ MCP 服务器模块加载成功")
        print("请使用 fastmcp 命令启动实际的 HTTP 服务")
        return True
    except Exception as e:
        print(f"❌ 模块加载失败: {e}")
        return False

def main():
    """主启动函数"""
    print("IMA Copilot MCP 服务器启动检查")
    print("=" * 40)

    # 检查配置文件
    if not check_env_file():
        sys.exit(1)

    # 检查环境变量
    if not check_required_env_vars():
        sys.exit(1)

    # 显示启动信息
    show_startup_info()

    # 根据命令行参数选择启动方式
    if len(sys.argv) > 1:
        if sys.argv[1] == "--direct":
            start_directly()
        elif sys.argv[1] == "--check":
            print("✅ 配置检查完成，所有必需项都已设置")
        else:
            print(f"未知参数: {sys.argv[1]}")
            print("可用参数: --direct, --check")
    else:
        # 默认使用 fastmcp 启动
        start_with_fastmcp()

if __name__ == "__main__":
    main()