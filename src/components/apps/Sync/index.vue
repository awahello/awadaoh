<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NButton, NInput, NSelect, NSwitch, useMessage } from 'naive-ui'
import { getSync, runSync, saveSync, testSync } from '@/api/panel/sync'
import { getFrontLock, saveFrontLock } from '@/api/panel/frontLock'

const ms = useMessage()

// ── 谷歌书签同步 ───────────────────────────────
const loading = ref(false)
const saving = ref(false)
const running = ref(false)
const testing = ref(false)

const sync = ref<Panel.SyncSetting>({
  enabled: false,
  path: '',
  interval: 300,
  mode: 'merge',
  lastSync: 0,
  lastResult: '',
})

const info = ref<any>({
  pathDisplay: '',
  resolved: '',
  exists: false,
  candidates: [],
  state: {},
})
const testResult = ref<any>(null)

const intervalOptions = [
  { label: '30 秒', value: 30 },
  { label: '1 分钟', value: 60 },
  { label: '5 分钟', value: 300 },
  { label: '15 分钟', value: 900 },
  { label: '30 分钟', value: 1800 },
  { label: '1 小时', value: 3600 },
  { label: '6 小时', value: 21600 },
]

function load() {
  loading.value = true
  getSync<any>()
    .then(({ data }) => {
      sync.value = {
        enabled: !!data.enabled,
        path: data.path || '',
        interval: data.interval || 300,
        mode: data.mode === 'replace' ? 'replace' : 'merge',
        lastSync: data.lastSync || 0,
        lastResult: data.lastResult || '',
      }
      info.value = data
    })
    .catch(e => ms.error(e?.message || '读取同步配置失败'))
    .finally(() => { loading.value = false })
}

function save() {
  saving.value = true
  saveSync<any>({
    enabled: sync.value.enabled,
    path: sync.value.path || '',
    interval: sync.value.interval || 300,
    mode: sync.value.mode || 'merge',
    lastSync: sync.value.lastSync || 0,
    lastResult: sync.value.lastResult || '',
  })
    .then(({ data }) => {
      ms.success(sync.value.enabled ? '已保存并同步了一次' : '已保存')
      const r = data?.sync
      if (r && r.ok === false)
        ms.error(r.error || '同步失败')
      else if (r && r.sites)
        ms.success(`同步完成：${r.sites} 个站点`)
      load()
    })
    .catch(e => ms.error(e?.message || '保存失败'))
    .finally(() => { saving.value = false })
}

function run() {
  running.value = true
  runSync<any>()
    .then(({ data }) => {
      if (data?.ok === false)
        ms.error(data.error || '同步失败')
      else
        ms.success(data?.skipped ? '文件没变化，跳过' : `同步完成：${data.sites} 个站点`)
      load()
    })
    .catch(e => ms.error(e?.message || '同步失败'))
    .finally(() => { running.value = false })
}

function test() {
  testing.value = true
  testResult.value = null
  testSync<any>(sync.value.path)
    .then(({ data }) => {
      testResult.value = data
      if (data?.ok)
        ms.success(`读到 ${data.sites} 个站点 / ${data.groups} 个分组`)
      else
        ms.error(data?.error || '检测失败')
    })
    .catch(e => ms.error(e?.message || '检测失败'))
    .finally(() => { testing.value = false })
}

function fmtTime(ts?: number) {
  if (!ts)
    return '从未'
  const d = new Date(ts * 1000)
  const p = (n: number) => (n < 10 ? `0${n}` : `${n}`)
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

// ── 前台访问密码 ───────────────────────────────
const frontEnabled = ref(false)
const frontHasPassword = ref(false)
const frontPass = ref('')
const frontSaving = ref(false)

function loadFront() {
  getFrontLock<any>()
    .then(({ data }) => {
      frontEnabled.value = !!data.enabled
    })
    .catch(() => {})
}

function saveFront() {
  if (frontEnabled.value && !frontHasPassword.value && !frontPass.value) {
    ms.error('开启前请先设置访问密码')
    return
  }
  frontSaving.value = true
  saveFrontLock<any>(frontEnabled.value, frontPass.value)
    .then(({ data }) => {
      frontHasPassword.value = !!data?.hasPassword
      frontPass.value = ''
      ms.success(frontEnabled.value ? '已开启，访客打开首页需要先输密码' : '已关闭')
    })
    .catch(e => ms.error(e?.message || '保存失败'))
    .finally(() => { frontSaving.value = false })
}

onMounted(() => {
  load()
  loadFront()
})
</script>

<template>
  <div class="sync-page">
    <div class="tip">
      <b>怎么和 Google 书签同步：</b>Chrome 登录 Google 账号后的书签，最终都会写到本机这个文件里 ——
      <code>…/User Data/Default/Bookmarks</code>（一个 JSON）。Google 同步只是改这个文件。<br>
      所以只要让面板盯着这个文件，它一变就自动重新导入，效果就等于「和收藏夹同步」，不用任何 Google 授权。
    </div>

    <div class="card">
      <h3>同步开关</h3>
      <div class="row">
        <label>自动同步</label>
        <div>
          <NSwitch v-model:value="sync.enabled" />
          <span class="hint" style="margin-left:10px">关闭后只保留手动「立即同步」</span>
        </div>
      </div>
      <div class="row">
        <label>书签文件</label>
        <div>
          <NInput v-model:value="sync.path" placeholder="留空即可，自动检测 Chrome / Edge / Chromium" />
          <div class="hint" style="margin-top:6px">
            Windows 例：<code>C:\Users\YOU\AppData\Local\Google\Chrome\User Data\Default\Bookmarks</code><br>
            macOS 例：<code>~/Library/Application Support/Google/Chrome/Default/Bookmarks</code><br>
            容器里跑的话，要先把宿主机这个目录挂进容器，再填容器内的路径（如 <code>/bookmarks/Bookmarks</code>）。
          </div>
        </div>
      </div>
      <div class="row">
        <label>检查间隔</label>
        <div>
          <NSelect v-model:value="sync.interval" :options="intervalOptions" style="max-width:200px" />
        </div>
      </div>
      <div class="row">
        <label>导入方式</label>
        <div>
          <NSelect
            v-model:value="sync.mode" style="max-width:260px"
            :options="[
              { label: '并入（保留我手动加的分组）', value: 'merge' },
              { label: '整体替换（只留书签里的）', value: 'replace' },
            ]"
          />
          <div class="hint" style="margin-top:6px">
            同名分组会保留原来的可见性设置，只换里面的站点。
          </div>
        </div>
      </div>
      <div class="actions">
        <NButton type="primary" :loading="saving" @click="save">保存</NButton>
        <NButton :loading="testing" @click="test">检测文件</NButton>
        <NButton :loading="running" @click="run">立即同步</NButton>
      </div>
    </div>

    <div class="card">
      <h3>当前状态</h3>
      <table class="kv">
        <tr><td>实际路径</td><td><code>{{ info.pathDisplay || '（未找到）' }}</code></td></tr>
        <tr>
          <td>文件存在</td>
          <td><span :class="info.exists ? 'ok' : 'bad'">{{ info.exists ? '是' : '否' }}</span></td>
        </tr>
        <tr><td>上次同步</td><td>{{ fmtTime(sync.lastSync) }}</td></tr>
        <tr><td>上次结果</td><td>{{ sync.lastResult || '—' }}</td></tr>
      </table>
      <div v-if="testResult" class="hint" style="margin-top:10px">
        <template v-if="testResult.ok">
          检测到 <b>{{ testResult.groups }}</b> 个分组 / <b>{{ testResult.sites }}</b> 个站点：{{ (testResult.names || []).join('、') }}
        </template>
        <template v-else>{{ testResult.error }}</template>
      </div>
      <div v-if="info.candidates && info.candidates.length" class="hint" style="margin-top:10px">
        自动探测会依次尝试：
        <code v-for="c in info.candidates" :key="c" style="margin-right:8px">{{ c }}</code>
      </div>
    </div>

    <div class="card">
      <h3>前台访问密码</h3>
      <div class="row">
        <label>要求先输密码</label>
        <div>
          <NSwitch v-model:value="frontEnabled" />
          <span class="hint" style="margin-left:10px">关掉就是现在这样：打开域名直接是导航</span>
        </div>
      </div>
      <div class="row">
        <label>访问密码</label>
        <div>
          <NInput
            v-model:value="frontPass" type="password" show-password-on="click"
            :placeholder="frontHasPassword ? '已设置，留空不修改' : '至少 4 位'"
          />
        </div>
      </div>
      <div class="hint" style="margin-top:8px">
        打开后访客打开首页先看到一把锁，输对密码才下发分组和站点 ——
        锁着的时候服务端根本不下发内容，不是前端藏起来。
        <br>解锁状态存在访客自己的浏览器里，12 小时有效，服务重启后要重新输。
      </div>
      <div class="actions">
        <NButton type="primary" :loading="frontSaving" @click="saveFront">保存</NButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sync-page {
  padding: 2px 2px 20px;
}

.tip {
  border: 1px solid rgba(255, 255, 255, 0.075);
  border-radius: 13px;
  background: rgba(91, 108, 255, 0.08);
  padding: 12px 14px;
  font-size: 12.5px;
  line-height: 1.7;
  color: #99A3BE;
  margin-bottom: 14px;
}

.tip b { color: #E9EDF7; }

.card {
  border: 1px solid rgba(255, 255, 255, 0.075);
  border-radius: 13px;
  background: #121927;
  padding: 16px;
  margin-bottom: 14px;
}

.card h3 {
  margin: 0 0 14px;
  font-size: 13px;
  font-weight: 700;
  color: #E9EDF7;
  letter-spacing: 0.2px;
}

.row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 12px;
}

.row > label {
  width: 96px;
  flex: 0 0 96px;
  padding-top: 7px;
  font-size: 12.5px;
  color: #99A3BE;
}

.row > div {
  flex: 1;
  min-width: 0;
}

.hint {
  font-size: 11.5px;
  line-height: 1.6;
  color: #65708D;
}

code {
  font-family: var(--mono, monospace);
  font-size: 11px;
  color: #22D3C5;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 4px;
}

table.kv { width: 100%; border-collapse: collapse; font-size: 12.5px; }

table.kv td { padding: 5px 0; color: #99A3BE; }

table.kv td:first-child { width: 96px; color: #65708D; }

.ok { color: #34D399; }

.bad { color: #F87171; }
</style>
