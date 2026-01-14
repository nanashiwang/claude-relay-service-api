# 卡密接口平台（FastAPI + MySQL）

目标：提供用户登录、API Key 发放、余额钱包、充值/退款申请、按产品类型提取卡密、批量导入卡密（txt 换行）的最小可用后端。

## 1. 启动 MySQL（可选：Docker）

```bash
docker compose up -d
```

## 2. 配置环境变量

复制 `.env.example` 为 `.env` 并按需修改：

- `DATABASE_URL`
- `JWT_SECRET`
- `ADMIN_USERNAME` / `ADMIN_PASSWORD`

## 3. 安装依赖

```bash
python -m pip install -r requirements.txt
```

## 4. 初始化数据库（建表 + 预置产品 + 创建管理员）

```bash
python "scripts/init_db.py"
```

可选：把模型里的字段备注同步到 MySQL（默认只打印 SQL）：

```bash
python "scripts/apply_db_comments.py" --apply
```

## 5. 运行

```bash
uvicorn "api:app" --reload --host 0.0.0.0 --port 8000
```

也可以直接：

- IDE 里直接运行 `api.py`（点击运行按钮即可）
- Windows 双击 `start.bat` 或在 PowerShell 执行 `./start.ps1`

打开 API 文档：

- Swagger UI: `http://127.0.0.1:8000/docs`
- 登录页：`http://127.0.0.1:8000/`（代理商登录窗口）
- 控制台：`http://127.0.0.1:8000/web/dashboard.html`

## 6. 功能概览

- 用户：注册/登录（JWT）
- 管理员：为用户创建/吊销 API Key、审批充值/退款、批量导入卡密、调整产品价格
- 用户：提交充值申请/退款申请、查看余额与流水、按 SKU 提取卡密（API Key 或 JWT）

## 7. 最小使用流程（建议直接用 Swagger）

1) 初始化后，用管理员账号登录：`POST /api/v1/auth/login`  
2) 给产品设置价格：`PATCH /api/v1/products/{product_id}`（例如 `price_cents=1000`）  
3) 导入卡密：`POST /api/v1/admin/cards/import`（`product_sku` + txt 文件）  
4) 用户注册并登录：`POST /api/v1/auth/register` + `POST /api/v1/auth/login`  
5) 管理员给用户创建 API Key：`POST /api/v1/admin/users/{user_id}/api-keys`  
6) 用户用 API Key 提取卡密：`POST /api/v1/cards/claim`（Header: `X-API-Key`）
