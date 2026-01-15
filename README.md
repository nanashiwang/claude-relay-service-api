# 全自动卡券（卡密）发放平台（FastAPI + MySQL）

本项目是一个面向“代理/渠道”的**卡券（卡密）发放平台**，覆盖从产品与定价、卡密库存管理、钱包余额、充值/退款申请到卡密提取与导出的一整套闭环能力。充值/退款采用管理员审核（人工确认）以匹配“线下转账”场景，其余流程尽量自动化。

有意向部署/定制/合作，可联系 QQ：`438274867`。

## 功能概览

- 多角色：管理员/代理登录，权限隔离。
- 产品体系：SKU（如 `codex/gemini/claude`）+ 规格（天卡/按量卡）+ 价格/币种 + 上下架。
- 卡密库存：TXT 换行批量导入、SHA256 去重、可用/已提取/作废状态、库存统计。
- 购买与发放：支持登录购买（JWT）与 API Key 调用提取；支持批量购买数量选择、复制与导出 TXT。
- 余额钱包：金额统一使用“分”（整数）存储，避免浮点误差；流水记录（充值/购买/退款/管理员调整）。
- 充值/退款：用户提交申请 → 管理员通过/拒绝（可填原因，用户侧可见）。
- 支付配置：上传收款码图片 + 支付说明，充值页按支付方式展示对应信息。
- 纯后端托管：静态前端 `/web/*` 由后端直接托管，无需单独前端服务。

## 技术栈

- 后端：FastAPI、SQLAlchemy、Pydantic Settings、PyMySQL、JWT（`python-jose`）
- 数据库：MySQL 8
- 前端：原生 HTML/CSS/JS（静态资源在 `web/`）
- 容器化：Dockerfile + docker compose（支持本机/NAS）

## 访问入口

服务启动后（默认端口 `8000`）：

- Swagger：`http://127.0.0.1:8000/docs`
- 登录页：`http://127.0.0.1:8000/`
- 代理控制台：`http://127.0.0.1:8000/web/dashboard.html`
- 管理后台：`http://127.0.0.1:8000/web/admin.html`
- 店铺购卡：`http://127.0.0.1:8000/web/shop.html`
- 充值页：`http://127.0.0.1:8000/web/recharge.html`
- 退款页：`http://127.0.0.1:8000/web/refund.html`

## 快速开始（本地开发）

### 1）准备环境

- Python 3.11+
- MySQL 8（可用 Docker 启动）

### 2）配置环境变量

复制 `.env.example` 为 `.env`，至少配置：

- `DATABASE_URL`
- `JWT_SECRET`
- `ADMIN_USERNAME` / `ADMIN_PASSWORD`

示例（请按需修改）：

```dotenv
DATABASE_URL="mysql+pymysql://root:password@127.0.0.1:3306/card_platform?charset=utf8mb4"
JWT_SECRET="请替换为随机长字符串"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="admin123456"
DEFAULT_CURRENCY="CNY"
```

### 3）安装依赖

```bash
python -m pip install -r "requirements.txt"
```

### 4）初始化数据库

创建表 + 预置产品（默认 `codex/gemini/claude` 多规格 SKU）+ 创建管理员账号：

```bash
python "scripts/init_db.py"
```

可选：将 SQLAlchemy 字段备注同步到 MySQL（用于 DB 侧查看更直观）：

```bash
python "scripts/apply_db_comments.py" --apply
```

### 5）启动服务

推荐启动方式（端口 `8000`）：

```bash
python -m uvicorn "api:app" --reload --host "0.0.0.0" --port 8000
```

也可以：

- 直接运行 `api.py`（默认端口 `11113`，可通过 `PORT` 环境变量覆盖）
- Windows：双击 `start.bat` 或 PowerShell 执行 `./start.ps1`

## 使用流程（建议先跑通一遍）

### 管理员

1. 初始化 DB（会自动预置产品与管理员账号）
2. 登录管理后台：`/web/admin.html`
3. 产品管理：设置各 SKU 的 `price_cents`（分）
4. 卡密管理：导入 TXT 卡密（换行分隔）
5. 支付配置：上传收款码图片并保存（充值页会展示）
6. 充值审核：对用户充值申请通过/拒绝（拒绝原因会回显给用户）

### 代理（普通用户）

1. 注册/登录：`/`
2. 充值：在充值页选择支付方式并提交申请（线下转账后等待管理员审核）
3. 购卡：在店铺页选择 SKU 与数量购买，复制/导出卡密
4. 退款：如需退款，提交退款申请等待管理员审核

## Docker 部署（本机一键）

项目提供 `docker-compose.yml`（包含 MySQL）：

```bash
docker compose up -d --build
```

常用环境变量（可写入 `.env`）：

- `API_PORT`：对外端口（默认 `8000`）
- `MYSQL_PORT`：对外 MySQL 端口（默认 `3306`）
- `MYSQL_ROOT_PASSWORD` / `MYSQL_DATABASE` / `MYSQL_USER` / `MYSQL_PASSWORD`
- `JWT_SECRET` / `ADMIN_USERNAME` / `ADMIN_PASSWORD`

## NAS 部署（拉取镜像）

典型做法：NAS 上使用 `docker-compose.nas.yml` 拉取镜像，并挂载上传目录以持久化收款码图片。

`ports: "11113:8000"` 表示：浏览器访问 NAS 的 `11113`，容器内部服务端口是 `8000`。

收款码图片上传后文件落在：

- 容器内：`/app/web/uploads/payments/`
- NAS 上：`/volume3/docker/claude-relay-service-api/upload/payments/`（取决于你的挂载路径）

## 自动更新（Watchtower，可选）

如果希望 NAS 自动拉取最新镜像并重建容器，可加入 Watchtower（轮询检查 digest，只有更新才会拉取/重启）：

```yaml
services:
  api:
    image: ghcr.io/you/claude-relay-service-api:latest
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

  watchtower:
    image: containrrr/watchtower:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 300 --cleanup --label-enable
    restart: unless-stopped
```

安全提示：挂载 `/var/run/docker.sock` 代表 Watchtower 拥有控制 Docker 的高权限，请只使用可信镜像。

## 环境变量说明（重点）

- `DATABASE_URL`：SQLAlchemy 连接串（示例：`mysql+pymysql://user:pass@host:3306/db?charset=utf8mb4`）
- `JWT_SECRET`：JWT 签名密钥（生产必须替换为随机长字符串）
- `JWT_ALGORITHM`：默认 `HS256`
- `JWT_ACCESS_TOKEN_EXP_MINUTES`：JWT 过期分钟数（默认 `10080`=7 天）
- `DEFAULT_CURRENCY`：默认币种（默认 `CNY`）
- `ADMIN_USERNAME` / `ADMIN_PASSWORD`：初始化脚本用于创建管理员账号
- `TZ`：时区（建议 `Asia/Shanghai`）

## 数据模型与金额单位

金额/价格/余额均使用 `*_cents` 字段（整数，单位“分”），避免浮点误差与金额篡改问题：

- 产品价格：`products.price_cents`
- 钱包余额：`wallets.balance_cents`
- 充值/退款金额：`recharge_requests.amount_cents`、`refund_requests.amount_cents`
- 购买扣费：`card_claims.cost_cents` + `wallet_transactions`

## 关键接口（概览）

> `API_PREFIX = /api/v1`

- 认证：`POST /auth/register`、`POST /auth/login`、`GET /auth/me`
- 产品：`GET /products/by-category`；`PATCH /products/{id}`（管理员）
- 库存：
  - 用户侧：`GET /products/inventory/{sku}`（仅返回可用库存）
  - 管理侧：`GET /admin/inventory/{sku}`（返回 total/available/claimed/voided）
- 卡密发放：`POST /cards/claim(-by-login)`、`POST /cards/claim-batch(-by-login)`
- 充值/退款：
  - 用户：`POST/GET /recharge-requests`；`POST/GET /refund-requests`
  - 管理：`POST /admin/recharge-requests/{id}/approve|reject`；`POST /admin/refund-requests/{id}/approve|reject`
- 支付配置：`GET/POST/PATCH/DELETE /payment-configs`、`POST /payment-configs/upload-qr`
- 数据概览：`GET /admin/stats`（管理员）
- 订单记录：`GET /orders?limit=10`（管理员；对应卡密提取记录）
- 用户管理：`GET /admin/users`（管理员）
- API Key：`GET /admin/api-keys`、`POST /admin/users/{user_id}/api-keys`、`POST /admin/api-keys/{id}/revoke`

## 安全建议（生产必看）

- 必须替换：`JWT_SECRET`、`ADMIN_PASSWORD`，并限制后台访问范围（建议仅内网 + 反代鉴权）。
- 生产建议使用 HTTPS（反向代理：Nginx/Caddy/Traefik）。
- 数据库账号尽量最小权限（不建议长期使用 `root`）。
- 请确保业务合规使用本平台及其卡券/卡密内容。

## 联系方式

有意向部署/定制/合作，可联系 QQ：`438274867`。
