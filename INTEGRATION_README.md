# TwitterInteractionManager - Twitter交互管理器

## 概述

TwitterInteractionManager是一个集成了`twikit`库与现有`AccountsPool`系统的Twitter交互管理器。它提供了稳定可靠的Twitter交互功能，包括发帖、转推和关注用户，同时利用AccountsPool的强大账户管理、代理和错误处理能力。

## 功能特性

- **发帖功能**: 支持文本推文和媒体推文
- **转推功能**: 转推指定的推文
- **关注功能**: 关注指定的用户
- **智能账户选择**: 支持指定账户或自动选择default角色账户
- **精细化错误处理**: 自动处理各种Twitter API错误并更新账户状态
- **代理管理**: 集成AccountsPool的代理管理功能
- **速率限制处理**: 自动处理速率限制并临时锁定账户

## 安装依赖

确保已安装必要的依赖：

```bash
# 安装twikit（如果尚未安装）
pip install twikit

# 确保项目依赖已安装
pip install -r requirements.txt
```

## 快速开始

### 基本使用

```python
import asyncio
from social_x.twscrape.accounts_pool import AccountsPool
from social_x.twikit.manager import TwitterInteractionManager

async def main():
    # 初始化账户池
    accounts_pool = AccountsPool()
    
    # 创建交互管理器
    interaction_manager = TwitterInteractionManager(accounts_pool)
    
    # 发布推文
    tweet = await interaction_manager.create_tweet("Hello, Twitter!")
    print(f"推文发布成功: {tweet.id}")
    
    # 转推
    retweeted = await interaction_manager.retweet("1234567890123456789")
    print(f"转推成功: {retweeted.id}")
    
    # 关注用户
    user = await interaction_manager.follow_user("123456789")
    print(f"关注成功: {user.screen_name}")

asyncio.run(main())
```

### 指定账户使用

```python
# 使用指定账户发推
tweet = await interaction_manager.create_tweet(
    text="使用指定账户发推",
    username="specific_username"
)

# 使用指定账户转推
retweeted = await interaction_manager.retweet(
    tweet_id="1234567890123456789",
    username="specific_username"
)

# 使用指定账户关注
user = await interaction_manager.follow_user(
    user_id="123456789",
    username="specific_username"
)
```

### 媒体推文

```python
# 发布带媒体的推文
tweet = await interaction_manager.create_tweet(
    text="这是一条带图片的推文",
    media_ids=["media_id_1", "media_id_2"]
)
```

## API参考

### TwitterInteractionManager

#### 构造函数

```python
TwitterInteractionManager(accounts_pool: AccountsPool)
```

- `accounts_pool`: AccountsPool实例，用于账户管理

#### 方法

##### create_tweet

```python
async def create_tweet(
    text: str, 
    media_ids: Optional[List[str]] = None, 
    username: Optional[str] = None
) -> Tweet
```

创建推文。

**参数:**
- `text`: 推文内容
- `media_ids`: 媒体ID列表（可选）
- `username`: 指定使用的账户用户名（可选）

**返回:** Tweet对象

##### retweet

```python
async def retweet(
    tweet_id: str, 
    username: Optional[str] = None
) -> Tweet
```

转推推文。

**参数:**
- `tweet_id`: 要转推的推文ID
- `username`: 指定使用的账户用户名（可选）

**返回:** Tweet对象

##### follow_user

```python
async def follow_user(
    user_id: str, 
    username: Optional[str] = None
) -> User
```

关注用户。

**参数:**
- `user_id`: 要关注的用户ID
- `username`: 指定使用的账户用户名（可选）

**返回:** User对象

## 错误处理

TwitterInteractionManager实现了精细化的错误处理机制：

### 速率限制 (TooManyRequests)
- 自动解析重置时间或使用默认15分钟
- 临时锁定对应操作队列
- 不影响账户的其他功能

### 账户问题 (AccountSuspended/AccountLocked)
- 永久禁用账户
- 记录详细错误信息
- 防止继续使用无效账户

### 凭据问题 (Unauthorized)
- 永久禁用账户
- 标记为"凭据无效或Cookie已过期"
- 提示需要重新登录

### 权限问题 (Forbidden)
- 长时间锁定特定功能（24小时）
- 使用特殊队列名（如"CreateFriendship_ops"）
- 避免重复尝试被禁止的操作

### 网络问题 (HTTP/网络错误)
- 自动触发代理切换机制
- 利用AccountsPool的代理管理功能
- 提高连接成功率

## 配置要求

### 账户池配置

确保AccountsPool中的账户具有：

1. **有效的cookies**: 包含必要的认证信息
2. **正确的代理配置**: 如果需要使用代理
3. **适当的account_role**: 默认操作使用"default"角色

### 账户角色

- `default`: 用于默认的交互操作
- 其他角色可根据需要自定义

## 最佳实践

### 1. 错误处理

```python
try:
    tweet = await interaction_manager.create_tweet("测试推文")
    logger.info(f"推文发布成功: {tweet.id}")
except Exception as e:
    logger.error(f"推文发布失败: {e}")
    # 错误已被自动处理，账户状态已更新
```

### 2. 批量操作

```python
# 添加适当的延迟避免速率限制
for text in tweet_texts:
    try:
        tweet = await interaction_manager.create_tweet(text)
        await asyncio.sleep(10)  # 10秒延迟
    except Exception as e:
        logger.error(f"发推失败: {e}")
```

### 3. 账户管理

```python
# 定期检查账户状态
accounts = await accounts_pool.get_all()
for account in accounts:
    if not account.active:
        logger.warning(f"账户 {account.username} 已被禁用: {account.error_msg}")
```

## 注意事项

1. **账户准备**: 确保账户池中有足够的可用账户
2. **速率限制**: Twitter有严格的速率限制，请合理控制操作频率
3. **内容政策**: 确保发布的内容符合Twitter的社区准则
4. **监控日志**: 密切关注日志输出，及时发现和处理问题
5. **账户轮换**: 合理使用多个账户分散操作压力

## 故障排除

### 常见问题

1. **"没有可用的default角色账户"**
   - 检查账户池中是否有active=True且account_role='default'的账户
   - 确认账户未被锁定或禁用

2. **"Account xxx 缺少cookies信息"**
   - 检查账户的cookies字段是否为空
   - 重新登录账户获取有效cookies

3. **代理连接失败**
   - 检查代理配置是否正确
   - 确认代理服务器可用性

4. **速率限制频繁触发**
   - 增加操作间隔时间
   - 使用更多账户分散请求

## 示例代码

完整的使用示例请参考 `example_usage.py` 文件。

## 架构设计

TwitterInteractionManager遵循PRD文档的设计要求：

1. **无缝集成**: 与现有AccountsPool深度集成
2. **智能错误处理**: 精细化的异常处理和状态更新
3. **架构清晰**: 读写操作分离，易于维护
4. **功能专注**: 专注于核心交互功能（发帖、转推、关注）

## 技术实现

- **依赖管理**: 使用twikit作为Twitter API交互库
- **客户端实例化**: 动态创建配置好的twikit.Client实例
- **异常映射**: 将twikit异常映射到AccountsPool操作
- **队列管理**: 使用不同队列名区分不同操作类型
