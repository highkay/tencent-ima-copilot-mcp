# IMA Copilot MCP 服务器 (简化版)

基于 FastMCP v2 框架的腾讯 IMA Copilot MCP (Model Context Protocol) 服务器，**使用环境变量配置**，简化项目结构，专注于 MCP 协议实现。

## ✨ 主要特性

- 🚀 **简化架构**: 去掉独立的 Web 配置页面，通过环境变量进行配置
- 🤖 **MCP 协议支持**: 完整实现 Model Context Protocol 规范
- 🔧 **环境变量配置**: 通过 `.env` 文件管理所有配置，支持自动生成缺失参数
- 📡 **HTTP 传输**: 支持 HTTP 传输协议，便于 MCP Inspector 连接
- 🛠️ **丰富的 MCP 工具**: 提供腾讯 IMA 知识库问答功能
- 📊 **状态监控**: 实时监控服务器和认证状态
- 🎯 **一键启动**: 简化的启动流程，环境检查和自动配置

## 快速开始

### 1. 安装依赖

```bash
# 安装 FastMCP 和所有依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制配置文件模板
cp .env.example .env

# 编辑 .env 文件，填入从浏览器获取的 IMA 认证信息
nano .env  # 或使用其他编辑器
```

必需配置项：
- `IMA_COOKIES`: 从浏览器开发者工具获取的完整 cookies 字符串
- `IMA_X_IMA_COOKIE`: X-Ima-Cookie 请求头值
- `IMA_X_IMA_BKN`: X-Ima-Bkn 请求头值

### 3. 启动服务器

#### 方式一：使用启动脚本（推荐）

```bash
# Windows
start.bat

# 或使用 Python 脚本
python run.py
```

#### 方式二：使用 fastmcp 命令

```bash
# 使用环境变量配置
fastmcp run ima_server_simple.py:mcp --transport http --host 127.0.0.1 --port 8081
```

### 4. 使用 MCP Inspector

```bash
# 安装 MCP Inspector
npx @modelcontextprotocol/inspector

# 连接到服务器
# 在 Inspector 中输入: http://127.0.0.1:8081/mcp
```

### 服务端点

- **MCP 协议端点**: `http://127.0.0.1:8081/mcp`（用于 MCP Inspector）
- **配置检查**: 服务器启动时会自动验证环境变量配置

## 配置指南

### 获取 IMA 认证信息

1. 访问 [https://ima.qq.com](https://ima.qq.com)
2. 按 F12 打开开发者工具
3. 切换到 Network 标签页
4. 询问一个问题，找到向 `/cgi-bin/assistant/qa` 的 POST 请求
5. 复制 Request Headers 中的认证信息：
   - `Cookie` 字段完整内容 → `IMA_COOKIES`
   - `X-Ima-Cookie` 字段值 → `IMA_X_IMA_COOKIE`
   - `X-Ima-Bkn` 字段值 → `IMA_X_IMA_BKN`

### 环境变量配置示例

```bash
# .env 文件示例
IMA_COOKIES="sessionid=abc123; csrftoken=def456; pt2gguin=o123456;"
IMA_X_IMA_COOKIE="platform=1;client_version=1.0.0"
IMA_X_IMA_BKN="your_bkn_value_here"
IMA_MCP_PORT=8081
IMA_MCP_HOST=127.0.0.1
```

### 自动生成参数

- `IMA_CLIENT_ID`: 如果未设置，系统会自动生成 UUID
- `IMA_USKEY`: 如果未设置，系统会自动生成 32 字节随机字符串

## 可用的 MCP 工具

### 1. `ask`
向腾讯 IMA 知识库询问任何问题

**参数:**
- `question` (必需): 要询问的问题

**示例:**
```
问题: "什么是机器学习？"
问题: "如何制作番茄炒蛋？"
问题: "解释一下量子力学的基本原理"
```

IMA 是通用知识库，支持各种领域的问题，包括但不限于科学技术、生活常识、学习教育、文化历史等。

### 2. `ima_validate_config`
验证当前环境变量配置是否有效

**参数:** 无

**返回:** 配置验证结果，包含具体错误信息（如果有）

### 3. `ima_get_status`
获取 IMA 服务和配置状态

**参数:** 无

**返回:** 详细的服务状态，包括配置状态、环境变量状态等

## 可用的 MCP 资源

### 1. `ima://config`
获取当前配置信息（不包含敏感数据）

**内容:** 客户端ID、超时设置、重试次数等非敏感配置

### 2. `ima://status`
获取详细的服务状态

**内容:** 配置状态、环境变量设置情况、会话信息等

### 3. `ima://help`
获取帮助信息

**内容:** 完整的使用指南和配置说明

## 项目结构

```
tencent-ima-copilot-mcp/
├── ima_server_simple.py        # 🚀 简化的MCP服务器
├── run.py                      # 🎯 推荐启动脚本
├── start.bat                   # 🪟 Windows一键启动
├── requirements.txt            # 📦 Python依赖
├── .env.example                # ⚙️ 环境变量配置模板
├── src/                        # 🔧 核心源代码
│   ├── config.py               # 配置管理（环境变量版本）
│   ├── ima_client.py           # IMA API客户端
│   └── models.py               # 数据模型
├── test_refactored_functionality.py  # 🧪 功能测试脚本
├── USAGE_GUIDE.md              # 📖 详细使用指南
├── README.md                   # 📚 项目文档
├── CLAUDE.md                   # 🤖 AI辅助开发指导
└── pyproject.toml             # 📦 项目配置
```

## 配置选项

### 必需的环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `IMA_COOKIES` | 完整的 cookies 字符串 | `sessionid=abc123; csrftoken=def456;` |
| `IMA_X_IMA_COOKIE` | X-Ima-Cookie 请求头 | `platform=1;client_version=1.0.0` |
| `IMA_X_IMA_BKN` | X-Ima-Bkn 请求头 | `your_bkn_value` |

### 可选的环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `IMA_CLIENT_ID` | 客户端ID | 自动生成 UUID |
| `IMA_USKEY` | 设备唯一标识 | 自动生成 32 字节随机字符串 |
| `IMA_MCP_HOST` | MCP 服务器地址 | `127.0.0.1` |
| `IMA_MCP_PORT` | MCP 服务器端口 | `8081` |
| `IMA_MCP_DEBUG` | 调试模式 | `false` |
| `IMA_LOG_LEVEL` | 日志级别 | `INFO` |
| `IMA_REQUEST_TIMEOUT` | 请求超时时间（秒） | `30` |
| `IMA_RETRY_COUNT` | 重试次数 | `3` |
| `IMA_PROXY` | 代理设置 | 未设置 |

## 开发

### 运行测试

```bash
pytest
```

### 代码格式化

```bash
black src/
isort src/
```

### 类型检查

```bash
mypy src/
```

## 安全注意事项

- MCP 服务器默认只监听本地地址 (127.0.0.1)
- 敏感认证信息通过环境变量管理，请妥善保管 .env 文件
- 不要将 .env 文件提交到版本控制系统
- 在生产环境中请适当配置网络安全策略
- 定期更新认证信息以确保服务可用性

## 故障排除

### 常见问题

**Q: 环境变量配置错误怎么办？**
A: 检查 .env 文件中的必需配置项是否正确设置：
```bash
python run.py --check  # 仅检查配置，不启动服务
```

**Q: 端口被占用怎么办？**
A: 在 .env 文件中修改 `IMA_MCP_PORT` 为其他端口号

**Q: 认证失败怎么办？**
A: 检查 .env 文件中的认证信息是否正确，必要时重新从浏览器获取。

**Q: MCP Inspector 无法连接？**
A: 确保服务器正在运行，并使用正确的 URL 格式：`http://127.0.0.1:8081/mcp`

**Q: 支持哪些类型的问题？**
A: IMA 是通用知识库，支持各种领域的问题，包括但不限于科学技术、生活常识、学习教育、文化历史等。

**Q: 如何查看详细错误信息？**
A: 在 .env 文件中设置 `IMA_LOG_LEVEL=DEBUG` 启用详细日志

**Q: 如何验证配置是否正确？**
A: 使用 MCP Inspector 中的 `ima_validate_config` 工具进行验证

## 版本历史

### v0.4.0 (最新) - 简化版本
- 🚀 **架构简化**: 去掉独立的 Web 配置页面，改为环境变量配置
- 🔧 **配置简化**: 通过 .env 文件管理所有配置，支持自动生成缺失参数
- 📦 **打包简化**: 简化项目结构，减少依赖文件
- 🚀 **启动简化**: 一键启动脚本，自动环境检查
- 📚 **文档重构**: 详细的环境变量配置指南
- 🛠️ **工具增强**: 改进的配置验证和状态监控工具

### v0.3.0
- 🚀 **重大升级**: 采用 `FastMCP.from_fastapi()` 官方集成方式
- 🔧 **智能路由映射**: 通过 RouteMap 实现精确的路由转换控制
- 📋 **FastAPI 规范集成**: 自动将 FastAPI 路由转换为 MCP 资源

### v0.2.1
- 采用标准 fastmcp run 命令行启动方式
- 优化模块导出，支持 fastmcp CLI 工具

### v0.2.0
- 升级为标准 FastMCP 启动方式
- 统一服务器架构，单一服务提供 MCP 和 Web 界面

### v0.1.0
- 初始版本发布
- 实现基本的 MCP 服务器功能

## 贡献

欢迎提交 Issue 和 Pull Request！在提交前请确保：
1. 代码符合项目规范
2. 添加了必要的测试
3. 更新了相关文档

## 许可证

MIT License