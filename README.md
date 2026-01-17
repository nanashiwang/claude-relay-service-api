# 全自动卡券（卡密）发放平台（FastAPI + MySQL）

本项目是一个面向“代理渠道/分销”的**卡券（卡密）发放平台**，覆盖从产品与定价、卡密库存管理、钱包余额、充值/退款申请，到卡密提取与导出的完整闭环。充值/退款采用管理员人工审核以匹配线下转账场景，其余流程尽量自动化。

有意向部署定制/合作，可联系 QQ：`438274867`。

## 功能概览

- 多角色与登录安全：管理员/代理登录，权限隔离；登录/注册验证码校验（防爆破）
- 公告弹窗：登录后展示公告，支持 Markdown 排版与二维码；后台可配置标题/内容/二维码
- 产品体系：SKU + 规格（按天/按量）+ 价格/币种 + 上下架 + **折扣百分比**
- 折扣展示：前端展示原价 + 折后价 + 折扣标识，购买扣费按折后价计算
- 卡密库存：TXT 换行批量导入、SHA256 去重、可用/已提取/作废状态、库存统计
- 购买与发放：支持登录购买与 API Key 提取；支持批量购买、复制、导出 TXT
- 钱包与流水：余额以“分”为单位，记录充值/购买/退款/返利/管理员调整
- 充值/退款：用户提交申请，管理员通过/拒绝（可填原因，用户可见）
- 支付配置：上传收款码图片 + 支付说明，充值页按支付方式展示
- 推广返利：推广码 `U{user_id}` 或用户名；仅可绑定一次；被推广用户充值审核通过后发生购卡消费，推广人获得 **10% 返利**
- 纯后端托管：静态前端位于 `web/`，由后端直接托管，无需单独前端服务

## 技术栈

- 后端：FastAPI、SQLAlchemy、Pydantic Settings、PyMySQL、JWT（`python-jose`）
- 数据库：MySQL 8
- 前端：原生 HTML/CSS/JS（静态资源在 `web/`）
- 容器化：Dockerfile + docker compose（支持本机与 NAS）

## 访问入口

服务启动后（默认端口 `8000`）：

- Swagger：`http://127.0.0.1:8000/docs`
- 登录页：`http://127.0.0.1:8000/`
- 代理控制台：`http://127.0.0.1:8000/web/dashboard.html`
- 管理后台：`http://127.0.0.1:8000/web/admin.html`
- 店铺购卡：`http://127.0.0.1:8000/web/shop.html`
- 充值页：`http://127.0.0.1:8000/web/recharge.html`
- 退款页：`http://127.0.0.1:8000/web/refund.html`

## 界面截图（演示数据）

> 以下截图可用 `scripts/capture_screenshots.py` 自动启动服务并登录后生成（使用临时 SQLite 演示库，不依赖 MySQL）。

生成/更新截图：
```bash
python -m pip install playwright
python -m playwright install chromium
python "scripts/capture_screenshots.py" --output "docs/screenshots"
```

### 登录页
![](docs/screenshots/01_login.png)

### 代理控制台
![](docs/screenshots/02_dashboard.png)

### 店铺购卡
![](docs/screenshots/03_shop.png)

### 充值页（支付方式收款码展示）
![](docs/screenshots/04_recharge.png)

### 退款页
![](docs/screenshots/05_refund.png)

### 管理后台（概览）
![](docs/screenshots/06_admin_dashboard.png)

### 管理后台（充值审核）
![](docs/screenshots/07_admin_recharges.png)

### 管理后台（用户管理）
![](docs/screenshots/08_admin_users.png)

### 管理后台（支付配置）
![](docs/screenshots/09_admin_payments.png)

## 快速开始（本地开发）

### 1）准备环境
- Python 3.11+
- MySQL 8（可用 Docker 启动）

### 2）配置环境变量
复制 `.env.example` 为 `.env`，至少配置：

- `DATABASE_URL`（也支持别名 `DB_URL_QUANT`）
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

可选：同步 SQLAlchemy 字段备注到 MySQL（便于 DB 端查看）：

```bash
python "scripts/apply_db_comments.py" --apply
```

### 5）启动服务
推荐启动方式（端口 `8000`）：

```bash
python -m uvicorn "api:app" --reload --host "0.0.0.0" --port 8000
```

也可以：

- 直接运行 `api.py`（默认端口 `11113`，可通过 `PORT` 覆盖）
- Windows：双击 `start.bat` 或 PowerShell 执行 `./start.ps1`

## 使用流程（建议先跑通一遍）

### 管理员
1. 初始化 DB（自动生成产品与管理员账号）
2. 登录管理后台：`/web/admin.html`
3. 产品管理：设置 `price_cents` 与 `discount_percent`（例如 90 表示 9 折）
4. 卡密管理：选择 SKU 导入 TXT（换行分隔）
5. 支付配置：上传收款码图片并保存（充值页会展示）
6. 公告配置：设置公告内容与二维码（登录后弹窗展示）
7. 充值/退款审核：通过/拒绝（拒绝原因会回显给用户）

### 代理（普通用户）
1. 注册/登录（验证码校验）
2. 绑定推广人（可选，仅一次）：填推广码 `U{用户ID}` 或用户名
3. 充值：选择支付方式提交申请，等待管理员审核
4. 购卡：在店铺页选择 SKU 与数量购买，支持复制/导出 TXT
5. 退款：如需退款，提交退款申请等待审核

## 折扣规则说明

- `discount_percent` 为 1–99 的整数百分比
- 折后价 = `price_cents * discount_percent / 100`，四舍五入，最低 1 分
- 前端会展示原价 + 折后价 + 折扣标签（如 “9.5折”）

## 版本升级与数据库变更（重要）

- 新折扣字段：`products.discount_percent`（1-99 的整数百分比）
- 如已存在旧字段 `discount_price_cents`，请先迁移再删除（避免丢失历史折扣）

### 增加折扣字段
```sql
ALTER TABLE products
  ADD COLUMN discount_percent INT NULL COMMENT '折扣百分比(1-99)' AFTER price_cents;
```

### 可选：从旧折扣价迁移为百分比
```sql
UPDATE products
SET discount_percent = ROUND(discount_price_cents * 100 / price_cents)
WHERE discount_price_cents IS NOT NULL AND price_cents > 0;
```

### 可选：清理旧字段（确认迁移后再执行）
```sql
ALTER TABLE products DROP COLUMN discount_price_cents;
```

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

NAS 上可使用 `docker-compose.nas.yml` 拉取镜像，并挂载上传目录以持久化收款码/公告二维码：

- 容器内：
  - 支付收款码：`/app/web/uploads/payments/`
  - 公告二维码：`/app/web/uploads/announcements/`
- NAS 路径示例：
  - `/volume3/docker/claude-relay-service-api/upload/payments/`
  - `/volume3/docker/claude-relay-service-api/upload/announcements/`

`ports: "11113:8000"` 表示浏览器访问 NAS 的 `11113`，容器内服务端口是 `8000`。

## 自动更新（Watchtower，可选）

如需 NAS 自动拉取最新镜像并重建容器，可加入 Watchtower（轮询镜像 digest，仅有更新才重启）：

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
- `DB_URL_QUANT`：`DATABASE_URL` 的别名（历史兼容）
- `JWT_SECRET`：JWT 签名密钥（生产必须替换为随机长字符串）
- `JWT_ALGORITHM`：默认 `HS256`
- `JWT_ACCESS_TOKEN_EXP_MINUTES`：JWT 过期分钟数（默认 `10080`=7 天）
- `DEFAULT_CURRENCY`：默认币种（默认 `CNY`）
- `ADMIN_USERNAME` / `ADMIN_PASSWORD`：初始化脚本用于创建管理员账号
- `TZ`：时区（建议 `Asia/Shanghai`）

## 数据模型与金额单位

金额/价格/余额均使用 `*_cents` 字段（整数，单位“分”），避免浮点误差与金额篡改问题：

- 产品价格：`products.price_cents`
- 产品折扣：`products.discount_percent`
- 钱包余额：`wallets.balance_cents`
- 充值/退款金额：`recharge_requests.amount_cents`、`refund_requests.amount_cents`
- 购买扣费：`card_claims.cost_cents` + `wallet_transactions`

## 关键接口（概览）

> `API_PREFIX = /api/v1`

- 认证：`GET /auth/captcha`、`POST /auth/register`、`POST /auth/login`、`GET /auth/me`
- 公告：`GET /announcements`、`PATCH /announcements`、`POST /announcements/upload-qr`
- 产品：`GET /products/by-category`、`PATCH /products/{id}`（管理员）
- 库存：
  - 用户侧：`GET /products/inventory/{sku}`（仅可用库存）
  - 用户侧批量：`POST /products/inventory/batch`（一次返回多 SKU 可用库存）
  - 管理侧：`GET /admin/inventory/{sku}`（total/available/claimed/voided）
- 卡密发放：`POST /cards/claim(-by-login)`、`POST /cards/claim-batch(-by-login)`
- 充值/退款：
  - 用户：`POST/GET /recharge-requests`、`POST/GET /refund-requests`
  - 管理：`POST /admin/recharge-requests/{id}/approve|reject`、`POST /admin/refund-requests/{id}/approve|reject`
- 支付配置：`GET/POST/PATCH/DELETE /payment-configs`、`POST /payment-configs/upload-qr`
- 推广返利：`GET /referrals/me`、`POST /referrals/bind`、`GET /referrals/rebates`
- 数据概览：`GET /admin/stats`（管理员）
- 订单记录：`GET /orders?limit=10`（管理员，对应卡密提取记录）
- 用户管理：`GET /admin/users`（管理员）
- API Key：`GET /admin/api-keys`、`POST /admin/users/{user_id}/api-keys`、`POST /admin/api-keys/{id}/revoke`

## 安全建议（生产必看）

- 必须替换：`JWT_SECRET`、`ADMIN_PASSWORD`，并限制后台访问范围（建议仅内网 + 反代鉴权）
- 生产建议启用 HTTPS（反向代理：Nginx/Caddy/Traefik）
- 数据库账号尽量最小权限（不建议长期使用 `root`）
- 登录验证码已启用，仍建议搭配反代限流/风控
- 请确保业务合规使用本平台及其卡券/卡密内容

## 联系方式

有意向部署定制/合作，可联系 QQ：`438274867`。
