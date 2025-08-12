"""
TwitterInteractionManager集成测试

本文件用于测试TwitterInteractionManager与实际系统的集成。
注意：这些测试需要真实的账户和网络连接。
"""

import asyncio
import logging
from social_x.twscrape.accounts_pool import AccountsPool
from social_x.twikit.manager import TwitterInteractionManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_account_pool_integration():
    """测试与AccountsPool的集成"""
    logger.info("开始测试AccountsPool集成...")
    
    try:
        # 初始化账户池
        accounts_pool = AccountsPool()
        
        # 创建交互管理器
        manager = TwitterInteractionManager(accounts_pool)
        
        # 测试获取账户信息
        accounts = await accounts_pool.get_all()
        logger.info(f"账户池中共有 {len(accounts)} 个账户")
        
        # 检查是否有可用的default角色账户
        default_accounts = [acc for acc in accounts if acc.account_role == 'default' and acc.active]
        logger.info(f"可用的default角色账户: {len(default_accounts)} 个")
        
        if default_accounts:
            logger.info("✓ 有可用的default角色账户")
            for acc in default_accounts[:3]:  # 只显示前3个
                logger.info(f"  - {acc.username} (cookies: {'有' if acc.cookies else '无'}, proxy: {acc.proxy or '无'})")
        else:
            logger.warning("⚠ 没有可用的default角色账户")
        
        return True
        
    except Exception as e:
        logger.error(f"AccountsPool集成测试失败: {e}")
        return False


async def test_twikit_client_creation():
    """测试twikit客户端创建"""
    logger.info("开始测试twikit客户端创建...")
    
    try:
        accounts_pool = AccountsPool()
        manager = TwitterInteractionManager(accounts_pool)
        
        # 获取一个测试账户
        accounts = await accounts_pool.get_all()
        test_account = None
        
        for acc in accounts:
            if acc.active and acc.cookies:
                test_account = acc
                break
        
        if not test_account:
            logger.warning("⚠ 没有找到有效的测试账户（需要active=True且有cookies）")
            return False
        
        logger.info(f"使用测试账户: {test_account.username}")
        
        # 测试创建twikit客户端
        client = await manager._get_twikit_client(test_account)
        logger.info("✓ twikit客户端创建成功")
        
        # 检查客户端配置
        logger.info(f"  - 代理配置: {client.proxy or '无'}")
        logger.info(f"  - 语言设置: {client.language}")
        
        return True
        
    except Exception as e:
        logger.error(f"twikit客户端创建测试失败: {e}")
        return False


async def test_error_handling_simulation():
    """测试错误处理机制（模拟）"""
    logger.info("开始测试错误处理机制...")
    
    try:
        accounts_pool = AccountsPool()
        manager = TwitterInteractionManager(accounts_pool)
        
        # 模拟不同类型的错误
        from social_x.twikit.twikit.errors import TooManyRequests, Unauthorized
        
        # 测试速率限制错误处理
        rate_limit_error = TooManyRequests("Rate limit exceeded")
        rate_limit_error.headers = {"x-rate-limit-reset": "1640995200"}
        
        logger.info("模拟速率限制错误...")
        await manager._handle_twikit_error(rate_limit_error, "test_user")
        logger.info("✓ 速率限制错误处理完成")
        
        # 测试未授权错误处理
        auth_error = Unauthorized("Invalid credentials")
        logger.info("模拟未授权错误...")
        await manager._handle_twikit_error(auth_error, "test_user")
        logger.info("✓ 未授权错误处理完成")
        
        return True
        
    except Exception as e:
        logger.error(f"错误处理测试失败: {e}")
        return False


async def test_queue_name_detection():
    """测试队列名称检测"""
    logger.info("开始测试队列名称检测...")
    
    try:
        accounts_pool = AccountsPool()
        manager = TwitterInteractionManager(accounts_pool)
        
        # 测试队列名称检测
        queue_name = manager._get_queue_name_from_error_context()
        logger.info(f"检测到的队列名称: {queue_name}")
        
        # 队列名称应该是有效的字符串
        assert isinstance(queue_name, str), "队列名称应该是字符串"
        assert len(queue_name) > 0, "队列名称不能为空"
        
        logger.info("✓ 队列名称检测正常")
        return True
        
    except Exception as e:
        logger.error(f"队列名称检测测试失败: {e}")
        return False


async def test_method_signatures():
    """测试方法签名"""
    logger.info("开始测试方法签名...")
    
    try:
        accounts_pool = AccountsPool()
        manager = TwitterInteractionManager(accounts_pool)
        
        # 检查方法签名
        import inspect
        
        # 检查create_tweet方法
        create_tweet_sig = inspect.signature(manager.create_tweet)
        expected_params = ['text', 'media_ids', 'username']
        actual_params = list(create_tweet_sig.parameters.keys())
        
        for param in expected_params:
            assert param in actual_params, f"create_tweet缺少参数: {param}"
        
        # 检查retweet方法
        retweet_sig = inspect.signature(manager.retweet)
        expected_params = ['tweet_id', 'username']
        actual_params = list(retweet_sig.parameters.keys())
        
        for param in expected_params:
            assert param in actual_params, f"retweet缺少参数: {param}"
        
        # 检查follow_user方法
        follow_user_sig = inspect.signature(manager.follow_user)
        expected_params = ['user_id', 'username']
        actual_params = list(follow_user_sig.parameters.keys())
        
        for param in expected_params:
            assert param in actual_params, f"follow_user缺少参数: {param}"
        
        logger.info("✓ 所有方法签名正确")
        return True
        
    except Exception as e:
        logger.error(f"方法签名测试失败: {e}")
        return False


async def run_integration_tests():
    """运行所有集成测试"""
    logger.info("🚀 开始运行TwitterInteractionManager集成测试")
    
    tests = [
        ("AccountsPool集成", test_account_pool_integration),
        ("twikit客户端创建", test_twikit_client_creation),
        ("错误处理机制", test_error_handling_simulation),
        ("队列名称检测", test_queue_name_detection),
        ("方法签名检查", test_method_signatures),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"运行测试: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            result = await test_func()
            results.append((test_name, result))
            
            if result:
                logger.info(f"✅ {test_name} - 通过")
            else:
                logger.error(f"❌ {test_name} - 失败")
                
        except Exception as e:
            logger.error(f"❌ {test_name} - 异常: {e}")
            results.append((test_name, False))
    
    # 汇总结果
    logger.info(f"\n{'='*50}")
    logger.info("测试结果汇总")
    logger.info(f"{'='*50}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        logger.info("🎉 所有集成测试通过!")
        return True
    else:
        logger.error(f"⚠️ {total - passed} 个测试失败")
        return False


if __name__ == "__main__":
    # 运行集成测试
    success = asyncio.run(run_integration_tests())
    
    if success:
        print("\n🎉 TwitterInteractionManager集成测试全部通过!")
        exit(0)
    else:
        print("\n❌ 部分集成测试失败，请检查日志")
        exit(1)
