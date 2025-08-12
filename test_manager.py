"""
TwitterInteractionManager测试文件

本文件包含TwitterInteractionManager的基本测试用例。
"""

import asyncio
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from social_x.twscrape.accounts_pool import AccountsPool
from social_x.twscrape.account import Account
from social_x.twikit.manager import TwitterInteractionManager
from social_x.twikit.twikit.errors import TooManyRequests, AccountSuspended, Unauthorized, Forbidden
from social_x.twikit.twikit.tweet import Tweet
from social_x.twikit.twikit.user import User

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestTwitterInteractionManager(unittest.IsolatedAsyncioTestCase):
    """TwitterInteractionManager测试类"""
    
    async def asyncSetUp(self):
        """测试设置"""
        # 创建模拟的AccountsPool
        self.mock_accounts_pool = AsyncMock(spec=AccountsPool)
        
        # 创建模拟的Account
        self.mock_account = Account(
            username="test_user",
            password="test_pass",
            email="test@example.com",
            email_password="email_pass",
            user_agent="test_agent",
            active=True,
            cookies={"ct0": "test_token", "auth_token": "test_auth"},
            proxy="http://proxy:8080"
        )
        
        # 创建TwitterInteractionManager实例
        self.manager = TwitterInteractionManager(self.mock_accounts_pool)
    
    async def test_init(self):
        """测试初始化"""
        self.assertIsInstance(self.manager, TwitterInteractionManager)
        self.assertEqual(self.manager.accounts_pool, self.mock_accounts_pool)
    
    @patch('social_x.twikit.manager.TwikitClient')
    async def test_get_twikit_client(self, mock_client_class):
        """测试_get_twikit_client方法"""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # 测试正常情况
        client = await self.manager._get_twikit_client(self.mock_account)
        
        # 验证客户端创建参数
        mock_client_class.assert_called_once_with(
            language='zh-CN',
            proxy=self.mock_account.proxy
        )
        
        # 验证cookies设置
        mock_client.http.cookies.set.assert_called()
        
        self.assertEqual(client, mock_client)
    
    async def test_get_twikit_client_no_cookies(self):
        """测试没有cookies的情况"""
        account_no_cookies = Account(
            username="test_user",
            password="test_pass", 
            email="test@example.com",
            email_password="email_pass",
            user_agent="test_agent",
            active=True,
            cookies={},  # 空cookies
            proxy="http://proxy:8080"
        )
        
        with self.assertRaises(ValueError) as context:
            await self.manager._get_twikit_client(account_no_cookies)
        
        self.assertIn("缺少cookies信息", str(context.exception))
    
    async def test_handle_twikit_error_rate_limit(self):
        """测试处理速率限制错误"""
        error = TooManyRequests("Rate limit exceeded")
        error.headers = {"x-rate-limit-reset": "1640995200"}  # 示例时间戳
        
        await self.manager._handle_twikit_error(error, "test_user")
        
        # 验证调用了ban_queue方法
        self.mock_accounts_pool.ban_queue.assert_called_once()
    
    async def test_handle_twikit_error_account_suspended(self):
        """测试处理账户被封禁错误"""
        error = AccountSuspended("Account suspended")
        
        await self.manager._handle_twikit_error(error, "test_user")
        
        # 验证调用了mark_banned方法
        self.mock_accounts_pool.mark_banned.assert_called_once_with(
            "test_user", 
            "账户状态异常: Account suspended"
        )
    
    async def test_handle_twikit_error_unauthorized(self):
        """测试处理未授权错误"""
        error = Unauthorized("Unauthorized")
        
        await self.manager._handle_twikit_error(error, "test_user")
        
        # 验证调用了mark_banned方法
        self.mock_accounts_pool.mark_banned.assert_called_once_with(
            "test_user",
            "凭据无效或Cookie已过期 (Invalid credentials/cookies)"
        )
    
    async def test_handle_twikit_error_forbidden(self):
        """测试处理权限禁止错误"""
        error = Forbidden("Forbidden")
        
        await self.manager._handle_twikit_error(error, "test_user")
        
        # 验证调用了ban_queue方法，时长为24小时
        self.mock_accounts_pool.ban_queue.assert_called_once()
        args = self.mock_accounts_pool.ban_queue.call_args
        self.assertEqual(args[0][2], 24 * 60)  # 24小时转换为分钟
    
    @patch('social_x.twikit.manager.TwikitClient')
    async def test_create_tweet_success(self, mock_client_class):
        """测试成功创建推文"""
        # 设置模拟
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_tweet = MagicMock(spec=Tweet)
        mock_tweet.id = "123456789"
        mock_client.create_tweet.return_value = mock_tweet
        
        self.mock_accounts_pool.get_for_queue.return_value = self.mock_account
        
        # 执行测试
        result = await self.manager.create_tweet("Test tweet")
        
        # 验证结果
        self.assertEqual(result, mock_tweet)
        self.mock_accounts_pool.get_for_queue.assert_called_once_with(
            "CreateTweet", 
            account_role="default"
        )
        mock_client.create_tweet.assert_called_once_with(
            text="Test tweet", 
            media_ids=None
        )
    
    @patch('social_x.twikit.manager.TwikitClient')
    async def test_create_tweet_with_username(self, mock_client_class):
        """测试使用指定用户名创建推文"""
        # 设置模拟
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_tweet = MagicMock(spec=Tweet)
        mock_client.create_tweet.return_value = mock_tweet
        
        self.mock_accounts_pool.get.return_value = self.mock_account
        
        # 执行测试
        result = await self.manager.create_tweet("Test tweet", username="specific_user")
        
        # 验证结果
        self.mock_accounts_pool.get.assert_called_once_with("specific_user")
        mock_client.create_tweet.assert_called_once()
    
    async def test_create_tweet_no_account(self):
        """测试没有可用账户的情况"""
        self.mock_accounts_pool.get_for_queue.return_value = None
        
        with self.assertRaises(ValueError) as context:
            await self.manager.create_tweet("Test tweet")
        
        self.assertIn("没有可用的default角色账户", str(context.exception))
    
    @patch('social_x.twikit.manager.TwikitClient')
    async def test_retweet_success(self, mock_client_class):
        """测试成功转推"""
        # 设置模拟
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_tweet = MagicMock(spec=Tweet)
        mock_tweet.id = "123456789"
        mock_client.retweet.return_value = MagicMock()
        mock_client.get_tweet_by_id.return_value = mock_tweet
        
        self.mock_accounts_pool.get_for_queue.return_value = self.mock_account
        
        # 执行测试
        result = await self.manager.retweet("123456789")
        
        # 验证结果
        self.assertEqual(result, mock_tweet)
        mock_client.retweet.assert_called_once_with("123456789")
        mock_client.get_tweet_by_id.assert_called_once_with("123456789")
    
    @patch('social_x.twikit.manager.TwikitClient')
    async def test_follow_user_success(self, mock_client_class):
        """测试成功关注用户"""
        # 设置模拟
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_user = MagicMock(spec=User)
        mock_user.screen_name = "test_user"
        mock_client.follow_user.return_value = mock_user
        
        self.mock_accounts_pool.get_for_queue.return_value = self.mock_account
        
        # 执行测试
        result = await self.manager.follow_user("123456789")
        
        # 验证结果
        self.assertEqual(result, mock_user)
        self.mock_accounts_pool.get_for_queue.assert_called_once_with(
            "CreateFriendship", 
            account_role="default"
        )
        mock_client.follow_user.assert_called_once_with("123456789")


async def run_tests():
    """运行测试"""
    logger.info("开始运行TwitterInteractionManager测试")
    
    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTwitterInteractionManager)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        logger.info("所有测试通过!")
    else:
        logger.error(f"测试失败: {len(result.failures)} 个失败, {len(result.errors)} 个错误")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(run_tests())
