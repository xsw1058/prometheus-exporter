# 设计文档

## 概述

本设计为 NeuVector Prometheus Exporter 添加联邦集群自动加入功能。该功能将在 exporter 启动时自动执行，通过向主集群的 Controller 发送 RESTful API 请求来完成集群加入。设计采用异步重试机制，支持多种配置方式，并具备完善的错误处理能力。

核心设计原则：
- 最小侵入性：不修改现有的 NVApiCollector 类
- 独立性：加入功能失败不影响 exporter 的正常指标收集
- 可配置性：通过环境变量灵活控制功能行为
- 健壮性：完善的错误处理和重试机制

## 架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    NeuVector Exporter                        │
│                                                               │
│  ┌──────────────┐         ┌─────────────────────────────┐  │
│  │   Main       │         │  FederationJoinManager       │  │
│  │   Process    │────────▶│                              │  │
│  │              │         │  - 加载配置                   │  │
│  └──────────────┘         │  - 获取 Token                │  │
│         │                 │  - 发送加入请求               │  │
│         │                 │  - 处理错误和重试             │  │
│         │                 └─────────────────────────────┘  │
│         │                            │                      │
│         ▼                            ▼                      │
│  ┌──────────────┐         ┌─────────────────────────────┐  │
│  │ NVApiCollector│         │  HTTP Client                 │  │
│  │ (unchanged)   │         │  (requests library)          │  │
│  └──────────────┘         └─────────────────────────────┘  │
│                                      │                      │
└──────────────────────────────────────┼──────────────────────┘
                                       │
                                       ▼
                          ┌────────────────────────┐
                          │  NeuVector Controller  │
                          │  - /v1/fed/join        │
                          │  - Join Token URL      │
                          └────────────────────────┘
```

### 执行流程

```
启动 Exporter
    │
    ├─→ 检查 ENABLE_FED_JOIN 环境变量
    │       │
    │       ├─→ false/未设置 ──→ 跳过加入流程 ──→ 启动正常 exporter
    │       │
    │       └─→ true
    │           │
    │           ├─→ 加载配置参数
    │           │   ├─→ PAAS_STORE_ID
    │           │   ├─→ JOIN_TOKEN / JOIN_TOKEN_URL
    │           │   ├─→ MASTER_CLUSTER_ADDRESS (可选)
    │           │   ├─→ MASTER_CLUSTER_PORT (可选)
    │           │   └─→ JOINT_REST_SERVER / JOINT_REST_PORT
    │           │
    │           ├─→ 验证必要参数
    │           │   └─→ 缺少参数 ──→ 记录错误 ──→ 跳过加入流程
    │           │
    │           ├─→ 获取 Join Token
    │           │   ├─→ 直接从环境变量获取
    │           │   └─→ 从 URL 获取并解析
    │           │
    │           ├─→ 构建加入请求
    │           │   ├─→ 生成集群名称（PAAS_STORE_ID + 随机字符串）
    │           │   ├─→ 确定主集群地址
    │           │   └─→ 设置 joint_rest_info
    │           │
    │           └─→ 发送加入请求（带重试）
    │               ├─→ 成功 ──→ 记录日志 ──→ 继续
    │               ├─→ 400/409 错误 ──→ 停止重试 ──→ 继续
    │               ├─→ 401 错误 ──→ 重新登录 ──→ 重试
    │               └─→ 其他错误 ──→ 指数退避重试
    │
    └─→ 启动正常 exporter 功能
```

## 组件和接口

### FederationJoinManager 类

这是唯一新增的类，封装了所有联邦加入相关的功能。该类设计为自包含，所有配置、token 获取、请求发送和错误处理都在这个类中完成。

```python
class FederationJoinManager:
    """联邦加入管理器 - 处理集群自动加入的所有逻辑"""
    
    def __init__(self, ctrl_url: str, ctrl_user: str, ctrl_pass: str):
        """初始化管理器
        
        Args:
            ctrl_url: Controller URL
            ctrl_user: Controller 用户名
            ctrl_pass: Controller 密码
        """
        self.ctrl_url = ctrl_url
        self.ctrl_user = ctrl_user
        self.ctrl_pass = ctrl_pass
        
        # 配置参数（从环境变量加载）
        self.enabled = False
        self.paas_store_id = None
        self.join_token = None
        self.join_token_url = None
        self.master_cluster_address = None
        self.master_cluster_port = 443
        self.joint_rest_server = None
        self.joint_rest_port = None
        self.max_retries = 10
        self.initial_retry_delay = 10
        self.max_retry_delay = 300
        
        # 运行时状态
        self.retry_count = 0
    
    def load_config(self) -> bool:
        """从环境变量加载配置
        
        Returns:
            bool: 配置是否有效
        """
        pass
    
    def execute_join(self) -> bool:
        """执行完整的加入流程（主入口方法）
        
        Returns:
            bool: 是否成功加入
        """
        pass
    
    def _validate_config(self) -> tuple[bool, str]:
        """验证配置完整性
        
        Returns:
            tuple[bool, str]: (是否有效, 错误信息)
        """
        pass
    
    def _generate_cluster_name(self) -> str:
        """生成集群名称
        
        Returns:
            str: PAAS_STORE_ID + 6位随机字符串
        """
        pass
    
    def _get_master_address(self) -> str:
        """获取主集群地址
        
        Returns:
            str: 主集群地址（直接提供或根据 PAAS_STORE_ID 拼接）
        """
        pass
    
    def _fetch_join_token(self) -> tuple[bool, str]:
        """获取 join token
        
        Returns:
            tuple[bool, str]: (是否成功, token字符串)
        """
        pass
    
    def _fetch_token_from_url(self, url: str) -> tuple[bool, str]:
        """从 URL 获取 token
        
        Args:
            url: token URL
            
        Returns:
            tuple[bool, str]: (是否成功, token字符串)
        """
        pass
    
    def _parse_token(self, token: str) -> dict:
        """解析 token 内容（base64 解码）
        
        Args:
            token: base64 编码的 token
            
        Returns:
            dict: 包含 server 和 port 的字典
        """
        pass
    
    def _build_join_request(self, join_token: str, cluster_name: str) -> dict:
        """构建加入请求体
        
        Args:
            join_token: join token 字符串
            cluster_name: 集群名称
            
        Returns:
            dict: 请求体字典
        """
        pass
    
    def _send_join_request(self, request_body: dict) -> tuple[bool, int, str]:
        """发送加入请求到主集群
        
        Args:
            request_body: 请求体
            
        Returns:
            tuple[bool, int, str]: (是否成功, 状态码, 响应消息)
        """
        pass
    
    def _handle_error_response(self, status_code: int, message: str) -> str:
        """根据错误类型决定处理策略
        
        Args:
            status_code: HTTP 状态码
            message: 错误消息
            
        Returns:
            str: 处理策略 ('stop', 'reauth', 'retry')
        """
        pass
    
    def _calculate_backoff_delay(self) -> int:
        """计算指数退避延迟时间
        
        Returns:
            int: 等待秒数
        """
        pass
    
    def _reauth(self) -> bool:
        """重新认证到 Controller
        
        Returns:
            bool: 认证是否成功
        """
        pass
```

### 4. 环境变量定义

```python
# 新增环境变量常量
ENV_ENABLE_FED_JOIN = "ENABLE_FED_JOIN"
ENV_PAAS_STORE_ID = "PAAS_STORE_ID"
ENV_JOIN_TOKEN = "JOIN_TOKEN"
ENV_JOIN_TOKEN_URL = "JOIN_TOKEN_URL"
ENV_MASTER_CLUSTER_ADDRESS = "MASTER_CLUSTER_ADDRESS"
ENV_MASTER_CLUSTER_PORT = "MASTER_CLUSTER_PORT"
ENV_JOINT_REST_SERVER = "JOINT_REST_SERVER"
ENV_JOINT_REST_PORT = "JOINT_REST_PORT"
ENV_MAX_JOIN_RETRIES = "MAX_JOIN_RETRIES"
```

## 数据模型

### Join Request Body

```python
{
    "name": str,              # 集群名称：PAAS_STORE_ID + 随机字符串
    "join_token": str,        # Join token
    "joint_rest_info": {      # 当前集群的 REST 信息
        "server": str,        # 当前 controller 地址
        "port": int           # 当前 controller 端口
    }
}
```

### Join Token 结构（解码后）

```python
{
    "s": str,    # 主集群 server 地址
    "p": int     # 主集群 port 端口
}
```

### 配置数据结构

```python
{
    "enabled": bool,
    "paas_store_id": str,
    "join_token": str | None,
    "join_token_url": str | None,
    "master_cluster_address": str | None,
    "master_cluster_port": int,
    "joint_rest_server": str,
    "joint_rest_port": int,
    "max_retries": int,
    "initial_retry_delay": int,
    "max_retry_delay": int
}
```

## 正确性属性

*属性是一个特征或行为，应该在系统的所有有效执行中保持为真——本质上是关于系统应该做什么的形式化陈述。属性作为人类可读规范和机器可验证正确性保证之间的桥梁。*

### 属性 1：请求体结构完整性

*对于任意*有效的配置输入，构建的加入请求体都应该包含 name、join_token 和 joint_rest_info 三个必需字段。
**验证：需求 1.2**

### 属性 2：集群名称格式正确性

*对于任意*的 PAAS Store ID，生成的集群名称都应该以该 ID 开头，并且总长度应该等于 ID 长度加上随机后缀长度。
**验证：需求 1.3**

### 属性 3：Token 解析往返一致性

*对于任意*有效的 token 数据结构（包含 server 和 port），将其编码为 base64 后再解码，应该得到与原始数据等价的结构。
**验证：需求 2.3, 2.4**

### 属性 4：配置优先级一致性

*对于任意*同时提供直接值和计算值的配置项（如 master_cluster_address），系统都应该优先使用直接提供的值。
**验证：需求 3.1**

### 属性 5：地址拼接格式正确性

*对于任意*的 PAAS Store ID，当未提供 master_cluster_address 时，拼接生成的地址都应该匹配正则表达式 `^cn-wukong-r\d+\.mcd\.store$`。
**验证：需求 3.2, 3.3**

### 属性 6：指数退避单调性

*对于任意*的重试序列，每次重试的等待时间都应该大于或等于前一次的等待时间（直到达到最大值），且不超过配置的最大等待时间。
**验证：需求 4.1, 4.3**

### 属性 7：错误处理策略一致性

*对于任意*的 HTTP 错误响应，相同的状态码应该总是触发相同的处理策略（stop、reauth 或 retry）。
**验证：需求 5.1, 5.2, 5.3, 5.4, 5.5**

### 属性 8：配置验证完整性

*对于任意*缺少必要参数的配置，验证函数都应该返回失败，并且系统应该跳过加入流程。
**验证：需求 6.3**

### 属性 9：故障隔离性

*对于任意*导致加入失败的错误，exporter 的核心指标收集功能都应该能够正常启动和运行。
**验证：需求 6.5**

### 属性 10：日志记录完整性

*对于任意*的加入流程执行（无论成功或失败），都应该至少记录开始、token 获取、请求发送和结果这四个关键阶段的日志。
**验证：需求 7.1, 7.2, 7.3, 7.4, 7.5**

## 错误处理

### 错误分类和处理策略

| 错误类型 | HTTP 状态码 | 处理策略 | 说明 |
|---------|------------|---------|------|
| 参数错误 | 400 | 停止重试 | 请求参数有误，重试无意义 |
| 认证失败 | 401 | 重新登录后重试 | Token 可能过期，需要重新认证 |
| 集群已存在 | 409 | 停止重试 | 集群名称冲突，记录警告 |
| 服务器错误 | 500, 502, 503 | 指数退避重试 | 临时性错误，可能恢复 |
| 网络错误 | - | 指数退避重试 | 连接超时、DNS 解析失败等 |
| 配置错误 | - | 停止加入流程 | 缺少必要参数或参数无效 |

### 错误处理流程

```python
def handle_join_error(error_type, status_code, message):
    """
    根据错误类型决定处理策略
    
    Returns:
        str: 'stop', 'reauth', 'retry'
    """
    if status_code in [400, 409]:
        log_error(f"Non-retryable error: {status_code} - {message}")
        return 'stop'
    
    if status_code == 401:
        log_warning("Authentication failed, will re-login")
        return 'reauth'
    
    if status_code >= 500 or error_type == 'network':
        log_warning(f"Retryable error: {status_code} - {message}")
        return 'retry'
    
    # 未知错误，默认重试
    return 'retry'
```

### 重试机制

- 初始延迟：10 秒
- 退避策略：指数退避（每次翻倍）
- 最大延迟：300 秒（5 分钟）
- 最大重试次数：10 次（可配置）
- 总超时时间：约 85 分钟（10+20+40+80+160+300*5）

```python
def calculate_backoff_delay(retry_count, initial_delay=10, max_delay=300):
    """
    计算指数退避延迟时间
    
    Args:
        retry_count: 当前重试次数（从 0 开始）
        initial_delay: 初始延迟秒数
        max_delay: 最大延迟秒数
    
    Returns:
        int: 延迟秒数
    """
    delay = initial_delay * (2 ** retry_count)
    return min(delay, max_delay)
```

## 测试策略

### 单元测试

单元测试将覆盖 FederationJoinManager 类的各个方法：

1. **配置管理测试**
   - 环境变量加载
   - 配置验证
   - 集群名称生成
   - 主集群地址拼接

2. **Token 处理测试**
   - 直接 token 使用
   - 从 URL 获取 token
   - Token 解析和解码
   - 错误处理

3. **请求处理测试**
   - 请求体构建
   - 错误响应处理
   - 退避时间计算
   - 重试逻辑

### 基于属性的测试

基于属性的测试将使用 **Hypothesis** 库来验证正确性属性。Hypothesis 是 Python 中最流行的属性测试框架，能够自动生成测试数据并发现边界情况。

每个属性测试将：
- 运行至少 100 次迭代
- 使用随机生成的输入数据
- 验证对应的正确性属性
- 在测试代码中使用注释标记对应的属性编号

测试覆盖的属性：
1. 请求体结构完整性（属性 1）
2. 集群名称格式正确性（属性 2）
3. Token 解析往返一致性（属性 3）
4. 配置优先级一致性（属性 4）
5. 地址拼接格式正确性（属性 5）
6. 指数退避单调性（属性 6）
7. 错误处理策略一致性（属性 7）
8. 配置验证完整性（属性 8）
9. 故障隔离性（属性 9）
10. 日志记录完整性（属性 10）

### 集成测试

集成测试将验证整个加入流程：

1. **成功场景**
   - 使用 mock Controller API
   - 验证完整的加入流程
   - 确认 exporter 正常启动

2. **失败场景**
   - 模拟各种错误响应
   - 验证重试机制
   - 确认错误处理正确

3. **配置场景**
   - 测试不同的配置组合
   - 验证配置优先级
   - 测试边界条件

### 测试工具

- **pytest**: 测试框架
- **Hypothesis**: 基于属性的测试库
- **unittest.mock**: Mock HTTP 请求和响应
- **pytest-cov**: 代码覆盖率分析

## 实现注意事项

### 1. 线程安全

加入流程在主线程中同步执行，不涉及多线程问题。如果未来需要异步执行，应考虑：
- 使用线程锁保护共享状态
- 确保日志记录的线程安全
- 避免阻塞 exporter 的正常功能

### 2. 性能考虑

- 加入流程在启动时执行一次，不影响运行时性能
- 重试使用 time.sleep()，不消耗 CPU 资源
- 失败后不影响 exporter 的正常指标收集

### 3. 安全性

- 敏感信息（token、密码）不应出现在日志中
- 使用 HTTPS 进行所有 API 通信
- 验证 SSL 证书（生产环境）

### 4. 可观测性

- 记录详细的日志，便于问题排查
- 使用结构化日志格式
- 区分不同级别的日志（INFO、WARNING、ERROR）

### 5. 向后兼容

- 默认情况下功能关闭（ENABLE_FED_JOIN=false）
- 不修改现有的 NVApiCollector 类
- 新增的环境变量都是可选的

## 部署配置示例

### Docker Compose

```yaml
version: '3'
services:
  nv-exporter:
    image: neuvector/prometheus-exporter:latest
    environment:
      - CTRL_API_SERVICE=192.168.8.209:10443
      - CTRL_USERNAME=admin
      - CTRL_PASSWORD=Y3Lx1Ez3sq88oia3gG
      - EXPORTER_PORT=8068
      - ENABLE_FED_JOIN=true
      - PAAS_STORE_ID=u2204a
      - JOIN_TOKEN_URL=https://neuvector-wk-test.mcdchina.net/join_token
      - JOINT_REST_SERVER=192.168.8.209
      - JOINT_REST_PORT=10443
      - MAX_JOIN_RETRIES=10
    ports:
      - "8068:8068"
```

### Kubernetes

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nv-exporter-config
data:
  ENABLE_FED_JOIN: "true"
  PAAS_STORE_ID: "u2204a"
  JOIN_TOKEN_URL: "https://neuvector-wk-test.mcdchina.net/join_token"
  JOINT_REST_SERVER: "neuvector-svc-controller.neuvector"
  JOINT_REST_PORT: "10443"
  MAX_JOIN_RETRIES: "10"
---
apiVersion: v1
kind: Secret
metadata:
  name: nv-exporter-secret
type: Opaque
stringData:
  CTRL_USERNAME: admin
  CTRL_PASSWORD: Y3Lx1Ez3sq88oia3gG
```

