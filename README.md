<div align="center">

<img src="./public/logo.png" width="96" height="96" alt="AKKdaoh" />

# AKKdaoh

**自托管导航面板 / NAS 首页 / 浏览器起始页**

一个可以自己部署、自己掌控的网址导航站：分组管理图标、内置搜索、系统监控、Docker 容器管理、多用户与访客模式。

</div>

---

## 特性

- **导航站布局**：分组标题 + 图标网格，深/浅色自动跟随系统，背景图、模糊、遮罩全可调
- **图标分组管理**：拖拽排序、批量导入导出、书签 HTML 转换工具
- **内置搜索**：可自定义搜索引擎，支持页内图标快速过滤
- **系统监控**：CPU / 内存 / 磁盘 / 网络，可对访客公开
- **Docker 面板**：容器列表、启停、日志
- **多用户**：管理员 / 普通用户 / 访客模式，公开图库
- **数据备份**：整站配置一键导出为 JSON
- **单文件部署**：前端打包进 Go 二进制，一个进程跑完全站

## 快速部署

### docker compose（推荐）

```yaml
services:
  akkdaoh:
    image: awahello/akkdaoh:latest
    container_name: akkdaoh
    volumes:
      - ./conf:/app/conf
      - ./uploads:/app/uploads
      - ./database:/app/database
    ports:
      - 3002:3002
    environment:
      - TZ=Asia/Shanghai
    restart: unless-stopped
```

```bash
docker compose up -d
# 打开 http://服务器IP:3002
# 默认账号 admin / 密码 admin
```

### docker run

```bash
docker run -d --name akkdaoh \
  -p 3002:3002 \
  -e TZ=Asia/Shanghai \
  -v $(pwd)/conf:/app/conf \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/database:/app/database \
  --restart unless-stopped \
  awahello/akkdaoh:latest
```

### 自己构建镜像

```bash
git clone https://github.com/awahello/akkdaoh.git
cd akkdaoh
docker build -t awahello/akkdaoh:latest .
```

多架构（amd64 / arm64）：

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -t awahello/akkdaoh:latest --push .
```

推送 tag 到仓库后，`.github/workflows/docker.yml` 会自动构建并推送到 `ghcr.io/awahello/akkdaoh`。

## 目录约定

| 容器路径 | 说明 |
|---|---|
| `/app/conf` | `conf.ini` 主配置（端口、数据库类型、Redis 等） |
| `/app/database` | SQLite 数据文件 |
| `/app/uploads` | 用户上传的图标、背景图 |
| `/app/web` | 前端静态资源（镜像内已打包） |
| `/app/akkdaoh` | 后端可执行文件 |

## 从 Chrome 书签导入

仓库自带 `tools/bookmarks2sunpanel.py`，把浏览器导出的书签 HTML 转成本项目可导入的 JSON：

```bash
python tools/bookmarks2sunpanel.py bookmarks.html --icon favicon
```

生成的 `*.sun-panel.json` 在「设置 → 导出导入 → 导入配置」里导入即可。

## 环境变量 / 端口

| 项 | 默认 |
|---|---|
| 监听端口 | `3002` |
| 配置文件 | `/app/conf/conf.ini` |
| 数据库 | SQLite `database.db` |
| 时区 | `Asia/Shanghai` |

## 健康检查

镜像内置：

```
HEALTHCHECK CMD curl -fsS http://127.0.0.1:3002/ || exit 1
```

## 开发

```bash
npm install          # 前端依赖
npm run dev          # 前端 dev server
cd service && go run . -config   # 后端（首次会生成 conf/conf.ini）
npm run build        # 构建前端到 dist/
```

## 许可

本项目基于 MIT 许可发布，详见 [LICENSE](./LICENSE)。
