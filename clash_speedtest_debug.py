import requests
import subprocess # Keep import for potential future utility
import time
import urllib.parse
import traceback
import math

# --- 请根据您的 Clash 配置修改以下设置 ---
# Updated CLASH_API based on external-controller in YAML
CLASH_API = "http://127.0.0.1:9097"
# SECRET = "your_clash_api_secret" # 如果没有密码，改为 SECRET = ""
SECRET = "mytoken123" # 从你的配置文件中获取
# --- Common browser headers (for download test) ---
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}
# --- Clash API request headers (automatically includes Bearer token if SECRET is set) ---
CLASH_API_HEADERS = {"Authorization": f"Bearer {SECRET}"} if SECRET else {}
# -------------------------------------------------

# --- Script Configuration ---
# TEST_GROUP_NAME: The group that will be actively switched during testing.
#                  This group MUST contain all the nodes you want to test.
#                  We will now use "自动选择" as requested.
TEST_GROUP_NAME = "自动选择" # <--- 修改：测试时切换这个组 (url-test 类型也可以手动切换)

# SOURCE_GROUP: The group from which to initially get the list of all nodes.
#               Since "自动选择" also includes all nodes, we use it here too.
SOURCE_GROUP = "自动选择" # <--- 修改：也从这个组获取节点列表

# FINAL_TARGET_GROUP: The group you want to ultimately point to the best node found.
#                     This is likely your main manual selection group. "默认" from your config.
FINAL_TARGET_GROUP = "默认" # <--- 最终要设置的组

# --- EXCLUDE List: Keywords to exclude nodes from testing ---
# Nodes whose names contain any of these (case-insensitive) keywords will be skipped.
EXCLUDE = ["DIRECT", "REJECT", "GLOBAL", "PASS", "PROXY", "LAN",
           "直连", "全局", "放行", "代理", "漏网之鱼", "广告拦截", # Common Chinese keywords
           "自动选择", "故障转移", "负载均衡", "节点选择", "最终选择", # Group type names
           "全部节点", # Exclude other major groups if necessary
           "切换", "故障", # Other utility/group names
           # Add specific node names or patterns if needed
           # "中国", "国内", "china", "cn" # Uncomment to exclude CN nodes
           # Exclude info nodes based on your provider list
           "剩余流量", "套餐到期", "官网", "更新订阅", "跳过证书验证"
           ]

# --- Test Parameters ---
# Latency Test
LATENCY_TEST_URL = "http://www.gstatic.com/generate_204" # URL for latency check
LATENCY_TIMEOUT_MS = 5000 # Timeout for latency test in milliseconds (5 seconds)
MAX_ACCEPTABLE_LATENCY_MS = 400 # Nodes with latency above this value (ms) will not be considered for the final selection

# Download Speed Test
DOWNLOAD_TEST_URL = "https://speed.cloudflare.com/__down?bytes=100000000" # 100MB file from Cloudflare
DOWNLOAD_TEST_SIZE_BYTES = 100000000 # Expected size in bytes
DOWNLOAD_TIMEOUT_SECONDS = 90 # Timeout for the download test in seconds
DOWNLOAD_CHUNK_SIZE = 8192 # Chunk size for downloading
# -------------------------------------------------

def log(*m):
    """简单的日志记录功能。"""
    print(*m, flush=True)

def is_excluded(name):
    """检查节点名称是否包含 EXCLUDE 列表中的任何关键字。"""
    name_lower = name.lower()
    for keyword in EXCLUDE:
        if keyword.lower() in name_lower:
            return True
    return False

def get_testable_nodes():
    """通过 Clash API 从 SOURCE_GROUP 获取节点并使用 EXCLUDE 列表进行过滤。"""
    all_nodes = []
    try:
        # URL 编码组名以防包含特殊字符
        enc_source_group = urllib.parse.quote(SOURCE_GROUP, safe='')
        url = f"{CLASH_API}/proxies/{enc_source_group}"
        log(f"从源组 '{SOURCE_GROUP}' 获取节点: {url}") # 更新日志
        response = requests.get(url, headers=CLASH_API_HEADERS, timeout=10)
        response.raise_for_status() # 对错误的 HTTP 状态码抛出异常
        j = response.json()
        # 'all' 通常包含组中的节点列表 (对 url-test 和 select 都适用)
        all_nodes = j.get("all", [])
        if not all_nodes:
            log(f"警告: 在源组 '{SOURCE_GROUP}' 中找不到节点。组名是否正确且已填充？ 响应: {j}")
            return []

        log(f"在 '{SOURCE_GROUP}' 中找到的总节点数: {len(all_nodes)}")
        # 根据 EXCLUDE 列表过滤节点
        testable_nodes = [n for n in all_nodes if not is_excluded(n)]
        log(f"排除后待测试的节点数: {len(testable_nodes)}")

        # 如果有节点被排除，则记录下来以便查看
        if len(testable_nodes) < len(all_nodes):
             excluded_nodes = [n for n in all_nodes if is_excluded(n)]
             log(f"被排除的节点: {excluded_nodes}")
        return testable_nodes
    except requests.exceptions.RequestException as e:
        log(f"从 Clash API 获取节点时出错: {e}")
        log(f"请确保 Clash API 正在 {CLASH_API} 运行，SECRET（如果有）正确，并且组 '{SOURCE_GROUP}' 存在。")
        return []
    except Exception as e:
        log(f"获取节点时发生意外错误: {e}")
        traceback.print_exc() # 打印详细的回溯信息以处理意外错误
        return []

def switch_group_node(group_name, node_name):
    """通过 Clash API 将指定的组切换到指定的节点。"""
    # URL 编码名称
    enc_group_name = urllib.parse.quote(group_name, safe='')
    url = f"{CLASH_API}/proxies/{enc_group_name}"
    payload = {"name": node_name}
    response = None # 初始化 response 以避免潜在的 UnboundLocalError
    try:
        log(f"正在切换组 '{group_name}' 到节点 '{node_name}'...")
        # 使用 PUT 请求更改 'select' 或 'url-test' 类型组中选定的节点
        response = requests.put(url, headers=CLASH_API_HEADERS, json=payload, timeout=10)
        response.raise_for_status()
        log(f"成功切换组 '{group_name}' 到节点 '{node_name}'")
        return True
    except requests.exceptions.RequestException as e:
        response_info = f" 状态码: {response.status_code}" if response else ""
        log(f"切换组 '{group_name}' 到节点 '{node_name}' 时出错: {e}{response_info}")
        # 根据常见的状态码提供提示
        if response:
            if response.status_code == 400:
                log("提示: 状态码 400 通常意味着组/节点名称不正确，或者该节点对此组类型无效。")
            elif response.status_code == 404:
                log(f"提示: 状态码 404 意味着找不到组 '{group_name}'。")
        elif isinstance(e, requests.exceptions.ConnectionError):
            log("连接错误: Clash API 是否正在运行并且在指定的地址可访问？")
        return False
    except Exception as e:
        log(f"切换组时发生意外错误: {e}")
        traceback.print_exc()
        return False

def get_node_latency(node_name):
    """使用 Clash API 的 delay 端点测试特定节点的延迟。"""
    # URL 编码节点名称
    enc_node_name = urllib.parse.quote(node_name, safe='')
    # 构建用于延迟测试的 API URL
    url = f"{CLASH_API}/proxies/{enc_node_name}/delay?timeout={LATENCY_TIMEOUT_MS}&url={urllib.parse.quote(LATENCY_TEST_URL)}"
    latency = float('inf') # 默认为无穷大（表示失败）
    try:
        # 在请求超时时间上增加一个小缓冲区，以超出测试超时时间
        response = requests.get(url, headers=CLASH_API_HEADERS, timeout=(LATENCY_TIMEOUT_MS / 1000) + 2)
        response.raise_for_status()
        j = response.json()
        delay = j.get('delay', -1)
        # Clash API 返回的延迟以毫秒为单位，-1 或 0 通常表示超时或错误
        if delay > 0:
            latency = delay
    except requests.exceptions.RequestException as e:
        # 记录特定的请求错误，但不停止脚本
        # log(f"节点 {node_name} 的延迟测试失败: {e}")
        pass # 保持静默以获得更清晰的输出，无穷大表示失败
    except Exception as e:
        log(f"节点 {node_name} 在延迟测试期间发生意外错误: {e}")
        traceback.print_exc()
    return latency

def get_download_speed(node_name):
    """通过当前代理设置下载文件来测试下载速度。"""
    start_time = time.time()
    bytes_downloaded = 0
    response = None
    speed_mbps = 0.0
    try:
        log(f"开始为节点 {node_name} 从 {DOWNLOAD_TEST_URL} 进行下载测试...")
        # 使用 stream=True 避免将整个文件加载到内存中
        # 使用定义的 REQUEST_HEADERS 模拟浏览器
        response = requests.get(DOWNLOAD_TEST_URL, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS, headers=REQUEST_HEADERS)
        response.raise_for_status()

        for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
            if chunk:
                bytes_downloaded += len(chunk)
            # 同时在循环内部检查手动超时
            if time.time() - start_time > DOWNLOAD_TIMEOUT_SECONDS:
                 raise requests.exceptions.Timeout(f"下载循环在 {DOWNLOAD_TIMEOUT_SECONDS} 秒后手动超时。")

        end_time = time.time()
        duration = end_time - start_time

        # 检查下载是否合理完成并且花费了一些时间
        if duration > 0 and (bytes_downloaded >= DOWNLOAD_TEST_SIZE_BYTES * 0.95): # 允许 5% 的容差
            # 计算速度: (字节 * 8 比特/字节) / 秒 / 1,000,000 比特/Mbps
            speed_mbps = (bytes_downloaded * 8) / duration / 1_000_000
            log(f"下载完成: {bytes_downloaded / (1024*1024):.2f} MB in {duration:.2f} 秒。")
        elif duration <= 0:
            log(f"节点 {node_name} 的下载测试完成得太快，无法计算速度。")
        else:
            log(f"节点 {node_name} 的下载测试未完成 ({bytes_downloaded / (1024*1024):.2f} MB / {DOWNLOAD_TEST_SIZE_BYTES / (1024*1024):.2f} MB)。速度计算已跳过。")

    except requests.exceptions.Timeout:
        log(f"节点 {node_name} 的下载测试在 {DOWNLOAD_TIMEOUT_SECONDS} 秒后超时。")
    except requests.exceptions.RequestException as e:
        log(f"节点 {node_name} 的下载测试失败: {e}")
    except Exception as e:
        log(f"节点 {node_name} 在下载测试期间发生意外错误: {e}")
        traceback.print_exc()
    finally:
        # 确保连接已关闭
        if response:
            response.close()
    return speed_mbps

def main():
    """主函数，运行节点测试和切换过程。"""
    log("======== Clash 节点组合延迟和速度测试 ========")
    log(f"使用 Clash API 地址: {CLASH_API}")
    log(f"从组获取节点: '{SOURCE_GROUP}'")
    log(f"测试期间切换的组: '{TEST_GROUP_NAME}'") # 更新日志
    log(f"最终设置的目标组: '{FINAL_TARGET_GROUP}'")
    log(f"延迟测试 URL: {LATENCY_TEST_URL} (超时: {LATENCY_TIMEOUT_MS}ms)")
    log(f"下载测试 URL: {DOWNLOAD_TEST_URL} (超时: {DOWNLOAD_TIMEOUT_SECONDS}s)")
    log(f"最大可接受延迟: {MAX_ACCEPTABLE_LATENCY_MS} ms")
    log(f"排除的关键词: {EXCLUDE}")
    log("-------------------------------------------------------------")

    nodes_to_test = get_testable_nodes()
    if not nodes_to_test:
        log("根据源组和排除列表，没有可用于测试的节点。正在退出。")
        return

    results = {} # 用于存储测试结果的字典 {'node_name': {'latency': ms, 'speed': Mbps, 'error': msg}}
    node_count = len(nodes_to_test)
    best_node_overall = None # 跟踪找到的最佳节点

    for i, node in enumerate(nodes_to_test):
        log(f"----- 测试节点 {i+1}/{node_count}: {node} -----")

        # 1. 切换 TEST_GROUP_NAME ("自动选择") 到当前节点
        if not switch_group_node(TEST_GROUP_NAME, node):
             log(f"未能切换测试组 '{TEST_GROUP_NAME}' 到节点 {node}。跳过此节点的测试。")
             results[node] = {'latency': float('inf'), 'speed': 0.0, 'error': 'Test Group Switch Failed'}
             continue

        time.sleep(2) # 等待切换生效

        # 2. 测试延迟
        log(f"测试延迟...")
        latency = get_node_latency(node)
        latency_str = f"{latency} ms" if latency != float('inf') else "失败"
        log(f"延迟结果: {latency_str}")

        # 3. 测试下载速度
        speed_mbps = 0.0
        if latency <= LATENCY_TIMEOUT_MS * 1.5:
            log(f"测试下载速度...")
            speed_mbps = get_download_speed(node)
            speed_str = f"{speed_mbps:.2f} Mbps" if speed_mbps > 0 else "失败或 0 Mbps"
            log(f"速度结果: {speed_str}")
        else:
            log("由于延迟过高/失败，跳过速度测试。")

        results[node] = {'latency': latency, 'speed': speed_mbps}

    log("-------------------- 测试结果摘要 --------------------")
    sorted_nodes_display = sorted(results.keys(), key=lambda n: (
        results.get(n, {}).get('latency', float('inf')),
        -results.get(n, {}).get('speed', 0.0)
    ))

    for node in sorted_nodes_display:
        data = results.get(node, {})
        lat = data.get('latency', float('inf'))
        spd = data.get('speed', 0.0)
        err = data.get('error', None)

        lat_str = f"{lat} ms" if lat != float('inf') else "失败"
        if err:
            spd_str = f"N/A ({err})"
        elif spd > 0:
            spd_str = f"{spd:.2f} Mbps"
        elif lat != float('inf'):
             spd_str = "0.00 Mbps / 失败"
        else:
            spd_str = "N/A"

        status = f"延迟: {lat_str:<15} 速度: {spd_str}"
        log(f"{node:<40} {status}")
    log("-------------------------------------------------------------")

    # --- 根据标准查找最佳节点 ---
    eligible_nodes = {}
    for node, data in results.items():
        lat = data.get('latency', float('inf'))
        spd = data.get('speed', 0.0)
        err = data.get('error', None)
        if not err and isinstance(lat, (int, float)) and lat <= MAX_ACCEPTABLE_LATENCY_MS and spd > 0:
            eligible_nodes[node] = {'speed': spd, 'latency': lat}

    if not eligible_nodes:
        log(f"未找到符合标准的节点 (延迟 <= {MAX_ACCEPTABLE_LATENCY_MS} ms 且速度 > 0 Mbps)。")
        log(f"将保持组 '{FINAL_TARGET_GROUP}' 的当前选择。")
        log("======================= 脚本完成 =======================")
        return

    best_node_overall = max(eligible_nodes, key=lambda n: eligible_nodes[n]['speed'])
    best_speed = eligible_nodes[best_node_overall]['speed']
    best_latency = eligible_nodes[best_node_overall]['latency']

    log(f"找到符合标准的最佳节点:")
    log(f"  --> {best_node_overall} (速度: {best_speed:.2f} Mbps, 延迟: {best_latency} ms)")
    log("-------------------------------------------------------------")

    # --- 关键修正：在切换最终组之前，先将测试组切换到最佳节点 ---
    log(f"将测试组 '{TEST_GROUP_NAME}' 切换到最佳节点 '{best_node_overall}'...")
    if switch_group_node(TEST_GROUP_NAME, best_node_overall):
        log(f"成功将测试组 '{TEST_GROUP_NAME}' 切换到最佳节点。")

        # --- 然后再将最终目标组切换到测试组 ---
        log(f"尝试将最终目标组 '{FINAL_TARGET_GROUP}' 切换到 '{TEST_GROUP_NAME}' (现在指向最佳节点)...")
        if switch_group_node(FINAL_TARGET_GROUP, TEST_GROUP_NAME):
            log(f"成功将组 '{FINAL_TARGET_GROUP}' 切换到 '{TEST_GROUP_NAME}'。")
        else:
            log(f"未能将组 '{FINAL_TARGET_GROUP}' 切换到 '{TEST_GROUP_NAME}'。请检查 '{FINAL_TARGET_GROUP}' 的 proxies 配置是否包含 '{TEST_GROUP_NAME}'。")
            # 备选方案逻辑（通常不需要，但保留）
            log(f"尝试直接将组 '{FINAL_TARGET_GROUP}' 切换到最佳节点 '{best_node_overall}'...")
            if switch_group_node(FINAL_TARGET_GROUP, best_node_overall):
                 log(f"成功将组 '{FINAL_TARGET_GROUP}' 直接切换到 '{best_node_overall}'。")
            else:
                 log(f"直接切换到 '{best_node_overall}' 也失败了。组 '{FINAL_TARGET_GROUP}' 可能保持之前的状态。")
    else:
        log(f"未能将测试组 '{TEST_GROUP_NAME}' 切换到最佳节点 '{best_node_overall}'。最终切换中止。")


    log("======================= 脚本完成 =======================")

if __name__ == "__main__":
    main()
