# RUN · 校园跑助手（Web / Docker 版）

把原 [unirun](https://github.com/yanyaoli/unirun) 的 Tkinter 桌面工具改造成 **Docker 化的 Web 服务**：

- 每次使用都要单独登录；
- 提交结束（成功或失败）自动退出登录并销毁本次 token；
- 账号密码不落盘，token 只存在当前进程的内存会话里；
- 每个浏览器会话独立，互不共享 token；
- 默认只监听 `127.0.0.1`，不面向公网。

> 本项目仅供个人在可信的私有环境自托管。不要把它部署成“任何人注册就能用”的公开站点。

## 安全模型

| 项目 | 行为 |
| --- | --- |
| 手机号 / 密码 | 仅在 `POST /api/login` 的生命周期内使用，转发给上游后不缓存、不写文件、不写日志 |
| 上游 token | 只保存在服务端进程内存的 `Session` 对象中，浏览器拿到的只是一个随机 `HttpOnly` cookie |
| 会话隔离 | 每个浏览器会话独立 Session、独立 token、独立提交锁 |
| 自动登出 | 提交接口结束（无论成功/失败）立即销毁会话；也可手动退出 |
| 空闲超时 | 默认 15 分钟无操作自动销毁（`SESSION_IDLE_TTL`） |
| 绝对超时 | 默认 2 小时强制销毁（`SESSION_MAX_TTL`） |
| 持久化 | 没有任何数据库或 volume；容器重启 = 全部会话失效 |
| 密码落盘 | 原项目的 `user_data.json` 已完全移除 |

**仍然存在的边界：**

- 密码与 token 在服务器内存中不可避免地以明文形式短暂存在，root、core dump、调试器仍可能读取；
- 所有请求都从你的服务器出口 IP 发往上游，并发过高可能触发平台风控；
- 因此，这个服务只适合你自己或你完全信任的少数人使用。

## 快速开始

```bash
docker compose up -d --build
```

打开 <http://127.0.0.1:8000>。

停止并清除：

```bash
docker compose down
```

更新代码后重建：

```bash
docker compose up -d --build
```

### 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SESSION_IDLE_TTL` | `900` | 空闲多少秒后销毁会话 |
| `SESSION_MAX_TTL` | `7200` | 会话最长存活秒数 |
| `COOKIE_SECURE` | `0` | 走 HTTPS 时设为 `1` |
| `ACCESS_CODE` | 空 | 非空时，登录页需要额外输入访问口令 |
| `LOGIN_MAX_ATTEMPTS` | `10` | 单 IP 在窗口期内的登录尝试上限 |
| `LOGIN_WINDOW_SECONDS` | `300` | 登录限流窗口 |
| `UPSTREAM_TIMEOUT` | `20` | 上游请求超时秒数 |
| `APP_TIMEZONE` | `Asia/Shanghai` | 生成 `recordDate` 使用的时区；容器默认 UTC，必须显式设置 |
| `UNIRUN_HOST` | 上游地址 | 一般不需要改 |

### 放到反向代理后面

若用 Nginx / Caddy 提供 HTTPS：

1. 保持容器端口只绑定 `127.0.0.1`；
2. 设置 `COOKIE_SECURE=1`；
3. 建议再套一层 HTTP Basic Auth 或仅限内网/VPN 访问。

## 本地开发

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
uvicorn web.main:app --reload --port 8000
```

冒烟测试（不需要网络）：

```bash
python tests/smoke_test.py
```

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 单页界面 |
| `GET` | `/api/config` | 地图列表、参数范围、是否需要访问口令 |
| `POST` | `/api/login` | `{phone, password, access_code?}`，成功后种下会话 cookie |
| `GET` | `/api/me` | 当前会话的用户信息（不含 token） |
| `POST` | `/api/run` | `{distance, time, map}`，提交后**必定**销毁会话 |
| `POST` | `/api/logout` | 主动退出并销毁会话 |
| `GET` | `/healthz` | 容器健康检查 |

## 目录结构

```
.
├── app/
│   ├── auth.py              # 上游登录、token 校验
│   ├── config.py            # 上游常量
│   ├── session.py           # 内存会话存储 + 过期清理
│   ├── maps/                # 内置地图数据
│   └── services/
│       ├── mapdata.py       # 地图注册表
│       └── run.py           # 轨迹生成与跑步记录提交
├── utils/                   # MD5、签名、轨迹工具
├── web/
│   ├── main.py              # FastAPI 入口
│   └── static/              # 前端页面
├── tests/smoke_test.py
├── Dockerfile
└── docker-compose.yml
```

新增学校：把地图文件放进 `app/maps/`，然后在 `app/services/mapdata.py` 的 `MAPS` 中注册 key 与显示名称。

## 与原项目的差异

- 移除了 Tkinter GUI、`user_data.json` 和本地多账号管理；
- 移除了 `app/requests` 中依赖全局用户数据的写法，改为显式传入 token；
- 所有上游请求增加超时与异常处理；
- 轨迹生成增加空 `edge`、异常链路与最大步数保护；
- 速度检查、地图数据、签名算法保持原逻辑。

## 免责声明

本项目是原项目的 Web 容器化改造，仅用于技术学习与个人自托管。使用本工具产生的任何后果（包括但不限于账号异常、学校处分、平台封禁）由使用者自行承担。请遵守所在学校与平台的规定。

原项目：<https://github.com/yanyaoli/unirun>，MIT License，Copyright (c) 2024 yanyaoli。
