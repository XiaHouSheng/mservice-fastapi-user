# User Service - 用户微服务

基于 FastAPI 的用户微服务，提供完整的用户认证、授权和用户管理功能。

## 技术栈

- **FastAPI** - 异步 Web 框架
- **SQLAlchemy 2.0 (Async)** - 异步 ORM
- **SQLite (aiosqlite)** - 数据库
- **Pydantic v2** - 数据验证
- **JWT (python-jose)** - 令牌认证
- **Passlib (bcrypt)** - 密码哈希
- **Alembic** - 数据库迁移
- **Log Proxy** - 操作日志代理模式

## 项目结构

```
app/
├── main.py                 # 应用入口
├── core/                   # 核心配置（config/database/security/dependencies）
├── models/                 # ORM 模型（user/enums）
├── schemas/                # Pydantic 模型（user/token）
├── repositories/           # 数据访问层
├── services/               # 业务逻辑层（user/auth）
├── api/v1/routes/          # API 路由（auth/users）
├── proxy/                  # Log Proxy 日志代理
└── utils/                  # 工具（logger）
```

## 快速开始

### 1. 创建虚拟环境并安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，修改 SECRET_KEY 等配置
```

### 3. 运行服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 访问 API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 端点

### 认证 (`/api/v1/auth`)
| 方法 | 端点 | 功能 | 认证 |
|------|------|------|------|
| POST | `/register` | 用户注册 | 否 |
| POST | `/login` | 用户登录 | 否 |
| POST | `/refresh` | 刷新令牌 | 否 |
| POST | `/logout` | 用户登出 | 是 |

### 用户管理 (`/api/v1/users`)
| 方法 | 端点 | 功能 | 认证 |
|------|------|------|------|
| GET | `/me` | 获取当前用户 | 是 |
| PUT | `/me` | 更新当前用户 | 是 |
| POST | `/me/change-password` | 修改密码 | 是 |
| DELETE | `/me` | 软删除用户 | 是 |
| GET | `/{user_id}` | 获取指定用户 | 是 |
| GET | `/` | 用户列表（管理员） | 是 |

### 系统
| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/` | 服务信息 |

## 数据库迁移

```bash
# 生成迁移
alembic revision --autogenerate -m "描述"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

## Docker 部署

```bash
docker-compose up -d --build
```

## 运行测试

```bash
pytest tests/ -v
```

## 安全特性

- 密码 bcrypt 哈希存储（12 轮）
- JWT 访问令牌（30 分钟）+ 刷新令牌（7 天）
- 敏感信息日志自动脱敏
- CORS 来源限制
- SQL 注入防护（ORM 参数化查询）
- 输入数据验证（Pydantic）
- 软删除保留数据
- 操作日志审计（Log Proxy 模式）
