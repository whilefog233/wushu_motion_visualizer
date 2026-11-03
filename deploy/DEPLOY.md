# Kungfu V3 API 部署指南（阿里云 Linux 3）

## 一、环境准备

```bash
# 1. 安装 Python 3.11 和系统依赖
sudo dnf install -y python3.11 python3.11-devel gcc ffmpeg

# 2. 拉代码
sudo useradd -m -s /bin/bash kungfu
sudo mkdir -p /opt/kungfu
sudo chown kungfu:kungfu /opt/kungfu
sudo su - kungfu
cd /opt/kungfu

# 3. 创建虚拟环境（纯英文路径）
python3.11 -m venv /opt/kungfu/venv
/opt/kungfu/venv/bin/pip install --upgrade pip
/opt/kungfu/venv/bin/pip install -r requirements.txt -r requirements-api.txt
```

## 二、配置环境变量

编辑 `deploy/kungfu-api.service`，把 `KUNGFU_API_KEY` 换成随机长密钥：

```bash
# 生成随机密钥
openssl rand -hex 32
```

## 三、启动 API 服务

```bash
# 拷贝 service 文件
sudo cp deploy/kungfu-api.service /etc/systemd/system/

# 启动并设置开机自启
sudo systemctl daemon-reload
sudo systemctl enable kungfu-api
sudo systemctl start kungfu-api

# 看日志
sudo journalctl -u kungfu-api -f
```

API 监听 `127.0.0.1:8000`，外部不能直接访问。

## 四、配置 Nginx 反向代理 + HTTPS

```bash
# 1. 装 nginx
sudo dnf install -y nginx

# 2. 拷贝配置（替换域名）
sudo cp deploy/nginx.conf.example /etc/nginx/conf.d/kungfu.conf
# 编辑 kungfu.conf，把 kungfu-api.example.com 换成你的域名

# 3. 申请 SSL 证书（certbot）
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d kungfu-api.example.com

# 4. 启动 nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

## 五、阿里云安全组

在阿里云控制台 → ECS 实例 → 安全组，开放：

- **443/tcp**（HTTPS，给外部访问）
- **80/tcp**（HTTP，证书续期用）

**不要**开放 8000 端口（API 只监听本机）。

## 六、验证接口

```bash
# 健康检查
curl https://你的域名/health

# 上传视频分析
curl -X POST https://你的域名/api/v1/analyses \
  -H "X-API-Key: 你的密钥" \
  -F "video=@/path/to/你的视频.mp4"

# 轮询状态
curl https://你的域名/api/v1/analyses/{analysis_id} \
  -H "X-API-Key: 你的密钥"

# 获取结果
curl https://你的域名/api/v1/analyses/{analysis_id}/result \
  -H "X-API-Key: 你的密钥"

# 下载文件
curl -OJ https://你的域名/api/v1/analyses/{analysis_id}/files/metrics.csv \
  -H "X-API-Key: 你的密钥"
```

## 七、并发与资源

- `KUNGFU_MAX_CONCURRENT=1`：2 核 8G 机器限制同时只跑 1 个分析任务，避免 MediaPipe 占满 CPU
- 任务排队：同时上传多个视频时，后面的任务在队列里等，不会崩
- 进程重启：服务重启后，上次没跑完的任务会被标记为 `FAILED`（stage=RESTARTED），不会假装成功

## 八、Docker 部署（可选）

```bash
docker build -f deploy/Dockerfile -t kungfu-api .
docker run -d --name kungfu-api -p 127.0.0.1:8000:8000 \
  -e KUNGFU_API_KEY=你的密钥 \
  -e KUNGFU_CORS_ORIGIN=https://你的网站域名 \
  kungfu-api
```

## 九、网站后续调用 API 需要配置什么

1. **API Key**：把 `KUNGFU_API_KEY` 配到网站后端（环境变量或密钥管理），**不要写进前端代码**
2. **CORS**：如果网站域名和 API 域名不同，把网站域名加到 `KUNGFU_CORS_ORIGIN`（逗号分隔多个）
3. **轮询**：上传后立即返回 `analysis_id`，前端每 3-5 秒轮询状态，状态变成 `COMPLETED` 后拉 `/result`
4. **文件下载**：`/files/{filename}` 返回二进制，前端用 `URL.createObjectURL` 或直接 `<a download>` 下载
