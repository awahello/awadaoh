// 设置页逻辑：存面板地址、换 token、手动同步

const $ = (id) => document.getElementById(id)

function setState(el, text, bad) {
  el.textContent = text
  el.className = bad ? 'state bad' : 'state ok'
}

async function load() {
  const c = await chrome.storage.local.get(['panelUrl', 'token', 'intervalMin', 'autoPush', 'lastResult', 'lastTime'])
  $('panelUrl').value = c.panelUrl || ''
  $('intervalMin').value = c.intervalMin || 30
  $('autoPush').checked = c.autoPush !== false
  if (c.token)
    setState($('loginState'), '已保存 token', false)
  if (c.lastResult) {
    const t = c.lastTime ? new Date(c.lastTime).toLocaleString() : ''
    $('lastResult').textContent = `${t}  ${c.lastResult}`
  }
}

async function save() {
  const url = ($('panelUrl').value || '').trim().replace(/\/+$/, '')
  const intervalMin = Math.max(1, Number($('intervalMin').value) || 30)
  await chrome.storage.local.set({ panelUrl: url, intervalMin, autoPush: $('autoPush').checked })
  chrome.runtime.sendMessage({ type: 'reschedule', intervalMin })
  $('lastResult').textContent = '设置已保存'
}

async function login() {
  const url = ($('panelUrl').value || '').trim().replace(/\/+$/, '')
  const username = ($('username').value || '').trim()
  const password = $('password').value
  if (!url) {
    setState($('loginState'), '先填面板地址', true)
    return
  }
  if (!username || !password) {
    setState($('loginState'), '账号密码都要填', true)
    return
  }
  $('loginBtn').disabled = true
  setState($('loginState'), '登录中…', false)
  try {
    const resp = await fetch(url + '/api/v1/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    const data = await resp.json().catch(() => ({}))
    if (data.code === 0 && data.data && data.data.token) {
      await chrome.storage.local.set({ panelUrl: url, token: data.data.token })
      $('password').value = ''
      setState($('loginState'), '登录成功，token 已保存', false)
    }
    else {
      setState($('loginState'), data.msg || '登录失败', true)
    }
  }
  catch (e) {
    setState($('loginState'), '请求失败：' + e.message, true)
  }
  finally {
    $('loginBtn').disabled = false
  }
}

async function pushNow() {
  $('pushBtn').disabled = true
  $('lastResult').textContent = '推送中…'
  const res = await chrome.runtime.sendMessage({ type: 'push-now' })
  $('pushBtn').disabled = false
  if (res && res.ok)
    $('lastResult').textContent = res.message
  else
    $('lastResult').textContent = '失败：' + ((res && res.error) || '未知错误')
}

$('loginBtn').addEventListener('click', login)
$('pushBtn').addEventListener('click', pushNow)
$('saveBtn').addEventListener('click', save)
load()
