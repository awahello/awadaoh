# Awadaoh 书签同步 · Chrome 扩展

把 Chrome 书签推到自托管面板。装一次，之后书签一变就自动同步。

## 为什么不直接「登录谷歌」

Google **没有**公开的 Chrome 书签 API。Chrome 的同步走的是私有 protobuf 协议
（要 Chrome 自己的 OAuth client + 设备注册），第三方拿不到；老的
`bookmarks.google.com` 接口 2021 年就下线了。

所以「登录谷歌账号 → 第三方读到书签」这条路不存在。可行的等价做法是：
**Chrome 已经把书签同步到本机了，扩展读本地那份推给面板。**

只要你在 Chrome 里登录着谷歌账号，这台机器上的书签就是同步后的结果 ——
扩展一推，面板就和你的收藏夹一致了。

## 装

1. Chrome 打开 `chrome://extensions`
2. 右上角打开「开发者模式」
3. 点「加载已解压的扩展程序」，选这个 `chrome-extension` 目录
4. 点工具栏上的图标 → 弹出小面板 → 点「设置」（第一次会显示「还没配置」）

## 配

| 项 | 填什么 |
|---|---|
| 面板地址 | `https://nav.example.com`（不要结尾斜杠） |
| 账号 / 密码 | 面板的后台账号，用来换 token |
| 自动推送 | 开着就行，书签一变就推（防抖 3 秒） |
| 兜底间隔 | 默认 30 分钟，Chrome 同步是异步的，本地变了才知道 |

点「登录并保存 token」→ 点「立即同步」，应该看到
`同步成功：20 个分组 / 176 个站点`。

## 图标点不开 / 显示灰底 A

- **灰底 A** 是 Chrome 给「没有图标」的扩展用的占位图 —— 现在补了 16/48/128 三张
- **点了没反应** 是因为之前没配 `action.default_popup`，点了等于什么都没绑 —— 现在点开是小面板

改完要回 `chrome://extensions` 点一下 ↻ 重新加载，工具栏图标才会换掉。

## 它做了什么

```
chrome.bookmarks.getTree()
  → 转成 profile 里 Bookmarks 文件的节点格式（type/name/url/children）
  → POST {面板}/api/v1/panel/sync/push
      header: token: <面板 token>
      body:   {"roots": {"bookmark_bar": {...}, "other": {...}, "synced": {...}}}
  → 后端复用 panelSync.ParseChromeBookmarks + ApplyGroups 写库
```

合并规则跟「同步与访问」里的设置一致：`merge` 同名分组保留可见性、只换站点；
`replace` 整表重建。改动这个设置也会影响扩展推过来的数据。

## 注意

- **token 会过期**：面板重启或 12 小时后失效，设置页会显示「登录已过期」，重新登录一次即可
- **密码不存**：只用来换一次 token
- 书签多的话第一次推送要几秒，之后只有变化才推
- 面板如果是 http（不是 https），Chrome 扩展仍然可以访问，因为 manifest 里
  `host_permissions` 两个协议都放了
