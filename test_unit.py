#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单元测试 - 不依赖网络连接
"""

import os
import sys
import base64
import json

# 设置测试环境变量
os.environ["CTRL_API_SERVICE"] = "192.168.8.209:10443"
os.environ["CTRL_USERNAME"] = "admin"
os.environ["CTRL_PASSWORD"] = "test_password"
os.environ["EXPORTER_PORT"] = "8068"
os.environ["ENABLE_FED_JOIN"] = "true"
os.environ["PAAS_STORE_ID"] = "test123"
os.environ["JOIN_TOKEN"] = "test_token_value"  # 直接提供 token，不从 URL 获取
os.environ["JOINT_REST_SERVER"] = "192.168.1.100"
os.environ["JOINT_REST_PORT"] = "10443"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nv_exporter import FederationJoinManager

print("=" * 80)
print("单元测试 - FederationJoinManager")
print("=" * 80)

# 创建管理器实例
manager = FederationJoinManager("https://192.168.8.209:10443", "admin", "test_password")

# 测试 1: 配置加载
print("\n测试 1: 配置加载")
assert manager.load_config() == True, "配置加载应该返回 True"
assert manager.enabled == True, "enabled 应该为 True"
assert manager.paas_store_id == "test123", "paas_store_id 应该为 test123"
assert manager.join_token == "test_token_value", "join_token 应该正确加载"
assert manager.joint_rest_server == "192.168.1.100", "joint_rest_server 应该正确加载"
assert manager.joint_rest_port == 10443, "joint_rest_port 应该为 10443"
print("✓ 配置加载测试通过")

# 测试 2: 配置验证
print("\n测试 2: 配置验证")
valid, error_msg = manager._validate_config()
assert valid == True, f"配置验证应该通过，但得到错误: {error_msg}"
print("✓ 配置验证测试通过")

# 测试 3: 集群名称生成
print("\n测试 3: 集群名称生成")
cluster_name = manager._generate_cluster_name()
assert cluster_name.startswith("test123-"), f"集群名称应该以 'test123-' 开头，但得到: {cluster_name}"
assert len(cluster_name) == len("test123-") + 6, f"集群名称长度应该为 {len('test123-') + 6}，但得到: {len(cluster_name)}"
print(f"✓ 集群名称生成测试通过: {cluster_name}")

# 测试 4: 主集群地址获取（无直接地址）
print("\n测试 4: 主集群地址获取（拼接）")
manager.master_cluster_address = None
address = manager._get_master_address()
expected = "cn-wukong-rtest123.mcd.store"
assert address == expected, f"地址应该为 {expected}，但得到: {address}"
print(f"✓ 地址拼接测试通过: {address}")

# 测试 5: 主集群地址获取（有直接地址）
print("\n测试 5: 主集群地址获取（直接提供）")
manager.master_cluster_address = "custom.master.com"
address = manager._get_master_address()
assert address == "custom.master.com", f"应该使用直接提供的地址，但得到: {address}"
print(f"✓ 配置优先级测试通过: {address}")

# 测试 6: Token 获取（直接提供）
print("\n测试 6: Token 获取（直接提供）")
success, token = manager._fetch_join_token()
assert success == True, "Token 获取应该成功"
assert token == "test_token_value", f"Token 应该为 'test_token_value'，但得到: {token}"
print("✓ Token 获取测试通过")

# 测试 7: Token 解析
print("\n测试 7: Token 解析")
# 创建一个测试 token
test_token_data = {"s": "master.example.com", "p": 443}
test_token_json = json.dumps(test_token_data)
test_token_encoded = base64.b64encode(test_token_json.encode()).decode()

parsed = manager._parse_token(test_token_encoded)
assert parsed is not None, "Token 解析不应该返回 None"
assert parsed["server"] == "master.example.com", f"Server 应该为 'master.example.com'，但得到: {parsed['server']}"
assert parsed["port"] == 443, f"Port 应该为 443，但得到: {parsed['port']}"
print("✓ Token 解析测试通过")

# 测试 8: 请求体构建
print("\n测试 8: 请求体构建")
request_body = manager._build_join_request("test_token", "test_cluster")
assert "name" in request_body, "请求体应该包含 'name' 字段"
assert "join_token" in request_body, "请求体应该包含 'join_token' 字段"
assert "joint_rest_info" in request_body, "请求体应该包含 'joint_rest_info' 字段"
assert request_body["name"] == "test_cluster", f"name 应该为 'test_cluster'，但得到: {request_body['name']}"
assert request_body["join_token"] == "test_token", f"join_token 应该为 'test_token'，但得到: {request_body['join_token']}"
assert request_body["joint_rest_info"]["server"] == "192.168.1.100", "joint_rest_info.server 不正确"
assert request_body["joint_rest_info"]["port"] == 10443, "joint_rest_info.port 不正确"
print("✓ 请求体构建测试通过")

# 测试 9: 退避延迟计算
print("\n测试 9: 退避延迟计算")
delays = []
for i in range(6):
    manager.retry_count = i
    delay = manager._calculate_backoff_delay()
    delays.append(delay)

# 验证指数增长
assert delays[0] == 10, f"第 0 次重试延迟应该为 10，但得到: {delays[0]}"
assert delays[1] == 20, f"第 1 次重试延迟应该为 20，但得到: {delays[1]}"
assert delays[2] == 40, f"第 2 次重试延迟应该为 40，但得到: {delays[2]}"
assert delays[3] == 80, f"第 3 次重试延迟应该为 80，但得到: {delays[3]}"
assert delays[4] == 160, f"第 4 次重试延迟应该为 160，但得到: {delays[4]}"
assert delays[5] == 300, f"第 5 次重试延迟应该为 300（达到上限），但得到: {delays[5]}"

# 验证单调性
for i in range(len(delays) - 1):
    assert delays[i] <= delays[i+1], f"延迟应该单调递增，但 delays[{i}]={delays[i]} > delays[{i+1}]={delays[i+1]}"

print(f"✓ 退避延迟计算测试通过: {delays}")

# 测试 10: 错误处理策略
print("\n测试 10: 错误处理策略")
test_cases = [
    (400, "Bad Request", "stop"),
    (401, "Unauthorized", "reauth"),
    (409, "Conflict", "stop"),
    (500, "Internal Server Error", "retry"),
    (502, "Bad Gateway", "retry"),
    (503, "Service Unavailable", "retry"),
    (0, "Network Error", "retry"),
    (404, "Not Found", "retry"),  # 未知错误，默认重试
]

for status_code, message, expected in test_cases:
    strategy = manager._handle_error_response(status_code, message)
    assert strategy == expected, f"状态码 {status_code} 应该返回 '{expected}'，但得到: '{strategy}'"

print("✓ 错误处理策略测试通过")

# 测试 11: 配置验证失败场景
print("\n测试 11: 配置验证失败场景")

# 测试缺少 paas_store_id
manager_test = FederationJoinManager("https://test", "user", "pass")
manager_test.enabled = True
manager_test.paas_store_id = None
manager_test.joint_rest_server = "server"
manager_test.joint_rest_port = 443
manager_test.join_token = "token"
valid, error_msg = manager_test._validate_config()
assert valid == False, "缺少 paas_store_id 应该验证失败"
assert "PAAS_STORE_ID" in error_msg, f"错误消息应该提到 PAAS_STORE_ID，但得到: {error_msg}"

# 测试缺少 joint_rest_server
manager_test.paas_store_id = "test"
manager_test.joint_rest_server = None
valid, error_msg = manager_test._validate_config()
assert valid == False, "缺少 joint_rest_server 应该验证失败"
assert "JOINT_REST_SERVER" in error_msg, f"错误消息应该提到 JOINT_REST_SERVER，但得到: {error_msg}"

# 测试缺少 token 来源
manager_test.joint_rest_server = "server"
manager_test.join_token = None
manager_test.join_token_url = None
valid, error_msg = manager_test._validate_config()
assert valid == False, "缺少 token 来源应该验证失败"
assert "JOIN_TOKEN" in error_msg, f"错误消息应该提到 JOIN_TOKEN，但得到: {error_msg}"

print("✓ 配置验证失败场景测试通过")

# 测试 12: Token 解析往返一致性
print("\n测试 12: Token 解析往返一致性")
original_data = {"s": "test.server.com", "p": 8443}
# 编码
encoded = base64.b64encode(json.dumps(original_data).encode()).decode()
# 解码
decoded = manager._parse_token(encoded)
# 验证
assert decoded["server"] == original_data["s"], "往返后 server 应该一致"
assert decoded["port"] == original_data["p"], "往返后 port 应该一致"
print("✓ Token 解析往返一致性测试通过")

print("\n" + "=" * 80)
print("所有单元测试通过！✓")
print("=" * 80)
