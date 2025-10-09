# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

腾讯 IMA Copilot MCP 服务器是一个基于 fastmcp v2 的 Model Context Protocol 应用，**使用环境变量配置**，将腾讯 IMA Copilot 的 Web 版本功能封装为 MCP 服务，提供通用知识库问答功能。

## 技术架构 (简化版)

### 核心框架
- **fastmcp v2.11+**: 使用最新版本的 fastmcp 框架
- **环境变量配置**: 通过 .env 文件管理所有配置
- **FastMCP**: 直接创建 MCP 服务器，无需 FastAPI 集成
- **SSE (Server-Sent Events)**: 实现实时响应流

### 简化架构

项目采用**简化的单服务架构**，通过环境变量进行配置：

```
┌─────────────────────────────────────┐
│        IMA Copilot MCP 服务器        │
│                                     │
│  ┌─────────────────────────────┐    │
│  │      FastMCP 实例           │    │
│  │  - ask 工具                 │    │
│  │  - 配置验证工具             │    │
│  │  - 状态监控工具             │    │
│  │  - 帮助和状态资源           │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │     配置管理 (环境变量)      │    │
│  │  - .env 文件读取            │    │
│  │  - 自动生成缺失参数         │    │
│  │  - 配置验证                 │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │      IMA API 客户端         │    │
│  │  - 认证管理                 │    │
│  │  - 请求代理                 │    │
│  │  - 响应流处理               │    │
│  └─────────────────────────────┘    │
│                                     │
│  端口: 8081/mcp                      │
└─────────────────────────────────────┘
```

### 架构优势

1. **简化部署**: 单一服务，无需配置页面服务器
2. **环境变量配置**: 标准 12-factor 应用配置方式
3. **自动化配置**: 自动生成缺失的参数（client_id、uskey）
4. **易于维护**: 去掉复杂的 Web 界面和加密存储逻辑
5. **容器友好**: 环境变量配置方式天然适合容器化部署
5. **容器友好**: 环境变量配置方式天然适合容器化部署

## 项目结构

```
tencent-ima-copilot-mcp/
├── .env.example                # 环境变量配置模板
├── src/                        # 核心源代码
│   ├── config.py               # 简化的配置管理（基于环境变量）
│   ├── ima_client.py           # IMA API 客户端
│   └── models.py               # 数据模型
├── ima_server_simple.py        # 简化的 MCP 服务器
├── run.py                      # Python 启动脚本
├── start.bat                   # Windows 批处理启动脚本
├── requirements.txt            # Python 依赖
├── pyproject.toml             # 项目配置
├── README.md                  # 项目说明
└── CLAUDE.md                  # AI 辅助开发指导
```

### 核心文件说明

- **ima_server_simple.py**: 简化的 MCP 服务器主文件，使用 FastMCP 直接创建
- **src/config.py**: 基于环境变量的配置管理模块，支持自动生成缺失参数
- **src/ima_client.py**: IMA API 客户端，处理与腾讯 IMA 服务器的通信
- **run.py**: Python 启动脚本，包含环境检查和配置验证
- **start.bat**: Windows 批处理启动脚本，一键启动
- **.env.example**: 环境变量配置模板，包含详细说明

## 核心功能模块

### 1. IMA API 客户端 (`src/ima_client.py`)
- **功能**: 封装与腾讯 IMA Copilot API 的交互
- **主要接口**:
  - `ask_question(question: str)`: 发送问题并获取流式响应
  - `validate_auth()`: 验证认证信息是否有效
- **认证管理**: 处理 cookies、headers 和请求参数

### 2. 简化的 MCP 服务器 (`ima_server_simple.py`)
- **功能**: 使用 FastMCP 直接提供 MCP 协议的工具和资源
- **核心特性**:
  - 无需 FastAPI 集成，简化架构
  - 环境变量配置加载
  - 自动生成缺失参数
- **工具集**:
  - `ask`: 向腾讯 IMA 知识库询问任何问题
  - `ima_validate_config`: 验证环境变量配置是否有效
  - `ima_get_status`: 获取 IMA 服务和配置状态
- **资源集**:
  - `ima://config`: 配置信息（不包含敏感数据）
  - `ima://help`: 帮助信息
  - `ima://status`: 服务状态信息

### 3. 配置管理 (`src/config.py`)
- **功能**: 基于环境变量的配置管理
- **核心类**:
  - `AppConfig`: 应用配置，从环境变量读取
  - `IMAEnvironmentConfig`: IMA 认证配置，从环境变量读取
  - `ConfigManager`: 简化的配置管理器
- **特性**:
  - 自动生成缺失参数（client_id、uskey）
  - 环境变量验证
  - 无加密存储，直接从环境变量读取

## IMA API 接口分析

基于网络捕获数据，IMA Copilot 的主要接口特征：

### 请求格式
```http
POST https://ima.qq.com/cgi-bin/assistant/qa
Content-Type: text/event-stream
X-Ima-Cookie: [认证信息]
X-Ima-Bkn: [业务密钥]
Cookie: [会话cookies]
```

### 请求体结构
```json
{
  "session_id": "会话ID",
  "robot_type": 5,
  "question": "用户问题",
  "question_type": 2,
  "client_id": "客户端ID",
  "command_info": {
    "type": 14,
    "knowledge_qa_info": {
      "tags": [],
      "knowledge_ids": []
    }
  },
  "model_info": {
    "model_type": 4,
    "enable_enhancement": false
  },
  "history_info": {},
  "device_info": {
    "uskey": "设备密钥",
    "uskey_bus_infos_input": "业务信息"
  }
}
```

### 响应格式
- **类型**: Server-Sent Events (SSE)
- **消息类型**:
  - `knowledgeBase`: 知识库搜索状态
  - `Text`: 文本内容流
  - 系统消息：连接状态和控制信息

## 使用方式

### 分离式启动方式

#### 方式一：独立启动配置服务器和 MCP 服务器

**步骤 1：启动配置服务器**
```bash
# 启动独立的配置页面服务器
python start_config_server.py

# 或者使用简化版
python standalone_config_server.py
```

配置服务器启动后，在浏览器中访问：`http://127.0.0.1:8080`

**步骤 2：启动 MCP 服务器**
```bash
# 在另一个终端中启动 MCP 服务器
fastmcp run ima_server_unified.py:mcp --transport streamable-http --host 127.0.0.1 --port 8081
```

**步骤 3：使用 MCP Inspector**
```bash
# 启动 MCP Inspector
npx @modelcontextprotocol/inspector

# 连接到 MCP 服务器
# 在 Inspector 中输入: http://127.0.0.1:8081/mcp
```

#### 方式二：仅启动 MCP 服务器（配置通过 MCP 工具进行）

```bash
# 直接启动 MCP 服务器
fastmcp run ima_server_unified.py:mcp --transport streamable-http --host 127.0.0.1 --port 8081
```

通过 MCP Inspector 的 `get_config_page` 工具获取配置页面 HTML。

### 环境设置
```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

### 测试和开发
```bash
# 测试 FastAPI 集成
python test_openapi_integration.py

# 运行测试
pytest tests/

# 代码格式化
black src/
isort src/

# 类型检查
mypy src/
```

## 配置要求

### 必需的认证信息
- **IMA Cookies**: 包含会话认证信息
- **X-Ima-Cookie Header**: 平台和客户端信息
- **X-Ima-Bkn**: 业务密钥
- **设备信息**: uskey 和相关业务参数

### 可选配置
- **代理设置**: 支持网络代理配置
- **缓存设置**: 响应缓存配置
- **日志级别**: 调试和信息日志控制

## 安全考虑

1. **敏感信息保护**:
   - Cookies 和认证信息加密存储
   - 避免在日志中记录敏感数据

2. **访问控制**:
   - 配置页面需要本地访问保护
   - API 密钥轮换机制

3. **数据验证**:
   - 输入参数验证和清理
   - 响应数据安全过滤

## 测试策略

### 单元测试
- IMA 客户端功能测试
- 配置管理测试
- MCP 工具和资源测试

### 集成测试
- 端到端 API 调用测试
- SSE 流响应测试
- Web 界面交互测试

### 性能测试
- 并发请求处理
- 内存使用监控
- 响应时间基准测试

## 服务端口说明

### 默认端口配置

- **配置服务器**: `8080` - Web 配置界面
- **MCP 服务器**: `8081` - MCP 协议端点 (`/mcp`)
- **备用端口**: 可根据需要使用其他端口（如 8082, 8085, 8087, 8088）

### 端口使用说明

1. **配置服务器端口**: 浏览器直接访问 Web 界面
2. **MCP 协议端口**: MCP Inspector 连接端点，格式为 `http://127.0.0.1:PORT/mcp`
3. **端口冲突**: 如遇端口占用，可使用不同端口启动服务

## 故障排除

### 常见问题

1. **配置页面无法访问**
   - 确认配置服务器是否正常启动
   - 检查端口是否被占用
   - 验证浏览器访问地址是否正确

2. **MCP Inspector 无法连接**
   - 确认 MCP 服务器是否正常运行
   - 检查端口号是否正确
   - 使用正确的连接格式：`http://127.0.0.1:PORT/mcp`

3. **认证失败**
   - 检查从浏览器获取的 cookies 和 headers 是否正确
   - 确认认证信息是否过期
   - 重新从 IMA Web 页面获取最新的认证信息

4. **FastAPI 集成问题**
   - 运行 `python test_openapi_integration.py` 验证集成状态
   - 检查 FastMCP 版本是否支持 FastAPI 集成
   - 查看服务器日志中的错误信息

### 调试工具

- **FastAPI 集成测试**: `python test_openapi_integration.py`
- **配置验证**: 通过配置页面的"测试连接"功能
- **MCP 工具测试**: 使用 MCP Inspector 的 `ima_validate_config` 工具
- **日志分析**: 查看服务器启动和运行日志
- **网络请求追踪**: 使用浏览器开发者工具监控 IMA API 调用

## 版本控制

- **语义化版本**: 遵循 SemVer 规范
- **变更日志**: 记录重要功能更新和破坏性变更
- **分支策略**: Git Flow 工作流