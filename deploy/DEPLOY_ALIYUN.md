# 阿里云 ECS 部署说明

本项目更适合先以“视频上传分析”模式部署到云服务器。

当前“实时摄像头”模式基于 `cv2.VideoCapture(0)`，读取的是服务器本机摄像头：

- 本地运行很好用
- 不适合直接给公网用户调用自己手机或浏览器摄像头

## 推荐部署方式

1. 上传部署包到 ECS
2. 安装 Python 3.10 或 3.11
3. 解压项目
4. 运行 `deploy/start_streamlit.sh`
5. 放行 `8501` 端口，或接入 Nginx 反向代理

## 建议的服务器命令

```bash
sudo dnf install -y python3.11 python3.11-venv python3.11-pip
cd /opt
unzip wushu_motion_visualizer_deploy.zip -d wushu_motion_visualizer
cd wushu_motion_visualizer
bash deploy/start_streamlit.sh
```

如果系统没有 `python3.11`，也可以改成现有的 `python3`。

## 安全组

需要放行：

- `8501/tcp`

如果你后面要接域名，推荐：

- Nginx 对外监听 `80/443`
- Nginx 反向代理到 `127.0.0.1:8501`

## systemd 建议

生产环境建议把 Streamlit 配成 systemd 服务，而不是直接挂在终端里。

## 上传哪些文件

部署包里已经只保留这些运行必需内容：

- `app.py`
- `requirements.txt`
- `README.md`
- `configs/`
- `src/`
- `data/.gitkeep` 目录骨架
- `.streamlit/config.toml`
- `deploy/`
