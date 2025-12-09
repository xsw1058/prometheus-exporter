# 实现计划

- [x] 1. 添加环境变量常量定义
  - 在 nv_exporter.py 中添加新的环境变量常量
  - 包括：ENABLE_FED_JOIN, PAAS_STORE_ID, JOIN_TOKEN, JOIN_TOKEN_URL, MASTER_CLUSTER_ADDRESS, MASTER_CLUSTER_PORT, JOINT_REST_SERVER, JOINT_REST_PORT, MAX_JOIN_RETRIES
  - _需求：6.1, 6.2_

- [x] 2. 实现 FederationJoinManager 类的基础结构
  - [x] 2.1 创建 FederationJoinManager 类和 __init__ 方法
    - 定义类和初始化方法
    - 设置实例变量（ctrl_url, ctrl_user, ctrl_pass）
    - 初始化配置参数和运行时状态
    - _需求：1.1_

  - [x] 2.2 实现配置加载方法 load_config
    - 从环境变量读取所有配置参数
    - 处理类型转换（字符串转整数、布尔值）
    - 返回配置是否启用
    - _需求：6.1, 6.2, 6.3_

  - [x] 2.3 实现配置验证方法 _validate_config
    - 检查必要参数是否存在（paas_store_id, joint_rest_server, joint_rest_port）
    - 检查 token 来源（join_token 或 join_token_url 至少有一个）
    - 返回验证结果和错误信息
    - _需求：2.5, 6.3_

  - [ ]* 2.4 编写属性测试：配置验证完整性
    - **功能：neuvector-cluster-auto-join，属性 8：配置验证完整性**
    - **验证：需求 6.3**
    - 生成随机的配置组合（缺少不同的必要参数）
    - 验证所有缺少必要参数的配置都被拒绝
    - _需求：6.3_

- [x] 3. 实现集群名称和地址生成逻辑
  - [x] 3.1 实现 _generate_cluster_name 方法
    - 使用 PAAS_STORE_ID 作为前缀
    - 生成 6 位随机字符串（字母和数字）
    - 拼接并返回完整的集群名称
    - _需求：1.3_

  - [ ]* 3.2 编写属性测试：集群名称格式正确性
    - **功能：neuvector-cluster-auto-join，属性 2：集群名称格式正确性**
    - **验证：需求 1.3**
    - 生成随机的 PAAS Store ID
    - 验证生成的名称格式正确（以 ID 开头，长度正确）
    - _需求：1.3_

  - [x] 3.3 实现 _get_master_address 方法
    - 如果提供了 master_cluster_address，直接返回
    - 否则根据 PAAS_STORE_ID 拼接地址：cn-wukong-r{store_id}.mcd.store
    - _需求：3.1, 3.2, 3.3_

  - [ ]* 3.4 编写属性测试：配置优先级一致性
    - **功能：neuvector-cluster-auto-join，属性 4：配置优先级一致性**
    - **验证：需求 3.1**
    - 生成随机的直接地址和 Store ID
    - 验证当两者都提供时，优先使用直接地址
    - _需求：3.1_

  - [ ]* 3.5 编写属性测试：地址拼接格式正确性
    - **功能：neuvector-cluster-auto-join，属性 5：地址拼接格式正确性**
    - **验证：需求 3.2, 3.3**
    - 生成随机的 Store ID
    - 验证拼接的地址匹配正则表达式 ^cn-wukong-r\d+\.mcd\.store$
    - _需求：3.2, 3.3_

- [x] 4. 实现 Token 获取和解析功能
  - [x] 4.1 实现 _fetch_join_token 方法
    - 如果提供了 join_token，直接返回
    - 如果提供了 join_token_url，调用 _fetch_token_from_url
    - 记录 token 来源日志
    - _需求：2.1, 2.2, 7.2_

  - [x] 4.2 实现 _fetch_token_from_url 方法
    - 发送 HTTP GET 请求到指定 URL
    - 解析响应 JSON，提取 context 字段
    - 处理网络错误和解析错误
    - _需求：2.2_

  - [x] 4.3 实现 _parse_token 方法
    - 对 token 进行 base64 解码
    - 解析 JSON 获取 server (s) 和 port (p)
    - 返回包含 server 和 port 的字典
    - _需求：2.3, 2.4_

  - [ ]* 4.4 编写属性测试：Token 解析往返一致性
    - **功能：neuvector-cluster-auto-join，属性 3：Token 解析往返一致性**
    - **验证：需求 2.3, 2.4**
    - 生成随机的 token 数据（包含 server 和 port）
    - 编码为 base64 后再解码
    - 验证解码后的数据与原始数据一致
    - _需求：2.3, 2.4_

- [x] 5. 实现加入请求构建和发送
  - [x] 5.1 实现 _build_join_request 方法
    - 构建请求体字典
    - 包含 name（集群名称）
    - 包含 join_token
    - 包含 joint_rest_info（server 和 port）
    - _需求：1.2, 1.4_

  - [ ]* 5.2 编写属性测试：请求体结构完整性
    - **功能：neuvector-cluster-auto-join，属性 1：请求体结构完整性**
    - **验证：需求 1.2**
    - 生成随机的配置参数
    - 验证构建的请求体包含所有必需字段
    - _需求：1.2_

  - [x] 5.3 实现 _send_join_request 方法
    - 构建完整的 URL（主集群地址 + /v1/fed/join）
    - 发送 POST 请求
    - 处理响应，返回状态码和消息
    - 记录请求和响应日志
    - _需求：1.1, 7.3, 7.4_

- [x] 6. 实现错误处理和重试机制
  - [x] 6.1 实现 _handle_error_response 方法
    - 根据状态码决定处理策略
    - 400, 409 返回 'stop'
    - 401 返回 'reauth'
    - 500+ 或网络错误返回 'retry'
    - _需求：5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 6.2 编写属性测试：错误处理策略一致性
    - **功能：neuvector-cluster-auto-join，属性 7：错误处理策略一致性**
    - **验证：需求 5.1, 5.2, 5.3, 5.4, 5.5**
    - 生成随机的错误状态码
    - 多次调用错误处理方法
    - 验证相同状态码总是返回相同策略
    - _需求：5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 6.3 实现 _calculate_backoff_delay 方法
    - 计算指数退避延迟：initial_delay * (2 ** retry_count)
    - 限制最大延迟不超过 max_retry_delay
    - 返回延迟秒数
    - _需求：4.1, 4.2, 4.3_

  - [ ]* 6.4 编写属性测试：指数退避单调性
    - **功能：neuvector-cluster-auto-join，属性 6：指数退避单调性**
    - **验证：需求 4.1, 4.3**
    - 生成随机的重试序列
    - 验证每次延迟 >= 前一次延迟
    - 验证所有延迟 <= 最大延迟
    - _需求：4.1, 4.3_

  - [x] 6.5 实现 _reauth 方法
    - 调用现有的 _login 函数重新认证
    - 返回认证是否成功
    - _需求：5.2_

- [x] 7. 实现主执行流程 execute_join
  - [x] 7.1 实现 execute_join 方法主逻辑
    - 验证配置
    - 获取 join token
    - 生成集群名称
    - 构建请求体
    - 发送请求（带重试循环）
    - 处理各种错误响应
    - 记录详细日志
    - _需求：1.5, 4.4, 4.5, 7.1, 7.5_

  - [ ]* 7.2 编写属性测试：故障隔离性
    - **功能：neuvector-cluster-auto-join，属性 9：故障隔离性**
    - **验证：需求 6.5**
    - 模拟各种加入失败场景
    - 验证失败后 exporter 核心功能仍可启动
    - _需求：6.5_

  - [ ]* 7.3 编写属性测试：日志记录完整性
    - **功能：neuvector-cluster-auto-join，属性 10：日志记录完整性**
    - **验证：需求 7.1, 7.2, 7.3, 7.4, 7.5**
    - 生成随机的执行场景（成功和失败）
    - 验证所有场景都记录了关键阶段的日志
    - _需求：7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 8. 集成到主程序
  - [x] 8.1 在 main 函数中集成 FederationJoinManager
    - 在登录成功后、启动 exporter 服务器前调用
    - 创建 FederationJoinManager 实例
    - 调用 load_config 加载配置
    - 如果启用，调用 execute_join
    - 确保失败不影响后续流程
    - _需求：6.5_

  - [ ]* 8.2 编写集成测试
    - 测试完整的启动流程
    - 测试加入成功场景
    - 测试加入失败但 exporter 正常启动
    - 测试功能禁用场景
    - _需求：1.5, 6.1, 6.2, 6.4, 6.5_

- [x] 9. 检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户
