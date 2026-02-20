from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Image, Text
import aiohttp
import json
import base64
import asyncio
import hashlib
from typing import Optional, List, Dict, Tuple
from datetime import datetime

@register("censor", "cengwei", "AI 敏感内容检测和撤回插件", "1.0.0")
class CensorPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # NLP API 配置
        self.nlp_api_url = None
        self.nlp_api_key = None
        
        # 防重复检测 - 保存已检测的消息哈希
        self.checked_messages = {}
        self.max_cache_size = 1000
        
    async def initialize(self):
        """初始化插件，加载 AI API 配置"""
        try:
            config = self.context.get_config_value("censor", {})
            
            # 加载 API 配置（必需）
            self.nlp_api_url = config.get("nlp_api_url", "https://api.openai.com/v1/chat/completions")
            self.nlp_api_key = config.get("nlp_api_key", "")
            
            if not self.nlp_api_key:
                logger.warning("警告: 未配置 AI API 密钥，插件无法工作")
            
            logger.info("AI 敏感内容检测插件初始化完成")
        except Exception as e:
            logger.error(f"初始化插件失败: {e}")

    @filter.normal
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息并进行 AI 检测"""
        try:
            if not self.nlp_api_key:
                return
            
            # 获取消息信息
            message_chain = event.get_messages()
            message_str = event.message_str
            
            # 防重复检测 - 检查消息哈希
            message_hash = self._get_message_hash(message_str, message_chain)
            if self._is_already_checked(message_hash):
                return
            
            # 标记为已检测
            self._mark_as_checked(message_hash)
            
            # AI 检测所有内容（文本 + 图片）
            is_sensitive, reason = await self._ai_detect(message_str, message_chain)
            
            if is_sensitive:
                sender_name = event.get_sender_name()
                logger.warning(f"[AI检测] 检测到违禁内容 - 用户: {sender_name}, 原因: {reason}")
                
                # 撤回消息
                await self._recall_message(event)
        except Exception as e:
            logger.error(f"处理消息失败: {e}")

    def _get_message_hash(self, message_str: str, message_chain: List) -> str:
        """生成消息哈希以防重复检测"""
        content = message_str
        # 加入消息链内容用于哈希
        for msg in message_chain:
            if isinstance(msg, Text):
                content += str(msg)
            elif isinstance(msg, Image):
                content += "image"
        
        return hashlib.md5(content.encode()).hexdigest()
    
    def _is_already_checked(self, message_hash: str) -> bool:
        """检查消息是否已被检测过"""
        return message_hash in self.checked_messages
    
    def _mark_as_checked(self, message_hash: str):
        """标记消息为已检测"""
        self.checked_messages[message_hash] = True
        
        # 清理过量缓存
        if len(self.checked_messages) > self.max_cache_size:
            # 移除一半的旧记录
            keys_to_remove = list(self.checked_messages.keys())[:self.max_cache_size // 2]
            for key in keys_to_remove:
                del self.checked_messages[key]

    async def _ai_detect(self, message_str: str, message_chain: List) -> Tuple[bool, str]:
        """使用 AI 检测文本和图片内容"""
        # 检查文本内容
        text_sensitive, text_reason = await self._ai_check_text(message_str)
        if text_sensitive:
            return True, text_reason
        
        # 检查图片内容
        for msg in message_chain:
            if isinstance(msg, Image):
                image_sensitive, image_reason = await self._ai_check_image(msg)
                if image_sensitive:
                    return True, image_reason
        
        return False, ""
    
    async def _ai_check_text(self, text: str) -> Tuple[bool, str]:
        """AI 检测文本内容"""
        try:
            if not text.strip():
                return False, ""
            
            headers = {
                "Authorization": f"Bearer {self.nlp_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {
                        "role": "system",
                        "content": "你是内容审核员。判断文本是否包含敏感、违禁、不适当或有害内容（色情、暴力、违法等）。只回答'YES'或'NO'，若是YES，简短说明原因。"
                    },
                    {
                        "role": "user",
                        "content": f"审核：{text}"
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 50
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.nlp_api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=8)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"].strip()
                        
                        if content.upper().startswith("YES"):
                            reason = content.split("\n")[1] if "\n" in content else "AI 检测触发"
                            return True, reason
                    else:
                        logger.warning(f"AI API 状态码: {response.status}")
            
            return False, ""
        except asyncio.TimeoutError:
            logger.warning("AI API 请求超时")
            return False, ""
        except Exception as e:
            logger.error(f"AI 检测失败: {e}")
            return False, ""
    
    async def _ai_check_image(self, image: Image) -> Tuple[bool, str]:
        """AI 检测图片内容"""
        try:
            # 获取图片数据（如果可用）
            image_url = None
            if hasattr(image, 'url'):
                image_url = image.url
            elif hasattr(image, 'path'):
                # 如果是本地文件路径，需要转换为 URL 或 base64
                image_url = image.path
            
            if not image_url:
                return False, ""
            
            headers = {
                "Authorization": f"Bearer {self.nlp_api_key}",
                "Content-Type": "application/json"
            }
            
            # 如果是 URL，直接发送；如果是路径，转换为 base64
            if image_url.startswith(('http://', 'https://')):
                image_data = {
                    "type": "image_url",
                    "image_url": {"url": image_url}
                }
            else:
                # 读取图片并转换为 base64
                try:
                    with open(image_url, 'rb') as f:
                        image_base64 = base64.b64encode(f.read()).decode('utf-8')
                    image_data = {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                    }
                except Exception as e:
                    logger.error(f"读取图片失败: {e}")
                    return False, ""
            
            payload = {
                "model": "gpt-4-vision",  # 使用视觉模型
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            image_data,
                            {
                                "type": "text",
                                "text": "这张图片是否包含敏感、违禁、不适当或有害的内容？只回答'YES'或'NO'，若是YES，简短说明。"
                            }
                        ]
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 50
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.nlp_api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"].strip()
                        
                        if content.upper().startswith("YES"):
                            reason = content.split("\n")[1] if "\n" in content else "图片含违禁内容"
                            return True, reason
            
            return False, ""
        except asyncio.TimeoutError:
            logger.warning("图片 AI 检测超时")
            return False, ""
        except Exception as e:
            logger.error(f"图片 AI 检测失败: {e}")
            return False, ""

    async def _recall_message(self, event: AstrMessageEvent):
        """撤回消息"""
        try:
            if hasattr(event, 'recall') and callable(event.recall):
                await event.recall()
                logger.info("消息已撤回")
            elif hasattr(event, 'delete') and callable(event.delete):
                await event.delete()
                logger.info("消息已删除")
            else:
                logger.warning("当前平台不支持撤回消息")
        except Exception as e:
            logger.error(f"撤回消息失败: {e}")

    async def terminate(self):
        """插件卸载"""
        logger.info("AI 敏感内容检测插件已卸载")
