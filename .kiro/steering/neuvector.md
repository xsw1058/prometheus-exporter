---
inclusion: always
---
nv_exporter.py中的NVApiCollector类不要做任何更改，包括现在的文档也不要做任何的改变。
下面是本次测试使用的环境变量
os.environ[ENV_CTRL_API_SVC] = "192.168.8.209:10443"
os.environ[ENV_CTRL_USERNAME] = "admin"
os.environ[ENV_CTRL_PASSWORD] = "Y3Lx1Ez3sq88oia3gG"
os.environ[ENV_EXPORTER_PORT] = "8068"
os.environ[ENV_JOIN_TOKEN_URL] = "https://neuvector-wk-test.mcdchina.net/join_token"
os.environ[ENV_PAAS_STORE_ID] = "u2204a"

<!------------------------------------------------------------------------------------
   Add rules to this file or a short description and have Kiro refine them for you.
   
   Learn about inclusion modes: https://kiro.dev/docs/steering/#inclusion-modes
-------------------------------------------------------------------------------------> 