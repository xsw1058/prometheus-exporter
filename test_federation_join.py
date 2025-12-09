#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试联邦加入功能的脚本
"""

import os
import sys

# 设置测试环境变量
os.environ["CTRL_API_SERVICE"] = "192.168.8.209:10443"
os.environ["CTRL_USERNAME"] = "admin"
os.environ["CTRL_PASSWORD"] = "Y3Lx1Ez3sq88oia3gG"
os.environ["EXPORTER_PORT"] = "8068"
os.environ["ENABLE_FED_JOIN"] = "true"
os.environ["PAAS_STORE_ID"] = "u2204a"
os.environ["JOIN_TOKEN_URL"] = "https://neuvector-wk-test.mcdchina.net/join_token"
os.environ["JOINT_REST_SERVER"] = "192.168.8.209"
os.environ["JOINT_REST_PORT"] = "10443"

# 导入 nv_exporter 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("测试联邦加入功能")
print("=" * 80)

# 测试导入
try:
    from nv_exporter import FederationJoinManager, _login
    print("✓ 成功导入 FederationJoinManager 类")
except ImportError as e:
    print(f"✗ 导入失败: {e}")
    sys.exit(1)

# 测试配置加载
print("\n" + "=" * 80)
print("测试 1: 配置加载")
print("=" * 80)

ctrl_url = "https://" + os.environ["CTRL_API_SERVICE"]
ctrl_user = os.environ["CTRL_USERNAME"]
ctrl_pass = os.environ["CTRL_PASSWORD"]

manager = FederationJoinManager(ctrl_url, ctrl_user, ctrl_pass)
if manager.load_config():
    print("✓ 配置加载成功")
    print(f"  - PAAS Store ID: {manager.paas_store_id}")
    print(f"  - Join Token URL: {manager.join_token_url}")
    print(f"  - Joint REST Server: {manager.joint_rest_server}:{manager.joint_rest_port}")
else:
    print("✗ 配置加载失败")
    sys.exit(1)

# 测试配置验证
print("\n" + "=" * 80)
print("测试 2: 配置验证")
print("=" * 80)

valid, error_msg = manager._validate_config()
if valid:
    print("✓ 配置验证通过")
else:
    print(f"✗ 配置验证失败: {error_msg}")
    sys.exit(1)

# 测试集群名称生成
print("\n" + "=" * 80)
print("测试 3: 集群名称生成")
print("=" * 80)

cluster_name = manager._generate_cluster_name()
print(f"✓ 生成的集群名称: {cluster_name}")
if cluster_name.startswith(manager.paas_store_id):
    print("✓ 集群名称格式正确")
else:
    print("✗ 集群名称格式错误")

# 测试主集群地址获取
print("\n" + "=" * 80)
print("测试 4: 主集群地址获取")
print("=" * 80)

master_address = manager._get_master_address()
print(f"✓ 主集群地址: {master_address}")

# 测试 Token 获取
print("\n" + "=" * 80)
print("测试 5: Token 获取")
print("=" * 80)

success, token = manager._fetch_join_token()
if success:
    print("✓ Token 获取成功")
    print(f"  Token 长度: {len(token)} 字符")
    
    # 测试 Token 解析
    print("\n" + "=" * 80)
    print("测试 6: Token 解析")
    print("=" * 80)
    
    token_data = manager._parse_token(token)
    if token_data:
        print("✓ Token 解析成功")
        print(f"  - Server: {token_data.get('server')}")
        print(f"  - Port: {token_data.get('port')}")
    else:
        print("✗ Token 解析失败")
else:
    print(f"✗ Token 获取失败")

# 测试请求体构建
print("\n" + "=" * 80)
print("测试 7: 请求体构建")
print("=" * 80)

if success:
    request_body = manager._build_join_request(token, cluster_name)
    print("✓ 请求体构建成功")
    print(f"  - name: {request_body.get('name')}")
    print(f"  - join_token: {request_body.get('join_token')[:20]}...")
    print(f"  - joint_rest_info: {request_body.get('joint_rest_info')}")
    
    # 验证请求体结构
    if all(key in request_body for key in ['name', 'join_token', 'joint_rest_info']):
        print("✓ 请求体包含所有必需字段")
    else:
        print("✗ 请求体缺少必需字段")

# 测试退避延迟计算
print("\n" + "=" * 80)
print("测试 8: 退避延迟计算")
print("=" * 80)

delays = []
for i in range(5):
    manager.retry_count = i
    delay = manager._calculate_backoff_delay()
    delays.append(delay)
    print(f"  重试 {i}: {delay} 秒")

# 验证单调性
is_monotonic = all(delays[i] <= delays[i+1] for i in range(len(delays)-1))
if is_monotonic:
    print("✓ 退避延迟单调递增")
else:
    print("✗ 退避延迟不是单调递增")

# 测试错误处理策略
print("\n" + "=" * 80)
print("测试 9: 错误处理策略")
print("=" * 80)

test_cases = [
    (400, "Bad Request", "stop"),
    (401, "Unauthorized", "reauth"),
    (409, "Conflict", "stop"),
    (500, "Internal Server Error", "retry"),
    (0, "Network Error", "retry"),
]

all_correct = True
for status_code, message, expected in test_cases:
    strategy = manager._handle_error_response(status_code, message)
    if strategy == expected:
        print(f"✓ {status_code}: {strategy}")
    else:
        print(f"✗ {status_code}: 期望 {expected}, 得到 {strategy}")
        all_correct = False

if all_correct:
    print("✓ 所有错误处理策略正确")

print("\n" + "=" * 80)
print("基础功能测试完成")
print("=" * 80)

# 询问是否执行完整的加入流程
print("\n是否执行完整的联邦加入流程？这将向主集群发送实际的加入请求。")
print("注意：这需要先登录到 Controller。")
response = input("继续？(y/n): ")

if response.lower() == 'y':
    print("\n" + "=" * 80)
    print("执行完整的联邦加入流程")
    print("=" * 80)
    
    # 先登录
    print("\n登录到 Controller...")
    if _login(ctrl_url, ctrl_user, ctrl_pass) == 0:
        print("✓ 登录成功")
        
        # 执行加入
        print("\n开始联邦加入...")
        result = manager.execute_join()
        
        if result:
            print("\n✓ 联邦加入成功！")
        else:
            print("\n✗ 联邦加入失败")
    else:
        print("✗ 登录失败")
else:
    print("\n跳过完整的联邦加入流程")

print("\n" + "=" * 80)
print("测试结束")
print("=" * 80)
