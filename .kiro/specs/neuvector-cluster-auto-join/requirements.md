# 需求文档

## 简介

本功能为 NeuVector Prometheus Exporter 添加自动加入联邦集群的能力。当 exporter 启动时，它将自动向 NeuVector 主集群发送加入请求，使当前实例成为联邦集群的成员节点。该功能支持从 URL 获取或直接提供 join token，支持自动重试机制，并能根据不同的错误响应执行相应的处理逻辑。

## 术语表

- **Exporter**: NeuVector Prometheus Exporter，用于收集 NeuVector 指标并暴露给 Prometheus
- **Controller**: NeuVector 控制器，提供 RESTful API 接口
- **Federation**: NeuVector 联邦集群功能，允许多个集群组成联邦进行统一管理
- **Master Cluster**: 联邦集群中的主集群
- **Joint Cluster**: 联邦集群中的成员集群（也称为 worker 集群）
- **Join Token**: 用于验证加入请求的令牌，由主集群生成
- **PAAS Store ID**: 平台即服务存储标识符，用于标识集群
- **Joint REST Info**: 成员集群的 REST API 地址信息，主集群将通过此地址连接成员集群

## 需求

### 需求 1

**用户故事:** 作为系统管理员，我希望 exporter 能够自动向主集群发送加入请求，以便将当前实例加入到联邦集群中。

#### 验收标准

1. WHEN Exporter 启动时 THEN Exporter SHALL 向 Controller 的 `/v1/fed/join` 端点发送 POST 请求
2. WHEN 构建加入请求时 THEN Exporter SHALL 在请求体中包含 name、join_token、joint_rest_info 字段
3. WHEN 设置 name 字段时 THEN Exporter SHALL 使用 PAAS Store ID 加上随机字符串作为集群名称
4. WHEN 设置 joint_rest_info 字段时 THEN Exporter SHALL 包含当前 Controller 实例的 server 和 port 信息
5. WHEN 加入请求成功时 THEN Exporter SHALL 记录成功日志并继续正常运行

### 需求 2

**用户故事:** 作为系统管理员，我希望系统能够灵活获取 join token，以便支持不同的部署场景。

#### 验收标准

1. WHEN 环境变量中直接提供 join_token THEN Exporter SHALL 使用该 token 进行加入请求
2. WHEN 环境变量中提供 join_token_url THEN Exporter SHALL 通过 HTTP GET 请求从该 URL 获取 token
3. WHEN 从 URL 获取 token 时 THEN Exporter SHALL 解析响应中的 context 字段并进行 base64 解码
4. WHEN 解码 token 后 THEN Exporter SHALL 提取其中的 server 地址和 port 端口信息
5. IF 既未提供 join_token 也未提供 join_token_url THEN Exporter SHALL 记录错误并跳过加入流程

### 需求 3

**用户故事:** 作为系统管理员，我希望系统能够灵活配置主集群地址，以便适应不同的网络环境。

#### 验收标准

1. WHEN 环境变量中直接提供 master_cluster_address THEN Exporter SHALL 使用该地址作为主集群地址
2. WHEN 未提供 master_cluster_address 但提供了 PAAS Store ID THEN Exporter SHALL 根据 Store ID 拼接主集群地址
3. WHEN 拼接主集群地址时 THEN Exporter SHALL 使用格式 `cn-wukong-r{store_id}.mcd.store`
4. WHEN 未提供 master_cluster_port THEN Exporter SHALL 使用默认端口 443
5. WHEN 提供了 master_cluster_port THEN Exporter SHALL 使用指定的端口

### 需求 4

**用户故事:** 作为系统管理员，我希望加入失败时系统能够自动重试，以便应对临时网络故障或服务不可用的情况。

#### 验收标准

1. WHEN 加入请求失败时 THEN Exporter SHALL 使用指数退避策略进行重试
2. WHEN 第一次重试时 THEN Exporter SHALL 等待 10 秒后重试
3. WHEN 后续重试时 THEN Exporter SHALL 将等待时间翻倍，最大等待时间不超过 300 秒
4. WHEN 达到最大重试次数时 THEN Exporter SHALL 记录错误日志但继续运行 exporter 的其他功能
5. WHEN 重试成功时 THEN Exporter SHALL 停止重试并记录成功日志

### 需求 5

**用户故事:** 作为系统管理员，我希望系统能够根据不同的错误类型执行不同的处理逻辑，以便更智能地处理各种异常情况。

#### 验收标准

1. WHEN Controller 返回 400 错误（请求参数错误）THEN Exporter SHALL 记录错误详情并停止重试
2. WHEN Controller 返回 401 错误（认证失败）THEN Exporter SHALL 尝试重新登录后重试
3. WHEN Controller 返回 409 错误（集群已存在）THEN Exporter SHALL 记录警告日志并停止重试
4. WHEN Controller 返回 500 错误（服务器内部错误）THEN Exporter SHALL 继续使用退避策略重试
5. WHEN 发生网络连接错误时 THEN Exporter SHALL 继续使用退避策略重试

### 需求 6

**用户故事:** 作为系统管理员，我希望能够通过环境变量配置加入功能，以便在不同环境中灵活部署。

#### 验收标准

1. WHEN 设置环境变量 ENABLE_FED_JOIN 为 true THEN Exporter SHALL 启用自动加入功能
2. WHEN 未设置 ENABLE_FED_JOIN 或设置为 false THEN Exporter SHALL 跳过自动加入流程
3. WHEN 启用加入功能但缺少必要参数时 THEN Exporter SHALL 记录错误并跳过加入流程
4. WHEN 所有必要参数都已提供时 THEN Exporter SHALL 执行加入流程
5. WHEN 加入流程失败时 THEN Exporter SHALL 不影响 exporter 的正常指标收集功能

### 需求 7

**用户故事:** 作为开发人员，我希望系统能够记录详细的日志信息，以便排查问题和监控加入状态。

#### 验收标准

1. WHEN 开始加入流程时 THEN Exporter SHALL 记录包含集群名称和主集群地址的日志
2. WHEN 获取 join token 时 THEN Exporter SHALL 记录 token 来源（直接提供或从 URL 获取）
3. WHEN 发送加入请求时 THEN Exporter SHALL 记录请求的目标地址和端口
4. WHEN 收到响应时 THEN Exporter SHALL 记录响应状态码和关键信息
5. WHEN 发生错误时 THEN Exporter SHALL 记录详细的错误信息和堆栈跟踪
