# IMA Copilot MCP 服务器

基于 FastMCP v2 框架的腾讯 IMA Copilot MCP (Model Context Protocol) 服务器，**使用环境变量配置**，简化项目结构，专注于 MCP 协议实现。

## ✨ 主要特性

- 🚀 **简化架构**: 采用环境变量配置，无需独立的 Web 配置页面
- 🤖 **MCP 协议支持**: 完整实现 Model Context Protocol 规范
- 🔧 **环境变量配置**: 通过 `.env` 文件管理所有配置，支持自动生成缺失参数
- 📡 **HTTP 传输**: 支持 HTTP 传输协议，便于 MCP Inspector 连接
- 🛠️ **丰富的 MCP 工具**: 提供腾讯 IMA 知识库问答功能
- 🔄 **Token 自动刷新**: 智能管理认证 token，自动刷新保持会话有效
- 📊 **状态监控**: 实时监控服务器和认证状态
- 📝 **详细日志系统**: 自动生成带时间戳的调试日志，支持原始 SSE 响应持久化
- ⏱️ **超时保护**: 内置请求超时机制（55 秒），防止长时间阻塞
- 🎯 **一键启动**: 简化的启动流程，自动环境检查和配置验证
- 🐳 **Docker 支持**: 提供官方 Docker 镜像，开箱即用

## 快速开始

### 方式一：使用 Docker（推荐）

#### 1. 使用 Docker Run

```bash
# 拉取镜像
docker pull highkay/tencent-ima-copilot-mcp:latest

# 运行容器（需要替换以下三个必需的环境变量）
docker run -d \
  --name ima-copilot-mcp \
  -p 8081:8081 \
  -e IMA_X_IMA_COOKIE="your_x_ima_cookie_here" \
  -e IMA_X_IMA_BKN="your_x_ima_bkn_here" \
  -e IMA_KNOWLEDGE_BASE_ID="your_knowledge_base_id_here" \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  highkay/tencent-ima-copilot-mcp:latest

# 查看日志
docker logs -f ima-copilot-mcp

# 停止容器
docker stop ima-copilot-mcp

# 启动容器
docker start ima-copilot-mcp
```

#### 2. 使用 Docker Compose（更便捷）

创建 `.env` 文件（或直接在 shell 中设置环境变量）：

```bash
# .env 文件
IMA_X_IMA_COOKIE="your_x_ima_cookie_here"
IMA_X_IMA_BKN="your_x_ima_bkn_here"
IMA_KNOWLEDGE_BASE_ID="your_knowledge_base_id_here"

# 可选配置
IMA_MCP_LOG_LEVEL=INFO
IMA_REQUEST_TIMEOUT=30
```

启动服务：

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 重启服务
docker-compose restart
```

#### 3. 获取认证信息

按照下面的**获取 IMA 认证信息**部分的步骤，从浏览器获取三个必需的环境变量：
- `IMA_X_IMA_COOKIE`
- `IMA_X_IMA_BKN`
- `IMA_KNOWLEDGE_BASE_ID`

#### 4. 连接到服务

使用 MCP Inspector 连接：

```bash
npx @modelcontextprotocol/inspector
# 连接地址: http://localhost:8081/mcp
```

### 方式二：本地安装

#### 1. 安装依赖

```bash
# 安装 FastMCP 和所有依赖
pip install -r requirements.txt
```

#### 2. 配置环境变量

```bash
# 复制配置文件模板
cp .env.example .env

# 编辑 .env 文件，填入从浏览器获取的 IMA 认证信息
nano .env  # 或使用其他编辑器
```

#### 必需配置项

以下环境变量必须正确配置才能使用服务：

- **`IMA_X_IMA_COOKIE`**: X-Ima-Cookie 请求头值（包含平台信息、token 等）
- **`IMA_X_IMA_BKN`**: X-Ima-Bkn 请求头值（业务密钥）
- **`IMA_KNOWLEDGE_BASE_ID`**: 知识库 ID（从 init_session 请求中获取）

#### 可选配置项

- **`IMA_COOKIES`**: 完整的 cookies 字符串（可选，用于增强认证）
- **`IMA_CLIENT_ID`**: 客户端 ID（未设置时自动生成 UUID）
- **`IMA_USKEY`**: 设备唯一标识（未设置时自动生成 32 字节随机字符串）

#### 3. 获取 IMA 认证信息

#### 步骤 1: 访问 IMA Copilot

1. 访问 [https://ima.qq.com](https://ima.qq.com)
2. 按 F12 打开开发者工具
3. 切换到 **Network** (网络) 标签页
4. 在筛选框中输入 `assistant`

#### 步骤 2: 获取知识库 ID

1. 在 IMA 页面中选择你要使用的知识库
2. 在网络请求中找到 `init_session` 请求
3. 查看请求 Payload，复制 `knowledgeBaseInfoWithFolder.knowledge_base_id` 的值
4. 将此值设置为 `IMA_KNOWLEDGE_BASE_ID` 环境变量

#### 步骤 3: 获取认证头信息

1. 在 IMA 中询问一个问题
2. 找到向 `/cgi-bin/assistant/qa` 的 POST 请求
3. 查看 **Request Headers**，复制以下字段：
   - `X-Ima-Cookie` → `IMA_X_IMA_COOKIE`
   - `X-Ima-Bkn` → `IMA_X_IMA_BKN`
   - `Cookie` → `IMA_COOKIES`（可选）

#### 4. 启动服务器

##### 方式一：使用启动脚本（推荐）

```bash
# Windows
start.bat

# 或使用 Python 脚本（跨平台）
python run.py
```

启动脚本会自动：
- 检查 Python 和 fastmcp 是否安装
- 验证 .env 文件是否存在
- 检查必需的环境变量
- 生成调试日志文件
- 启动 MCP 服务器

##### 方式二：使用 fastmcp 命令

```bash
fastmcp run ima_server_simple.py:mcp --transport http --host 127.0.0.1 --port 8081
```

##### 方式三：仅验证配置

```bash
# 只检查配置，不启动服务器
python run.py --check
```

#### 5. 使用 MCP Inspector

```bash
# 安装 MCP Inspector
npx @modelcontextprotocol/inspector

# 连接到服务器
# 在 Inspector 中输入: http://127.0.0.1:8081/mcp
```

### 服务端点

- **MCP 协议端点**: `http://127.0.0.1:8081/mcp`（用于 MCP Inspector 或其他 MCP 客户端）
- **日志文件**: `logs/debug/ima_server_YYYYMMDD_HHMMSS.log`（自动生成）
- **原始 SSE 日志**: `logs/debug/raw/sse_*.log`（发生错误时自动保存）

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

**特性:**
- 自动管理会话，无需手动创建
- 智能 token 刷新，确保认证有效
- 55 秒超时保护，防止长时间等待
- 详细错误信息，便于问题诊断

IMA 是通用知识库，支持各种领域的问题，包括但不限于科学技术、生活常识、学习教育、文化历史等。

### 2. `ima_validate_config`

验证当前环境变量配置是否有效

**参数:** 无

**返回:** 配置验证结果，包含具体错误信息（如果有）

### 3. `ima_get_status`

获取 IMA 服务和配置状态

**参数:** 无

**返回:** 详细的服务状态，包括：
- 配置状态（是否已配置）
- 环境变量状态（各项配置是否设置）
- 会话信息（客户端 ID、创建时间等）
- 错误信息（如果有）

## 可用的 MCP 资源

### 1. `ima://config`

获取当前配置信息（不包含敏感数据）

**内容:**
- 客户端 ID
- 请求超时设置
- 重试次数
- 代理设置
- 配置创建/更新时间

### 2. `ima://status`

获取详细的服务状态

**内容:**
- 配置状态
- 环境变量设置情况
- 会话信息
- 错误信息（如果有）

### 3. `ima://help`

获取帮助信息

**内容:** 完整的使用指南和配置说明

## 项目结构

```
tencent-ima-copilot-mcp/
├── ima_server_simple.py        # 🚀 MCP 服务器主文件
├── run.py                      # 🎯 推荐启动脚本（环境检查 + 启动）
├── start.bat                   # 🪟 Windows 一键启动脚本
├── requirements.txt            # 📦 Python 依赖
├── pyproject.toml             # 📦 项目配置和元数据
├── .env.example                # ⚙️ 环境变量配置模板
├── .env                        # 🔐 环境变量配置（需自行创建）
├── src/                        # 🔧 核心源代码
│   ├── config.py               # 配置管理（基于环境变量）
│   ├── ima_client.py           # IMA API 客户端（会话管理、token 刷新）
│   └── models.py               # 数据模型（Pydantic 模型）
├── logs/                       # 📝 日志目录（自动生成）
│   └── debug/                  # 调试日志
│       ├── ima_server_*.log    # 服务器运行日志
│       ├── ima_debug_*.log     # run.py 启动日志
│       └── raw/                # 原始 SSE 响应（错误时保存）
├── CLAUDE.md                   # 🤖 AI 辅助开发指导
└── README.md                   # 📚 项目文档（本文件）
```

## 配置选项

### 必需的环境变量

| 变量名 | 说明 | 获取方式 |
|--------|------|---------|
| `IMA_X_IMA_COOKIE` | X-Ima-Cookie 请求头 | 从浏览器开发者工具的 Network 标签中复制 |
| `IMA_X_IMA_BKN` | X-Ima-Bkn 请求头 | 从浏览器开发者工具的 Network 标签中复制 |
| `IMA_KNOWLEDGE_BASE_ID` | 知识库 ID | 从 init_session 请求的 Payload 中获取 |

### 可选的环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `IMA_COOKIES` | 完整的 cookies 字符串 | 未设置（可选，用于增强认证） |
| `IMA_CLIENT_ID` | 客户端 ID | 自动生成 UUID |
| `IMA_USKEY` | 设备唯一标识 | 自动生成 32 字节随机字符串 |
| `IMA_MCP_HOST` | MCP 服务器地址 | `127.0.0.1` |
| `IMA_MCP_PORT` | MCP 服务器端口 | `8081` |
| `IMA_MCP_DEBUG` | 调试模式 | `false` |
| `IMA_MCP_LOG_LEVEL` | 日志级别 | `INFO` |
| `IMA_REQUEST_TIMEOUT` | 请求超时时间（秒） | `30` |
| `IMA_RETRY_COUNT` | 重试次数 | `3` |
| `IMA_PROXY` | 代理设置 | 未设置 |

### 环境变量配置示例

```bash
# .env 文件示例

# ===== 必需配置 =====
IMA_X_IMA_COOKIE="PLATFORM=H5; CLIENT-TYPE=256053; WEB-VERSION=999.999.999; IMA-GUID=guid-xxx; IMA-TOKEN=xxx; IMA-REFRESH-TOKEN=xxx; UID-TYPE=2; TOKEN-TYPE=14"
IMA_X_IMA_BKN="1842948893"
IMA_KNOWLEDGE_BASE_ID="7305806844290061"

# ===== 可选配置 =====
# IMA_COOKIES="RK=xxx; ptcz=xxx; pac_uid=xxx; uin=xxx; skey=xxx"
# IMA_CLIENT_ID="your-custom-client-id"
# IMA_USKEY="your-custom-uskey"

# ===== 服务器配置 =====
IMA_MCP_HOST=127.0.0.1
IMA_MCP_PORT=8081
IMA_MCP_LOG_LEVEL=INFO
```

## 核心功能详解

### Token 自动刷新

客户端会自动管理认证 token：
- 首次请求前自动刷新 token（10 秒超时）
- 从 `X-Ima-Cookie` 中提取 `IMA-REFRESH-TOKEN` 和用户 ID
- 调用 `/cgi-bin/auth_login/refresh` 端点刷新 token
- 更新配置中的 `current_token` 和 `token_valid_time`
- Token 刷新失败时返回友好的错误信息

### 会话管理

自动管理 IMA 会话：
- 首次请求时调用 `/cgi-bin/session_logic/init_session` 创建会话
- 会话 ID 在客户端生命周期内保持不变
- 支持多轮对话（通过 `history_info` 参数）

### 详细日志系统

提供多层次的日志记录：
- **服务器日志**: `logs/debug/ima_server_*.log` - 包含所有请求和响应的详细信息
- **启动日志**: `logs/debug/ima_debug_*.log` - 记录启动过程的详细信息
- **原始 SSE 日志**: `logs/debug/raw/sse_*.log` - 发生错误时保存原始 SSE 响应，便于排查问题
- **日志级别**: 可通过 `IMA_MCP_LOG_LEVEL` 环境变量调整（DEBUG/INFO/WARNING/ERROR）

### 超时保护

多层次的超时保护机制：
- **Token 刷新超时**: 10 秒
- **问答请求超时**: 55 秒（为 MCP 协议的 60 秒超时预留缓冲）
- **HTTP 请求超时**: 可通过 `IMA_REQUEST_TIMEOUT` 配置（默认 30 秒）

## 开发

### 运行测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 运行测试并生成覆盖率报告
pytest --cov=src --cov-report=html
```

### 代码格式化

```bash
# 格式化代码
black src/ *.py

# 排序导入
isort src/ *.py

# 同时运行
black src/ *.py && isort src/ *.py
```

### 类型检查

```bash
mypy src/
```

### 调试模式

启用详细的调试日志：

```bash
# 在 .env 文件中设置
IMA_MCP_LOG_LEVEL=DEBUG

# 或设置环境变量
export IMA_MCP_LOG_LEVEL=DEBUG  # Linux/Mac
set IMA_MCP_LOG_LEVEL=DEBUG     # Windows
```

### Docker 镜像构建

#### 本地构建镜像

```bash
# 构建镜像
docker build -t highkay/tencent-ima-copilot-mcp:latest .

# 构建多平台镜像（需要 buildx）
docker buildx build --platform linux/amd64,linux/arm64 \
  -t highkay/tencent-ima-copilot-mcp:latest .

# 测试镜像
docker run --rm \
  -e IMA_X_IMA_COOKIE="your_cookie" \
  -e IMA_X_IMA_BKN="your_bkn" \
  -e IMA_KNOWLEDGE_BASE_ID="your_kb_id" \
  -p 8081:8081 \
  highkay/tencent-ima-copilot-mcp:latest
```

#### GitHub Actions 自动发布

本项目配置了 GitHub Actions，可以自动构建和发布 Docker 镜像：

- **触发条件**:
  - Push 到 `main` 分支 → 生成 `latest` 标签
  - 创建 Git tag（如 `v1.0.0`）→ 生成版本标签（`1.0.0`, `1.0`, `1`）
  - Pull Request → 仅构建，不推送

- **镜像平台**: `linux/amd64`, `linux/arm64`

- **所需 Secrets**:
  - `DOCKER_USERNAME`: Docker Hub 用户名
  - `DOCKER_PASSWORD`: Docker Hub 访问令牌（Access Token）

在 GitHub 仓库设置中添加这两个 Secrets，即可启用自动发布。

## 安全注意事项

- ⚠️ **本地访问**: MCP 服务器默认只监听本地地址 (127.0.0.1)，不暴露到公网
- 🔐 **敏感信息保护**: 认证信息通过环境变量管理，请妥善保管 `.env` 文件
- 🚫 **版本控制**: 不要将 `.env` 文件提交到版本控制系统（已在 `.gitignore` 中配置）
- 🔄 **定期更新**: 定期从浏览器重新获取认证信息以确保服务可用性
- 🌐 **网络安全**: 在生产环境中请适当配置网络安全策略
- 📝 **日志安全**: 日志文件可能包含敏感信息，请妥善保管

## 故障排除

### 常见问题

**Q: 环境变量配置错误怎么办？**

A: 使用配置检查命令验证：
```bash
python run.py --check
```
或在 MCP Inspector 中使用 `ima_validate_config` 工具。

**Q: 端口被占用怎么办？**

A: 在 `.env` 文件中修改 `IMA_MCP_PORT` 为其他端口号：
```bash
IMA_MCP_PORT=8082
```

**Q: 认证失败（Token 验证失败）怎么办？**

A:
1. 检查 `.env` 文件中的 `IMA_X_IMA_COOKIE` 和 `IMA_X_IMA_BKN` 是否正确
2. 确认 `IMA_X_IMA_COOKIE` 中包含 `IMA-REFRESH-TOKEN` 字段
3. 重新从浏览器获取最新的认证信息
4. 查看日志文件 `logs/debug/ima_server_*.log` 了解详细错误

**Q: MCP Inspector 无法连接？**

A:
1. 确保服务器正在运行（查看控制台输出）
2. 使用正确的 URL 格式：`http://127.0.0.1:8081/mcp`
3. 检查防火墙是否阻止了连接
4. 尝试使用 `curl` 测试连接：
   ```bash
   curl http://127.0.0.1:8081/mcp
   ```

**Q: 请求超时怎么办？**

A:
1. 检查网络连接是否正常
2. 尝试增加超时时间（在 `.env` 中设置 `IMA_REQUEST_TIMEOUT=60`）
3. 简化问题内容
4. 查看日志文件了解详细错误信息

**Q: 支持哪些类型的问题？**

A: IMA 是通用知识库，支持各种领域的问题，包括但不限于：
- 科学技术
- 生活常识
- 学习教育
- 文化历史
- 健康医疗
- 法律咨询
- 等等

**Q: 如何查看详细错误信息？**

A:
1. 启用调试日志：在 `.env` 文件中设置 `IMA_MCP_LOG_LEVEL=DEBUG`
2. 查看服务器日志：`logs/debug/ima_server_*.log`
3. 查看原始 SSE 响应：`logs/debug/raw/sse_*.log`（发生错误时自动生成）

**Q: 如何获取知识库 ID？**

A:
1. 访问 [https://ima.qq.com](https://ima.qq.com)
2. 按 F12 打开开发者工具，切换到 Network 标签
3. 在 IMA 中选择要使用的知识库
4. 找到 `init_session` 请求
5. 查看 Payload 中的 `knowledgeBaseInfoWithFolder.knowledge_base_id`

**Q: 服务器启动后没有响应？**

A:
1. 检查是否正确配置了必需的环境变量
2. 查看控制台输出的错误信息
3. 使用 `ima_get_status` 工具检查服务状态
4. 查看日志文件了解详细信息

## 版本历史

### v0.5.0 (当前) - 增强版本
- 🔄 **Token 自动刷新**: 智能管理认证 token，自动刷新保持会话有效
- 📝 **详细日志系统**: 带时间戳的调试日志，原始 SSE 响应持久化
- ⏱️ **超时保护**: 多层次超时机制（token 刷新 10s、问答 55s）
- 🔧 **会话管理**: 自动创建和管理 IMA 会话
- 📊 **错误诊断**: 友好的错误信息，详细的堆栈跟踪
- 🚀 **启动优化**: 完善的环境检查和配置验证

### v0.4.0 - 简化版本
- 🚀 **架构简化**: 去掉独立的 Web 配置页面，改为环境变量配置
- 🔧 **配置简化**: 通过 `.env` 文件管理所有配置，支持自动生成缺失参数
- 📦 **打包简化**: 简化项目结构，减少依赖文件
- 🚀 **启动简化**: 一键启动脚本，自动环境检查
- 📚 **文档重构**: 详细的环境变量配置指南
- 🛠️ **工具增强**: 改进的配置验证和状态监控工具

### v0.3.0
- 🚀 **重大升级**: 采用 `FastMCP.from_fastapi()` 官方集成方式
- 🔧 **智能路由映射**: 通过 RouteMap 实现精确的路由转换控制
- 📋 **FastAPI 规范集成**: 自动将 FastAPI 路由转换为 MCP 资源

### v0.2.1
- 采用标准 `fastmcp run` 命令行启动方式
- 优化模块导出，支持 fastmcp CLI 工具

### v0.2.0
- 升级为标准 FastMCP 启动方式
- 统一服务器架构，单一服务提供 MCP 和 Web 界面

### v0.1.0
- 初始版本发布
- 实现基本的 MCP 服务器功能

## 技术栈

- **Python**: 3.9+
- **MCP 框架**: FastMCP v2.11+
- **Web 框架**: FastAPI v0.115+
- **HTTP 服务器**: Uvicorn
- **HTTP 客户端**: aiohttp
- **数据验证**: Pydantic v2.10+
- **配置管理**: pydantic-settings
- **异步 I/O**: asyncio, aiofiles

## 贡献

欢迎提交 Issue 和 Pull Request！在提交前请确保：

1. ✅ 代码符合项目规范（使用 black 和 isort 格式化）
2. ✅ 通过所有测试（`pytest`）
3. ✅ 通过类型检查（`mypy src/`）
4. ✅ 添加了必要的测试
5. ✅ 更新了相关文档

## 许可证

MIT License
