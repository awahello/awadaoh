# 更新说明

## v1.0.0

首个版本。

- 品牌与工程标识全面更换：`akkdaoh`
- 新增导航站风格视觉层（`src/styles/global.less`）：分组标题主色竖条、图标卡 76px 圆角方块与悬停浮起、胶囊搜索框、自定义滚动条
- 主色板改为靛蓝 `#5B6CFF` + 青绿 `#22D3C5`，深浅色主题统一由 `src/hooks/useTheme.ts` 覆盖
- 新增品牌图标生成器 `scripts/gen-assets.py`（SVG / PNG / ICO 全部本地生成，无外部依赖）
- Dockerfile 改为多阶段 + 健康检查，支持 buildx 多架构
- 新增 `.github/workflows/docker.yml`：推 tag 自动构建并推送 `ghcr.io/<owner>/<repo>`
- 新增 `tools/bookmarks2sunpanel.py`：Chrome / Edge 书签 HTML 转导入配置
