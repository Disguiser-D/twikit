"""
social_x.twikit - Twitter交互管理模块

该模块提供了TwitterInteractionManager类，用于集成twikit库与AccountsPool系统，
实现稳定可靠的Twitter交互功能。

主要功能：
- 发布推文 (create_tweet)
- 转推推文 (retweet)  
- 关注用户 (follow_user)
- 智能错误处理和账户状态管理
- 代理管理集成

使用示例：
    from social_x.twscrape.accounts_pool import AccountsPool
    from social_x.twikit import TwitterInteractionManager
    
    accounts_pool = AccountsPool()
    manager = TwitterInteractionManager(accounts_pool)
    
    # 发布推文
    tweet = await manager.create_tweet("Hello, Twitter!")
    
    # 转推
    retweeted = await manager.retweet("1234567890123456789")
    
    # 关注用户
    user = await manager.follow_user("123456789")
"""

from .manager import TwitterInteractionManager

__all__ = ['TwitterInteractionManager']

__version__ = '1.0.0'
__author__ = 'Social X Team'
__description__ = 'Twitter交互管理器 - 集成twikit与AccountsPool'
