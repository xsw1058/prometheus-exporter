#!/bin/bash
# 演示联邦加入功能的脚本

echo "=========================================="
echo "NeuVector 联邦加入功能演示"
echo "=========================================="
echo ""

# 设置环境变量
export CTRL_API_SERVICE="192.168.8.209:10443"
export CTRL_USERNAME="admin"
export CTRL_PASSWORD="Y3Lx1Ez3sq88oia3gG"
export EXPORTER_PORT="8068"

# 联邦加入配置
export ENABLE_FED_JOIN="true"
export PAAS_STORE_ID="u2204a"
export JOIN_TOKEN_URL="https://neuvector-wk-test.mcdchina.net/join_token"
export JOINT_REST_SERVER="192.168.8.209"
export JOINT_REST_PORT="10443"
export MAX_JOIN_RETRIES="3"

echo "环境变量配置："
echo "  CTRL_API_SERVICE: $CTRL_API_SERVICE"
echo "  ENABLE_FED_JOIN: $ENABLE_FED_JOIN"
echo "  PAAS_STORE_ID: $PAAS_STORE_ID"
echo "  JOIN_TOKEN_URL: $JOIN_TOKEN_URL"
echo "  JOINT_REST_SERVER: $JOINT_REST_SERVER"
echo "  JOINT_REST_PORT: $JOINT_REST_PORT"
echo ""

echo "启动 NeuVector Exporter..."
echo "注意：联邦加入功能将在启动时自动执行"
echo ""

# 启动 exporter（这里只是演示，实际运行会启动 HTTP 服务器）
# python3 nv_exporter.py

echo "如果要实际运行，请取消注释上面的 python3 命令"
echo ""
echo "=========================================="
echo "演示结束"
echo "=========================================="
