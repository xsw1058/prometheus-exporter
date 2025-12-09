# NeuVector 联邦集群自动加入功能

## 概述

此功能允许 NeuVector Prometheus Exporter 在启动时自动加入到联邦集群中。通过配置环境变量，exporter 可以自动向主集群发送加入请求，无需手动操作。

## 功能特性

- ✅ 自动向主集群发送加入请求
- ✅ 支持从环境变量或 URL 获取 join token
- ✅ 灵活的主集群地址配置（直接提供或自动拼接）
- ✅ 智能错误处理和重试机制
- ✅ 指数退避策略，避免过度重试
- ✅ 失败不影响 exporter 的正常功能
- ✅ 详细的日志记录，便于问题排查

## 环境变量配置

### 必需的环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `ENABLE_FED_JOIN` | 启用联邦加入功能 | `true` |
| `PAAS_STORE_ID` | 平台存储标识符，用于生成集群名称 | `u2204a` |
| `JOINT_REST_SERVER` | 当前 Controller 的地址（主集群将连接此地址） | `192.168.8.209` |
| `JOINT_REST_PORT` | 当前 Controller 的端口 | `10443` |

### Token 配置（二选一）

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `JOIN_TOKEN` | 直接提供 join token | `eyJzIjoiZXhhbXBsZS5jb20iLCJwIjo0NDN9` |
| `JOIN_TOKEN_URL` | 获取 join token 的 URL | `https://master.example.com/join_token` |

### 可选的环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `MASTER_CLUSTER_ADDRESS` | 主集群地址（如不提供，将根据 PAAS_STORE_ID 自动拼接） | 无 |
| `MASTER_CLUSTER_PORT` | 主集群端口 | `443` |
| `MAX_JOIN_RETRIES` | 最大重试次数 | `10` |

## 使用示例

### 示例 1：使用 Docker Compose

```yaml
version: '3'
services:
  nv-exporter:
    image: neuvector/prometheus-exporter:latest
    environment:
      # 基础配置
      - CTRL_API_SERVICE=192.168.8.209:10443
      - CTRL_USERNAME=admin
      - CTRL_PASSWORD=your_password
      - EXPORTER_PORT=8068
      
      # 联邦加入配置
      - ENABLE_FED_JOIN=true
      - PAAS_STORE_ID=u2204a
      - JOIN_TOKEN_URL=https://neuvector-master.example.com/join_token
      - JOINT_REST_SERVER=192.168.8.209
      - JOINT_REST_PORT=10443
    ports:
      - "8068:8068"
```

### 示例 2：使用 Kubernetes

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nv-exporter-config
data:
  ENABLE_FED_JOIN: "true"
  PAAS_STORE_ID: "prod-cluster-01"
  JOIN_TOKEN_URL: "https://neuvector-master.example.com/join_token"
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
  CTRL_PASSWORD: your_password
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nv-exporter
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nv-exporter
  template:
    metadata:
      labels:
        app: nv-exporter
    spec:
      containers:
      - name: exporter
        image: neuvector/prometheus-exporter:latest
        env:
        - name: CTRL_API_SERVICE
          value: "neuvector-svc-controller.neuvector:10443"
        - name: EXPORTER_PORT
          value: "8068"
        - name: CTRL_USERNAME
          valueFrom:
            secretKeyRef:
              name: nv-exporter-secret
              key: CTRL_USERNAME
        - name: CTRL_PASSWORD
          valueFrom:
            secretKeyRef:
              name: nv-exporter-secret
              key: CTRL_PASSWORD
        envFrom:
        - configMapRef:
            name: nv-exporter-config
        ports:
        - containerPort: 8068
```

### 示例 3：直接提供 Join Token

```bash
export CTRL_API_SERVICE="192.168.8.209:10443"
export CTRL_USERNAME="admin"
export CTRL_PASSWORD="your_password"
export EXPORTER_PORT="8068"
export ENABLE_FED_JOIN="true"
export PAAS_STORE_ID="test123"
export JOIN_TOKEN="eyJzIjoibWFzdGVyLmV4YW1wbGUuY29tIiwicCI6NDQzfQ=="
export JOINT_REST_SERVER="192.168.8.209"
export JOINT_REST_PORT="10443"

python3 nv_exporter.py
```

## 工作流程

1. **启动检查**：Exporter 启动时检查 `ENABLE_FED_JOIN` 环境变量
2. **配置加载**：如果启用，加载所有相关的环境变量
3. **配置验证**：验证必需参数是否完整
4. **获取 Token**：从环境变量或 URL 获取 join token
5. **生成集群名称**：使用 `PAAS_STORE_ID` + 6位随机字符串
6. **发送加入请求**：向主集群发送 POST 请求到 `/v1/fed/join`
7. **错误处理**：根据响应状态码决定是否重试
8. **继续运行**：无论加入成功或失败，exporter 都会继续正常运行

## 错误处理

### 错误类型和处理策略

| HTTP 状态码 | 错误类型 | 处理策略 |
|------------|---------|---------|
| 400 | 请求参数错误 | 停止重试，记录错误 |
| 401 | 认证失败 | 重新登录后重试 |
| 409 | 集群已存在 | 停止重试，记录警告 |
| 500+ | 服务器错误 | 使用指数退避重试 |
| 0 | 网络错误 | 使用指数退避重试 |

### 重试机制

- **初始延迟**：10 秒
- **退避策略**：指数退避（每次翻倍）
- **最大延迟**：300 秒（5 分钟）
- **最大重试次数**：10 次（可配置）

重试延迟序列：10s → 20s → 40s → 80s → 160s → 300s → 300s → ...

## 日志示例

### 成功加入

```
============================================================
Starting federation join process...
============================================================
Cluster name: u2204a-Xy9K2m
Master cluster address: cn-wukong-ru2204a.mcd.store:443
Joint REST info: 192.168.8.209:10443
Fetching join token from URL: https://neuvector-master.example.com/join_token
Successfully fetched join token from URL
Sending join request to https://cn-wukong-ru2204a.mcd.store:443/v1/fed/join
Join request successful: 200
============================================================
Federation join completed successfully!
============================================================
```

### 失败并重试

```
============================================================
Starting federation join process...
============================================================
Cluster name: u2204a-Xy9K2m
Master cluster address: cn-wukong-ru2204a.mcd.store:443
Joint REST info: 192.168.8.209:10443
Sending join request to https://cn-wukong-ru2204a.mcd.store:443/v1/fed/join
Join request failed: 500 - Internal Server Error
Retryable error: 500 - Internal Server Error
Retry 1/10 after 10 seconds...
Sending join request to https://cn-wukong-ru2204a.mcd.store:443/v1/fed/join
Join request successful: 200
============================================================
Federation join completed successfully!
============================================================
```

### 配置错误

```
============================================================
Starting federation join process...
============================================================
Configuration validation failed: PAAS_STORE_ID is required
Skipping federation join
```

## 测试

项目包含两个测试脚本：

### 1. 单元测试（test_unit.py）

测试所有核心功能，不依赖网络连接：

```bash
python3 test_unit.py
```

测试内容：
- 配置加载和验证
- 集群名称生成
- 主集群地址获取
- Token 解析
- 请求体构建
- 退避延迟计算
- 错误处理策略

### 2. 集成测试（test_federation_join.py）

测试完整的加入流程（需要网络连接）：

```bash
python3 test_federation_join.py
```

## 故障排查

### 问题：配置验证失败

**症状**：日志显示 "Configuration validation failed"

**解决方案**：
1. 检查所有必需的环境变量是否已设置
2. 确保 `JOIN_TOKEN` 或 `JOIN_TOKEN_URL` 至少提供一个
3. 验证端口号是否为有效的整数

### 问题：Token 获取失败

**症状**：日志显示 "Failed to fetch join token"

**解决方案**：
1. 检查 `JOIN_TOKEN_URL` 是否可访问
2. 验证 URL 返回的 JSON 格式是否正确（应包含 "context" 字段）
3. 检查网络连接和 DNS 解析

### 问题：加入请求失败（400 错误）

**症状**：日志显示 "Non-retryable error: 400"

**解决方案**：
1. 检查 join token 是否有效
2. 验证 `JOINT_REST_SERVER` 和 `JOINT_REST_PORT` 是否正确
3. 确保主集群可以访问当前 Controller 的地址

### 问题：加入请求失败（401 错误）

**症状**：日志显示 "Authentication failed"

**解决方案**：
1. 检查 `CTRL_USERNAME` 和 `CTRL_PASSWORD` 是否正确
2. 验证用户是否有权限执行联邦加入操作

### 问题：加入请求失败（409 错误）

**症状**：日志显示 "Non-retryable error: 409"

**解决方案**：
1. 集群名称可能已存在，等待一段时间后重启（会生成新的随机后缀）
2. 或者手动从主集群中删除已存在的集群

## 安全注意事项

1. **敏感信息保护**：
   - 不要在日志中记录完整的 token 或密码
   - 使用 Kubernetes Secret 存储敏感信息

2. **网络安全**：
   - 生产环境应启用 SSL 证书验证
   - 使用防火墙限制主集群和成员集群之间的访问

3. **权限控制**：
   - 为 exporter 创建专用的只读用户账号
   - 限制联邦加入操作的权限

## 兼容性

- Python 3.6+
- NeuVector Controller API v1
- 不影响现有的 exporter 功能
- 向后兼容（默认禁用）

## 贡献

如有问题或建议，请提交 Issue 或 Pull Request。

## 许可证

与 NeuVector Prometheus Exporter 项目保持一致。
