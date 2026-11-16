// Awadaoh 书签同步 · 后台脚本
//
// 为什么是「读本地书签」而不是「调 Google 接口」：
//   Google 没有公开的 Chrome 书签 API，Chrome 同步走的是私有 protobuf 协议，
//   第三方拿不到。但 Chrome 已经把书签同步到了每台登录同一账号的机器上，
//   所以读本地那份（chrome.bookmarks.getTree()）就等于读到了同步结果。
//
// 触发时机：
//   - 安装 / 浏览器启动
//   - 书签增删改移（防抖 3 秒，一次拖拽只推一次）
//   - 每 30 分钟兜底一次（Chrome 同步是异步的，本地变了才知道）

const ALARM = 'awadaoh-sync'
const DEFAULT_INTERVAL_MIN = 30

let timer = null
let syncing = false

async function getCfg() {
  const c = await chrome.storage.local.get(['panelUrl', 'token', 'intervalMin', 'autoPush', 'lastResult'])
  return {
    panelUrl: (c.panelUrl || '').replace(/\/+$/, ''),
    token: c.token || '',
    intervalMin: c.intervalMin || DEFAULT_INTERVAL_MIN,
    autoPush: c.autoPush !== false,
    lastResult: c.lastResult || '',
  }
}

async function setLastResult(text) {
  await chrome.storage.local.set({ lastResult: text, lastTime: Date.now() })
}

// Chrome 的 getTree() 返回 [root]，root.children 按 id 分：
//   "1" 书签栏 / "2" 其他书签 / "3" 移动设备书签
//
// 注意：getTree() 的节点是 {id, title, url?, children?}，
// 而 profile 里的 Bookmarks 文件是 {type:'url'|'folder', name, url, children}。
// 后端解析的是后者，所以这里必须转一遍 —— 不转的话 type 全是 undefined，
// 后端会一个书签都解析不出来（返回 0 组 0 站，很难查）。
function toProfileNode(n) {
  const isFolder = !n.url
  return {
    type: isFolder ? 'folder' : 'url',
    name: n.title || '',
    url: n.url || '',
    children: isFolder ? (n.children || []).map(toProfileNode) : [],
  }
}

function buildRoots(tree) {
  const root = tree && tree[0]
  const roots = {}
  const map = { 1: 'bookmark_bar', 2: 'other', 3: 'synced' }
  for (const child of (root && root.children) || []) {
    const key = map[child.id]
    if (key)
      roots[key] = toProfileNode(child)
  }
  return { roots }
}

function countSites(node) {
  let n = 0
  for (const ch of (node && node.children) || []) {
    if (ch.type === 'url')
      n++
    else
      n += countSites(ch)
  }
  return n
}

async function pushOnce(manual) {
  if (syncing)
    return { ok: false, error: '正在同步中' }
  syncing = true
  try {
    const cfg = await getCfg()
    if (!cfg.panelUrl || !cfg.token) {
      await setLastResult('还没配置面板地址或账号，点「打开设置」')
      return { ok: false, error: 'not configured' }
    }
    if (!manual && !cfg.autoPush)
      return { ok: false, error: 'auto push disabled' }

    const tree = await chrome.bookmarks.getTree()
    const payload = buildRoots(tree)
    const total = countSites(payload.roots.bookmark_bar) + countSites(payload.roots.other)

    const resp = await fetch(cfg.panelUrl + '/api/v1/panel/sync/push', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // 面板的鉴权就是读这个头
        token: cfg.token,
      },
      body: JSON.stringify(payload),
    })
    const data = await resp.json().catch(() => ({}))

    if (data.code === 0) {
      const msg = `同步成功：${data.data.groups} 个分组 / ${data.data.sites} 个站点`
      await setLastResult(msg)
      return { ok: true, message: msg, total }
    }
    if (data.code === 1000 || resp.status === 401) {
      // token 过期（面板重启或 12 小时到期），提示重新登录
      await setLastResult('登录已过期，请到设置里重新登录')
      return { ok: false, error: 'token expired' }
    }
    await setLastResult(`失败：${data.msg || resp.status}`)
    return { ok: false, error: data.msg || String(resp.status) }
  }
  catch (e) {
    await setLastResult(`网络错误：${e.message}`)
    return { ok: false, error: e.message }
  }
  finally {
    syncing = false
  }
}

// 书签变动 → 防抖 3 秒再推，避免一次批量操作推几十次
function scheduleSync() {
  clearTimeout(timer)
  timer = setTimeout(() => { pushOnce(false) }, 3000)
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(ALARM, { periodInMinutes: DEFAULT_INTERVAL_MIN })
  scheduleSync()
})

chrome.runtime.onStartup.addListener(() => {
  scheduleSync()
})

chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === ALARM)
    pushOnce(false)
})

for (const ev of ['onCreated', 'onRemoved', 'onChanged', 'onMoved', 'onChildrenReordered', 'onImportEnded']) {
  if (chrome.bookmarks[ev])
    chrome.bookmarks[ev].addListener(scheduleSync)
}

// 设置页点「立即同步」走这里
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === 'push-now') {
    pushOnce(true).then(sendResponse)
    return true // 异步回复
  }
  if (msg && msg.type === 'reschedule') {
    const min = Math.max(1, Number(msg.intervalMin) || DEFAULT_INTERVAL_MIN)
    chrome.alarms.clear(ALARM)
    chrome.alarms.create(ALARM, { periodInMinutes: min })
    sendResponse({ ok: true })
    return true
  }
})
