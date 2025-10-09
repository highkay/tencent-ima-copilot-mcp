"""
IMA API 客户端实现
"""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from urllib.parse import unquote

import aiohttp

from models import (
    IMAConfig,
    IMARequest,
    IMAResponse,
    IMAMessage,
    MessageType,
    KnowledgeBaseMessage,
    TextMessage,
    DeviceInfo,
    MCPToolResult,
    IMAStatus,
    TokenRefreshRequest,
    TokenRefreshResponse,
    InitSessionRequest,
    InitSessionResponse,
    EnvInfo,
    KnowledgeBaseInfoWithFolder,
)

logger = logging.getLogger(__name__)


class IMAAPIClient:
    """IMA API 客户端"""

    def __init__(self, config: IMAConfig):
        self.config = config
        self.base_url = "https://ima.qq.com"
        self.api_endpoint = "/cgi-bin/assistant/qa"
        self.refresh_endpoint = "/cgi-bin/auth_login/refresh"
        self.init_session_endpoint = "/cgi-bin/session_logic/init_session"
        self.session: Optional[aiohttp.ClientSession] = None
        self.current_session_id: Optional[str] = None
        self.session_initialized: bool = False

    def _is_token_expired(self) -> bool:
        """检查token是否过期"""
        if not self.config.token_updated_at or not self.config.token_valid_time:
            return True

        from datetime import timedelta
        expired_time = self.config.token_updated_at + timedelta(seconds=self.config.token_valid_time)
        return datetime.now() > expired_time

    def _parse_user_id_from_cookies(self) -> Optional[str]:
        """从IMA_X_IMA_COOKIE中解析IMA-UID"""
        try:
            # 从IMA_X_IMA_COOKIE中提取IMA-UID
            import re
            uid_pattern = r"IMA-UID=([^;]+)"
            match = re.search(uid_pattern, self.config.x_ima_cookie)
            if match:
                uid = match.group(1)
                logger.info(f"成功解析IMA-UID: {uid}")
                return uid

            # 如果在IMA_X_IMA_COOKIE中没找到，尝试从cookies中查找
            user_id_pattern = r"user_id=([a-f0-9]{16})"
            match = re.search(user_id_pattern, self.config.cookies)
            if match:
                logger.info(f"从cookies中解析user_id: {match.group(1)}")
                return match.group(1)
        except Exception as e:
            logger.warning(f"解析user_id失败: {e}")
        return None

    def _parse_refresh_token_from_cookies(self) -> Optional[str]:
        """从IMA_X_IMA_COOKIE中解析IMA-TOKEN（用于刷新token）"""
        try:
            # 从IMA_X_IMA_COOKIE中提取IMA-TOKEN
            import re
            token_pattern = r"IMA-TOKEN=([^;]+)"
            match = re.search(token_pattern, self.config.x_ima_cookie)
            if match:
                token = match.group(1)
                logger.info(f"成功解析IMA-TOKEN: {token[:20]}...")
                return token

            # 如果在IMA_X_IMA_COOKIE中没找到，尝试从cookies中查找
            refresh_token_pattern = r"refresh_token=([^;]+)"
            match = re.search(refresh_token_pattern, self.config.cookies)
            if match:
                logger.info(f"从cookies中解析refresh_token: {match.group(1)[:20]}...")
                return match.group(1)
        except Exception as e:
            logger.warning(f"解析IMA-TOKEN失败: {e}")
        return None

    async def refresh_token(self) -> bool:
        """刷新访问令牌"""
        if not self.config.user_id or not self.config.refresh_token:
            # 尝试从cookies中解析
            self.config.user_id = self._parse_user_id_from_cookies()
            self.config.refresh_token = self._parse_refresh_token_from_cookies()

            if not self.config.user_id or not self.config.refresh_token:
                logger.warning("缺少token刷新所需的user_id或refresh_token")
                return False

        try:
            session = await self._get_session()

            # 构建刷新请求
            refresh_request = TokenRefreshRequest(
                user_id=self.config.user_id,
                refresh_token=self.config.refresh_token
            )

            refresh_url = f"{self.base_url}{self.refresh_endpoint}"

            async with session.post(
                refresh_url,
                json=refresh_request.dict(),
                headers={
                    "accept": "*/*",
                    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                    "content-type": "application/json",
                    "from_browser_ima": "1",
                    "x-ima-cookie": self.config.x_ima_cookie,
                    "referer": "https://ima.qq.com/wikis"
                }
            ) as response:
                if response.status == 200:
                    response_data = await response.json()
                    refresh_response = TokenRefreshResponse(**response_data)

                    if refresh_response.code == 0 and refresh_response.token:
                        # 更新token信息
                        self.config.current_token = refresh_response.token
                        self.config.token_valid_time = int(refresh_response.token_valid_time or "7200")
                        self.config.token_updated_at = datetime.now()

                        logger.info("Token刷新成功")
                        return True
                    else:
                        logger.warning(f"Token刷新失败: {refresh_response.msg}")
                        return False
                else:
                    logger.error(f"Token刷新请求失败，状态码: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Token刷新异常: {e}")
            return False

    async def ensure_valid_token(self) -> bool:
        """确保token有效，如果过期则刷新"""
        # 如果没有current_token，或者token过期，尝试刷新
        if self._is_token_expired():
            # 如果有refresh_token和user_id，尝试刷新token
            if self.config.refresh_token and self.config.user_id:
                logger.info("Token已过期，尝试刷新...")
                return await self.refresh_token()
            else:
                # 如果没有refresh_token，说明使用基于cookies的认证，不需要token
                logger.info("使用基于cookies的认证，无需token刷新")
                return True

        # Token仍然有效
        return True

    
    def _parse_cookies(self, cookie_string: str) -> Dict[str, str]:
        """解析 Cookie 字符串为字典"""
        cookies = {}
        if not cookie_string:
            return cookies

        # 处理不同格式的 Cookie 字符串
        cookie_parts = cookie_string.split(';')
        for part in cookie_parts:
            if '=' in part:
                name, value = part.strip().split('=', 1)
                cookies[name.strip()] = value.strip()
        return cookies

    def _build_headers(self, for_init_session: bool = False) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "x-ima-cookie": self.config.x_ima_cookie,
            "from_browser_ima": "1",
            "extension_version": "999.999.999",
            "x-ima-bkn": self.config.x_ima_bkn,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            "accept": "application/json" if for_init_session else "text/event-stream",  # init_session期望JSON，qa期望SSE
            "content-type": "application/json",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "sec-ch-ua": '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

        # 如果有当前token，添加到请求头
        if self.config.current_token:
            headers["authorization"] = f"Bearer {self.config.current_token}"

        return headers

    async def _get_session(self, for_init_session: bool = False) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,
                use_dns_cache=True,
                # 启用连接池和keep-alive
                keepalive_timeout=60,
                enable_cleanup_closed=True,
            )

            # 增加超时时间以处理大响应
            # 对于SSE流，需要更长的读取时间
            timeout = aiohttp.ClientTimeout(
                total=min(self.config.timeout, 120),  # 总超时最多2分钟
                sock_read=90,   # socket 读取超时增加到90秒
                connect=30,     # 连接超时
                sock_connect=30, # socket连接超时
            )

            # 配置代理（如果设置）
            proxy = None
            if self.config.proxy:
                proxy = self.config.proxy

            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                cookies=self._parse_cookies(self.config.cookies),
                headers=self._build_headers(for_init_session),
                trust_env=True,
                # 增加读取缓冲区大小
                read_bufsize=2**20,  # 1MB
                # 启用自动解压缩
                auto_decompress=True,
            )

        return self.session

    async def close(self):
        """关闭客户端会话"""
        if self.session and not self.session.closed:
            await self.session.close()

    def _generate_session_id(self) -> str:
        """生成会话 ID"""
        import random
        import string
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=24))

    def _generate_temp_uskey(self) -> str:
        """生成临时 uskey"""
        import base64
        import secrets

        # 生成 32 字节的随机数据
        random_bytes = secrets.token_bytes(32)
        # 编码为 Base64 字符串
        return base64.b64encode(random_bytes).decode('utf-8')

    def _build_request(self, question: str) -> IMARequest:
        """构建 IMA API 请求"""
        # 使用 init_session 获取的 session_id，如果没有则生成一个
        session_id = self.current_session_id or self._generate_session_id()

        # 如果没有提供 uskey，尝试生成一个临时的
        uskey = self.config.uskey
        if not uskey:
            uskey = self._generate_temp_uskey()

        # 提取 IMA-GUID
        try:
            ima_guid = self.config.x_ima_cookie.split('IMA-GUID=')[1].split(';')[0]
        except (IndexError, AttributeError):
            ima_guid = "default_guid"

        device_info = DeviceInfo(
            uskey=uskey,
            uskey_bus_infos_input=f"{ima_guid}_{int(datetime.now().timestamp())}"
        )

        return IMARequest(
            session_id=session_id,
            robot_type=self.config.robot_type,
            question=question,
            question_type=2,
            client_id=self.config.client_id,
            command_info={
                "type": 14,
                "knowledge_qa_info": {
                    "tags": [],
                    "knowledge_ids": []
                }
            },
            model_info={
                "model_type": self.config.model_type,
                "enable_enhancement": False
            },
            history_info={},
            device_info=device_info
        )

    def _parse_sse_message(self, line: str) -> Optional[IMAMessage]:
        """解析 SSE 消息"""
        try:
            # 处理标准 SSE 格式
            if line.startswith('data: '):
                data = line[6:]  # 移除 'data: ' 前缀
            elif line.startswith('event: ') or line.startswith('id: '):
                # SSE 控制消息，跳过
                return None
            else:
                # 非标准格式，直接使用
                data = line

            # 跳过空行和结束标记
            if not data or data == '[DONE]' or data.strip() == '':
                return None

            # 解析 JSON 数据
            json_data = json.loads(data)

            # 处理不同的消息格式
            # 格式1: 包含消息列表的响应
            if 'msgs' in json_data and isinstance(json_data['msgs'], list):
                # 这是最终响应，包含多个消息
                for msg in json_data['msgs']:
                    if isinstance(msg, dict) and 'content' in msg:
                        # 提取内容
                        content = msg.get('content', '')
                        if content:
                            return TextMessage(
                                type=MessageType.TEXT,
                                content=content,
                                text=content,
                                raw=data
                            )
                return None

            # 格式2: 直接包含内容字段
            if 'content' in json_data:
                content = json_data['content']
                if isinstance(content, str) and content:
                    return TextMessage(
                        type=MessageType.TEXT,
                        content=content,
                        text=content,
                        raw=data
                    )

            # 格式3: 包含 Text 字段
            if 'Text' in json_data and isinstance(json_data['Text'], str):
                return TextMessage(
                    type=MessageType.TEXT,
                    content=json_data['Text'],
                    text=json_data['Text'],
                    raw=data
                )

            # 格式4: 知识库消息
            if 'type' in json_data and json_data['type'] == 'knowledgeBase':
                # 确保content字段存在
                if 'content' not in json_data:
                    json_data['content'] = json_data.get('processing', '知识库搜索中...')
                return KnowledgeBaseMessage(**json_data)

            # 格式5: 其他格式的消息，尝试提取有用信息
            if 'question' in json_data and 'answer' in json_data:
                # 问答格式
                answer = json_data.get('answer', '')
                if answer:
                    return TextMessage(
                        type=MessageType.TEXT,
                        content=answer,
                        text=answer,
                        raw=data
                    )

            # 如果都无法匹配，将整个JSON作为内容
            return IMAMessage(
                type=MessageType.SYSTEM,
                content=str(json_data),
                raw=data
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse SSE message: {e}, line: {line[:100]}...")
            return None

    async def _process_sse_stream(self, response: aiohttp.ClientResponse) -> AsyncGenerator[IMAMessage, None]:
        """处理 SSE 流 - 完整处理所有消息"""
        buffer = ""
        full_response = ""
        message_count = 0
        no_data_timeout = 60  # 增加到60秒无数据超时，适合长响应
        last_data_time = asyncio.get_event_loop().time()
        start_time = asyncio.get_event_loop().time()

        try:
            async for chunk in response.content:
                current_time = asyncio.get_event_loop().time()

                # 检查超时
                if current_time - last_data_time > no_data_timeout:
                    logger.warning(f"SSE 流读取超时，无数据时间超过{no_data_timeout}秒")
                    break

                if chunk:
                    last_data_time = current_time
                    message_count += 1

                    try:
                        chunk_str = chunk.decode('utf-8')
                    except UnicodeDecodeError:
                        # 尝试使用其他编码或忽略无效字节
                        try:
                            chunk_str = chunk.decode('gbk')
                        except UnicodeDecodeError:
                            # 如果都失败，使用错误处理模式
                            chunk_str = chunk.decode('utf-8', errors='ignore')

                    buffer += chunk_str
                    full_response += chunk_str

                    # 处理完整的行
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()

                        if line:
                            message = self._parse_sse_message(line)
                            if message:
                                yield message

                    # 定期报告处理进度（每500条消息）
                    if message_count % 500 == 0:
                        elapsed_time = current_time - start_time
                        logger.info(f"已处理 {message_count} 条消息，耗时 {elapsed_time:.1f} 秒")

        except asyncio.TimeoutError:
            logger.error("SSE 流读取超时")
            raise
        except aiohttp.ClientPayloadError as e:
            logger.error(f"SSE 流数据错误: {e}")
            raise
        except Exception as e:
            logger.error(f"SSE 流处理异常: {e}")
            # 不重新抛出异常，继续尝试解析完整响应
        finally:
            # 确保响应被正确关闭
            if not response.closed:
                response.close()

        # 处理剩余的缓冲区内容
        if buffer.strip():
            remaining_lines = buffer.strip().split('\n')
            for line in remaining_lines:
                line = line.strip()
                if line:
                    message = self._parse_sse_message(line)
                    if message:
                        yield message

        # 如果没有从 SSE 流中解析到足够消息，尝试将整个响应作为 JSON 处理
        # 这是为了处理 IMA 可能返回的完整 JSON 响应
        if message_count < 100:  # 只有在消息较少时才尝试完整解析
            logger.debug(f"消息数量较少({message_count})，尝试完整解析响应...")

            # 尝试解析整个响应为 JSON
            try:
                if full_response.strip():
                    response_data = json.loads(full_response.strip())
                    logger.debug("成功解析完整响应为 JSON")

                    # 尝试从响应中提取有用信息
                    messages = self._extract_messages_from_response(response_data)
                    for message in messages:
                        yield message
                else:
                    logger.debug("响应内容为空")

            except json.JSONDecodeError as e:
                logger.debug(f"无法解析完整响应为 JSON: {e}")

                # 最后尝试：逐行解析响应
                if full_response:
                    lines = full_response.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and line != '[DONE]':
                            message = self._parse_sse_message(line)
                            if message:
                                yield message
                else:
                    logger.debug("没有可用的响应数据")

        # 记录最终处理统计
        elapsed_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"SSE 流处理完成: {message_count} 条消息，响应大小 {len(full_response)} 字节，耗时 {elapsed_time:.1f} 秒")

    def _extract_messages_from_response(self, response_data: Dict[str, Any]) -> List[IMAMessage]:
        """从完整响应中提取消息 - 只关注qa返回的msgs中最后一个对象"""
        messages = []

        try:
            # 查找qa响应中的msgs列表
            if 'msgs' in response_data and isinstance(response_data['msgs'], list):
                msgs_list = response_data['msgs']
                if msgs_list:
                    # 获取最后一个消息对象
                    last_msg = msgs_list[-1]
                    if isinstance(last_msg, dict):
                        # 检查是否是qa消息类型 (type: 3)
                        if last_msg.get('type') == 3:
                            qa_content = last_msg.get('content', {})
                            if isinstance(qa_content, dict):
                                # 提取answer内容
                                answer = qa_content.get('answer', '')
                                if isinstance(answer, str) and answer:
                                    # 解析answer中的JSON（通常是转义的）
                                    try:
                                        answer_data = json.loads(answer)
                                        if isinstance(answer_data, dict) and 'Text' in answer_data:
                                            text_content = answer_data['Text']
                                            messages.append(TextMessage(
                                                type=MessageType.TEXT,
                                                content=text_content,
                                                text=text_content,
                                                raw=str(last_msg)
                                            ))
                                        else:
                                            # 如果不是预期的格式，直接使用answer内容
                                            messages.append(TextMessage(
                                                type=MessageType.TEXT,
                                                content=answer,
                                                text=answer,
                                                raw=str(last_msg)
                                            ))
                                    except json.JSONDecodeError:
                                        # 如果无法解析JSON，直接使用answer内容
                                        messages.append(TextMessage(
                                            type=MessageType.TEXT,
                                            content=answer,
                                            text=answer,
                                            raw=str(last_msg)
                                        ))

                                # 提取context_refs内容
                                context_refs = qa_content.get('context_refs', '')
                                if context_refs:
                                    # 解析context_refs（通常是JSON格式的参考资料）
                                    try:
                                        context_data = json.loads(context_refs)
                                        if isinstance(context_data, dict):
                                            # 构建参考资料文本
                                            ref_text = "\n\n📚 参考资料:\n"
                                            if 'medias' in context_data and isinstance(context_data['medias'], list):
                                                for i, media in enumerate(context_data['medias'][:5], 1):  # 最多显示5个
                                                    title = media.get('title', f'资料{i}')
                                                    intro = media.get('introduction', '')
                                                    if intro:
                                                        intro = intro[:150] + "..." if len(intro) > 150 else intro
                                                        ref_text += f"{i}. {title}\n   {intro}\n"
                                                    else:
                                                        ref_text += f"{i}. {title}\n"

                                            # 将参考资料作为文本消息添加
                                            if context_data.get('medias'):
                                                messages.append(TextMessage(
                                                    type=MessageType.TEXT,
                                                    content=ref_text,
                                                    text=ref_text,
                                                    raw=str(last_msg)
                                                ))
                                    except json.JSONDecodeError:
                                        # 如果无法解析JSON，直接作为文本处理
                                        messages.append(TextMessage(
                                            type=MessageType.TEXT,
                                            content=f"\n\n📚 参考资料:\n{context_refs}",
                                            text=f"\n\n📚 参考资料:\n{context_refs}",
                                            raw=str(last_msg)
                                        ))

            logger.info(f"从响应中提取了 {len(messages)} 条消息（仅处理qa msgs中最后一个对象）")
            return messages

        except Exception as e:
            logger.error(f"提取消息时出错: {e}")
            # 如果无法解析，返回原始内容作为系统消息
            messages.append(IMAMessage(
                type=MessageType.SYSTEM,
                content=str(response_data),
                raw=str(response_data)
            ))
            return messages

    async def init_session(self, knowledge_base_id: Optional[str] = None) -> str:
        """初始化会话，获取有效的 session_id"""
        # 使用配置中的知识库ID，如果没有提供参数
        kb_id = knowledge_base_id or getattr(self.config, 'knowledge_base_id', '7305806844290061')

        # 确保token有效
        if not await self.ensure_valid_token():
            logger.error("无法获取有效的访问令牌")
            raise ValueError("Authentication failed - unable to obtain valid token")

        session = await self._get_session(for_init_session=True)

        # 构建初始化请求
        init_request = InitSessionRequest(
            envInfo=EnvInfo(
                robotType=5,
                interactType=0
            ),
            byKeyword=kb_id,
            relatedUrl=kb_id,
            sceneType=1,
            msgsLimit=10,
            forbidAutoAddToHistoryList=True,
            knowledgeBaseInfoWithFolder=KnowledgeBaseInfoWithFolder(
                knowledge_base_id=kb_id,
                folder_ids=[]
            )
        )

        url = f"{self.base_url}{self.init_session_endpoint}"
        request_json = init_request.model_dump()

        logger.info(f"初始化会话URL: {url}")
        logger.info(f"初始化会话参数: {json.dumps(request_json, ensure_ascii=False, indent=2)}")

        try:
            async with session.post(
                url,
                json=request_json,
                headers={"content-type": "application/json"}
            ) as response:
                response.raise_for_status()

                response_data = await response.json()
                logger.info(f"初始化会话响应: {json.dumps(response_data, ensure_ascii=False, indent=2)}")

                # 解析响应
                init_response = InitSessionResponse(**response_data)

                if init_response.code == 0 and init_response.session_id:
                    self.current_session_id = init_response.session_id
                    self.session_initialized = True
                    logger.info(f"会话初始化成功，session_id: {self.current_session_id}")
                    return self.current_session_id
                else:
                    logger.error(f"会话初始化失败 (code: {init_response.code}): {init_response.msg}")
                    raise ValueError(f"Session initialization failed (code: {init_response.code}): {init_response.msg}")

        except aiohttp.ClientError as e:
            logger.error(f"会话初始化HTTP请求失败: {e}")
            raise
        except Exception as e:
            logger.error(f"会话初始化异常: {e}")
            raise

    async def ask_question(self, question: str) -> AsyncGenerator[IMAMessage, None]:
        """向 IMA 询问问题"""
        if not question.strip():
            raise ValueError("Question cannot be empty")

        # 确保token有效
        if not await self.ensure_valid_token():
            logger.error("无法获取有效的访问令牌")
            raise ValueError("Authentication failed - unable to obtain valid token")

        # 如果会话未初始化，先初始化会话
        if not self.session_initialized or not self.current_session_id:
            logger.info("会话未初始化，开始初始化...")
            await self.init_session()

        session = await self._get_session()
        request_data = self._build_request(question)

        url = f"{self.base_url}{self.api_endpoint}"
        request_json = request_data.model_dump()

        logger.info(f"请求URL: {url}")
        logger.info(f"请求参数: {json.dumps(request_json, ensure_ascii=False, indent=2)}")

        response = None
        try:
            response = await session.post(
                url,
                json=request_json,
                headers={"content-type": "application/json"}
            )

            # 检查响应状态
            if response.status != 200:
                response_text = await response.text()
                logger.error(f"HTTP请求失败，状态码: {response.status}")
                logger.error(f"响应内容: {response_text[:500]}...")
                raise ValueError(f"HTTP请求失败: {response.status} - {response_text[:200]}")

            # 检查响应类型
            content_type = response.headers.get('content-type', '')
            logger.debug(f"响应类型: {content_type}, 状态码: {response.status}")

            if 'text/event-stream' not in content_type:
                # 读取响应内容进行诊断
                response_text = await response.text()
                logger.error(f"意外的响应类型: {content_type}")
                logger.error(f"响应内容: {response_text[:500]}...")

                # 尝试解析JSON错误响应
                try:
                    error_data = json.loads(response_text)
                    logger.error(f"API错误响应: {json.dumps(error_data, ensure_ascii=False, indent=2)}")
                except json.JSONDecodeError as e:
                    logger.error(f"无法解析错误响应为JSON: {e}")
                    logger.error(f"原始响应内容: {response_text}")

                raise ValueError(f"Expected SSE response, got {content_type}. 可能原因: 1) 认证信息错误 2) 请求参数问题 3) API端点变更")

            # 处理流式响应
            message_count = 0
            async for message in self._process_sse_stream(response):
                message_count += 1
                yield message

            # 移除这个日志，因为在 _process_sse_stream 中已经有更详细的统计信息

            # 如果没有收到任何消息，至少返回一个系统消息
            if message_count == 0:
                logger.warning("未收到有效SSE消息")
                yield IMAMessage(
                    type=MessageType.SYSTEM,
                    content="未收到有效响应，但请求已成功发送",
                    raw="No valid SSE messages received"
                )

        except asyncio.TimeoutError as e:
            logger.error(f"请求超时: {e}")
            raise ValueError(f"请求超时: {str(e)}")
        except aiohttp.ClientError as e:
            logger.error(f"HTTP请求失败: {e}")
            raise ValueError(f"HTTP请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"询问过程中发生未知错误: {e}")
            # 重新抛出异常，但包装为更友好的错误信息
            raise ValueError(f"询问失败: {str(e)}")
        finally:
            # 确保响应被正确关闭
            if response and not response.closed:
                response.close()

    def _is_login_expired_error(self, error_str: str) -> bool:
        """检测是否是登录过期相关错误"""
        login_expired_patterns = [
            "Session initialization failed",
            "登录过期",
            "登录失败",
            "authentication failed",
            "认证失败",
            "code: 600001",
            "code: 600002",
            "code: 600003",
            "token expired",
            "会话已过期",
            "请重新登录",
            "unauthorized",
            "401"
        ]

        error_lower = error_str.lower()
        return any(pattern.lower() in error_lower for pattern in login_expired_patterns)

    async def ask_question_complete(self, question: str) -> List[IMAMessage]:
        """获取完整的问题回答 - 支持自动 token 刷新重试"""
        messages = []
        max_retries = 2  # 最大重试次数

        for attempt in range(max_retries + 1):  # 总共尝试 max_retries + 1 次
            try:
                async for message in self.ask_question(question):
                    messages.append(message)

                # 如果成功获取到消息，直接返回
                if messages:
                    break

            except Exception as e:
                error_str = str(e)
                logger.error(f"Failed to get complete answer (attempt {attempt + 1}/{max_retries + 1}): {e}")

                # 检查是否是登录过期错误
                if self._is_login_expired_error(error_str):
                    if attempt < max_retries:
                        logger.info(f"检测到登录/认证过期错误，尝试刷新 token... (错误: {error_str[:100]})")

                        # 尝试刷新 token
                        refresh_success = await self.refresh_token()
                        if refresh_success:
                            logger.info("Token 刷新成功，重新尝试会话初始化...")
                            # 重置会话状态，强制重新初始化
                            self.session_initialized = False
                            self.current_session_id = None
                            # 关闭现有会话，重新创建
                            if self.session and not self.session.closed:
                                await self.session.close()
                                self.session = None
                            # 重置消息列表，准备重新尝试
                            messages = []
                            continue
                        else:
                            logger.warning("Token 刷新失败，无法恢复会话")
                    else:
                        logger.error(f"已达到最大重试次数，token 刷新失败。原始错误: {error_str}")
                else:
                    # 如果不是登录过期错误，直接记录错误并重试
                    if attempt < max_retries:
                        logger.info(f"非登录过期错误，重试中... (错误: {error_str[:100]})")
                        # 重置消息列表，准备重新尝试
                        messages = []
                        # 短暂延迟后重试
                        await asyncio.sleep(1)
                        continue

                # 如果已经重试完成，记录最终错误
                if attempt == max_retries:
                    error_message = IMAMessage(
                        type=MessageType.SYSTEM,
                        content=f"获取回答失败: {error_str}",
                        raw=str(e)
                    )
                    messages.append(error_message)

        return messages

    def _extract_text_content(self, messages: List[IMAMessage]) -> str:
        """从消息列表中提取文本内容 - 现在只处理answer和context_refs的拼接"""
        if not messages:
            return "没有收到任何响应"

        content_parts = []

        for message in messages:
            if isinstance(message, TextMessage) and message.text:
                content_parts.append(message.text)
            elif hasattr(message, 'content') and message.content:
                content_parts.append(message.content)

        # 拼接所有内容
        final_result = ''.join(content_parts).strip()

        # 清理和格式化结果
        final_result = self._clean_response_content(final_result)

        logger.info(f"最终响应内容长度: {len(final_result)}")
        return final_result

    def _clean_response_content(self, content: str) -> str:
        """清理和格式化响应内容"""
        if not content:
            return content

        # 移除多余的空白行
        lines = content.split('\n')
        cleaned_lines = []
        prev_empty = False

        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
                prev_empty = False
            elif not prev_empty:
                cleaned_lines.append('')
                prev_empty = True

        return '\n'.join(cleaned_lines)

    
    def _extract_knowledge_info(self, messages: List[IMAMessage]) -> List[Dict[str, Any]]:
        """从消息列表中提取知识库信息"""
        knowledge_items = []

        for message in messages:
            if isinstance(message, KnowledgeBaseMessage) and message.medias:
                for media in message.medias:
                    knowledge_items.append({
                        'id': media.id,
                        'title': media.title,
                        'subtitle': media.subtitle,
                        'introduction': media.introduction,
                        'timestamp': media.timestamp,
                        'knowledge_base': media.knowledge_base_info.name if media.knowledge_base_info else None
                    })

        return knowledge_items

    async def validate_config(self) -> bool:
        """验证配置是否有效"""
        try:
            # 发送一个简单的测试问题
            test_messages = await self.ask_question_complete("测试连接")
            return len(test_messages) > 0
        except Exception as e:
            logger.error(f"Config validation failed: {e}")
            return False

    async def get_status(self) -> IMAStatus:
        """获取客户端状态"""
        status = IMAStatus()

        if not self.config:
            return status

        status.is_configured = True

        try:
            # 验证认证状态
            is_valid = await self.validate_config()
            status.is_authenticated = is_valid
            status.last_test_time = datetime.now()

            if not is_valid:
                status.error_message = "认证失败，请检查配置"

        except Exception as e:
            status.error_message = str(e)
            logger.error(f"Failed to get status: {e}")

        return status


class IMAToolExecutor:
    """IMA 工具执行器"""

    def __init__(self, client: IMAAPIClient):
        self.client = client

    async def ask_question(self, question: str, include_knowledge: bool = True) -> MCPToolResult:
        """执行询问问题工具"""
        try:
            messages = await self.client.ask_question_complete(question)

            if not messages:
                return MCPToolResult(
                    success=False,
                    content="",
                    error="未收到响应"
                )

            # 提取主要回答内容
            answer_text = self.client._extract_text_content(messages)

            # 构建响应内容
            content_parts = [f"**问题**: {question}\n\n**回答**:\n{answer_text}"]

            # 添加知识库信息（如果需要）
            if include_knowledge:
                knowledge_info = self.client._extract_knowledge_info(messages)
                if knowledge_info:
                    content_parts.append("\n\n**参考资料**:")
                    for i, item in enumerate(knowledge_info[:5], 1):  # 最多显示5个参考资料
                        content_parts.append(f"{i}. {item['title']}")
                        if item.get('introduction'):
                            content_parts.append(f"   {item['introduction'][:100]}...")

            final_content = '\n'.join(content_parts)

            return MCPToolResult(
                success=True,
                content=final_content,
                metadata={
                    'message_count': len(messages),
                    'knowledge_sources': len(self.client._extract_knowledge_info(messages))
                }
            )

        except Exception as e:
            logger.error(f"Failed to execute ask_question: {e}")
            return MCPToolResult(
                success=False,
                content="",
                error=f"询问失败: {str(e)}"
            )

  