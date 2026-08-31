# User Service - 用户微服务

基于 FastAPI 的多租户用户微服务，采用**主表 + 业务扩展表**的分表架构，通过**微服务注册机 + 响应分发器**实现按 `service_name` 动态返回不同业务格式的用户响应。

## 技术栈

- **FastAPI** - 异步 Web 框架
- **SQLAlchemy 2.0 (Async)** - 异步 ORM
- **SQLite (aiosqlite)** - 数据库
- **Pydantic v2** - 数据验证
- **JWT (python-jose)** - 令牌认证
- **Passlib (bcrypt)** - 密码哈希
- **Alembic** - 数据库迁移
- **Log Proxy** - 操作日志代理模式

## 架构设计

### 分表设计

主表存储公共字段，每个业务一张扩展表存储专属字段，通过 `user_id` 外键一对一关联。

```
users（主表）                    user_forum_profiles（论坛扩展表）
├── id (PK)               ┌──→ ├── id (PK)
├── username               │    ├── user_id (FK, unique)
├── email                  │    ├── level
├── hashed_password        │    ├── points
├── full_name              │    └── title
├── service_name ──────────┘
├── created_at
├── updated_at
├── deleted_at
└── is_deleted

                         user_shop_profiles（商城扩展表）
                         ├── id (PK)
                         ├── user_id (FK, unique)
                         ├── member_level
                         ├── balance
                         └── coupons
```

### 核心机制

| 组件 | 文件 | 职责 |
|------|------|------|
| **微服务注册机** | `app/core/service_registry.py` | 以 `service_name` 为 key，注册扩展表模型、校验模型、响应构建器 |
| **响应分发器** | `app/core/response_dispatcher.py` | 根据用户 `service_name` 取出对应构建器，传入用户+扩展记录，返回业务专属响应 |
| **业务注册入口** | `app/services/business_registry.py` | 所有业务统一在此注册，应用启动时自动加载 |
| **通用 Profile Repository** | `app/repositories/profile_repository.py` | 泛型扩展表 CRUD，传入扩展表模型类即可操作 |

### 数据流

```
注册请求 ──→ UserService.create_user()
                ├── 写入 users 主表
                └── 根据 service_name 找到扩展表模型
                    └── ProfileRepository.create(user_id, profile)

查询请求 ──→ UserService.get_user_with_profile()
                ├── 读 users 主表
                └── ProfileRepository.get_by_user_id(user_id)
                    └── ResponseDispatcher.dispatch(user, profile)
                        └── 根据 service_name 调用对应构建器 → 业务专属响应
```

## 项目结构

```
app/
├── main.py                          # 应用入口（lifespan 启动时注册业务服务）
├── core/
│   ├── config.py                    # 配置管理
│   ├── database.py                  # SQLite 异步连接
│   ├── security.py                  # JWT + 密码加密
│   ├── dependencies.py              # 认证依赖
│   ├── service_registry.py          # 微服务注册机
│   └── response_dispatcher.py       # 响应分发器
├── models/
│   ├── user.py                      # User 主表模型
│   └── extensions/                  # 业务扩展表
│       ├── base.py                  # 扩展表抽象基类
│       ├── forum.py                 # 论坛扩展表
│       └── shop.py                  # 商城扩展表
├── schemas/                         # Pydantic 模型
│   ├── user.py                      # 用户请求/响应（含 profile 扩展字段）
│   └── token.py                     # Token 模型
├── repositories/
│   ├── user_repository.py           # 主表 CRUD
│   └── profile_repository.py        # 通用扩展表 CRUD（泛型）
├── services/
│   ├── user_service.py              # 用户业务逻辑（含扩展表同步）
│   ├── auth_service.py              # 认证业务逻辑
│   └── business_registry.py         # 业务注册主入口
├── api/v1/routes/
│   ├── auth.py                      # 认证路由
│   └── users.py                     # 用户路由（接入分发器）
├── proxy/
│   └── log_proxy.py                 # Log Proxy 日志代理
└── utils/
    └── logger.py                    # 日志配置
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
# 编辑 .env，配置 JWT_PRIVATE_KEY / JWT_PUBLIC_KEY（密钥路径或 PEM 字符串）等
```

### 3. 生成 JWT 密钥（RS256 非对称）

```bash
python scripts/generate_jwt_keys.py
```

生成：
- `keys/jwt_private.pem`：**私钥**，仅保留在 user-service，严禁提交仓库（已加入 `.gitignore`）；
- `keys/jwt_public.pem`：**公钥**，可分发给任何需要校验 JWT 的兄弟服务。

### 4. 运行服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 访问 API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 端点

### 认证 (`/api/v1/auth`)

| 方法 | 端点 | 功能 | 认证 |
|------|------|------|------|
| POST | `/register` | 用户注册（支持 `profile` 扩展字段） | 否 |
| POST | `/login` | 用户登录（返回 JWT） | 否 |
| POST | `/refresh` | 刷新令牌 | 否 |
| POST | `/logout` | 用户登出 | 是 |

### 用户管理 (`/api/v1/users`)

| 方法 | 端点 | 功能 | 认证 |
|------|------|------|------|
| GET | `/me` | 获取当前用户（按 `service_name` 分发响应格式） | 是 |
| PUT | `/me` | 更新当前用户（支持 `profile` 扩展字段更新） | 是 |
| POST | `/me/change-password` | 修改密码 | 是 |
| DELETE | `/me` | 软删除用户 | 是 |
| GET | `/{user_id}` | 获取指定用户（按 `service_name` 分发） | 是 |
| GET | `/` | 用户列表（支持按 `service_name` 筛选，批量分发） | 是 |

### 系统

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/` | 服务信息 |

## 用户模型

### 主表字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键，自增 |
| `username` | String(50) | 用户名，唯一 |
| `email` | String(100) | 邮箱，唯一 |
| `hashed_password` | String(255) | bcrypt 密码哈希 |
| `full_name` | String(100) | 全名，可空 |
| `service_name` | String(50) | 业务服务标识，默认 `default` |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |
| `deleted_at` | DateTime | 删除时间（软删除） |
| `is_deleted` | Boolean | 是否软删除 |

### 注册请求示例

```json
{
  "username": "forum_user",
  "email": "forum@example.com",
  "password": "Test@1234",
  "full_name": "Forum User",
  "service_name": "forum",
  "profile": {
    "level": 5,
    "points": 1000,
    "title": "论坛达人"
  }
}
```

### 响应示例（按 service_name 分发）

**service_name = "forum"**
```json
{
  "id": 1,
  "username": "forum_user",
  "email": "forum@example.com",
  "full_name": "Forum User",
  "service_name": "forum",
  "forum": {
    "level": 5,
    "points": 1000,
    "title": "论坛达人"
  }
}
```

**service_name = "shop"**
```json
{
  "id": 2,
  "username": "shop_user",
  "email": "shop@example.com",
  "full_name": null,
  "service_name": "shop",
  "shop": {
    "member_level": "黄金会员",
    "balance": 999.99,
    "coupons": 5
  }
}
```

**service_name = "default"（未注册的服务回退到此）**
```json
{
  "id": 3,
  "username": "default_user",
  "email": "default@example.com",
  "full_name": null,
  "service_name": "default",
  "created_at": "2026-08-29T00:00:00",
  "updated_at": null
}
```

## 新增业务服务指南

### 步骤 1：创建扩展表模型

在 `app/models/extensions/` 下新建文件，继承 `BaseProfile`：

```python
# app/models/extensions/game.py
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.extensions.base import BaseProfile

class GameProfile(BaseProfile):
    __tablename__ = "user_game_profiles"

    game_id: Mapped[str] = mapped_column(String(50), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
```

### 步骤 2：实现响应构建器

在 `app/services/business_registry.py` 中添加：

```python
def build_game_response(user: User, profile: GameProfile | None) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "service_name": user.service_name,
        "game": {
            "game_id": profile.game_id if profile else "",
            "rank": profile.rank if profile else 0,
        },
    }
```

### 步骤 3：注册服务

在 `business_registry.py` 的 `setup_services()` 中添加：

```python
if not registry.has("game"):
    registry.register(
        name="game",
        description="游戏服务",
        profile_model=GameProfile,
        response_builder=build_game_response,
    )
```

完成后，`service_name="game"` 的用户会自动使用 `user_game_profiles` 表存储扩展字段，并返回游戏专属格式的响应。

## 数据库迁移

```bash
# 生成迁移（会自动检测主表和所有扩展表）
alembic revision --autogenerate -m "描述"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

## Docker 部署

### 1. 先在本机生成 JWT 密钥

```bash
python scripts/generate_jwt_keys.py
# 生成 keys/jwt_private.pem（私钥）与 keys/jwt_public.pem（公钥）
```

> `keys/` 目录已被 `.dockerignore` 排除，**不会烘焙进镜像**；运行时通过 `./keys:/app/keys:ro` 只读卷注入。
> **务必先在宿主机生成好密钥再启动容器**，否则容器启动即失败（密钥缺失 fail-fast）。

### 2. 构建并启动

```bash
docker-compose up -d --build
```

- JWT 私钥 / 公钥：`./keys:/app/keys:ro` 只读挂载注入（容器仅读取，私钥不落盘在镜像层）
- SQLite 数据库：`./data:/app/data` 卷持久化
- 日志：`./logs:/app/logs` 挂载
- 生产环境建议：私钥放入密钥管理服务（KMS / Vault / 云 Secret），通过 Secret 挂载覆盖 `JWT_PRIVATE_KEY`，公钥可分发给各兄弟服务校验

## 运行测试

```bash
pytest tests/ -v
```

测试覆盖：
- 认证 API（注册、登录、刷新、重复注册、错误密码）
- 用户管理 API（CRUD、密码修改、软删除、列表、按 service_name 分发）
- 注册机（注册、重复检测、获取、列出、装饰器、注销）
- 分发器（默认服务、多服务分发、profile 传入、未知服务回退、批量分发）

## JWT 认证（RS256 非对称加密）

本服务使用 **RS256 非对称算法**签发与校验 JWT：

- **签发**：登录 / 注册时使用 `keys/jwt_private.pem`（私钥）签名，私钥只存在于 user-service，绝不外发。
- **本服务校验**：内部用 `keys/jwt_public.pem`（公钥）校验自己签发的令牌。
- **其他服务校验**：其他服务只需持有**公钥**即可验证 user-service 签发的令牌，无需也不应接触私钥。公钥获取方式：
  1. 直接复制 `keys/jwt_public.pem` 文件；
  2. 从本服务动态拉取：`GET /.well-known/jwks.json`（标准 JWKS 格式）。

配置项（`.env`，值既可以是 PEM 文件路径，也可以是 PEM 字符串）：

```
JWT_PRIVATE_KEY=keys/jwt_private.pem
JWT_PUBLIC_KEY=keys/jwt_public.pem
ALGORITHM=RS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 其他服务校验示例（Python + python-jose）

```python
from jose import jwt

# 方式一：使用公钥 PEM 文件
with open("keys/jwt_public.pem", "rb") as f:
    public_key = f.read()
payload = jwt.decode(token, public_key, algorithms=["RS256"])

# 方式二：从 user-service 的 JWKS 端点动态获取公钥
import requests
jwks = requests.get("http://user-service:8000/.well-known/jwks.json").json()
payload = jwt.decode(token, jwks["keys"][0], algorithms=["RS256"])
```

> 注意：`kid` 未使用场景下直接传 JWKS 中的第一个 key 即可；若后续支持多密钥轮换，请按 `kid` 匹配。

## 安全特性

- 密码 bcrypt 哈希存储（12 轮）
- JWT RS256 非对称签名：私钥签发、公钥校验（访问令牌 30 分钟 + 刷新令牌 7 天），公开 JWKS 端点供其他服务验证
- 敏感信息日志自动脱敏（password、email 等）
- CORS 来源限制
- SQL 注入防护（ORM 参数化查询）
- 输入数据验证（Pydantic）
- 软删除保留数据
- 操作日志审计（Log Proxy 模式，自动记录 Repository 层所有操作）
