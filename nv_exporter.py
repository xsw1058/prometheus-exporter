# pylint: disable=missing-module-docstring
# pylint: disable=bare-except
# pylint: disable=too-many-statements
# pylint: disable=too-many-locals

# This script uses the neuvector api to get information which can be used by
# prometheus. It used the following library
# https://prometheus.github.io/client_python/

# ----------------------------------------
# Imports
# ----------------------------------------
import argparse
import base64
import json
import os
import random
import signal
import string
import sys
import time
import urllib3
import requests
from prometheus_client import start_http_server, Metric, REGISTRY

# ----------------------------------------
# Constants
# ----------------------------------------

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SESSION = requests.Session()
ENABLE_ENFORCER_STATS = False

# ----------------------------------------
# Functions
# ----------------------------------------


def _login(ctrl_url, ctrl_user, ctrl_pass):
    """
    Login to the api and get a token
    """
    print("Login to controller ...")
    body = {"password": {"username": ctrl_user, "password": ctrl_pass}}
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(ctrl_url + '/v1/auth',
                                 headers=headers,
                                 data=json.dumps(body),
                                 verify=False)
    except requests.exceptions.RequestException as login_error:
        print(login_error)
        return -1

    if response.status_code != 200:
        message = json.loads(response.text)["message"]
        print(message)
        return -1

    token = json.loads(response.text)["token"]["token"]

    # Update request session
    SESSION.headers.update({"Content-Type": "application/json"})
    SESSION.headers.update({'X-Auth-Token': token})
    return 0

# ----------------------------------------
# Classes
# ----------------------------------------


class FederationJoinManager:
    """联邦加入管理器 - 处理集群自动加入的所有逻辑"""
    
    def __init__(self, endpoint, ctrl_user, ctrl_pass):
        """初始化管理器
        
        Args:
            ctrl_url: Controller URL
            ctrl_user: Controller 用户名
            ctrl_pass: Controller 密码
        """
        self._endpoint = endpoint
        self.ctrl_url = "https://" + endpoint
        self.ctrl_user = ctrl_user
        self.ctrl_pass = ctrl_pass
        # self._url = "https://" + endpoint

        # 配置参数（从环境变量加载）
        self.enabled = False
        self.paas_store_id = None
        self.join_token = None
        self.join_token_url = None
        self.join_address = None
        self.join_port = 443
        self.joint_rest_server = None
        self.joint_rest_port = None
        self.max_retries = 10
        self.initial_retry_delay = 10
        self.max_retry_delay = 300
        
        # 运行时状态
        self.retry_count = 0
    
    def load_config(self):
        """从环境变量加载配置
        
        Returns:
            bool: 配置是否启用
        """
        # 检查是否启用联邦加入功能
        enable_str = os.environ.get(ENV_ENABLE_FED_JOIN, "false").lower()
        self.enabled = enable_str in ["true", "1", "yes"]
        
        if not self.enabled:
            return False
        
        # 加载必要参数
        self.paas_store_id = os.environ.get(ENV_PAAS_STORE_ID)
        self.join_token = os.environ.get(ENV_JOIN_TOKEN)
        self.join_token_url = os.environ.get(ENV_JOIN_TOKEN_URL)
        self.join_address = os.environ.get(ENV_JOIN_ADDRESS)
        self.joint_rest_server = os.environ.get(ENV_JOINT_REST_SERVER)
        
        # 加载可选参数
        port_str = os.environ.get(ENV_JOIN_PORT)
        if port_str:
            try:
                self.join_port = int(port_str)
            except ValueError:
                print(f"Warning: Invalid MASTER_CLUSTER_PORT value: {port_str}, using default 443")
                self.join_port = 443
        
        joint_port_str = os.environ.get(ENV_JOINT_REST_PORT)
        if joint_port_str:
            try:
                self.joint_rest_port = int(joint_port_str)
            except ValueError:
                print(f"Warning: Invalid JOINT_REST_PORT value: {joint_port_str}")
                self.joint_rest_port = None
        
        max_retries_str = os.environ.get(ENV_MAX_JOIN_RETRIES)
        if max_retries_str:
            try:
                self.max_retries = int(max_retries_str)
            except ValueError:
                print(f"Warning: Invalid MAX_JOIN_RETRIES value: {max_retries_str}, using default 10")
                self.max_retries = 10
        
        return True
    
    def _validate_config(self):
        """验证配置完整性
        
        Returns:
            tuple[bool, str]: (是否有效, 错误信息)
        """
        # 检查必要参数
        if not self.paas_store_id:
            return False, "PAAS_STORE_ID is required"
        
        # if not self.joint_rest_server:
        #     return False, "JOINT_REST_SERVER is required"
        
        # if not self.joint_rest_port:
        #     return False, "JOINT_REST_PORT is required"
        
        # 检查 token 来源（至少有一个）
        if not self.join_token and not self.join_token_url:
            return False, "Either JOIN_TOKEN or JOIN_TOKEN_URL must be provided"
        
        return True, ""
    
    def _generate_cluster_name(self):
        """生成集群名称
        
        Returns:
            str: PAAS_STORE_ID + 6位随机字符串
        """
        # 生成 6 位随机字符串（字母和数字）
        random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        return f"{self.paas_store_id}-{random_suffix}"
    
    def _get_join_address(self):
        """获取主集群地址
        
        Returns:
            str: 主集群地址（直接提供或根据 PAAS_STORE_ID 拼接）
        """
        # 如果直接提供了地址，优先使用
        if self.join_address:
            return self.join_address
        
        # 否则根据 PAAS_STORE_ID 拼接地址
        return f"cn-wukong-r{self.paas_store_id}.mcd.store"
    
    def _fetch_join_token(self):
        """获取 join token
        
        Returns:
            tuple[bool, str]: (是否成功, token字符串)
        """
        # 如果直接提供了 token，使用它
        if self.join_token:
            print("Using join token from environment variable")
            return True, self.join_token
        
        # 如果提供了 URL，从 URL 获取
        if self.join_token_url:
            print(f"Fetching join token from URL: {self.join_token_url}")
            return self._fetch_token_from_url(self.join_token_url)
        
        # 不应该到达这里，因为 _validate_config 已经检查过
        return False, ""
    
    def _fetch_token_from_url(self, url):
        """从 URL 获取 token
        
        Args:
            url: token URL
            
        Returns:
            tuple[bool, str]: (是否成功, token字符串)
        """
        try:
            response = requests.get(url, verify=False)
            if response.status_code == 200:
                response_json = json.loads(response.text)
                join_token = response_json.get("context")
                if join_token:
                    print("Successfully fetched join token from URL")
                    return True, join_token
                else:
                    print("Error: 'context' field not found in response")
                    return False, ""
            else:
                print(f"Error: Failed to fetch token, status code: {response.status_code}")
                return False, ""
        except requests.exceptions.RequestException as e:
            print(f"Error: Network error while fetching token: {e}")
            return False, ""
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse JSON response: {e}")
            return False, ""
    
    def _parse_token(self, token):
        """解析 token 内容（base64 解码）
        
        Args:
            token: base64 编码的 token
            
        Returns:
            dict: 包含 server 和 port 的字典，失败返回 None
        """
        try:
            # Base64 解码
            token_str = base64.b64decode(token).decode("utf-8")
            # 解析 JSON
            token_data = json.loads(token_str)
            # 提取 server 和 port
            server = token_data.get("s")
            port = token_data.get("p")
            if server and port:
                return {"server": server, "port": port}
            else:
                print("Error: Token does not contain 's' or 'p' fields")
                return None
        except Exception as e:
            print(f"Error: Failed to parse token: {e}")
            return None
    
    def _build_join_request(self, join_token, cluster_name):
        """构建加入请求体
        
        Args:
            join_token: join token 字符串
            cluster_name: 集群名称
            
        Returns:
            dict: 请求体字典
        """
        request_body = {
            "name": cluster_name,
            "join_token": join_token,
            "joint_rest_info": {
                "server": self._get_join_address(),
                "port": self.join_port
            }
        }
        return request_body
    
    def _send_join_request(self, request_body):
        """发送加入请求到主集群
        
        Args:
            request_body: 请求体
            
        Returns:
            tuple[bool, int, str]: (是否成功, 状态码, 响应消息)
        """
        # 获取主集群地址
        # master_address = self._get_master_address()
        # master_port = self.master_cluster_port
        
        # 构建完整的 URL
        # url = f"https://{master_address}:{master_port}/v1/fed/join"
        
        print(f"Sending request body:{request_body}")
        print(f"Sending ctrl_url: {self.ctrl_url}")
        try:
            response = SESSION.post(self.ctrl_url + "/v1/fed/join", data=json.dumps(request_body), verify=False)
            status_code = response.status_code
            
            if status_code == 200:
                print(f"Join request successful: {status_code}")
                return True, status_code, "Success"
            else:
                try:
                    message = json.loads(response.text).get("message", response.text)
                except:
                    message = response.text
                print(f"Join request failed: {status_code} - {message}")
                return False, status_code, message
        except requests.exceptions.RequestException as e:
            print(f"Network error during join request: {e}")
            return False, 0, str(e)
    
    def _handle_error_response(self, status_code, message):
        """根据错误类型决定处理策略
        
        Args:
            status_code: HTTP 状态码
            message: 错误消息
            
        Returns:
            str: 处理策略 ('stop', 'reauth', 'retry')
        """
        # 400, 409 错误：停止重试
        if status_code in [400, 409]:
            print(f"Non-retryable error: {status_code} - {message}")
            return 'stop'
        
        # 401 错误：重新认证
        if status_code == 401:
            print(f"Authentication failed, will re-login: {status_code} - {message}")
            return 'reauth'
        
        # 500+ 错误或网络错误：重试
        if status_code >= 500 or status_code == 0:
            print(f"Retryable error: {status_code} - {message}")
            return 'retry'
        
        # 其他未知错误，默认重试
        print(f"Unknown error, will retry: {status_code} - {message}")
        return 'retry'
    
    def _calculate_backoff_delay(self):
        """计算指数退避延迟时间
        
        Returns:
            int: 等待秒数
        """
        delay = self.initial_retry_delay * (2 ** self.retry_count)
        return min(delay, self.max_retry_delay)
    
    def _reauth(self):
        """重新认证到 Controller
        
        Returns:
            bool: 认证是否成功
        """
        print("Re-authenticating to controller...")
        result = _login(self.ctrl_url, self.ctrl_user, self.ctrl_pass)
        return result == 0
    
    def execute_join(self):
        """执行完整的加入流程（主入口方法）
        
        Returns:
            bool: 是否成功加入
        """
        print("=" * 60)
        print("Starting federation join process...")
        print("=" * 60)
        
        # 验证配置
        valid, error_msg = self._validate_config()
        if not valid:
            print(f"Configuration validation failed: {error_msg}")
            print("Skipping federation join")
            return False
        
        # 获取 join token
        success, join_token = self._fetch_join_token()
        if not success:
            print("Failed to fetch join token")
            print("Skipping federation join")
            return False
        
        # 生成集群名称
        cluster_name = self._generate_cluster_name()
        
        print(f"Cluster name: {cluster_name}")
        # print(f"Joint REST info: {self.joint_rest_server}:{self.joint_rest_port}")
        
        # 构建请求体
        request_body = self._build_join_request(join_token, cluster_name)
        
        # 发送请求（带重试）
        self.retry_count = 0
        while self.retry_count <= self.max_retries:
            if self.retry_count > 0:
                delay = self._calculate_backoff_delay()
                print(f"Retry {self.retry_count}/{self.max_retries} after {delay} seconds...")
                time.sleep(delay)
            
            # 发送加入请求
            success, status_code, message = self._send_join_request(request_body)
            
            if success:
                print("=" * 60)
                print("Federation join completed successfully!")
                print("=" * 60)
                return True
            
            # 处理错误
            strategy = self._handle_error_response(status_code, message)
            
            if strategy == 'stop':
                print("Stopping retry due to non-retryable error")
                break
            elif strategy == 'reauth':
                if self._reauth():
                    print("Re-authentication successful, retrying...")
                    # 不增加 retry_count，直接重试
                    continue
                else:
                    print("Re-authentication failed, stopping")
                    break
            elif strategy == 'retry':
                self.retry_count += 1
                if self.retry_count > self.max_retries:
                    print(f"Max retries ({self.max_retries}) reached")
                    break
        
        print("=" * 60)
        print("Federation join failed, but exporter will continue running")
        print("=" * 60)
        return False


class NVApiCollector:
    """
    main api object
    """

    def __init__(self, endpoint, ctrl_user, ctrl_pass):
        """
        Initialize the object
        """
        self._endpoint = endpoint
        self._user = ctrl_user
        self._pass = ctrl_pass
        self._url = "https://" + endpoint

    def sigterm_handler(self, _signo, _stack_frame):
        """
        Logout when terminated
        """
        print("Logout ...")
        SESSION.delete(self._url + '/v1/auth')
        sys.exit(0)

    def get(self, path):
        """
        Function to perform the get operations
        inside the class
        """
        retry = 0
        while retry < 2:
            try:
                response = SESSION.get(self._url + path, verify=False)
            except requests.exceptions.RequestException as response_error:
                print(response_error)
                retry += 1
            else:
                if response.status_code == 401 or response.status_code == 408:
                    _login(self._url, self._user, self._pass)
                    retry += 1
                else:
                    return response

        print("Failed to GET " + path)

    def collect(self):
        """
        Collect the required information
        This method is called by the library, for more information
        see https://prometheus.io/docs/instrumenting/writing_clientlibs/#overall-structure
        """
        eps = self._endpoint.split(':')
        ep = eps[0]

        # Get system summary
        response = self.get('/v1/system/summary')
        if response:
            sjson = json.loads(response.text)
            # Set summary metrics
            metric = Metric('nv_summary', 'A summary of ' + ep, 'summary')
            metric.add_sample('nv_summary_services',
                              value=sjson["summary"]["services"],
                              labels={'target': ep})
            metric.add_sample('nv_summary_policy',
                              value=sjson["summary"]["policy_rules"],
                              labels={'target': ep})
            metric.add_sample('nv_summary_runningWorkloads',
                              value=sjson["summary"]["running_workloads"],
                              labels={'target': ep})
            metric.add_sample('nv_summary_totalWorkloads',
                              value=sjson["summary"]["workloads"],
                              labels={'target': ep})
            metric.add_sample('nv_summary_hosts',
                              value=sjson["summary"]["hosts"],
                              labels={'target': ep})
            metric.add_sample('nv_summary_controllers',
                              value=sjson["summary"]["controllers"],
                              labels={'target': ep})
            metric.add_sample('nv_summary_enforcers',
                              value=sjson["summary"]["enforcers"],
                              labels={'target': ep})
            metric.add_sample('nv_summary_pods',
                              value=sjson["summary"]["running_pods"],
                              labels={'target': ep})
            metric.add_sample('nv_summary_disconnectedEnforcers',
                              value=sjson["summary"]["disconnected_enforcers"],
                              labels={'target': ep})
            dt = sjson["summary"]["cvedb_create_time"]
            if not dt:
                metric.add_sample('nv_summary_cvedbVersion',
                                  value=1.0,
                                  labels={'target': ep})
            else:
                metric.add_sample('nv_summary_cvedbVersion',
                                  value=sjson["summary"]["cvedb_version"],
                                  labels={'target': ep})
            # Convert time, set CVEDB create time
            dt = sjson["summary"]["cvedb_create_time"]
            if not dt:
                metric.add_sample('nv_summary_cvedbTime',
                                  value=0,
                                  labels={'target': ep})
            else:
                ts = time.strptime(dt, '%Y-%m-%dT%H:%M:%SZ')
                metric.add_sample('nv_summary_cvedbTime',
                                  value=time.mktime(ts) * 1000,
                                  labels={'target': ep})
            yield metric

        # Get conversation
        response = self.get('/v1/conversation')
        if response:
            # Set conversation metrics
            metric = Metric('nv_conversation', 'conversation of ' + ep,
                            'gauge')
            for c in json.loads(response.text)['conversations']:
                try:
                    c['ports']
                except KeyError:
                    port_exists = False
                else:
                    port_exists = True
                if port_exists is True:
                    for k in c['ports']:
                        if c['bytes'] != 0:
                            metric.add_sample('nv_conversation_bytes',
                                              value=c['bytes'],
                                              labels={
                                                  'port': k,
                                                  'from': c['from'],
                                                  'to': c['to'],
                                                  'target': ep
                                              })
            yield metric

        # Get enforcer
        if ENABLE_ENFORCER_STATS:
            response = self.get('/v1/enforcer')
            if response:
                # Read each enforcer, set enforcer metrics
                metric = Metric('nv_enforcer', 'enforcers of ' + ep, 'gauge')
                for c in json.loads(response.text)['enforcers']:
                    response2 = self.get('/v1/enforcer/' + c['id'] + '/stats')
                    if response2:
                        ejson = json.loads(response2.text)
                        metric.add_sample('nv_enforcer_cpu',
                                          value=ejson['stats']['span_1']['cpu'],
                                          labels={
                                              'id': c['id'],
                                              'host': c['host_name'],
                                              'display': c['display_name'],
                                              'target': ep
                                          })
                        metric.add_sample('nv_enforcer_memory',
                                          value=ejson['stats']['span_1']['memory'],
                                          labels={
                                              'id': c['id'],
                                              'host': c['host_name'],
                                              'display': c['display_name'],
                                              'target': ep
                                          })
                yield metric

        # Get controller
        response = self.get('/v1/controller')
        if response:
            # Read each controller, set controller metrics
            metric = Metric('nv_controller', 'controllers of ' + ep, 'gauge')
            for c in json.loads(response.text)['controllers']:
                response2 = self.get('/v1/controller/' + c['id'] + '/stats')
                if response2:
                    ejson = json.loads(response2.text)
                    metric.add_sample('nv_controller_cpu',
                                      value=ejson['stats']['span_1']['cpu'],
                                      labels={
                                          'id': c['id'],
                                          'host': c['host_name'],
                                          'display': c['display_name'],
                                          'target': ep
                                      })
                    metric.add_sample('nv_controller_memory',
                                      value=ejson['stats']['span_1']['memory'],
                                      labels={
                                          'id': c['id'],
                                          'host': c['host_name'],
                                          'display': c['display_name'],
                                          'target': ep
                                      })
            yield metric

        # Get host
        response = self.get('/v1/host')
        if response:
            # Set host metrics
            metric = Metric('nv_host', 'host information of ' + ep, 'gauge')
            for c in json.loads(response.text)['hosts']:
                metric.add_sample('nv_host_memory',
                                  value=c['memory'],
                                  labels={
                                      'name': c['name'],
                                      'id': c['id'],
                                      'target': ep
                                  })
            yield metric

        # Get debug admission stats
        response = self.get('/v1/debug/admission_stats')
        if response:
            if response.status_code != 200:
                print("Admission control stats request failed: %s" % response)
            else:
                djson = json.loads(response.text)
                # Set admission metrics
                metric = Metric('nv_admission', 'Debug admission stats of ' + ep,
                                'gauge')
                metric.add_sample('nv_admission_allowed',
                                  value=djson['stats']['k8s_allowed_requests'],
                                  labels={'target': ep})
                metric.add_sample('nv_admission_denied',
                                  value=djson['stats']['k8s_denied_requests'],
                                  labels={'target': ep})
                yield metric

        # Get image vulnerability
        response = self.get('/v1/scan/registry')
        if response:
            # Set vulnerability metrics
            metric = Metric('nv_image_vulnerability',
                            'image vulnerability of ' + ep, 'gauge')
            for c in json.loads(response.text)['summarys']:
                response2 = self.get('/v1/scan/registry/' + c['name'] + '/images')
                if response2:
                    for img in json.loads(response2.text)['images']:
                        metric.add_sample('nv_image_vulnerabilityHigh',
                                          value=img['high'],
                                          labels={
                                              'name': "%s:%s" % (img['repository'], img['tag']),
                                              'imageid': img['image_id'],
                                              'target': ep
                                          })
                        metric.add_sample('nv_image_vulnerabilityMedium',
                                          value=img['medium'],
                                          labels={
                                              'name': "%s:%s" % (img['repository'], img['tag']),
                                              'imageid': img['image_id'],
                                              'target': ep
                                          })
            yield metric

        # Get platform vulnerability
        response = self.get('/v1/scan/platform/')
        if response:
            # Set vulnerability metrics
            metric = Metric('nv_platform_vulnerability',
                            'platform vulnerability of ' + ep, 'gauge')
            for platform in json.loads(response.text)['platforms']:
                if (platform['high'] != 0 or platform['medium'] != 0):
                    metric.add_sample('nv_platform_vulnerabilityHigh',
                                    value=platform['high'],
                                    labels={
                                        'name': platform['platform'],
                                        'target': ep
                                    })
                    metric.add_sample('nv_platform_vulnerabilityMedium',
                                    value=platform['medium'],
                                    labels={
                                        'name': platform['platform'],
                                        'target': ep
                                    })
            yield metric

        # Get container vulnerability
        response = self.get('/v1/workload?brief=true')
        if response:
            # Set vulnerability metrics
            cvlist = []
            metric = Metric('nv_container_vulnerability',
                            'container vulnerability of ' + ep, 'gauge')
            for c in json.loads(response.text)['workloads']:
                if c['service'] not in cvlist and c['service_mesh_sidecar'] is False:
                    scan = c['scan_summary']
                    if scan != None and (scan['high'] != 0 or scan['medium'] != 0):
                        metric.add_sample('nv_container_vulnerabilityHigh',
                                          value=scan['high'],
                                          labels={
                                              'service': c['service'],
                                              'target': ep
                                          })
                        metric.add_sample('nv_container_vulnerabilityMedium',
                                          value=scan['medium'],
                                          labels={
                                              'service': c['service'],
                                              'target': ep
                                          })
                        cvlist.append(c['service'])
            yield metric

        # Set Log metrics
        metric = Metric('nv_log', 'log of ' + ep, 'gauge')
        # Get log threat
        response = self.get('/v1/log/threat')
        if response:
            # Set threat
            ttimelist = []
            tnamelist = []
            tcnamelist = []
            tcnslist = []
            tsnamelist = []
            tsnslist = []
            tidlist = []
            for c in json.loads(response.text)['threats']:
                ttimelist.append(c['reported_timestamp'])
                tnamelist.append(c['name'])
                tcnamelist.append(c['client_workload_name'])
                tcnslist.append(c['client_workload_domain'] if 'client_workload_domain' in c else "")
                tsnamelist.append(c['server_workload_name'])
                tsnslist.append(c['server_workload_domain'] if 'server_workload_domain' in c else "")
                tidlist.append(c['id'])
            for x in range(0, min(5, len(tidlist))):
                metric.add_sample('nv_log_events',
                                  value=ttimelist[x] * 1000,
                                  labels={
                                      'log': "threat",
                                      'fromname': tcnamelist[x],
                                      'fromns': tcnslist[x],
                                      'toname': tsnamelist[x],
                                      'tons': tsnamelist[x],
                                      'id': tidlist[x],
                                      'name': tnamelist[x],
                                      'target': ep
                                  })

        # Get log incident
        response = self.get('/v1/log/incident')
        if response:
            # Set incident metrics
            itimelist = []
            inamelist = []
            iwnamelist = []
            iclusterlist = []
            iwnslist = []
            iwidlist = []
            iidlist = []
            iproc_name_list = []
            iproc_path_list = []
            iproc_cmd_list = []
            ifile_path_list = []
            ifile_name_list = []

            for c in json.loads(response.text)['incidents']:
                itimelist.append(c['reported_timestamp'])
                iidlist.append(c['id'])
                inamelist.append(c['name'])

                # Check proc_name
                if 'proc_name' in c:
                    iproc_name_list.append(c['proc_name'])
                else:
                    iproc_name_list.append("")

                # Check proc_path
                if 'proc_path' in c:
                    iproc_path_list.append(c['proc_path'])
                else:
                    iproc_path_list.append("")

                # Check proc_cmd
                if 'proc_cmd' in c:
                    iproc_cmd_list.append(c['proc_cmd'])
                else:
                    iproc_cmd_list.append("")

                # Check file_path
                if 'file_path' in c:
                    ifile_path_list.append(c['file_path'])
                else:
                    ifile_path_list.append("")

                # Check file_name
                if 'file_name' in c:
                    ifile_name_list.append(c['file_name'])
                else:
                    ifile_name_list.append("")

                if 'workload_name' in c:
                    iwnamelist.append(c['workload_name'])
                    iclusterlist.append(c['cluster_name'])
                    iwnslist.append(c['workload_domain'] if 'workload_domain' in c else "")
                    iwidlist.append(c['workload_id'])
                else:
                    iwnamelist.append("")
                    iclusterlist.append("")
                    iwnslist.append("")
                    iwidlist.append("")

            for x in range(0, min(5, len(iidlist))):
                metric.add_sample('nv_log_events',
                                  value=itimelist[x] * 1000,
                                  labels={
                                      'log': "incident",
                                      'fromname': iwnamelist[x],
                                      'fromns': iwnslist[x],
                                      'fromid': iwidlist[x],
                                      'toname': " ",
                                      'tons': " ",
                                      'cluster': iclusterlist[x],
                                      'name': inamelist[x],
                                      'id': iidlist[x],
                                      'procname': iproc_name_list[x],
                                      'procpath': iproc_path_list[x],
                                      'proccmd': iproc_cmd_list[x],
                                      'filepath': ifile_path_list[x],
                                      'filename': ifile_name_list[x],
                                      'target': ep
                                  })

        # Get log violation
        response = self.get('/v1/log/violation')
        if response:
            # Set violation metrics
            vtimelist = []
            vnamelist = []
            vcnamelist = []
            vcnslist = []
            vcidlist = []
            vsnamelist = []
            vsnslist = []
            vidlist = []
            for c in json.loads(response.text)['violations']:
                vtimelist.append(c['reported_timestamp'])
                vcnamelist.append(c['client_name'])
                vcnslist.append(c['client_domain'] if 'client_domain' in c else "")
                vcidlist.append(c['client_id'])
                vnamelist.append("Network Violation")
                vsnamelist.append(c['server_name'])
                vsnslist.append(c['server_domain'] if 'server_domain' in c else "")
                vidlist.append(c['id'])
            for x in range(0, min(5, len(vidlist))):
                metric.add_sample('nv_log_events',
                                  value=vtimelist[x] * 1000,
                                  labels={
                                      'log': "violation",
                                      'id': vidlist[x],
                                      'fromname': vcnamelist[x],
                                      'fromns': vcnslist[x],
                                      'fromid': vcidlist[x],
                                      'toname': vsnamelist[x],
                                      'tons': vsnslist[x],
                                      'name': vnamelist[x],
                                      'target': ep
                                  })
            yield metric

        # Get federated information
        # Create nv_fed metric
        metric = Metric('nv_fed', 'log of ' + ep, 'gauge')

        # Get the api endpoint
        response = self.get('/v1/fed/member')

        # Check the respone
        if response:

            # Perform json load
            sjson = json.loads(response.text)

            # Check if the cluster is a federated master
            if sjson['fed_role'] == "master":

                # Set name of the master cluster
                fed_master_name = sjson['master_cluster']['name']

                # Loop through the list of nodes
                for fed_worker in sjson['joint_clusters']:

                    # Set status variable
                    if fed_worker['status'] != "synced":

                        # Set value to 0
                        fed_worker_value = 0

                    else:
                        fed_worker_value = 1

                    # Write the fed master metrics
                    metric.add_sample('nv_fed_master',
                                      value=fed_worker_value,
                                      labels={
                                          'master': fed_master_name,
                                          'worker': fed_worker['name'],
                                          'status': fed_worker['status']
                                      })
                yield metric

            # Add worker metrics
            else:

                # Write the worker metrics
                if sjson['fed_role'] != "joint":
                    fed_joint_status = 0
                else:
                    fed_joint_status = 1

                # Check if there is a master entry present
                if 'master_cluster' in sjson:
                    fed_master_cluster = sjson['master_cluster']['name']
                else:
                    fed_master_cluster = ""

                # Write the metrics
                metric.add_sample('nv_fed_worker',
                                  value=fed_joint_status,
                                  labels={
                                      'status': sjson['fed_role'],
                                      'master': fed_master_cluster
                                  })
                yield metric


ENV_CTRL_API_SVC = "CTRL_API_SERVICE"
ENV_CTRL_USERNAME = "CTRL_USERNAME"
ENV_CTRL_PASSWORD = "CTRL_PASSWORD"
ENV_EXPORTER_PORT = "EXPORTER_PORT"
ENV_ENFORCER_STATS = "ENFORCER_STATS"

# Federation join environment variables
ENV_ENABLE_FED_JOIN = "ENABLE_FED_JOIN"
ENV_PAAS_STORE_ID = "PAAS_STORE_ID"
ENV_JOIN_TOKEN = "JOIN_TOKEN"
ENV_JOIN_TOKEN_URL = "JOIN_TOKEN_URL"
ENV_JOIN_ADDRESS = "JOIN_ADDRESS"
ENV_JOIN_PORT = "JOIN_PORT"
ENV_JOINT_REST_SERVER = "JOINT_REST_SERVER"
ENV_JOINT_REST_PORT = "JOINT_REST_PORT"
ENV_MAX_JOIN_RETRIES = "MAX_JOIN_RETRIES"
# 设置测试环境变量
os.environ["CTRL_API_SERVICE"] = "192.168.8.209:10443"
os.environ["CTRL_USERNAME"] = "admin"
os.environ["CTRL_PASSWORD"] = "Y3Lx1Ez3sq88oia3gG"
os.environ["EXPORTER_PORT"] = "8068"
os.environ["ENABLE_FED_JOIN"] = "true"
os.environ["PAAS_STORE_ID"] = "u2204a"
os.environ["JOIN_ADDRESS"] = "u2204a.xsw.com"
# os.environ["JOIN_PORT"] = "10443"
os.environ["JOIN_TOKEN_URL"] = "https://neuvector.xsw.com/join_token"
# os.environ["JOINT_REST_SERVER"] = "192.168.8.209"
# os.environ["JOINT_REST_PORT"] = "10443"
# os.environ["JOIN_TOKEN"] = "eyJzIjoibmV1dmVjdG9yLXdrLXRlc3QubWNkY2hpbmEubmV0IiwicCI6NDQzLCJ0IjoiS2g5b3YvczhxRXJSMFVRU1ZERjRwdW1JRmFxZktycWxhajZyRTZvVzhEVFhYQWVYK1VhR01HS0pTNnN5Nmc9PSJ9"

if __name__ == '__main__':
    PARSER = argparse.ArgumentParser(description='NeuVector command line.')
    PARSER.add_argument("-e", "--port", type=int, help="exporter port")
    PARSER.add_argument("-s",
                        "--server",
                        type=str,
                        help="controller API service")
    PARSER.add_argument("-u",
                        "--username",
                        type=str,
                        help="controller user name")
    PARSER.add_argument("-p",
                        "--password",
                        type=str,
                        help="controller user password")
    ARGSS = PARSER.parse_args()

    if ARGSS.server:
        CTRL_SVC = ARGSS.server
    elif ENV_CTRL_API_SVC in os.environ:
        CTRL_SVC = os.environ.get(ENV_CTRL_API_SVC)
    else:
        sys.exit("Controller API service endpoint must be specified.")

    if ARGSS.port:
        PORT = ARGSS.port
    elif ENV_EXPORTER_PORT in os.environ:
        PORT = int(os.environ.get(ENV_EXPORTER_PORT))
    else:
        sys.exit("Exporter port must be specified.")

    if ARGSS.username:
        CTRL_USER = ARGSS.username
    elif ENV_CTRL_USERNAME in os.environ:
        CTRL_USER = os.environ.get(ENV_CTRL_USERNAME)
    else:
        CTRL_USER = "admin"

    if ARGSS.password:
        CTRL_PASS = ARGSS.password
    elif ENV_CTRL_PASSWORD in os.environ:
        CTRL_PASS = os.environ.get(ENV_CTRL_PASSWORD)
    else:
        CTRL_PASS = "admin"

    if ENV_ENFORCER_STATS in os.environ:
        try:
            ENABLE_ENFORCER_STATS = bool(os.environ.get(ENV_ENFORCER_STATS))
        except NameError:
            ENABLE_ENFORCER_STATS = False

    # Login and get token
    if _login("https://" + CTRL_SVC, CTRL_USER, CTRL_PASS) < 0:
        sys.exit(1)
    # Federation join (if enabled)
    try:
        fed_manager = FederationJoinManager(CTRL_SVC, CTRL_USER, CTRL_PASS)
        if fed_manager.load_config():
            print("\nFederation join is enabled")
            fed_manager.execute_join()
        else:
            print("\nFederation join is disabled")
    except Exception as e:
        print(f"\nFederation join failed with exception: {e}")
        print("Continuing with normal exporter operation...")

    print("\nStart exporter server ...")
    start_http_server(PORT)

    print("Register collector ...")
    COLLECTOR = NVApiCollector(CTRL_SVC, CTRL_USER, CTRL_PASS)
    REGISTRY.register(COLLECTOR)
    signal.signal(signal.SIGTERM, COLLECTOR.sigterm_handler)

    while True:
        time.sleep(30)
