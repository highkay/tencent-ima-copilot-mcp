"""
IMA API 客户端实现
"""
import asyncio
import base64
import json
import logging
import random
import re
import secrets
import string
import traceback
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import unquote

import aiohttp

from models import (
    IMAConfig,
    IMARequest,
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
        self.raw_log_dir: Optional[Path] = None

        if getattr(self.config, "enable_raw_logging", False):
            raw_dir_value = getattr(self.config, "raw_log_dir", None)
            raw_dir = Path(raw_dir_value) if raw_dir_value else Path("logs") / "sse_raw"
            try:
                raw_dir.mkdir(parents=True, exist_ok=True)
                self.raw_log_dir = raw_dir
                logger.info(f"Raw SSE logs will be written to: {raw_dir}")
            except Exception as exc:
                logger.error(f"Failed to prepare raw SSE log directory: {exc}")

    def _should_persist_raw(self, stream_error: Optional[str]) -> bool:
        """判断当前是否需要保存原始SSE响应"""
        if not self.raw_log_dir or not getattr(self.config, "enable_raw_logging", False):
            return False

        if stream_error:
            return True  # always persist on errors

        return getattr(self.config, "raw_log_on_success", False)

    def _persist_raw_response(
        self,
        trace_id: str,
        attempt_index: int,
        question: Optional[str],
        full_response: str,
        message_count: int,
        parsed_message_count: int,
        failed_parse_count: int,
        elapsed_time: float,
        stream_error: Optional[str],
    ) -> Optional[Path]:
        """将原始SSE响应落盘，便于排查问题"""
        if not self._should_persist_raw(stream_error):
            return None

        assert self.raw_log_dir is not None  # for type checkers

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        suffix = f"attempt{attempt_index + 1}"
        filename = f"sse_{timestamp}_{trace_id}_{suffix}.log"
        target_path = self.raw_log_dir / filename

        max_bytes = getattr(self.config, "raw_log_max_bytes", 0) or 0
        encoded = full_response.encode("utf-8", errors="replace")
        response_bytes = len(encoded)
        truncated = False

        if max_bytes > 0 and response_bytes > max_bytes:
            encoded = encoded[:max_bytes]
            truncated = True

        preview_question = None
        if question:
            preview_question = question.strip()
            if len(preview_question) > 200:
                preview_question = preview_question[:200] + "..."

        metadata = {
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id,
            "attempt": attempt_index + 1,
            "question": preview_question,
            "message_count": message_count,
            "parsed_message_count": parsed_message_count,
            "failed_parse_count": failed_parse_count,
            "elapsed_seconds": round(elapsed_time, 3),
            "response_bytes": response_bytes,
            "truncated": truncated,
            "stream_error": stream_error,
        }

        try:
            header = json.dumps(metadata, ensure_ascii=False, indent=2)
            body = encoded.decode("utf-8", errors="replace")

            with target_path.open("w", encoding="utf-8") as fp:
                fp.write(header)
                fp.write("\n\n")
                fp.write(body)

            logger.info(f"Raw SSE response saved to {target_path} (trace_id={trace_id})")
            return target_path
        except Exception as exc:
            logger.error(f"Failed to persist raw SSE response: {exc}")
            return None

    def _is_token_expired(self) -> bool:
        """检查token是否过期"""
        if not self.config.token_updated_at or not self.config.token_valid_time:
            return True
        
        expired_time = self.config.token_updated_at + timedelta(seconds=self.config.token_valid_time)
        return datetime.now() > expired_time

    def _parse_user_id_from_cookies(self) -> Optional[str]:
        """从IMA_X_IMA_COOKIE中解析IMA-UID"""
        try:
            uid_pattern = r"IMA-UID=([^;]+)"
            match = re.search(uid_pattern, self.config.x_ima_cookie)
            if match:
                return match.group(1)

            user_id_pattern = r"user_id=([a-f0-9]{16})"
            if self.config.cookies:
                match = re.search(user_id_pattern, self.config.cookies)
                if match:
                    return match.group(1)
        except Exception as e:
            logger.warning(f"解析user_id失败: {e}")
        return None

    def _parse_refresh_token_from_cookies(self) -> Optional[str]:
        """从IMA_X_IMA_COOKIE中解析IMA-REFRESH-TOKEN"""
        try:
            refresh_token_pattern = r"IMA-REFRESH-TOKEN=([^;]+)"
            match = re.search(refresh_token_pattern, self.config.x_ima_cookie)
            if match:
                token = unquote(match.group(1))
                logger.info(f"成功从 x_ima_cookie 解析 IMA-REFRESH-TOKEN (长度: {len(token)})")
                return token
            
            logger.warning("在 x_ima_cookie 中未找到 IMA-REFRESH-TOKEN")
            
            token_pattern = r"IMA-TOKEN=([^;]+)"
            match = re.search(token_pattern, self.config.x_ima_cookie)
            if match:
                token = unquote(match.group(1))
                logger.warning(f"使用 IMA-TOKEN 作为 refresh_token（长度: {len(token)}）")
                return token

            if self.config.cookies:
                refresh_token_pattern = r"refresh_token=([^;]+)"
                match = re.search(refresh_token_pattern, self.config.cookies)
                if match:
                    token = unquote(match.group(1))
                    logger.info(f"成功从 cookies 解析 refresh_token")
                    return token
            
            logger.warning("未能从任何来源解析到 refresh_token")
        except Exception as e:
            logger.error(f"解析 refresh_token 失败: {e}\n{traceback.format_exc()}")
        return None

    async def refresh_token(self) -> bool:
        """刷新访问令牌"""
        logger.info("🔄 开始刷新 Token")
        
        if not self.config.user_id or not self.config.refresh_token:
            logger.info("从 cookies 中解析 user_id 和 refresh_token")
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
            
            # 构建请求头 - 添加 x-ima-bkn
            refresh_headers = {
                "accept": "*/*",
                "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                "content-type": "application/json",
                "from_browser_ima": "1",
                "x-ima-cookie": self.config.x_ima_cookie,
                "x-ima-bkn": self.config.x_ima_bkn,
                "referer": "https://ima.qq.com/wikis"
            }
            
            request_body = refresh_request.model_dump()

            async with session.post(
                refresh_url,
                json=request_body,
                headers=refresh_headers
            ) as response:
                response_text = await response.text()
                if response.status == 200:
                    try:
                        response_data = await response.json()
                        refresh_response = TokenRefreshResponse(**response_data)

                        if refresh_response.code == 0 and refresh_response.token:
                            # 更新token信息
                            self.config.current_token = refresh_response.token
                            self.config.token_valid_time = int(refresh_response.token_valid_time or "7200")
                            self.config.token_updated_at = datetime.now()

                            logger.info(f"✅ Token刷新成功 (有效期: {self.config.token_valid_time}秒)")
                            return True
                        else:
                            logger.warning("=" * 60)
                            logger.warning(f"Token刷新失败")
                            logger.warning(f"  响应代码: {refresh_response.code}")
                            logger.warning(f"  错误信息: {refresh_response.msg}")
                            # 尝试从原始响应数据中获取更多错误信息
                            if 'type' in response_data:
                                logger.warning(f"  响应类型: {response_data['type']}")
                            if 'caused_by' in response_data:
                                logger.warning(f"  引起原因: {response_data['caused_by']}")
                            logger.warning("=" * 60)
                            return False
                    except json.JSONDecodeError as je:
                        logger.error(f"无法解析响应为 JSON: {je}")
                        logger.error(f"原始响应: {response_text[:200]}")
                        return False
                else:
                    logger.error("=" * 60)
                    logger.error(f"Token刷新请求失败")
                    logger.error(f"  状态码: {response.status}")
                    logger.error(f"  响应内容: {response_text[:200]}")
                    logger.error("=" * 60)
                    return False

        except Exception as e:
            logger.error(f"Token刷新异常: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            return False

    async def ensure_valid_token(self) -> bool:
        """确保token有效，如果过期则刷新"""
        if self._is_token_expired():
            if self.config.refresh_token and self.config.user_id:
                logger.info("Token已过期，尝试刷新...")
                return await self.refresh_token()
            else:
                logger.info("尝试从cookies中解析refresh_token并主动刷新...")
                self.config.user_id = self._parse_user_id_from_cookies()
                self.config.refresh_token = self._parse_refresh_token_from_cookies()
                
                if self.config.refresh_token and self.config.user_id:
                    logger.info("成功从cookies中解析凭据，开始刷新token...")
                    return await self.refresh_token()
                else:
                    logger.warning("无法从cookies中解析refresh_token，将使用原始cookies")
                    return True

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
        x_ima_cookie = self.config.x_ima_cookie
        
        if self.config.current_token:
            x_ima_cookie = re.sub(
                r'IMA-TOKEN=[^;]+',
                f'IMA-TOKEN={self.config.current_token}',
                x_ima_cookie
            )
            
            if 'IMA-TOKEN=' not in x_ima_cookie:
                x_ima_cookie = x_ima_cookie + f'; IMA-TOKEN={self.config.current_token}'
        
        headers = {
            "x-ima-cookie": x_ima_cookie,
            "from_browser_ima": "1",
            "extension_version": "999.999.999",
            "x-ima-bkn": self.config.x_ima_bkn,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            "accept": "application/json" if for_init_session else "text/event-stream",
            "content-type": "application/json",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "sec-ch-ua": '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

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
                keepalive_timeout=60,
                enable_cleanup_closed=True,
            )

            timeout = aiohttp.ClientTimeout(
                total=min(self.config.timeout, 300),
                sock_read=180,
                connect=30,
                sock_connect=30,
            )

            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                cookies=self._parse_cookies(self.config.cookies or ""),
                headers=self._build_headers(for_init_session),
                trust_env=True,
                read_bufsize=5 * 2**20,
                auto_decompress=True,
            )

        return self.session

    async def close(self):
        """关闭客户端会话"""
        if self.session and not self.session.closed:
            await self.session.close()

    def _generate_session_id(self) -> str:
        """生成会话 ID"""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=24))

    def _generate_temp_uskey(self) -> str:
        """生成临时 uskey"""
        return base64.b64encode(secrets.token_bytes(32)).decode('utf-8')

    def _build_request(self, question: str) -> IMARequest:
        """构建 IMA API 请求"""
        session_id = self.current_session_id or self._generate_session_id()
        uskey = self._generate_temp_uskey()

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
            if line.startswith('data: '):
                data = line[6:]
            elif line.startswith(('event: ', 'id: ')):
                return None
            else:
                data = line

            if not data or data == '[DONE]' or not data.strip():
                return None

            json_data = json.loads(data)

            if 'msgs' in json_data and isinstance(json_data['msgs'], list):
                for msg in json_data['msgs']:
                    if isinstance(msg, dict) and 'content' in msg:
                        content = msg.get('content', '')
                        if content:
                            return TextMessage(
                                type=MessageType.TEXT,
                                content=content,
                                text=content,
                                raw=data
                            )
                return None

            if 'content' in json_data:
                content = json_data['content']
                if isinstance(content, str) and content:
                    return TextMessage(
                        type=MessageType.TEXT,
                        content=content,
                        text=content,
                        raw=data
                    )

            if 'Text' in json_data and isinstance(json_data['Text'], str):
                return TextMessage(
                    type=MessageType.TEXT,
                    content=json_data['Text'],
                    text=json_data['Text'],
                    raw=data
                )

            if 'type' in json_data and json_data['type'] == 'knowledgeBase':
                if 'content' not in json_data:
                    json_data['content'] = json_data.get('processing', '知识库搜索中...')
                return KnowledgeBaseMessage(**json_data)

            if 'question' in json_data and 'answer' in json_data:
                answer = json_data.get('answer', '')
                if answer:
                    return TextMessage(
                        type=MessageType.TEXT,
                        content=answer,
                        text=answer,
                        raw=data
                    )

            return IMAMessage(
                type=MessageType.SYSTEM,
                content=str(json_data),
                raw=data
            )

        except (json.JSONDecodeError, KeyError, ValueError):
            raise

    async def _process_sse_stream(
        self,
        response: aiohttp.ClientResponse,
        *,
        trace_id: str,
        attempt_index: int,
        question: Optional[str],
    ) -> AsyncGenerator[IMAMessage, None]:
        """处理 SSE 流"""
        buffer = ""
        full_response = ""
        message_count = 0
        parsed_message_count = 0
        failed_parse_count = 0
        initial_timeout = 180
        chunk_timeout = 120
        last_data_time = asyncio.get_event_loop().time()
        start_time = asyncio.get_event_loop().time()
        has_received_data = False
        sample_chunks = []
        stream_error: Optional[str] = None

        try:
            logger.debug(f"🔄 [SSE流] 开始读取 (trace_id={trace_id})")
            async for chunk in response.content:
                current_time = asyncio.get_event_loop().time()

                timeout_threshold = chunk_timeout if has_received_data else initial_timeout
                elapsed_since_last_data = current_time - last_data_time
                
                if elapsed_since_last_data > timeout_threshold:
                    stream_error = f"Timeout after {elapsed_since_last_data:.1f}s with {message_count} chunks"
                    break

                if chunk:
                    has_received_data = True
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
                            logger.warning(f"Chunk {message_count} 解码失败")

                    buffer += chunk_str
                    full_response += chunk_str

                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            try:
                                message = self._parse_sse_message(line)
                                if message:
                                    parsed_message_count += 1
                                    yield message
                            except (json.JSONDecodeError, KeyError, ValueError):
                                failed_parse_count += 1


        except asyncio.TimeoutError:
            if has_received_data and parsed_message_count > 0:
                stream_error = None
            else:
                stream_error = "SSE timeout"
                logger.error(f"❌ [SSE流] 超时错误（未收到数据）, trace_id={trace_id}")
        except aiohttp.ClientPayloadError as exc:
            stream_error = f"SSE payload error: {exc}"
            logger.error(f"❌ [SSE流] ClientPayloadError: {exc}, trace_id={trace_id}")
        except Exception as exc:
            stream_error = f"SSE exception: {exc}"
            logger.error(f"❌ [SSE流] 未知异常: {type(exc).__name__}: {exc}, trace_id={trace_id}\n{traceback.format_exc()}")
        finally:
            # 确保响应被正确关闭
            if not response.closed:
                response.close()

            elapsed_time = asyncio.get_event_loop().time() - start_time
            self._persist_raw_response(
                trace_id=trace_id,
                attempt_index=attempt_index,
                question=question,
                full_response=full_response,
                message_count=message_count,
                parsed_message_count=parsed_message_count,
                failed_parse_count=failed_parse_count,
                elapsed_time=elapsed_time,
                stream_error=stream_error,
            )

        # 处理剩余的缓冲区内容
        if buffer.strip():
            remaining_lines = buffer.strip().split('\n')
            for i, line in enumerate(remaining_lines):
                line = line.strip()
                if line:
                    try:
                        message = self._parse_sse_message(line)
                        if message:
                            parsed_message_count += 1
                            yield message
                    except (json.JSONDecodeError, KeyError, ValueError):
                        failed_parse_count += 1

        if message_count < 100 or not has_received_data:
            try:
                if full_response.strip():
                    response_data = json.loads(full_response.strip())
                    messages = self._extract_messages_from_response(response_data)
                    for message in messages:
                        yield message

            except json.JSONDecodeError:
                if full_response:
                    lines = full_response.split('\n')
                    for i, line in enumerate(lines):
                        line = line.strip()
                        if line and line != '[DONE]':
                            message = self._parse_sse_message(line)
                            if message:
                                parsed_message_count += 1
                                yield message
                            else:
                                failed_parse_count += 1

        elapsed_time = asyncio.get_event_loop().time() - start_time
        
        logger.info("=" * 80)
        logger.info(f"✅ [SSE流] 处理完成 (trace_id={trace_id})")
        logger.info(f"  收到数据块: {message_count} 个, 成功解析: {parsed_message_count} 条, 失败: {failed_parse_count} 次")
        logger.info(f"  响应大小: {len(full_response)} 字节, 耗时: {elapsed_time:.1f} 秒")
        if stream_error:
            logger.info(f"  流错误: {stream_error}")
        logger.info("=" * 80)

        if message_count > 100 and parsed_message_count < 5:
            logger.error(f"严重: 收到 {message_count} 个chunk但只解析出 {parsed_message_count} 条消息，"
                        f"解析率 {(parsed_message_count/message_count*100):.1f}%")
            logger.debug(f"前10个chunk样本: {sample_chunks}")

    def _extract_messages_from_response(self, response_data: Dict[str, Any]) -> List[IMAMessage]:
        """从完整响应中提取消息"""
        messages = []

        try:
            if 'msgs' in response_data and isinstance(response_data['msgs'], list):
                msgs_list = response_data['msgs']
                if msgs_list:
                    last_msg = msgs_list[-1]
                    if isinstance(last_msg, dict):
                        if last_msg.get('type') == 3:
                            qa_content = last_msg.get('content', {})
                            if isinstance(qa_content, dict):
                                answer = qa_content.get('answer', '')
                                if isinstance(answer, str) and answer:
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
                                            messages.append(TextMessage(
                                                type=MessageType.TEXT,
                                                content=answer,
                                                text=answer,
                                                raw=str(last_msg)
                                            ))
                                    except json.JSONDecodeError:
                                        messages.append(TextMessage(
                                            type=MessageType.TEXT,
                                            content=answer,
                                            text=answer,
                                            raw=str(last_msg)
                                        ))

                                context_refs = qa_content.get('context_refs', '')
                                if context_refs:
                                    try:
                                        context_data = json.loads(context_refs)
                                        if isinstance(context_data, dict):
                                            ref_text = "\n\n📚 参考资料:\n"
                                            if 'medias' in context_data and isinstance(context_data['medias'], list):
                                                for i, media in enumerate(context_data['medias'][:5], 1):
                                                    title = media.get('title', f'资料{i}')
                                                    intro = media.get('introduction', '')
                                                    if intro:
                                                        intro = intro[:150] + "..." if len(intro) > 150 else intro
                                                        ref_text += f"{i}. {title}\n   {intro}\n"
                                                    else:
                                                        ref_text += f"{i}. {title}\n"

                                            if context_data.get('medias'):
                                                messages.append(TextMessage(
                                                    type=MessageType.TEXT,
                                                    content=ref_text,
                                                    text=ref_text,
                                                    raw=str(last_msg)
                                                ))
                                    except json.JSONDecodeError:
                                        messages.append(TextMessage(
                                            type=MessageType.TEXT,
                                            content=f"\n\n📚 参考资料:\n{context_refs}",
                                            text=f"\n\n📚 参考资料:\n{context_refs}",
                                            raw=str(last_msg)
                                        ))

            logger.info(f"从响应中提取了 {len(messages)} 条消息")
            return messages

        except Exception as e:
            logger.error(f"提取消息时出错: {e}")
            messages.append(IMAMessage(
                type=MessageType.SYSTEM,
                content=str(response_data),
                raw=str(response_data)
            ))
            return messages

    async def init_session(self, knowledge_base_id: Optional[str] = None) -> str:
        """初始化会话"""
        kb_id = knowledge_base_id or getattr(self.config, 'knowledge_base_id', '7305806844290061')

        logger.info(f"🔄 初始化会话 (知识库: {kb_id})")
        if not await self.ensure_valid_token():
            logger.error("❌ 无法获取有效的访问令牌")
            raise ValueError("Authentication failed - unable to obtain valid token")
        
        session = await self._get_session(for_init_session=True)

        init_request = InitSessionRequest(
            envInfo=EnvInfo(
                robotType=5,
                interactType=0
            ),
            byKeyword=kb_id,
            relatedUrl=kb_id,
            sceneType=1,
            msgsLimit=0,
            forbidAutoAddToHistoryList=True,
            knowledgeBaseInfoWithFolder=KnowledgeBaseInfoWithFolder(
                knowledge_base_id=kb_id,
                folder_ids=[]
            )
        )
        
        url = f"{self.base_url}{self.init_session_endpoint}"
        request_json = init_request.model_dump()

        try:
            async with session.post(
                url,
                json=request_json,
                headers={"content-type": "application/json"}
            ) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logger.error(f"初始化会话失败，HTTP状态码: {response.status}")
                    logger.error(f"响应内容: {response_text}")
                    raise ValueError(f"init_session HTTP错误 {response.status}: {response_text[:500]}")
                
                response.raise_for_status()

                response_data = await response.json()
                init_response = InitSessionResponse(**response_data)

                if init_response.code == 0 and init_response.session_id:
                    self.current_session_id = init_response.session_id
                    self.session_initialized = True
                    logger.info(f"✅ 会话初始化成功 (session_id: {self.current_session_id[:16]}...)")
                    return self.current_session_id
                else:
                    logger.error(f"❌ 会话初始化失败 (code: {init_response.code}): {init_response.msg}")
                    raise ValueError(f"Session initialization failed (code: {init_response.code}): {init_response.msg}")

        except aiohttp.ClientError as e:
            logger.error(f"会话初始化HTTP请求失败: {e}")
            raise
        except Exception as e:
            logger.error(f"会话初始化异常: {e}")
            raise

    async def ask_question(self, question: str) -> AsyncGenerator[IMAMessage, None]:
        """向 IMA 询问问题"""
        logger.debug(f"🔍 ask_question 被调用 (session: {self.current_session_id[:16] if self.current_session_id else 'None'}...)")
        
        if not question.strip():
            raise ValueError("Question cannot be empty")

        # 确保token有效
        if not await self.ensure_valid_token():
            logger.error("❌ [诊断] 无法获取有效的访问令牌")
            raise ValueError("Authentication failed - unable to obtain valid token")

        # 每次调用都初始化新会话，实现上下文隔离
        logger.debug("🔄 初始化新会话（上下文隔离）")
        
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
        
        # 重置会话状态
        self.current_session_id = None
        self.session_initialized = False
        
        try:
            await self.init_session()
        except Exception as init_error:
            logger.error(f"❌ [诊断] 会话初始化失败: {init_error}")
            logger.error("  这可能是导致 'No valid session ID provided' 错误的原因")
            raise

        session = await self._get_session()
        request_data = self._build_request(question)

        url = f"{self.base_url}{self.api_endpoint}"
        request_json = request_data.model_dump()

        logger.debug(f"请求URL: {url}")
        logger.debug(f"请求参数: {json.dumps(request_json, ensure_ascii=False, indent=2)}")

        # 生成trace_id用于跟踪
        trace_id = str(uuid.uuid4())[:8]
        logger.debug(f"本次请求trace_id: {trace_id}")

        response = None
        try:
            logger.debug(f"发送问题: {question[:50]}...")
            
            response = await session.post(
                url,
                json=request_json,
                headers={"content-type": "application/json"}
            )

            # 检查响应状态
            if response.status != 200:
                response_text = await response.text()
                logger.error(f"❌ [诊断] HTTP请求失败，状态码: {response.status}")
                logger.error(f"  响应内容: {response_text[:500]}...")
                
                # 特别检查 400 错误和 session ID 相关的问题
                if response.status == 400:
                    logger.error("=" * 80)
                    logger.error("🚨 [诊断] 收到 HTTP 400 错误 - 详细诊断信息:")
                    logger.error("  可能的原因:")
                    logger.error("    1. session_id 无效或已过期")
                    logger.error("    2. 认证信息（cookies/headers）无效")
                    logger.error("    3. 请求参数格式错误")
                    logger.error(f"  当前使用的 session_id: {self.current_session_id}")
                    logger.error(f"  会话初始化状态: {self.session_initialized}")
                    logger.error(f"  HTTP session 对象: {self.session}")
                    logger.error(f"  HTTP session 是否关闭: {self.session.closed if self.session else 'N/A'}")
                    logger.error(f"  Token 是否存在: {bool(self.config.current_token)}")
                    logger.error(f"  Token 更新时间: {self.config.token_updated_at}")
                    logger.error("=" * 80)
                
                raise ValueError(f"HTTP请求失败: {response.status} - {response_text[:200]}")

            # 检查响应类型
            content_type = response.headers.get('content-type', '')
            logger.debug(f"响应类型: {content_type}, 状态码: {response.status}")

            if 'text/event-stream' not in content_type:
                # 读取响应内容进行诊断
                response_text = await response.text()
                logger.error(f"意外的响应类型: {content_type}")
                
                if not response_text.strip():
                    logger.error("收到了空的错误响应内容。")
                    raise ValueError(f"Expected SSE response, got {content_type} with empty body. 可能原因: 1) 认证信息错误 2) 请求参数问题 3) API端点变更")

                logger.error(f"响应内容 (前1000字符): {response_text[:1000]}")

                # 尝试解析JSON错误响应
                try:
                    error_data = json.loads(response_text)
                    error_msg = error_data.get('msg', '未知错误')
                    error_code = error_data.get('code', 'N/A')
                    logger.error(f"API错误响应 (code: {error_code}): {error_msg}")
                    logger.debug(f"完整错误详情: {json.dumps(error_data, ensure_ascii=False, indent=2)}")
                    raise ValueError(f"API返回错误 (code: {error_code}): {error_msg}")
                except json.JSONDecodeError:
                    logger.error("无法将错误响应解析为JSON。")
                    logger.error(f"原始响应内容: {response_text}")
                    raise ValueError(f"预期的SSE响应，但收到 {content_type}。响应无法解析为JSON: {response_text[:200]}")

            # 处理流式响应
            message_count = 0
            async for message in self._process_sse_stream(
                response,
                trace_id=trace_id,
                attempt_index=0,
                question=question
            ):
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
            "401",
            "Expected SSE response",  # 服务器返回非SSE响应通常意味着会话/认证失败
        ]

        error_lower = error_str.lower()
        return any(pattern.lower() in error_lower for pattern in login_expired_patterns)

    async def ask_question_complete(self, question: str) -> List[IMAMessage]:
        """获取完整的问题回答 - 支持自动 token 刷新重试"""
        messages = []
        max_retries = 2  # 最大重试次数
        
        # 生成主trace_id用于整个请求
        main_trace_id = str(uuid.uuid4())[:8]
        logger.info(f"🚀 开始问答 (trace_id={main_trace_id}): {question[:50]}...")

        for attempt in range(max_retries + 1):  # 总共尝试 max_retries + 1 次
            logger.debug(f"📍 尝试 {attempt + 1}/{max_retries + 1}")
            try:
                async for message in self.ask_question(question):
                    messages.append(message)
                    logger.debug(f"  收到消息 #{len(messages)}: {type(message).__name__}")

                # 如果成功获取到消息，直接返回
                if messages:
                    logger.info(f"✅ 问答完成 ({len(messages)}条消息)")
                    break
                else:
                    logger.warning(f"⚠️ [完整问答] 未获取到任何消息，尝试次数: {attempt + 1}/{max_retries + 1}")

            except Exception as e:
                error_str = str(e)
                logger.error("=" * 80)
                logger.error(f"❌ [完整问答] 尝试 {attempt + 1}/{max_retries + 1} 失败")
                logger.error(f"  异常类型: {type(e).__name__}")
                logger.error(f"  异常信息: {error_str[:200]}")
                logger.error("=" * 80)

                # 检查是否是登录过期错误
                if self._is_login_expired_error(error_str):
                    if attempt < max_retries:
                        logger.info(f"🔄 认证错误，刷新token...")

                        # 尝试刷新 token
                        refresh_success = await self.refresh_token()
                        if refresh_success:
                            logger.info("✅ Token刷新成功，重试中...")
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
                            logger.error("❌ [完整问答] Token刷新失败，停止重试")
                            break  # 刷新失败，直接退出循环，不再重试
                    else:
                        logger.error(f"❌ [完整问答] 已达最大重试次数 ({max_retries})，停止重试")
                        break  # 达到最大重试次数，直接退出循环
                else:
                    # 如果不是登录过期错误，检查是否应该重试
                    if attempt < max_retries:
                        logger.info(f"🔄 [完整问答] 非认证错误，延迟1秒后重试...")
                        logger.info(f"  错误摘要: {error_str[:100]}")
                        # 重置消息列表，准备重新尝试
                        messages = []
                        # 短暂延迟后重试
                        await asyncio.sleep(1)
                        continue
                    else:
                        logger.error(f"❌ [完整问答] 已达最大重试次数 ({max_retries})，停止重试")
                        break  # 达到最大重试次数，直接退出循环

        # 如果循环结束但没有消息，添加错误消息
        if not messages:
            logger.error("=" * 80)
            logger.error(f"❌ [完整问答] 所有尝试均失败，未获取到任何消息")
            logger.error(f"  main_trace_id: {main_trace_id}")
            logger.error("=" * 80)
            error_message = IMAMessage(
                type=MessageType.SYSTEM,
                content=f"获取回答失败: 所有 {max_retries + 1} 次尝试均失败",
                raw="All retries exhausted"
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

        logger.debug(f"最终响应内容长度: {len(final_result)}")
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

  
