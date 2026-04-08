# pay_chat_api

使用 FastAPI + SQLAlchemy 实现用户基础 CRUD，并支持 JWT 登录鉴权。

## 运行方式

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 启动服务：

```bash
uvicorn main:app --reload
```

## 数据库配置

代码中默认使用：

```python
DB_URL = "mysql+pymysql://root:Aa11221122@localhost:3306/pay_chat"
```

## JWT 配置

- `access_token`：7 天有效
- `refresh_token`：30 天有效
- `refresh_token` 失效后，接口会返回 401，需要重新登录。

## 接口

### 用户 CRUD

- `POST /users`：创建用户
- `GET /users`：分页查询用户列表
- `GET /users/{user_id}`：查询单个用户
- `PUT /users/{user_id}`：更新用户
- `DELETE /users/{user_id}`：删除用户

### 认证

- `POST /auth/login`：手机号+密码登录，返回 access token 和 refresh token
- `POST /auth/refresh`：使用 refresh token 刷新新的 token 对
