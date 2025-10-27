"""
数据模型定义
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, HttpUrl
from enum import Enum


class MessageType(str, Enum):
    """IMA 响应消息类型"""
    SYSTEM = "system"
    RAW = "raw"
    TEXT = "text"
    KNOWLEDGE_BASE = "knowledgeBase"


class DeviceInfo(BaseModel):
    """设备信息模型"""
    uskey: str
    uskey_bus_infos_input: str


class IMARequest(BaseModel):
    """IMA API 请求模型"""
    session_id: str
    robot_type: int
    question: str
    question_type: int = 2
    client_id: str
    command_info: Dict[str, Any] = Field(default_factory=lambda: {
        "type": 14,
        "knowledge_qa_info": {
            "tags": [],
            "knowledge_ids": []
        }
    })
    model_info: Dict[str, Any]
    history_info: Dict[str, Any] = Field(default_factory=dict)
    device_info: DeviceInfo


class IMAMessage(BaseModel):
    """IMA 响应消息模型"""
    type: MessageType
    content: str
    raw: Optional[str] = None


class KnowledgeBaseInfo(BaseModel):
    """知识库信息"""
    id: str
    name: str
    logo: Optional[HttpUrl] = None
    introduction: Optional[str] = None
    description: Optional[str] = None
    creator_name: Optional[str] = None
    permission_type: Optional[int] = None


class MediaInfo(BaseModel):
    """媒体信息模型"""
    id: str
    type: int
    title: str
    subtitle: Optional[str] = None
    introduction: Optional[str] = None
    logo: Optional[HttpUrl] = None
    cover: Optional[HttpUrl] = None
    jump_url: Optional[str] = None
    jump_url_info: Optional[Dict[str, Any]] = None
    timestamp: Optional[int] = None
    index: Optional[int] = None
    publisher: Optional[str] = None
    tips: Optional[str] = None
    role_type: Optional[int] = None
    permission_info: Optional[Dict[str, Any]] = None
    source_type: Optional[int] = None
    knowledge_base_info: Optional[KnowledgeBaseInfo] = None


class KnowledgeBaseMessage(IMAMessage):
    """知识库消息模型"""
    content: str = ""  # 知识库搜索状态描述
    processing: Optional[str] = None
    stage: Optional[int] = None
    medias: Optional[List[MediaInfo]] = None


class TextMessage(IMAMessage):
    """文本消息模型"""
    text: str


class IMAResponse(BaseModel):
    """IMA API 完整响应模型"""
    code: int = 0
    msg: str = ""
    msg_seq_id: str
    support_mind_map: bool = False
    intent_report_id: Optional[Dict[str, int]] = None
    debug_profile: Optional[Dict[str, Any]] = None
    qa_permission: Optional[Dict[str, Any]] = None


class TokenRefreshRequest(BaseModel):
    """Token刷新请求模型"""
    user_id: str
    refresh_token: str
    token_type: int = 14


class TokenRefreshResponse(BaseModel):
    """Token刷新响应模型"""
    code: int
    msg: str
    token: Optional[str] = None
    token_valid_time: Optional[str] = None
    user_id: Optional[str] = None


# --- init_session Models ---

class KnowledgeBaseInfoWithFolder(BaseModel):
    knowledge_base_id: str
    folder_ids: List[str] = []


class EnvInfo(BaseModel):
    robotType: int
    interactType: int = 0


class InitSessionRequest(BaseModel):
    envInfo: EnvInfo
    byKeyword: str
    relatedUrl: str
    sceneType: int
    msgsLimit: int = 10
    forbidAutoAddToHistoryList: bool = True
    knowledgeBaseInfoWithFolder: KnowledgeBaseInfoWithFolder


class SessionInfo(BaseModel):
    id: str
    # other fields can be added if needed


class InitSessionResponse(BaseModel):
    code: int
    msg: str
    session_id: Optional[str] = None
    session_info: Optional[SessionInfo] = None


class IMAConfig(BaseModel):
    """IMA 配置模型"""
    # 基础认证信息
    cookies: Optional[str] = Field(None, description="完整的 Cookie 字符串（可选）")
    x_ima_cookie: str = Field(..., description="X-Ima-Cookie Header 值")
    x_ima_bkn: str = Field(..., description="X-Ima-Bkn Header 值")

    # 核心参数
    knowledge_base_id: str = Field(..., description="知识库ID")

    # 设备信息
    uskey: Optional[str] = Field(None, description="设备 uskey（动态生成，暂时可选）")
    client_id: str = Field(..., description="客户端 ID")

    # Token刷新相关
    user_id: Optional[str] = Field(None, description="用户ID，用于token刷新")
    refresh_token: Optional[str] = Field(None, description="刷新令牌")
    current_token: Optional[str] = Field(None, description="当前访问令牌")
    token_valid_time: Optional[int] = Field(None, description="令牌有效时间（秒）")
    token_updated_at: Optional[datetime] = Field(None, description="令牌更新时间")

    # 可选行为参数
    robot_type: int = Field(5, description="机器人类型")
    scene_type: int = Field(1, description="场景类型")
    model_type: int = Field(4, description="模型类型")

    # 可选配置
    proxy: Optional[str] = Field(None, description="代理设置")
    timeout: int = Field(30, description="请求超时时间（秒）")
    retry_count: int = Field(3, description="重试次数")
    enable_raw_logging: bool = Field(False, description="Enable writing raw SSE responses to disk")
    raw_log_dir: Optional[str] = Field(None, description="Directory for raw SSE logs")
    raw_log_max_bytes: int = Field(1048576, description="Maximum bytes saved per raw response")
    raw_log_on_success: bool = Field(False, description="Save raw response even when successful")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def is_complete(self) -> bool:
        """检查配置是否完整（包含所有必需字段）"""
        return bool(
            self.x_ima_cookie and
            self.x_ima_bkn and
            self.client_id
        )


class IMAStatus(BaseModel):
    """IMA 状态模型"""
    is_configured: bool = False
    is_authenticated: bool = False
    last_test_time: Optional[datetime] = None
    error_message: Optional[str] = None
    session_info: Optional[Dict[str, Any]] = None


class MCPToolResult(BaseModel):
    """MCP 工具执行结果"""
    success: bool
    content: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AskQuestionArgs(BaseModel):
    """询问问题参数"""
    question: str = Field(..., description="要询问的问题")
    include_knowledge: bool = Field(True, description="是否包含知识库信息")
    max_length: Optional[int] = Field(None, description="最大响应长度")


class SearchStocksArgs(BaseModel):
    """股票搜索工具参数"""
    query: str = Field(..., description="股票搜索关键词")
    limit: int = Field(10, ge=1, le=50, description="返回结果数量")


class GetRecommendationsArgs(BaseModel):
    """获取投资推荐参数"""
    sector: Optional[str] = Field(None, description="行业或板块过滤条件")
    time_range: Optional[str] = Field(None, description="时间范围过滤条件")
    limit: int = Field(20, ge=1, le=100, description="推荐数量")


