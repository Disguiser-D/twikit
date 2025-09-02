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
from httpx import ConnectTimeout, ConnectError, RequestError
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
        # 获取详细错误信息
        error_details = str(error) if str(error) else "无详细描述"
        if hasattr(error, 'response') and error.response:
            error_details += f" (HTTP {error.response.status_code})"
        if hasattr(error, '__cause__') and error.__cause__:
            error_details += f" 根本原因: {str(error.__cause__)}"
        
        logger.error(f"账户 {username} 发生twikit错误: {type(error).__name__}: {error_details}")
        
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
                
            elif isinstance(error, (httpx.HTTPStatusError, httpx.RequestError, ConnectTimeout, ConnectError)):
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
                error_details = str(error) if str(error) else "无详细描述"
                if hasattr(error, 'response') and error.response:
                    error_details += f" (HTTP {error.response.status_code})"
                if hasattr(error, '__cause__') and error.__cause__:
                    error_details += f" 根本原因: {str(error.__cause__)}"
                logger.error(f"账户 {username} 发生未知错误: {type(error).__name__}: {error_details}")
                
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
                if frame and frame.f_code.co_name in ['create_tweet', 'retweet', 'reply_to_tweet', 'follow_user', 'update_profile_info']:
                    method_name = frame.f_code.co_name
                    if method_name == 'create_tweet':
                        return 'CreateTweet'
                    elif method_name == 'retweet':
                        return 'Retweet'
                    elif method_name == 'reply_to_tweet':
                        return 'CreateTweet'
                    elif method_name == 'follow_user':
                        return 'CreateFriendship'
                    elif method_name == 'update_profile_info':
                        return 'UpdateProfile'
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
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        username: Optional[str] = None
    ) -> Tweet:
        """
        转推推文

        Args:
            tweet_id: 要转推的推文ID
            text: 转推时添加的内容（可选）
                - 如果为空或None，执行普通转推
                - 如果有内容，执行引用转推（quoted retweet）
            media_ids: 媒体ID列表（仅在引用转推时有效）
            username: 指定使用的账户用户名（可选，默认使用default角色账户）

        Returns:
            转推的Tweet对象或引用推文的Tweet对象

        Raises:
            ValueError: 当指定的账户不可用时
            TwitterException: 当转推失败时
        """
        # 判断是普通转推还是引用转推
        is_quote_retweet = text is not None and text.strip()

        # 根据转推类型选择队列
        queue_name = "CreateTweet" if is_quote_retweet else "Retweet"

        # 获取账户
        if username:
            account = await self.accounts_pool.get(username)
            if not account:
                raise ValueError(f"指定的账户 {username} 不存在")
        else:
            account = await self.accounts_pool.get_for_queue(queue_name, account_role="default")
            if not account:
                raise ValueError("没有可用的default角色账户")

        try:
            # 创建twikit客户端
            client = await self._get_twikit_client(account)

            if is_quote_retweet:
                # 引用转推：使用create_tweet方法，设置attachment_url
                # 尝试多种URL格式，从最通用的开始
                attachment_urls_to_try = [
                    f"https://x.com/i/status/{tweet_id}",  # 新的通用格式
                ]

                last_error = None
                for attachment_url in attachment_urls_to_try:
                    try:
                        tweet = await client.create_tweet(
                            text=text,
                            media_ids=media_ids,
                            attachment_url=attachment_url
                        )
                        logger.info(f"账户 {account.username} 成功引用转推推文: {tweet_id}，内容: {text[:50]}..., URL: {attachment_url}")
                        return tweet
                    except Exception as create_error:
                        last_error = create_error
                        logger.warning(f"使用URL {attachment_url} 引用转推失败: {create_error}")
                        continue

                # 如果所有URL格式都失败，抛出最后一个错误
                logger.error(f"所有引用转推URL格式都失败，最后错误: {last_error}")
                raise TwitterException(f"引用转推失败: {last_error}")
            else:
                # 普通转推：使用retweet方法
                response = await client.retweet(tweet_id)
                logger.info(f"账户 {account.username} 成功转推推文: {tweet_id}")

                # 由于get_tweet_by_id可能存在解析问题，我们创建一个简化的Tweet对象
                # 或者直接返回成功信息，让调用者知道转推已完成
                from social_x.twikit.twikit.tweet import Tweet
                from social_x.twikit.twikit.user import User

                # 创建一个简化的用户对象
                simple_user = User(client, {
                    'rest_id': 'unknown',
                    'legacy': {
                        'screen_name': 'unknown',
                        'name': 'Unknown User',
                        'created_at': 'Unknown',
                        'description': '',
                        'followers_count': 0,
                        'friends_count': 0,
                        'statuses_count': 0,
                        'favourites_count': 0,
                        'listed_count': 0,
                        'verified': False,
                        'protected': False
                    }
                })

                # 创建一个简化的Tweet对象表示转推成功
                simple_tweet_data = {
                    'rest_id': tweet_id,
                    'legacy': {
                        'created_at': 'Unknown',
                        'full_text': f'Retweeted tweet {tweet_id}',
                        'lang': 'en',
                        'in_reply_to_status_id_str': None,
                        'is_quote_status': False,
                        'reply_count': 0,
                        'favorite_count': 0,
                        'favorited': False,
                        'retweet_count': 0,
                        'retweeted': True,
                        'possibly_sensitive': False,
                        'entities': {'hashtags': [], 'urls': [], 'user_mentions': [], 'symbols': []}
                    }
                }

                return Tweet(client, simple_tweet_data, simple_user)

        except Exception as error:
            await self._handle_twikit_error(error, account.username)
            raise

    async def reply_to_tweet(
        self,
        tweet_id: str,
        text: str,
        media_ids: Optional[List[str]] = None,
        username: Optional[str] = None
    ) -> Tweet:
        """
        回复推文

        Args:
            tweet_id: 要回复的推文ID
            text: 回复内容
            media_ids: 媒体ID列表（可选）
            username: 指定使用的账户用户名（可选，默认使用default角色账户）

        Returns:
            回复的Tweet对象

        Raises:
            ValueError: 当指定的账户不可用时
            TwitterException: 当回复失败时
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

            # 创建回复推文
            tweet = await client.create_tweet(
                text=text,
                media_ids=media_ids,
                reply_to=tweet_id
            )

            logger.info(f"账户 {account.username} 成功回复推文: {tweet_id}，内容: {text[:50]}...")
            return tweet

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

    async def update_profile_info(
        self,
        username: Optional[str] = None,
        **kwargs
    ) -> User:
        """
        更新用户个人资料信息
        
        Args:
            username: 指定使用的账户用户名（可选，默认使用default角色账户）
            **kwargs: 个人资料更新参数
                - name (str): 显示名称
                - description (str): 个人简介/Bio
                - location (str): 位置信息（建议使用英文城市名）
                - url (str): 个人网站链接
                - profile_link_color (str): 个人资料链接颜色（十六进制，不包含#）
                - include_entities (bool): 是否在响应中包含实体信息
                - skip_status (bool): 是否在响应中跳过状态信息
            
        Returns:
            更新后的User对象
            
        Raises:
            ValueError: 当指定的账户不可用时
            TwitterException: 当个人资料更新失败时
            
        Examples:
            # 使用指定账户更新资料
            user = await manager.update_profile_info(
                username="specific_account",
                name="Crypto Enthusiast",
                description="Building the future of Web3 🚀",
                location="New York"
            )
            
            # 使用默认账户更新资料
            user = await manager.update_profile_info(
                name="DeFi Trader",
                location="London"
            )
        """
        # 获取账户
        if username:
            account = await self.accounts_pool.get(username)
            if not account:
                raise ValueError(f"指定的账户 {username} 不存在")
        else:
            account = await self.accounts_pool.get_for_queue("UpdateProfile", account_role="default")
            if not account:
                raise ValueError("没有可用的default角色账户")
        
        try:
            # 创建twikit客户端
            client = await self._get_twikit_client(account)
            
            # 更新个人资料
            user = await client.update_profile_info(**kwargs)
            
            # 构建日志消息，显示更新的字段
            updated_fields = []
            if 'name' in kwargs:
                updated_fields.append(f"name='{kwargs['name']}'")
            if 'description' in kwargs:
                desc_preview = kwargs['description'][:50] + "..." if len(kwargs['description']) > 50 else kwargs['description']
                updated_fields.append(f"description='{desc_preview}'")
            if 'location' in kwargs:
                updated_fields.append(f"location='{kwargs['location']}'")
            if 'url' in kwargs:
                updated_fields.append(f"url='{kwargs['url']}'")
            if 'profile_link_color' in kwargs:
                updated_fields.append(f"link_color='{kwargs['profile_link_color']}'")
            
            fields_str = ", ".join(updated_fields) if updated_fields else "未知字段"
            logger.info(f"账户 {account.username} 成功更新个人资料: {fields_str}")
            return user
            
        except Exception as error:
            await self._handle_twikit_error(error, account.username)
            raise
