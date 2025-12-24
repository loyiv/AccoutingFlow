## 阿里云 ECS 部署指南（推荐：Docker Compose 一键）

目标：在阿里云 ECS 上部署本项目，使外网可访问：
- 前端：`http://你的域名/`（或 `http://你的服务器IP/`）
- 后端：`http://你的域名/api/docs`

> 说明：这是“最小可跑通闭环”的部署方式；生产可进一步替换为阿里云 RDS、加 HTTPS、做备份/监控。

## 不使用 Docker 的部署（宝塔/Nginx + systemd + 本机 MySQL）

如果你明确“不用 Docker”，推荐架构是：
- **Nginx**：对外提供 80/443；静态托管前端 `dist/`；反代 `/api/` 到后端
- **后端**：systemd 常驻（gunicorn + uvicorn worker），监听 `127.0.0.1:8000`
 - **数据库**：本机 MySQL 8.x（或后续换阿里云 RDS MySQL）

仓库已提供模板文件：
- Nginx 配置：`deploy/nginx/accountingflow.conf`
- systemd 服务：`backend/deploy/accountingflow-backend.service`
- 后端环境变量模板：`backend/deploy/backend.env.template`

### 0) 目录规划（服务器）

建议放到：
- `/opt/accountingflow/backend`（后端代码）
- `/opt/accountingflow/frontend`（前端代码与 dist）
- `/opt/accountingflow/storage`（附件存储）

### 1) 安装依赖（概念说明）

你需要安装：
- PostgreSQL 16（或 15+）
- Python 3.12（建议），以及 venv
- Node.js 20 LTS（仅用于构建前端；也可在本地构建后上传 dist）
- Nginx（宝塔通常自带）

> 不同系统（Ubuntu/CentOS/Alibaba Cloud Linux）命令不同。你 SSH 后执行 `cat /etc/os-release`，我可以按你的系统给你一键命令。

### 2) 初始化数据库

创建数据库与用户（示例，MySQL 8.x）：

```bash
mysql -uroot -p -e "CREATE DATABASE accountingflow CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
mysql -uroot -p -e "CREATE USER 'accountingflow'@'localhost' IDENTIFIED BY '强密码';"
mysql -uroot -p -e "GRANT ALL PRIVILEGES ON accountingflow.* TO 'accountingflow'@'localhost'; FLUSH PRIVILEGES;"
```

### 3) 部署后端（systemd）

1) 创建运行用户与目录：

```bash
sudo useradd -r -m -s /usr/sbin/nologin accountingflow || true
sudo mkdir -p /opt/accountingflow/{backend,frontend,storage}
sudo chown -R accountingflow:accountingflow /opt/accountingflow
```

2) 把 `main/backend` 上传到 `/opt/accountingflow/backend`（保持结构不变）。

3) 创建 venv 并安装依赖：

```bash
cd /opt/accountingflow/backend
python3.12 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

4) 配置环境变量文件：

```bash
sudo mkdir -p /etc/accountingflow
sudo cp /opt/accountingflow/backend/deploy/backend.env.template /etc/accountingflow/backend.env
sudo nano /etc/accountingflow/backend.env
```

务必修改：
- `DATABASE_URL`（填真实用户名/密码，MySQL 示例见模板）
- `JWT_SECRET`（强随机）
- seed 默认密码

5) 安装 systemd 服务并启动：

```bash
sudo cp /opt/accountingflow/backend/deploy/accountingflow-backend.service /etc/systemd/system/accountingflow-backend.service
sudo systemctl daemon-reload
sudo systemctl enable --now accountingflow-backend
sudo systemctl status accountingflow-backend --no-pager
```

后端此时应在 `127.0.0.1:8000` 监听：

```bash
curl -s http://127.0.0.1:8000/health
```

### 4) 部署前端（build + Nginx 静态托管）

1) 把 `main/frontend` 上传到 `/opt/accountingflow/frontend`

2) 构建：

```bash
cd /opt/accountingflow/frontend
export VITE_API_BASE=/api
npm install
npm run build
```

3) 配置 Nginx（宝塔：网站配置里粘贴也可以）

把 `deploy/nginx/accountingflow.conf` 的内容复制到 Nginx 站点配置，并确认：
- `root` 指向 `/opt/accountingflow/frontend/dist`
- `/api/` 反代到 `http://127.0.0.1:8000/`

重载 Nginx：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 5) 外网访问

确保安全组放行 80/443 后：
- `http://你的服务器IP/`
- `http://你的服务器IP/api/docs`

> 如果你用宝塔，通常只需要建站并让 Nginx 监听 80，然后把配置粘贴进去即可。

### 1) 购买 ECS 推荐配置

- **操作系统**：Ubuntu 22.04 LTS（推荐）或 Alibaba Cloud Linux 3
- **实例规格**（测试/演示）：
  - 2 核 4GB 内存（推荐，Docker + Postgres + API + Nginx 更稳）
  - 磁盘 40GB+
- **带宽**：1–5Mbps（演示够用）

### 2) 安全组放行端口

在 ECS 安全组入方向规则放行：
- 22（SSH）
- 80（HTTP）
- 443（HTTPS，后面上证书再开；也可以先开着）
 - （可选）8080（如果你用宝塔/宿主 Nginx 占用了 80，则把本项目映射到 8080）

> 不建议对公网开放 5432（数据库），本项目 compose 也不需要开放。

### 3) SSH 连接服务器

本地 PowerShell（Windows）：

```powershell
ssh root@你的服务器IP
```

首次连接可能会询问指纹，输入 `yes`。

### 4) 在服务器安装 Docker + Compose（Ubuntu 22.04 示例）

```bash
sudo apt update -y
sudo apt install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update -y
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

docker -v
docker compose version
```

### 5) 上传代码到服务器

方式 A：用 git（推荐）

```bash
sudo mkdir -p /opt/accountingflow
sudo chown -R $USER:$USER /opt/accountingflow
cd /opt/accountingflow
git clone <你的仓库地址> repo
```

方式 B：用 scp（把本地 `main/` 传上去）

本地 PowerShell：

```powershell
scp -r "C:\Users\Lenovo\Desktop\会计软件\main" root@你的服务器IP:/opt/accountingflow/
```

### 6) 配置生产环境变量（强烈建议）

在服务器 `/opt/accountingflow/main` 下创建 `.env`（Docker Compose 会自动读取）：

```bash
cd /opt/accountingflow/main
nano .env
```

建议内容（至少改 `JWT_SECRET` 和默认密码）：

```env
POSTGRES_DB=accountingflow
POSTGRES_USER=accountingflow
POSTGRES_PASSWORD=请改成强密码

DATABASE_URL=postgresql+psycopg://accountingflow:请改成强密码@db:5432/accountingflow

JWT_SECRET=请改成强随机值
JWT_ALG=HS256
JWT_EXPIRE_MINUTES=720

# 生产推荐填你的域名（http/https），例如：https://demo.example.com
CORS_ORIGINS=http://你的域名,https://你的域名

SEED_ADMIN_PASSWORD=请改
SEED_ACCOUNTANT_PASSWORD=请改
SEED_MANAGER_PASSWORD=请改

# 如果服务器上 80 已被宝塔/Nginx 占用，可用 8080 对外提供本系统
WEB_PORT=8080
```

### 7) 一键启动（生产 compose）

```bash
cd /opt/accountingflow/main
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml ps
```

查看日志：

```bash
docker compose -f docker-compose.prod.yml logs -f --tail=200
```

### 8) 访问验证

- 打开：`http://你的服务器IP/`（或如果设置了 `WEB_PORT=8080`：`http://你的服务器IP:8080/`）
- 登录（用你在 `.env` 里设置的 seed 密码）
- 走通：待过账草稿 → 预校验 → 过账 → 报表生成/下钻

### 9) 绑定域名 + HTTPS（建议后续做）

两种常见方式：
- **Nginx/Certbot**（在宿主机装 Nginx，反代到容器 80，签发 Let’s Encrypt）
- **Caddy**（更简单，自动签证书）

如果你告诉我你的域名、是否已经解析到 ECS、以及你偏好的方式（Nginx 或 Caddy），我可以把命令按你的环境写成“一键脚本”。



