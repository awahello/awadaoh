// 点工具栏图标弹出的面板：看状态、立即同步、进设置

const $ = (id) => document.getElementById(id)

function fmtTime(ts) {
  if (!ts)
    return ''
  const d = new Date(ts)
  const p = (n) => (n < 10 ? '0' + n : '' + n)
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

async function render() {
  const c = await chrome.storage.local.get(['panelUrl', 'token', 'lastResult', 'lastTime'])
  const box = $('state')

  if (!c.panelUrl || !c.token) {
    box.innerHTML = '<span class="bad">还没配置</span><br>'
      + '<span class="t">点下面的「设置」填面板地址，并用后台账号登录一次</span>'
    return
  }

  const last = c.lastResult || '还没同步过'
  const bad = /失败|错误|过期|找不到/.test(last)
  box.innerHTML = `<span class="${bad ? 'bad' : 'ok'}">${last}</span>`
    + (c.lastTime ? `<br><span class="t">${fmtTime(c.lastTime)}</span>` : '')
    + `<br><span class="t">${c.panelUrl}</span>`
}

async function pushNow() {
  $('pushBtn').disabled = true
  $('state').textContent = '推送中…'
  try {
    const res = await chrome.runtime.sendMessage({ type: 'push-now' })
    if (res && res.ok)
      $('state').innerHTML = `<span class="ok">${res.message}</span>`
    else
      $('state').innerHTML = `<span class="bad">失败：${(res && res.error) || '未知错误'}</span>`
  }
  catch (e) {
    $('state').innerHTML = `<span class="bad">失败：${e.message}</span>`
  }
  $('pushBtn').disabled = false
  setTimeout(render, 1200)
}

$('pushBtn').addEventListener('click', pushNow)
$('optBtn').addEventListener('click', () => chrome.runtime.openOptionsPage())
render()
