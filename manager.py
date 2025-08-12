"""
Twitter交互管理器 - 集成twikit与AccountsPool

该模块实现了TwitterInteractionManager类，用于将twikit的交互功能与现有的AccountsPool无缝集成。
提供发帖、转推和关注用户的核心交互功能，同时利用AccountsPool的账户管理、代理和错误处理能力。
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import httpx
from social_x.twikit.twikit.client.client import Client as TwikitClient
from social_x.twikit.twikit.errors import (
    TooManyRequests,
    AccountSuspended,
    AccountLocked,
    Unauthorized,
    Forbidden,
    TwitterException
)
from social_x.twikit.twikit.tweet import Tweet
from social_x.twikit.twikit.user import User

from social_x.twscrape.accounts_pool import AccountsPool
from social_x.twscrape.account import Account

logger = logging.getLogger(__name__)


class TwitterInteractionManager:
    """
    Twitter交互管理器
    
    集成twikit与AccountsPool，提供稳定可靠的Twitter交互功能。
    支持发帖、转推和关注用户，具备智能错误处理和账户状态管理。
    """
    
    def __init__(self, accounts_pool: AccountsPool):
        """
        初始化Twitter交互管理器
        
        Args:
            accounts_pool: AccountsPool实例，用于账户管理
        """
        self.accounts_pool = accounts_pool
        logger.info("TwitterInteractionManager初始化完成")
    
    async def _get_twikit_client(self, account: Account) -> TwikitClient:
        """
        根据Account对象创建配置好的twikit.Client实例
        
        Args:
            account: 从AccountsPool获取的Account对象
            
        Returns:
            配置好的twikit.Client实例
            
        Raises:
            ValueError: 当account缺少必要的cookies时
        """
        if not account.cookies:
            raise ValueError(f"Account {account.username} 缺少cookies信息")
        
        # 创建twikit客户端
        client = TwikitClient(
            language='zh-CN',
            proxy=account.proxy
        )
        
        # 设置cookies
        for name, value in account.cookies.items():
            client.http.cookies.set(name, value)
        
        logger.debug(f"为账户 {account.username} 创建twikit客户端，代理: {account.proxy}")
        return client
    
    async def _handle_twikit_error(self, error: Exception, username: str):
        """
        处理twikit异常并更新AccountsPool中的账户状态
        
        Args:
            error: twikit抛出的异常
            username: 发生错误的账户用户名
        """
        logger.error(f"账户 {username} 发生twikit错误: {type(error).__name__}: {str(error)}")
        
        try:
            if isinstance(error, TooManyRequests):
                # 速率限制 - 临时锁定账户
                duration_minutes = 15  # 默认15分钟
                
                # 尝试从错误headers中解析重置时间
                if hasattr(error, 'headers') and error.headers:
                    reset_time = error.headers.get('x-rate-limit-reset')
                    if reset_time:
                        try:
                            reset_timestamp = int(reset_time)
                            current_timestamp = int(datetime.now(timezone.utc).timestamp())
                            duration_minutes = max(1, (reset_timestamp - current_timestamp) // 60)
                        except (ValueError, TypeError):
                            pass
                
                # 根据操作类型确定队列名
                queue_name = self._get_queue_name_from_error_context()
                await self.accounts_pool.ban_queue(username, queue_name, duration_minutes)
                logger.info(f"账户 {username} 因速率限制被临时锁定 {duration_minutes} 分钟")
                
            elif isinstance(error, (AccountSuspended, AccountLocked)):
                # 账户被封禁或锁定 - 永久禁用
                error_msg = f"账户状态异常: {str(error)}"
                await self.accounts_pool.mark_banned(username, error_msg)
                logger.warning(f"账户 {username} 被永久禁用: {error_msg}")
                
            elif isinstance(error, Unauthorized):
                # 凭据/授权问题 - 永久禁用
                error_msg = "凭据无效或Cookie已过期 (Invalid credentials/cookies)"
                await self.accounts_pool.mark_banned(username, error_msg)
                logger.warning(f"账户 {username} 因凭据问题被永久禁用")
                
            elif isinstance(error, Forbidden):
                # 操作权限问题 - 长时间锁定特定功能
                duration_minutes = 24 * 60  # 24小时
                queue_name = self._get_queue_name_from_error_context() + "_ops"  # 添加_ops后缀表示权限锁定
                await self.accounts_pool.ban_queue(username, queue_name, duration_minutes)
                logger.warning(f"账户 {username} 因权限问题被锁定 {duration_minutes//60} 小时")
                
            elif isinstance(error, (httpx.HTTPStatusError, httpx.RequestError)):
                # HTTP或网络错误 - 处理代理失败
                result = await self.accounts_pool.handle_proxy_failure(username)
                if result == 0:
                    logger.info(f"账户 {username} 代理切换成功")
                elif result == 1:
                    logger.error(f"账户 {username} 代理切换失败")
                else:
                    logger.debug(f"账户 {username} 网络错误，未触发代理切换")
                    
            else:
                # 其他未知错误 - 记录日志
                logger.error(f"账户 {username} 发生未知错误: {type(error).__name__}: {str(error)}")
                
        except Exception as handle_error:
            logger.error(f"处理账户 {username} 错误时发生异常: {handle_error}")
    
    def _get_queue_name_from_error_context(self) -> str:
        """
        根据当前操作上下文确定队列名称

        Returns:
            队列名称字符串
        """
        import inspect

        # 通过调用栈确定当前操作类型
        frame = inspect.currentframe()
        try:
            # 向上查找调用栈，找到公共方法
            while frame:
                frame = frame.f_back
                if frame and frame.f_code.co_name in ['create_tweet', 'retweet', 'follow_user']:
                    method_name = frame.f_code.co_name
                    if method_name == 'create_tweet':
                        return 'CreateTweet'
                    elif method_name == 'retweet':
                        return 'Retweet'
                    elif method_name == 'follow_user':
                        return 'CreateFriendship'
                    break
        finally:
            del frame

        # 默认返回通用队列名
        return "TwitterInteraction"
    
    async def create_tweet(
        self, 
        text: str, 
        media_ids: Optional[List[str]] = None, 
        username: Optional[str] = None
    ) -> Tweet:
        """
        创建推文
        
        Args:
            text: 推文内容
            media_ids: 媒体ID列表（可选）
            username: 指定使用的账户用户名（可选，默认使用default角色账户）
            
        Returns:
            创建的Tweet对象
            
        Raises:
            ValueError: 当指定的账户不可用时
            TwitterException: 当推文创建失败时
        """
        # 获取账户
        if username:
            account = await self.accounts_pool.get(username)
            if not account:
                raise ValueError(f"指定的账户 {username} 不存在")
        else:
            account = await self.accounts_pool.get_for_queue("CreateTweet", account_role="default")
            if not account:
                raise ValueError("没有可用的default角色账户")
        
        try:
            # 创建twikit客户端
            client = await self._get_twikit_client(account)
            
            # 创建推文
            tweet = await client.create_tweet(text=text, media_ids=media_ids)
            
            logger.info(f"账户 {account.username} 成功创建推文: {text[:50]}...")
            return tweet
            
        except Exception as error:
            await self._handle_twikit_error(error, account.username)
            raise
    
    async def retweet(
        self,
        tweet_id: str,
        username: Optional[str] = None
    ) -> Tweet:
        """
        转推推文

        Args:
            tweet_id: 要转推的推文ID
            username: 指定使用的账户用户名（可选，默认使用default角色账户）

        Returns:
            转推的Tweet对象

        Raises:
            ValueError: 当指定的账户不可用时
            TwitterException: 当转推失败时
        """
        # 获取账户
        if username:
            account = await self.accounts_pool.get(username)
            if not account:
                raise ValueError(f"指定的账户 {username} 不存在")
        else:
            account = await self.accounts_pool.get_for_queue("Retweet", account_role="default")
            if not account:
                raise ValueError("没有可用的default角色账户")

        try:
            # 创建twikit客户端
            client = await self._get_twikit_client(account)

            # 执行转推
            response = await client.retweet(tweet_id)

            logger.info(f"账户 {account.username} 成功转推推文: {tweet_id}")

            # twikit的retweet方法返回Response对象，但PRD要求返回Tweet对象
            # 为了符合接口要求，我们需要获取原始推文信息
            try:
                original_tweet = await client.get_tweet_by_id(tweet_id)
                return original_tweet
            except Exception as get_error:
                logger.warning(f"获取转推的原始推文失败: {get_error}")
                # 如果无法获取原始推文，抛出异常而不是返回无效对象
                raise TwitterException(f"转推成功但无法获取推文信息: {get_error}")

        except Exception as error:
            await self._handle_twikit_error(error, account.username)
            raise
    
    async def follow_user(
        self, 
        user_id: str, 
        username: Optional[str] = None
    ) -> User:
        """
        关注用户
        
        Args:
            user_id: 要关注的用户ID
            username: 指定使用的账户用户名（可选，默认使用default角色账户）
            
        Returns:
            被关注的User对象
            
        Raises:
            ValueError: 当指定的账户不可用时
            TwitterException: 当关注失败时
        """
        # 获取账户
        if username:
            account = await self.accounts_pool.get(username)
            if not account:
                raise ValueError(f"指定的账户 {username} 不存在")
        else:
            account = await self.accounts_pool.get_for_queue("CreateFriendship", account_role="default")
            if not account:
                raise ValueError("没有可用的default角色账户")
        
        try:
            # 创建twikit客户端
            client = await self._get_twikit_client(account)
            
            # 关注用户
            user = await client.follow_user(user_id)
            
            logger.info(f"账户 {account.username} 成功关注用户: {user_id}")
            return user
            
        except Exception as error:
            await self._handle_twikit_error(error, account.username)
            raise
