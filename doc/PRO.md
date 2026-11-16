# PRO 授权解锁说明

## 结论

PRO 判定集中在**一个函数**：

```
sun-panel/biz.(*ProAuthType).ProIsExpired
```

把它入口改成 `mov w0,#0 ; ret`（arm64）/ `xor eax,eax ; ret`（amd64），即恒定返回
`false` = 未过期，PRO 功能全部放行。

## 为什么一个函数就够

扫 `.text` 段里所有 `bl` 指令，指向该函数的调用点共 13 处：

| 调用点 | 解锁的功能 |
|---|---|
| `biz.(*GlobalSettingType).GetSiteSetting` | 前台 PRO 标识 / 入口显示 |
| `api_v1.docker.(*Container).ExecSwitchActionByContainerID` | 容器内执行命令 |
| `api_v1.docker.(*Container).RestartContainer` | 容器重启 |
| `api_v1.panel.(*BackupApi).Backup` | 整站备份 |
| `api_v1.panel.(*BackupApi).DownloadBackupZIPFile` | 备份下载 |
| `api_v1.panel.(*BackupApi).UploadZipFile` | 备份上传 |
| `api_v1.panel.(*BackupApi).Recovery` | 备份恢复 |
| `api_v1.panel.(*GlobalSettingApi).SaveCustomJsAndCssCode` | 自定义 JS / CSS |
| `api_v1.panel.(*PublicGalleryApi).UploadImg` | 公共图库上传 |
| `api_v1.micro_app.(*MicroAppApi).notLoginMicroappCountLimit` | micro app 数量上限 |
| `api_v1.openness.(*Openness).ProIsExpired` | 开放接口 |
| `biz.(*ProAuthType).timerFunc` | 授权状态定时刷新 |
| `biz.(*ProAuthType).TempAuthIsExpired` | 临时登录态判断 |

`TempAuthIsExpired` 有自己的判断逻辑，**不要动**，动了会把"未登录"当成"已登录"，
反而让授权刷新流程出错。

## 前端

PRO 版前端在 micro-app 宿主里算 `isPro`：

```js
isPro: h.data ? !h.data.isExpired : false
```

后端已放行时这个值仍可能是 `false`（前端会在拿到 auth 信息前先渲染 micro app），
所以把表达式整体换成 `!0`。压缩后的变量名每版会变，`tools/patch-web.py` 用正则匹配。

## 用法

```bash
# 1. 取官方 PRO 版 release 包（linux_arm64 / linux_amd64）
tar xzf sun-panel_vX_linux_arm64.tar.gz

# 2. 一键打补丁并组装 pro/ 物料
./tools/build-pro.sh ./sun-panel_vX_linux_arm64

# 3. 构建镜像
docker build -f Dockerfile.pro -t awahello/awadaoh-pro:latest .

# 4. 跑起来
docker run -d --name awadaoh-pro -p 3055:3055 \
  -v $(pwd)/conf:/app/conf \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/database:/app/database \
  awahello/awadaoh-pro:latest
```

单独验证 / 回滚：

```bash
python tools/patch-pro.py ./pro/awadaoh --check    # 已打补丁返回 0
python tools/patch-pro.py ./pro/awadaoh --revert   # 从 .orig 还原
```

## 版本适配

脚本按 Go 符号表定位，**换版本不用改偏移**：

1. 读 ELF64 `.symtab`，找 `sun-panel/biz.(*ProAuthType).ProIsExpired`
2. `st_value` → 用 `PT_LOAD` 段换算出文件偏移
3. 覆盖函数前 8 字节（arm64）或 3 字节（amd64）

前置条件：二进制**没被 strip**（官方 release 未 strip，符号表完整）。
如果哪天 strip 了，就得靠 `.gopclntab` 里的 `funcname` 表反查，或者按
`ProIsExpired` 的调用点特征码定位。

## 边界

- 补丁只改授权判定，不碰数据、不上报、不加后门。
- 升级上游版本后需要重新打补丁（脚本幂等，重复跑会提示"已打过"）。
- 二进制仍是闭源产物；`LICENSE` 里的 MIT 只覆盖开源部分。
