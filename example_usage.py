"""
TwitterInteractionManager使用示例

本文件演示如何使用TwitterInteractionManager进行Twitter交互操作。
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


async def example_create_tweet():
    """发推示例"""
    # 初始化账户池
    accounts_pool = AccountsPool()
    
    # 创建交互管理器
    interaction_manager = TwitterInteractionManager(accounts_pool)
    
    try:
        # 使用默认账户发推
        tweet = await interaction_manager.create_tweet(
            text="这是一条测试推文 #测试",
            media_ids=None  # 可以添加媒体ID列表
        )
        logger.info(f"成功发布推文: {tweet.id}")
        
        # 使用指定账户发推
        tweet2 = await interaction_manager.create_tweet(
            text="这是另一条测试推文",
            username="specific_username"  # 指定特定账户
        )
        logger.info(f"使用指定账户发布推文: {tweet2.id}")
        
    except Exception as e:
        logger.error(f"发推失败: {e}")


async def example_retweet():
    """转推示例"""
    accounts_pool = AccountsPool()
    interaction_manager = TwitterInteractionManager(accounts_pool)
    
    try:
        # 转推指定推文
        tweet_id = "1234567890123456789"  # 替换为实际的推文ID
        retweeted_tweet = await interaction_manager.retweet(tweet_id)
        logger.info(f"成功转推: {retweeted_tweet.id}")
        
    except Exception as e:
        logger.error(f"转推失败: {e}")


async def example_follow_user():
    """关注用户示例"""
    accounts_pool = AccountsPool()
    interaction_manager = TwitterInteractionManager(accounts_pool)
    
    try:
        # 关注指定用户
        user_id = "123456789"  # 替换为实际的用户ID
        user = await interaction_manager.follow_user(user_id)
        logger.info(f"成功关注用户: {user.screen_name}")
        
    except Exception as e:
        logger.error(f"关注用户失败: {e}")


async def example_batch_operations():
    """批量操作示例"""
    accounts_pool = AccountsPool()
    interaction_manager = TwitterInteractionManager(accounts_pool)
    
    # 批量发推
    tweet_texts = [
        "批量推文 1 #测试",
        "批量推文 2 #测试", 
        "批量推文 3 #测试"
    ]
    
    for i, text in enumerate(tweet_texts):
        try:
            tweet = await interaction_manager.create_tweet(text)
            logger.info(f"批量发推 {i+1}/3 成功: {tweet.id}")
            
            # 添加延迟避免速率限制
            await asyncio.sleep(10)
            
        except Exception as e:
            logger.error(f"批量发推 {i+1}/3 失败: {e}")


async def example_error_handling():
    """错误处理示例"""
    accounts_pool = AccountsPool()
    interaction_manager = TwitterInteractionManager(accounts_pool)
    
    try:
        # 尝试发布可能触发错误的推文
        tweet = await interaction_manager.create_tweet(
            text="这是一条可能触发速率限制的推文"
        )
        logger.info(f"推文发布成功: {tweet.id}")
        
    except Exception as e:
        logger.error(f"推文发布失败，错误已被处理: {e}")
        # 错误处理逻辑已在TwitterInteractionManager内部完成
        # 包括账户状态更新、锁定等操作


async def main():
    """主函数 - 运行所有示例"""
    logger.info("开始TwitterInteractionManager使用示例")
    
    # 注意：在实际使用前，请确保：
    # 1. 账户池中有可用的账户
    # 2. 账户具有有效的cookies
    # 3. 代理配置正确（如果需要）
    
    try:
        # 运行各种示例
        await example_create_tweet()
        await asyncio.sleep(5)
        
        await example_retweet()
        await asyncio.sleep(5)
        
        await example_follow_user()
        await asyncio.sleep(5)
        
        await example_batch_operations()
        await asyncio.sleep(5)
        
        await example_error_handling()
        
    except Exception as e:
        logger.error(f"示例运行失败: {e}")
    
    logger.info("TwitterInteractionManager使用示例完成")


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())
