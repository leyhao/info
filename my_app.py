import os
import re
import json
import time
import base64
import shutil
import asyncio
import requests
import platform
import subprocess
import threading

# 环境变量
UPLOAD_URL = os.environ.get("UPLOAD_URL", "")  # 节点或订阅上传地址[cite: 1]
PROJECT_URL = os.environ.get("PROJECT_URL", "")  # 项目url[cite: 1]
AUTO_ACCESS = os.environ.get("AUTO_ACCESS", "false").lower() == "true"  # 保活[cite: 1]
FILE_PATH = os.environ.get("FILE_PATH", "./sub")  # 节点路径[cite: 1]
SUB_PATH = os.environ.get("SUB_PATH", "sub")  # 订阅token[cite: 1]
UUID = os.environ.get("UUID", "694e2fa9-a45a-49f1-ab10-311cc3e51fde")  # UUID[cite: 1]
ARGO_DOMAIN = os.environ.get("ARGO_DOMAIN", "strm2.134850.xyz")  # Argo固定域名[cite: 1]
ARGO_AUTH = os.environ.get("ARGO_AUTH", "eyJhIjoiNGY5NGY1NmZhZDg2YzkyMWMzNDc0ZWI2Njk0NGM3YzQiLCJ0IjoiOWZiODZjODItZGYzYy00MzEzLTkwMTYtZWI0MTkyM2QyNjU3IiwicyI6IllUbG1NMlU1WXpZdE9EZ3dNQzAwT1dFd0xUZ3lPRFF0T1RkaE9HVTFZVGRsTnpkaiJ9")  # Argo密钥[cite: 1]
ARGO_PORT = int(os.environ.get("PORT", "8001"))  # Argo监听端口[cite: 1]
CFIP = os.environ.get("CFIP", "saas.sin.fan")  # 优选ip[cite: 1]
CFPORT = int(os.environ.get("CFPORT", "443"))  # 优选端口[cite: 1]
NAME = os.environ.get("NAME", "Stream2")  # 节点名称[cite: 1]
CHAT_ID = os.environ.get("CHAT_ID", "5997361836")  # Telegram chat_id[cite: 1]
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8319407327:AAE2-FXu7opHzIqHtTZ_Mu57kyJhQWg2Zu0")  # Telegram bot_token[cite: 1]


# 创建运行目录
def create_directory():
  print("\033c", end="")
  if not os.path.exists(FILE_PATH):
    os.makedirs(FILE_PATH)
    print(f"{FILE_PATH} 已创建")
  else:
    print(f"{FILE_PATH} 已存在")


# 全局变量路径定义
web_path = os.path.join(FILE_PATH, "web")
bot_path = os.path.join(FILE_PATH, "bot")
sub_path = os.path.join(FILE_PATH, "sub.txt")
list_path = os.path.join(FILE_PATH, "list.txt")
boot_log_path = os.path.join(FILE_PATH, "boot.log")
config_path = os.path.join(FILE_PATH, "config.json")


# 删除旧节点
def delete_nodes():
  if not UPLOAD_URL:
    return
  if not os.path.exists(sub_path):
    return
  try:
    with open(sub_path, "r") as file:
      file_content = file.read()

    # 解码并提取节点
    decoded = base64.b64decode(file_content).decode("utf-8")
    nodes = [
        line
        for line in decoded.split("\n")
        if any(
            p in line
            for p in [
                "vless://",
                "vmess://",
                "trojan://",
                "hysteria2://",
                "tuic://",
            ]
        )
    ]
    if not nodes:
      return
    requests.post(
        f"{UPLOAD_URL}/api/delete-nodes", json={"nodes": nodes}, timeout=10
    )
  except Exception as e:
    print(f"删除节点时出错: {e}")


# 清理旧文件
def cleanup_old_files():
  paths_to_delete = ["web", "bot", "boot.log", "list.txt"]
  for file in paths_to_delete:
    file_path = os.path.join(FILE_PATH, file)
    try:
      if os.path.exists(file_path):
        if os.path.isdir(file_path):
          shutil.rmtree(file_path)
        else:
          os.remove(file_path)
    except Exception as e:
      print(f"删除 {file_path} 失败: {e}")


# 判断系统架构
def get_system_architecture():
  architecture = platform.machine().lower()
  if "arm" in architecture or "aarch64" in architecture:
    return "arm"
  else:
    return "amd"


# 根据架构下载文件
def download_file(file_name, file_url):
  file_path = os.path.join(FILE_PATH, file_name)
  try:
    response = requests.get(file_url, stream=True)
    response.raise_for_status()
    with open(file_path, "wb") as f:
      for chunk in response.iter_content(chunk_size=8192):
        f.write(chunk)
    print(f"{file_name} 下载成功")
    return True
  except Exception as e:
    if os.path.exists(file_path):
      os.remove(file_path)
    print(f"{file_name} 下载失败: {e}")
    return False


# 获取对应架构的文件列表
def get_files_for_architecture(architecture):
  repo_url = "https://github.com/polycc2021/my-assets/releases/download"

  if architecture == "arm":
    web_url = f"{repo_url}/v1.0.0-arm/web"
    bot_url = f"{repo_url}/v1.0.1-arm/2go"
  else:
    web_url = f"{repo_url}/v1.0.0/web"
    bot_url = f"{repo_url}/v1.0.1/2go"

  # 基础组件：web (核心), bot (隧道)
  files = [
      {"fileName": "web", "fileUrl": web_url},
      {"fileName": "bot", "fileUrl": bot_url},
  ]

  return files


# 授权文件执行权限
def authorize_files(file_paths):
  for relative_file_path in file_paths:
    absolute_file_path = os.path.join(FILE_PATH, relative_file_path)
    if os.path.exists(absolute_file_path):
      try:
        os.chmod(absolute_file_path, 0o775)
        print(f"授权成功: {absolute_file_path} (775)")
      except Exception as e:
        print(f"授权失败 {absolute_file_path}: {e}")


# 配置 Argo 隧道
def argo_type():
  if not ARGO_AUTH or not ARGO_DOMAIN:
    print("ARGO_DOMAIN 或 ARGO_AUTH 变量为空，使用临时隧道")
    return

  if "TunnelSecret" in ARGO_AUTH:
    with open(os.path.join(FILE_PATH, "tunnel.json"), "w") as f:
      f.write(ARGO_AUTH)

    tunnel_id = ARGO_AUTH.split('"')[11]
    tunnel_yml = f"""
tunnel: {tunnel_id}
credentials-file: {os.path.join(FILE_PATH, 'tunnel.json')}
protocol: http2

ingress:
  - hostname: {ARGO_DOMAIN}
    service: http://localhost:{ARGO_PORT}
    originRequest:
      noTLSVerify: true
  - service: http_status:404
"""
    with open(os.path.join(FILE_PATH, "tunnel.yml"), "w") as f:
      f.write(tunnel_yml)
  else:
    print(f"使用 Token 连接隧道，请确保 Cloudflare 中设置了端口 {ARGO_PORT}")


# 执行 Shell 命令并返回输出
def exec_cmd(command):
  try:
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = process.communicate()
    return stdout + stderr
  except Exception as e:
    print(f"执行命令出错: {e}")
    return str(e)


# 下载并运行必要文件
async def download_files_and_run():
  architecture = get_system_architecture()
  files_to_download = get_files_for_architecture(architecture)

  if not files_to_download:
    return

  # 批量下载
  success = all(download_file(f["fileName"], f["fileUrl"]) for f in files_to_download)
  if not success:
    print("部分文件下载失败，停止后续操作")
    return
  actual_downloaded_files = [f["fileName"] for f in files_to_download]
  authorize_files(actual_downloaded_files)

  # 生成配置文件 config.json
  config = {
      "log": {
          "access": "/dev/null",
          "error": "/dev/null",
          "loglevel": "none",
      },
      "inbounds": [
          {
              "port": ARGO_PORT,
              "protocol": "vless",
              "settings": {
                  "clients": [
                      {
                          "id": UUID,
                          "flow": "xtls-rprx-vision",
                      },
                  ],
                  "decryption": "none",
                  "fallbacks": [
                      {"dest": 3001},
                      {"path": "/vless-argo", "dest": 3002},
                      {"path": "/vmess-argo", "dest": 3003},
                      {"path": "/trojan-argo", "dest": 3004},
                  ],
              },
              "streamSettings": {
                  "network": "tcp",
              },
          },
          {
              "port": 3001,
              "listen": "127.0.0.1",
              "protocol": "vless",
              "settings": {
                  "clients": [
                      {"id": UUID},
                  ],
                  "decryption": "none",
              },
              "streamSettings": {"network": "ws", "security": "none"},
          },
          {
              "port": 3002,
              "listen": "127.0.0.1",
              "protocol": "vless",
              "settings": {
                  "clients": [{"id": UUID, "level": 0}],
                  "decryption": "none",
              },
              "streamSettings": {
                  "network": "ws",
                  "security": "none",
                  "wsSettings": {"path": "/vless-argo"},
              },
              "sniffing": {
                  "enabled": True,
                  "destOverride": ["http", "tls", "quic"],
                  "metadataOnly": False,
              },
          },
          {
              "port": 3003,
              "listen": "127.0.0.1",
              "protocol": "vmess",
              "settings": {"clients": [{"id": UUID, "alterId": 0}]},
              "streamSettings": {
                  "network": "ws",
                  "wsSettings": {"path": "/vmess-argo"},
              },
              "sniffing": {
                  "enabled": True,
                  "destOverride": ["http", "tls", "quic"],
                  "metadataOnly": False,
              },
          },
          {
              "port": 3004,
              "listen": "127.0.0.1",
              "protocol": "trojan",
              "settings": {
                  "clients": [
                      {"password": UUID},
                  ]
              },
              "streamSettings": {
                  "network": "ws",
                  "security": "none",
                  "wsSettings": {"path": "/trojan-argo"},
              },
              "sniffing": {
                  "enabled": True,
                  "destOverride": ["http", "tls", "quic"],
                  "metadataOnly": False,
              },
          },
      ],
      "outbounds": [
          {"protocol": "freedom", "tag": "direct"},
          {"protocol": "blackhole", "tag": "block"},
      ],
  }
  with open(
      os.path.join(FILE_PATH, "config.json"), "w", encoding="utf-8"
  ) as config_file:
    json.dump(config, config_file, ensure_ascii=False, indent=2)

  # 运行 web (Xray/Sing-box core)
  command = f"nohup {os.path.join(FILE_PATH, 'web')} -c {os.path.join(FILE_PATH, 'config.json')} >/dev/null 2>&1 &"
  try:
    exec_cmd(command)
    print("web 正在运行")
    time.sleep(1)
  except Exception as e:
    print(f"web 运行错误: {e}")

  # 运行 cloudflared (bot)
  if os.path.exists(os.path.join(FILE_PATH, "bot")):
    if re.match(r"^[A-Z0-9a-z=]{120,250}$", ARGO_AUTH):
      args = f"tunnel --edge-ip-version auto --no-autoupdate --protocol http2 run --token {ARGO_AUTH}"
    elif "TunnelSecret" in ARGO_AUTH:
      args = f"tunnel --edge-ip-version auto --config {os.path.join(FILE_PATH, 'tunnel.yml')} run"
    else:
      args = f"tunnel --edge-ip-version auto --no-autoupdate --protocol http2 --logfile {os.path.join(FILE_PATH, 'boot.log')} --loglevel info --url http://localhost:{ARGO_PORT}"

    try:
      exec_cmd(f"nohup {os.path.join(FILE_PATH, 'bot')} {args} >/dev/null 2>&1 &")
      print("bot 正在运行")
      time.sleep(2)
    except Exception as e:
      print(f"执行命令出错: {e}")

  time.sleep(5)

  # 提取域名并生成订阅
  await extract_domains()


# 从 cloudflared 日志中提取域名
async def extract_domains(retry_count=0):
  argo_domain = None
  max_retries = 3  # 最大重试次数

  if ARGO_AUTH and ARGO_DOMAIN:
    argo_domain = ARGO_DOMAIN
    print(f"Argo 域名: {argo_domain}")
    await generate_links(argo_domain)
  else:
    try:
      if not os.path.exists(boot_log_path):
        if retry_count < max_retries:
          await asyncio.sleep(2)
          return await extract_domains(retry_count + 1)
        else:
          print("错误：无法生成 Argo 日志文件，停止重试")
          return
      with open(boot_log_path, "r") as f:
        file_content = f.read()

      domain_match = re.search(
          r"https?://([^ ]*trycloudflare\.com)/?", file_content
      )
      if domain_match:
        argo_domain = domain_match.group(1)
        print(f"Argo 域名获取成功: {argo_domain}")
        await generate_links(argo_domain)
      else:
        if retry_count < max_retries:
          print(f"未找到 Argo 域名，正在进行第 {retry_count + 1} 次重试...")
          if os.path.exists(boot_log_path):
            os.remove(boot_log_path)
          exec_cmd(f"pkill -f {os.path.basename(bot_path)}")
          await asyncio.sleep(3)
          args = f"tunnel --edge-ip-version auto --no-autoupdate --protocol http2 --logfile {boot_log_path} --loglevel info --url http://localhost:{ARGO_PORT}"
          exec_cmd(f"nohup {bot_path} {args} >/dev/null 2>&1 &")
          await asyncio.sleep(6)  # 等待启动
          await extract_domains(retry_count + 1)  # 递归调用，次数+1
        else:
          print(
              f"已达到最大重试次数 ({max_retries})，Argo 启动失败，请检查网络或参数"
          )

    except Exception as e:
      print(f"读取 boot.log 或重启 bot 出错: {e}")


# 上传节点到订阅服务
def upload_nodes():
  if UPLOAD_URL and PROJECT_URL:
    subscription_url = f"{PROJECT_URL}/{SUB_PATH}"
    json_data = {"subscription": [subscription_url]}

    try:
      response = requests.post(
          f"{UPLOAD_URL}/api/add-subscriptions",
          json=json_data,
          headers={"Content-Type": "application/json"},
      )

      if response.status_code == 200:
        print("订阅上传成功")
    except Exception as e:
      pass

  elif UPLOAD_URL:
    if not os.path.exists(list_path):
      return
    with open(list_path, "r") as f:
      content = f.read()

    nodes = [
        line
        for line in content.split("\n")
        if any(
            protocol in line
            for protocol in [
                "vless://",
                "vmess://",
                "trojan://",
                "hysteria2://",
                "tuic://",
            ]
        )
    ]
    if not nodes:
      return
    json_data = json.dumps({"nodes": nodes})
    try:
      response = requests.post(
          f"{UPLOAD_URL}/api/add-nodes",
          data=json_data,
          headers={"Content-Type": "application/json"},
      )
      if response.status_code == 200:
        print("节点上传成功")
    except:
      return None
  else:
    return


# 推送通知到 Telegram
def send_telegram():
  if not BOT_TOKEN or not CHAT_ID:
    print("TG 变量为空，跳过推送到 TG")
    return

  try:
    with open(sub_path, "r") as f:
      message = f.read()

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    escaped_name = re.sub(r"([_*\[\]()~>#+=|{}.!\-])", r"\\\1", NAME)
    params = {
        "chat_id": CHAT_ID,
        "text": f"**{escaped_name}节点推送通知**\n{message}",
        "parse_mode": "MarkdownV2",
    }

    requests.post(url, params=params)
    print("TG 消息发送成功")
  except Exception as e:
    print(f"TG 消息发送失败: {e}")


# 生成链接和订阅内容
async def generate_links(argo_domain):
  ISP = "US-Google_LLC"
  try:
    response = requests.get("https://speed.cloudflare.com/meta", timeout=3)
    if response.status_code == 200:
      try:
        data = response.json()
        isp_name = data.get("asOrganization", "ISP").replace(" ", "_")
        location = data.get("country", "Unknown")
        ISP = f"{isp_name}-{location}"
      except:
        meta_info = response.text.split('"')
        if len(meta_info) > 25:
          ISP = f"{meta_info[25]}-{meta_info[17]}".replace(" ", "_").strip()
  except Exception as e:
    print(f"获取 ISP 信息失败: {e}，将使用默认值")

  time.sleep(2)
  VMESS = {
      "v": "2",
      "ps": f"{NAME}-{ISP}",
      "add": CFIP,
      "port": CFPORT,
      "id": UUID,
      "aid": "0",
      "scy": "none",
      "net": "ws",
      "type": "none",
      "host": argo_domain,
      "path": "/vmess-argo?ed=2560",
      "tls": "tls",
      "sni": argo_domain,
      "alpn": "",
      "fp": "chrome",
  }

  list_txt = f"""
vless://{UUID}@{CFIP}:{CFPORT}?encryption=none&security=tls&sni={argo_domain}&fp=chrome&type=ws&host={argo_domain}&path=%2Fvless-argo%3Fed%3D2560#{NAME}-{ISP}

vmess://{base64.b64encode(json.dumps(VMESS).encode('utf-8')).decode('utf-8')}

trojan://{UUID}@{CFIP}:{CFPORT}?security=tls&sni={argo_domain}&fp=chrome&type=ws&host={argo_domain}&path=%2Ftrojan-argo%3Fed%3D2560#{NAME}-{ISP}
    """

  list_txt = list_txt.strip()
  with open(os.path.join(FILE_PATH, "list.txt"), "w", encoding="utf-8") as list_file:
    list_file.write(list_txt)

  sub_txt = base64.b64encode(list_txt.encode("utf-8")).decode("utf-8")
  with open(os.path.join(FILE_PATH, "sub.txt"), "w", encoding="utf-8") as sub_file:
    sub_file.write(sub_txt)

  # 强化日志输出，确保能被日志系统捕获
  print("\n" + "=" * 60, flush=True)
  print("=== SUB_DATA_START ===", flush=True)
  print(sub_txt, flush=True)
  print("=== SUB_DATA_END ===", flush=True)
  print(f"确认: {os.path.join(FILE_PATH, 'sub.txt')} 保存成功", flush=True)
  print("=" * 60 + "\n", flush=True)

  # 执行额外操作
  send_telegram()
  upload_nodes()

  return sub_txt


# 添加自动访问任务
def add_visit_task():
  if not AUTO_ACCESS or not PROJECT_URL:
    print("跳过添加自动访问任务")
    return

  try:
    response = requests.post(
      "https://keep.gvrander.eu.org/add-url",
      json={"url": PROJECT_URL},
      headers={"Content-Type": "application/json"},
      timeout=10
    )
    if response.status_code == 200:
      print("自动访问任务添加成功")
    else:
      print(f"自动访问任务添加失败，状态码: {response.status_code}")
  except Exception as e:
    print(f"添加 URL 失败: {e}")


# 300秒后清理文件
def clean_files():
  def _cleanup():
    time.sleep(300)
    files_to_delete = [
      boot_log_path, config_path, list_path, web_path, bot_path,
      os.path.join(FILE_PATH, "tunnel.json"),
      os.path.join(FILE_PATH, "tunnel.yml"),
    ]

    for file in files_to_delete:
      try:
        if os.path.exists(file):
          if os.path.isdir(file):
            shutil.rmtree(file)
          else:
            os.remove(file)
      except:
        pass

    print("\033c", end="")
    print("程序正在运行")
    print("感谢使用本脚本，祝您使用愉快！")

  threading.Thread(target=_cleanup, daemon=True).start()


# 启动服务器的主函数
async def start_server():
  components = [os.path.basename(p) for p in [web_path, bot_path]]
  valid_components = [c for c in components if c]  # 过滤掉空值
  if valid_components:
    pattern = "|".join(valid_components)
    exec_cmd(f'pkill -f "{pattern}"')

  delete_nodes()
  cleanup_old_files()
  create_directory()
  argo_type()
  await download_files_and_run()
  add_visit_task()
  clean_files()
  print("执行完毕")
  print(f"\n日志将在 300 秒后删除")


if __name__ == "__main__":
  try:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_server())
    print("\n" + "=" * 50)
    print("后台服务已启动成功！")
    print("主程序进入保持存活状态 (Ctrl+C 可退出)")
    print("=" * 50)
    while True:
      time.sleep(60)

  except KeyboardInterrupt:
    print("\n[!] 接收到退出信号，正在关闭服务...")
  except Exception as e:
    print(f"\n[!] 运行过程中发生致命错误: {e}")
  finally:
    print("[*] 进程已安全退出")