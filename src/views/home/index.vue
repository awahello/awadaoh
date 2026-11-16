<script setup lang="ts">
import { VueDraggable } from 'vue-draggable-plus'
import { NDropdown, NModal, NSkeleton, NSpin, useDialog, useMessage } from 'naive-ui'
import { nextTick, onMounted, ref, computed } from 'vue'
import { AppStarter, EditItem } from './components'
import { SearchBox, SystemMonitor } from '@/components/deskModule'
import { ItemIcon, SvgIcon } from '@/components/common'
import { deletes, getClientEnv, getListByGroupId, saveSort } from '@/api/panel/itemIcon'
import { edit as editGroup, getList as getGroupList } from '@/api/panel/itemIconGroup'

import { setTitle, updateLocalUserInfo } from '@/utils/cmn'
import { useAuthStore, usePanelState } from '@/store'
import { PanelPanelConfigStyleEnum, PanelStateNetworkModeEnum } from '@/enums'
import { VisitMode } from '@/enums/auth'
import { router } from '@/router'
import { t } from '@/locales'

interface ItemGroup extends Panel.ItemIconGroup {
  sortStatus?: boolean
  hoverStatus: boolean
  items?: Panel.ItemInfo[]
}

const ms = useMessage()
const dialog = useDialog()
const panelState = usePanelState()
const authStore = useAuthStore()

const scrollContainerRef = ref<HTMLElement | undefined>(undefined)

const editItemInfoShow = ref<boolean>(false)
const editItemInfoData = ref<Panel.ItemInfo | null>(null)
const windowShow = ref<boolean>(false)
const windowSrc = ref<string>('')
const windowTitle = ref<string>('')

const windowIframeRef = ref(null)
const windowIframeIsLoad = ref<boolean>(false)

const dropdownMenuX = ref(0)
const dropdownMenuY = ref(0)
const dropdownShow = ref(false)
const currentRightSelectItem = ref<Panel.ItemInfo | null>(null)
const currentAddItenIconGroupId = ref<number | undefined>()

const settingModalShow = ref(false)

const items = ref<ItemGroup[]>([])
const filterItems = ref<ItemGroup[]>([])

// 能不能改内容：只有真正登录（不是访客模式）才可以。
// 访客看到的每一处「添加 / 排序 / 可见性 / 右键编辑」都要走这个开关，
// 少一处就会出现「未登录也能在前端点添加、弹出添加项目框」。
const canEdit = computed(() => authStore.visitMode === VisitMode.VISIT_MODE_LOGIN)

// 侧栏左上角那个渐变方块里的字：取站点名首字母，没配就 A
const brandMark = computed(() => (panelState.panelConfig.logoText || 'A').trim().charAt(0).toUpperCase() || 'A')

// 左侧分类筛选：null = 全部
const activeGroupId = ref<number | null>(null)
const totalItemCount = computed(() => filterItems.value.reduce((n, g) => n + (g.items?.length || 0), 0))

// 访问者自己是不是在内网：内网 → 内网地址直接连；外网 → 内网卡提示需要内网环境
const clientIntranet = ref(false)
async function detectClientEnv() {
  try {
    const { code, data } = await getClientEnv()
    if (code !== 0 || !data)
      return
    clientIntranet.value = !!data.intranet
    // 在内网就自动切内网模式，内网地址优先（点开就是直连，不走外网绕一圈）
    if (clientIntranet.value && panelState.networkMode === PanelStateNetworkModeEnum.wan) {
      panelState.setNetworkMode(PanelStateNetworkModeEnum.lan)
      ms.info(t('panelHome.autoLanMode'))
    }
  }
  catch {
    // 探测失败就按外网处理，不影响正常浏览
  }
}

// 分类可见性：0 公开 / 1 登录后可见 / 2 隐藏
const visibilityOptions = [
  { label: t('common.visiblePublic'), key: 0 },
  { label: t('common.visibleLogin'), key: 1 },
  { label: t('common.visibleHidden'), key: 2 },
]
function visibilityIcon(v?: number) {
  if (v === 1)
    return 'mdi:account-lock-outline'
  if (v === 2)
    return 'mdi:eye-off-outline'
  return 'mdi:eye-outline'
}
function visibilityLabel(v?: number) {
  if (v === 1)
    return t('common.visibleLogin')
  if (v === 2)
    return t('common.visibleHidden')
  return t('common.visiblePublic')
}
async function handleSetGroupVisible(group: ItemGroup, visible: number) {
  try {
    await editGroup({ ...group, visible })
    group.visible = visible
    ms.success(t('common.saveSuccess'))
  }
  catch (e: any) {
    ms.error(e?.message || t('common.saveFail'))
  }
}

function openPage(openMethod: number, url: string, title?: string) {
  switch (openMethod) {
    case 1:
      window.location.href = url
      break
    case 2:
      window.open(url)
      break
    case 3:
      windowShow.value = true
      windowSrc.value = url
      windowTitle.value = title || url
      windowIframeIsLoad.value = true
      break

    default:
      break
  }
}

function jumpTo(item: Panel.ItemInfo) {
  let jumpUrl = ''
  if (item)
    jumpUrl = (panelState.networkMode === PanelStateNetworkModeEnum.lan ? item.lanUrl : item.url) as string
  if (item.lanUrl === '')
    jumpUrl = item.url

  openPage(item.openMethod, jumpUrl, item.title)
}

function handleItemClick(itemGroupIndex: number, item: Panel.ItemInfo) {
  if (items.value[itemGroupIndex] && items.value[itemGroupIndex].sortStatus) {
    handleEditItem(item)
    return
  }

  // 当前不在内网、地址又被收起来了：明确告诉它要什么环境，别点出一个死页
  if (item.masked) {
    ms.warning(t('panelHome.needIntranet'))
    return
  }

  // 登录用户能看到内网地址，但人可能在外网：先问一句，别让他以为站点挂了
  if (item.private && !clientIntranet.value) {
    dialog.warning({
      title: t('common.warning'),
      content: t('panelHome.needIntranetConfirm'),
      positiveText: t('common.confirm'),
      negativeText: t('common.cancel'),
      onPositiveClick: () => jumpTo(item),
    })
    return
  }

  jumpTo(item)
}

function handWindowIframeIdLoad(payload: Event) {
  windowIframeIsLoad.value = false
}

function getList() {
  // 获取组数据
  getGroupList<Common.ListResponse<ItemGroup[]>>().then(({ code, data }) => {
    // 访客模式没配公开账号时后端返回 1001，data 是空的 —— 走空列表，别抛 TypeError
    if (code !== 0 || !data || !data.list) {
      items.value = []
      filterItems.value = []
      return
    }
    items.value = data.list
    for (let i = 0; i < data.list.length; i++) {
      const element = data.list[i]
      if (element.id)
        updateItemIconGroupByNet(i, element.id)
    }
    filterItems.value = items.value
    // console.log(items)
  }).catch(() => {
    items.value = []
    filterItems.value = []
  })
}

// 从后端获取组下面的图标
function updateItemIconGroupByNet(itemIconGroupIndex: number, itemIconGroupId: number) {
  getListByGroupId<Common.ListResponse<Panel.ItemInfo[]>>(itemIconGroupId).then((res) => {
    if (res.code === 0)
      items.value[itemIconGroupIndex].items = res.data.list
  })
}

function handleRightMenuSelect(key: string | number) {
  dropdownShow.value = false
  if (key === 'needIntranet') {
    ms.warning(t('panelHome.needIntranet'))
    return
  }
  let jumpUrl = panelState.networkMode === PanelStateNetworkModeEnum.lan ? currentRightSelectItem.value?.lanUrl : currentRightSelectItem.value?.url
  if (currentRightSelectItem.value?.lanUrl === '')
    jumpUrl = currentRightSelectItem.value.url
  switch (key) {
    case 'newWindows':
      window.open(jumpUrl)
      break
    case 'openWanUrl':
      if (currentRightSelectItem.value)
        openPage(currentRightSelectItem.value?.openMethod, currentRightSelectItem.value?.url, currentRightSelectItem.value?.title)
      break
    case 'openLanUrl':
      if (currentRightSelectItem.value && currentRightSelectItem.value.lanUrl)
        openPage(currentRightSelectItem.value?.openMethod, currentRightSelectItem.value.lanUrl, currentRightSelectItem.value?.title)
      break
    case 'edit':
      // 这里有个奇怪的问题，如果不使用{...}的方式 父组件的值会同步修改 标记一下
      handleEditItem({ ...currentRightSelectItem.value } as Panel.ItemInfo)
      break
    case 'delete':
      dialog.warning({
        title: t('common.warning'),
        content: t('common.deleteConfirmByName', { name: currentRightSelectItem.value?.title }),
        positiveText: t('common.confirm'),
        negativeText: t('common.cancel'),
        onPositiveClick: () => {
          deletes([currentRightSelectItem.value?.id as number]).then(({ code, msg }) => {
            if (code === 0) {
              ms.success(t('common.deleteSuccess'))
              getList()
            }
            else {
              ms.error(`${t('common.deleteFail')}:${msg}`)
            }
          })
        },
      })

      break
    default:
      break
  }
}

function handleContextMenu(e: MouseEvent, itemGroupIndex: number, item: Panel.ItemInfo) {
  if (items.value[itemGroupIndex] && items.value[itemGroupIndex].sortStatus)
    return

  e.preventDefault()
  currentRightSelectItem.value = item
  dropdownShow.value = false
  nextTick().then(() => {
    dropdownShow.value = true
    dropdownMenuX.value = e.clientX
    dropdownMenuY.value = e.clientY
  })
}

function onClickoutside() {
  // message.info('clickoutside')
  dropdownShow.value = false
}

function handleEditSuccess(item: Panel.ItemInfo) {
  getList()
}

function handleChangeNetwork(mode: PanelStateNetworkModeEnum) {
  panelState.setNetworkMode(mode)
  if (mode === PanelStateNetworkModeEnum.lan)
    ms.success(t('panelHome.changeToLanModelSuccess'))

  else
    ms.success(t('panelHome.changeToWanModelSuccess'))
}

// 结束拖拽
// function handleEndDrag(event: any, itemIconGroup: Panel.ItemIconGroup) {
//   // console.log(event)
//   // console.log(items.value)
// }

function handleSaveSort(itemGroup: ItemGroup) {
  const saveItems: Common.SortItemRequest[] = []
  if (itemGroup.items) {
    for (let i = 0; i < itemGroup.items.length; i++) {
      const element = itemGroup.items[i]
      saveItems.push({
        id: element.id as number,
        sort: i + 1,
      })
    }

    saveSort({ itemIconGroupId: itemGroup.id as number, sortItems: saveItems }).then(({ code, msg }) => {
      if (code === 0) {
        ms.success(t('common.saveSuccess'))
        itemGroup.sortStatus = false
      }
      else {
        ms.error(`${t('common.saveFail')}:${msg}`)
      }
    })
  }
}

function getDropdownMenuOptions() {
  const dropdownMenuOptions = [
    {
      label: t('iconItem.newWindowOpen'),
      key: 'newWindows',
    },

  ]

  // 不在内网、地址被收起来的卡：不给打开，只说明为什么打不开
  if (currentRightSelectItem.value?.masked) {
    dropdownMenuOptions.length = 0
    dropdownMenuOptions.push({
      label: t('panelHome.needIntranet'),
      key: 'needIntranet',
    })
  }
  else {
    if (currentRightSelectItem.value?.lanUrl && panelState.networkMode === PanelStateNetworkModeEnum.wan) {
      dropdownMenuOptions.push({
        label: t('panelHome.openLanUrl'),
        key: 'openLanUrl',
      })
    }

    if (currentRightSelectItem.value?.lanUrl && panelState.networkMode === PanelStateNetworkModeEnum.lan) {
      dropdownMenuOptions.push({
        label: t('panelHome.openWanUrl'),
        key: 'openWanUrl',
      })
    }
  }

  if (authStore.visitMode === VisitMode.VISIT_MODE_LOGIN) {
    dropdownMenuOptions.push({
      label: t('common.edit'),
      key: 'edit',
    }, {
      label: t('common.delete'),
      key: 'delete',
    })
  }

  return dropdownMenuOptions
}

onMounted(() => {
  // 更新用户信息
  updateLocalUserInfo()
  getList()

  // 先问一句「我在不在内网」，再决定内网卡是能直连还是提示需要内网
  detectClientEnv()

  // 更新同步云端配置
  panelState.updatePanelConfigByCloud()

  // 设置标题
  if (panelState.panelConfig.logoText)
    setTitle(panelState.panelConfig.logoText)
})

// 前端搜索过滤
function itemFrontEndSearch(keyword?: string) {
  keyword = keyword?.trim()
  if (keyword !== '' && panelState.panelConfig.searchBoxSearchIcon) {
    const filteredData = ref<ItemGroup[]>([])
    for (let i = 0; i < items.value.length; i++) {
      const element = items.value[i].items?.filter((item: Panel.ItemInfo) => {
        return (
          item.title.toLowerCase().includes(keyword?.toLowerCase() ?? '')
          || item.url.toLowerCase().includes(keyword?.toLowerCase() ?? '')
          || item.description?.toLowerCase().includes(keyword?.toLowerCase() ?? '')
        )
      })
      if (element && element.length > 0)
        filteredData.value.push({ items: element, hoverStatus: false })
    }
    filterItems.value = filteredData.value
  }
  else {
    filterItems.value = items.value
  }
}

function handleSetHoverStatus(groupIndex: number, hoverStatus: boolean) {
  if (items.value[groupIndex])
    items.value[groupIndex].hoverStatus = hoverStatus
}

function handleSetSortStatus(groupIndex: number, sortStatus: boolean) {
  if (items.value[groupIndex])
    items.value[groupIndex].sortStatus = sortStatus

  // 并未保存排序重新更新数据
  if (!sortStatus) {
    // 单独更新组
    if (items.value[groupIndex] && items.value[groupIndex].id)
      updateItemIconGroupByNet(groupIndex, items.value[groupIndex].id as number)
  }
}

function handleEditItem(item: Panel.ItemInfo) {
  if (!canEdit.value)
    return
  editItemInfoData.value = item
  editItemInfoShow.value = true
  currentAddItenIconGroupId.value = undefined
}

function handleAddItem(itemIconGroupId?: number) {
  if (!canEdit.value)
    return
  editItemInfoData.value = null
  editItemInfoShow.value = true
  if (itemIconGroupId)
    currentAddItenIconGroupId.value = itemIconGroupId
}
</script>


<template>
  <div class="nav-shell">
    <!-- 壁纸：面板老配置里有图就用，没有就是 nav 那套纯深色 + 环境光 -->
    <div
      v-if="panelState.panelConfig.backgroundImageSrc"
      class="wallpaper" :style="{
        filter: `blur(${panelState.panelConfig.backgroundBlur}px)`,
        background: `url(${panelState.panelConfig.backgroundImageSrc}) no-repeat`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }"
    />
    <div
      v-if="panelState.panelConfig.backgroundImageSrc"
      class="wallpaper-mask" :style="{ backgroundColor: `rgba(0,0,0,${panelState.panelConfig.backgroundMaskNumber})` }"
    />

    <!-- ── 左侧分类栏 ─────────────────────────────────── -->
    <aside class="side">
      <div class="brand">
        <div class="brand-mark">{{ brandMark }}</div>
        <div class="brand-text">
          <div class="brand-name">{{ panelState.panelConfig.logoText || 'Awadaoh' }}</div>
          <div class="brand-sub">{{ t('panelHome.selfHosted') }}</div>
        </div>
      </div>

      <nav class="cats">
        <button class="cat" :class="{ 'is-on': activeGroupId === null }" @click="activeGroupId = null">
          <span class="cat-name">{{ t('common.all') }}</span>
          <span class="cat-num">{{ totalItemCount }}</span>
        </button>
        <button
          v-for="g in filterItems" :key="g.id" class="cat"
          :class="{ 'is-on': activeGroupId === g.id }" :title="g.title"
          @click="activeGroupId = activeGroupId === g.id ? null : (g.id ?? null)"
        >
          <span class="cat-name">{{ g.title }}</span>
          <span class="cat-num">{{ (g.items || []).length }}</span>
        </button>
      </nav>

      <div class="side-foot">
        <span class="stat"><i class="dot" />{{ totalItemCount }} {{ t('panelHome.sites') }}</span>
        <button v-if="canEdit" class="icon-btn" :title="t('common.style')" @click="settingModalShow = true">
          <SvgIcon icon="majesticons-applications" />
        </button>
      </div>
    </aside>

    <!-- ── 右侧主区 ──────────────────────────────────── -->
    <main class="main">
      <header class="top">
        <div v-if="panelState.panelConfig.searchBoxShow" class="search-wrap">
          <SearchBox @itemSearch="itemFrontEndSearch" />
        </div>
        <div class="top-actions">
          <button
            v-if="panelState.networkMode === PanelStateNetworkModeEnum.lan && panelState.panelConfig.netModeChangeButtonShow"
            class="icon-btn" :title="t('panelHome.changeToWanModel')"
            @click="handleChangeNetwork(PanelStateNetworkModeEnum.wan)"
          >
            <SvgIcon icon="material-symbols:lan-outline-rounded" />
          </button>
          <button
            v-if="panelState.networkMode === PanelStateNetworkModeEnum.wan && panelState.panelConfig.netModeChangeButtonShow"
            class="icon-btn" :title="t('panelHome.changeToLanModel')"
            @click="handleChangeNetwork(PanelStateNetworkModeEnum.lan)"
          >
            <SvgIcon icon="mdi:wan" />
          </button>
          <button v-if="canEdit" class="icon-btn" :title="t('common.style')" @click="settingModalShow = true">
            <SvgIcon icon="majesticons-applications" />
          </button>
          <button
            v-if="authStore.visitMode === VisitMode.VISIT_MODE_PUBLIC"
            class="icon-btn" :title="t('panelHome.goToLogin')" @click="router.push('/login')"
          >
            <SvgIcon icon="material-symbols:account-circle" />
          </button>
        </div>
      </header>

      <div ref="scrollContainerRef" class="scroll">
        <div class="content">
          <!-- 系统状态：跟分组一个样式，别单独搞一块浮在中间 -->
          <section
            v-if="panelState.panelConfig.systemMonitorShow
              && ((panelState.panelConfig.systemMonitorPublicVisitModeShow && authStore.visitMode === VisitMode.VISIT_MODE_PUBLIC)
                || authStore.visitMode === VisitMode.VISIT_MODE_LOGIN)"
            class="group is-monitor"
          >
            <SystemMonitor :allow-edit="canEdit" :show-title="true" />
          </section>

          <!-- 分组纵向排列 -->
          <template v-for="(itemGroup, itemGroupIndex) in filterItems" :key="itemGroup.id || itemGroupIndex">
            <section
              v-if="activeGroupId === null || activeGroupId === itemGroup.id"
              class="group"
              :class="{ 'is-sorting': itemGroup.sortStatus }"
              @mouseenter="handleSetHoverStatus(itemGroupIndex, true)"
              @mouseleave="handleSetHoverStatus(itemGroupIndex, false)"
            >
              <div class="group-head">
                <span class="bar" />
                <span class="group-name">{{ itemGroup.title }}</span>
                <span class="group-num">{{ (itemGroup.items || []).length }}</span>
                <div
                  v-if="canEdit"
                  class="group-tools" :class="itemGroup.hoverStatus || itemGroup.sortStatus ? 'is-on' : ''"
                >
                  <button :title="t('common.add')" @click="handleAddItem(itemGroup.id)">
                    <SvgIcon icon="typcn:plus" />
                  </button>
                  <button :title="t('common.sort')" @click="handleSetSortStatus(itemGroupIndex, !itemGroup.sortStatus)">
                    <SvgIcon icon="ri:drag-drop-line" />
                  </button>
                  <NDropdown
                    trigger="click" :options="visibilityOptions"
                    @select="(v: any) => handleSetGroupVisible(itemGroup, Number(v))"
                  >
                    <button :title="`${t('common.groupVisible')}：${visibilityLabel(itemGroup.visible)}`">
                      <SvgIcon :icon="visibilityIcon(itemGroup.visible)" />
                    </button>
                  </NDropdown>
                </div>
              </div>

              <div v-if="itemGroup.items">
              <VueDraggable
                v-model="itemGroup.items" item-key="sort" :animation="300"
                class="grid" :class="{ 'is-info': panelState.panelConfig.iconStyle === PanelPanelConfigStyleEnum.info }"
                filter=".not-drag"
                :disabled="!itemGroup.sortStatus"
              >
                <div
                  v-for="item, index in itemGroup.items" :key="index"
                  class="site" :class="{ 'is-locked': item.masked, 'is-drag': itemGroup.sortStatus }"
                  :title="item.masked ? t('panelHome.needIntranet') : item.description"
                  @click="handleItemClick(itemGroupIndex, item)"
                  @contextmenu="(e) => handleContextMenu(e, itemGroupIndex, item)"
                >
                  <div class="site-ico">
                    <ItemIcon
                      v-if="!item.masked" :item-icon="item.icon" :size="30"
                      force-background="transparent"
                    />
                    <span v-else class="site-lock">🔒</span>
                  </div>
                  <div class="site-name">{{ item.title }}</div>
                  <div v-if="panelState.panelConfig.iconStyle === PanelPanelConfigStyleEnum.info && !panelState.panelConfig.iconTextInfoHideDescription" class="site-desc">
                    {{ item.description }}
                  </div>
                </div>

                <!-- 空分组的「添加」占位卡：只有登录后才有，访客看到的是空分组 -->
                <div v-if="itemGroup.items.length === 0 && canEdit" class="not-drag site is-add" @click="handleAddItem(itemGroup.id)">
                  <div class="site-ico"><SvgIcon icon="typcn:plus" /></div>
                  <div class="site-name">{{ t('common.add') }}</div>
                </div>
              </VueDraggable>
              </div>

              <div v-if="itemGroup.sortStatus" class="sort-bar">
                <button class="btn-save" @click="handleSaveSort(itemGroup)">
                  <SvgIcon icon="material-symbols:save" />
                  {{ t('common.saveSort') }}
                </button>
              </div>
            </section>
          </template>

          <div v-if="filterItems.length === 0" class="empty">
            {{ t('common.noData') }}
          </div>
        </div>

        <div class="foot" v-html="panelState.panelConfig.footerHtml" />
      </div>
    </main>

    <!-- 右键菜单 -->
    <NDropdown
      placement="bottom-start" trigger="manual" :x="dropdownMenuX" :y="dropdownMenuY"
      :options="getDropdownMenuOptions()" :show="dropdownShow" :on-clickoutside="onClickoutside" @select="handleRightMenuSelect"
    />

    <AppStarter v-model:visible="settingModalShow" />

    <EditItem v-model:visible="editItemInfoShow" :item-info="editItemInfoData" :item-group-id="currentAddItenIconGroupId" @done="handleEditSuccess" />

    <!-- 弹窗 -->
    <NModal
      v-model:show="windowShow" :mask-closable="false" preset="card"
      style="max-width: 1000px;height: 600px;border-radius: 1rem;" :bordered="true" size="small" role="dialog"
      aria-modal="true"
    >
      <template #header>
        <div class="flex items-center">
          <span class="mr-[20px]">
            {{ windowTitle }}
          </span>

          <NSpin v-if="windowIframeIsLoad" size="small" />
        </div>
      </template>
      <div class="w-full h-full rounded-2xl overflow-hidden border dark:border-zinc-700">
        <div v-if="windowIframeIsLoad" class="flex flex-col p-5">
          <NSkeleton height="50px" width="100%" class="rounded-lg" />
          <NSkeleton height="180px" width="100%" class="mt-[20px] rounded-lg" />
          <NSkeleton height="180px" width="100%" class="mt-[20px] rounded-lg" />
        </div>
        <iframe
          v-show="!windowIframeIsLoad" id="windowIframeId" ref="windowIframeRef" :src="windowSrc"
          class="w-full h-full" frameborder="0" @load="handWindowIframeIdLoad"
        />
      </div>
    </NModal>
  </div>
</template>

<style>
body,
html {
  overflow: hidden;
  background-color: #090D16;
}
</style>

<style scoped>
/* ══ 面板首页 = nav 的视觉语言 ══════════════════════════════════
   左边固定分类栏、右边顶部搜索 + 分组网格，尺寸和颜色全部照
   nav/static/index.html 抄，两边看起来才是同一个产品。 */

.nav-shell {
  --bg: #090D16;
  --side: rgba(13, 18, 30, 0.92);
  --panel: #121927;
  --panel-2: #182033;
  --panel-3: #1E2740;
  --line: rgba(255, 255, 255, 0.075);
  --line-strong: rgba(255, 255, 255, 0.14);
  --text: #E9EDF7;
  --text-2: #99A3BE;
  --text-3: #65708D;
  --brand: #5B6CFF;
  --brand-hi: #7C8AFF;
  --accent: #22D3C5;
  --r: 13px;
  --r-sm: 9px;
  --r-lg: 18px;
  --side-w: 236px;
  --shadow-1: 0 2px 10px rgba(3, 6, 16, 0.45);
  --shadow-2: 0 14px 34px rgba(3, 6, 16, 0.55);
  --shadow-brand: 0 12px 28px rgba(91, 108, 255, 0.35);

  position: relative;
  display: flex;
  width: 100%;
  height: 100%;
  color: var(--text);
  font-family: "Inter", "PingFang SC", "HarmonyOS Sans SC", "Microsoft YaHei",
    -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 14px;
  user-select: none;
  background:
    radial-gradient(900px 520px at 8% -12%, rgba(91, 108, 255, 0.30), transparent 62%),
    radial-gradient(760px 480px at 102% 108%, rgba(34, 211, 197, 0.18), transparent 62%),
    var(--bg);
}

/* 壁纸层（面板老配置） */
.wallpaper {
  position: absolute;
  inset: 0;
  overflow: hidden;
  transform: scale(1.05);
  z-index: 0;
}

.wallpaper-mask {
  position: absolute;
  inset: 0;
  z-index: 0;
}

/* ── 左侧分类栏 ─────────────────────────────────────── */
.side {
  position: relative;
  z-index: 3;
  width: var(--side-w);
  flex: 0 0 var(--side-w);
  display: flex;
  flex-direction: column;
  background: var(--side);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  border-right: 1px solid var(--line);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 18px 14px;
  flex-shrink: 0;
}

.brand-mark {
  width: 34px;
  height: 34px;
  border-radius: 11px;
  background: linear-gradient(135deg, var(--brand), var(--accent));
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 16px;
  font-weight: 800;
  box-shadow: 0 6px 16px rgba(91, 108, 255, 0.4);
  flex-shrink: 0;
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.2px;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brand-sub {
  margin-top: 3px;
  font-size: 10.5px;
  letter-spacing: 0.6px;
  color: var(--text-3);
  text-transform: uppercase;
}

.cats {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cat {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text-2);
  font-size: 13px;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.cat:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text);
}

.cat.is-on {
  background: rgba(91, 108, 255, 0.16);
  color: var(--text);
  font-weight: 600;
}

.cat-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cat-num {
  flex: 0 0 auto;
  font-size: 11px;
  color: var(--text-3);
  font-variant-numeric: tabular-nums;
}

.cat.is-on .cat-num {
  color: var(--brand-hi);
}

.side-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px 14px;
  border-top: 1px solid var(--line);
  flex-shrink: 0;
}

.stat {
  display: flex;
  align-items: center;
  gap: 7px;
  flex: 1;
  min-width: 0;
  font-size: 11.5px;
  color: var(--text-3);
  overflow: hidden;
  white-space: nowrap;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent);
  flex-shrink: 0;
}

/* ── 主区 ──────────────────────────────────────────── */
.main {
  position: relative;
  z-index: 2;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.top {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 22px;
  flex-shrink: 0;
}

.search-wrap {
  flex: 1;
  max-width: 560px;
  min-width: 0;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.icon-btn {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--text-2);
  font-size: 17px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}

.icon-btn:hover {
  background: var(--panel-2);
  color: var(--text);
  border-color: var(--line-strong);
}

.scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.content {
  padding: 4px 22px 8px;
}

/* ── 分组 ──────────────────────────────────────────── */
.group {
  position: relative;
  margin-bottom: 26px;
}

.group-head {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 13px;
}

.bar {
  width: 3px;
  height: 15px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--brand), var(--accent));
  flex-shrink: 0;
}

.group-name {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.2px;
}

.group-num {
  font-size: 11.5px;
  color: var(--text-3);
  font-variant-numeric: tabular-nums;
}

.group-tools {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}

.group-tools.is-on {
  opacity: 1;
}

.group-tools button {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--text-3);
  font-size: 15px;
  cursor: pointer;
}

.group-tools button:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text);
}

/* 排序中的分组描个边，跟拖拽状态对应 */
.group.is-sorting {
  padding: 10px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--r-lg);
  background: rgba(0, 0, 0, 0.18);
}

/* ── 站点网格 ──────────────────────────────────────── */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 12px;
}

.site {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 9px;
  padding: 16px 8px 12px;
  border-radius: var(--r);
  border: 1px solid transparent;
  background: var(--panel);
  box-shadow: var(--shadow-1);
  cursor: pointer;
  transition: transform 0.18s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.18s, border-color 0.18s, background 0.18s;
  overflow: hidden;
}

.site:hover {
  transform: translateY(-4px);
  background: var(--panel-2);
  border-color: rgba(91, 108, 255, 0.38);
  box-shadow: var(--shadow-brand);
}

.site.is-drag {
  cursor: move;
}

.site-ico {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  overflow: hidden;
  background: transparent;
  flex-shrink: 0;
  color: var(--text-3);
  font-size: 20px;
}

.site-name {
  max-width: 100%;
  font-size: 12.5px;
  font-weight: 500;
  text-align: center;
  line-height: 1.35;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-word;
}

.site:hover .site-name {
  color: var(--text);
}

/* 内网地址被收起来的卡 */
.site.is-locked {
  cursor: default;
  border: 1px dashed var(--line-strong);
  box-shadow: none;
  background: var(--panel);
}

.site.is-locked:hover {
  transform: none;
  border-color: var(--line-strong);
  box-shadow: none;
  background: var(--panel);
}

.site-lock {
  font-size: 18px;
  opacity: 0.65;
}

.site.is-add {
  border: 1px dashed var(--line-strong);
  background: transparent;
  box-shadow: none;
}

.site.is-add:hover {
  border-color: var(--brand);
  background: rgba(91, 108, 255, 0.08);
}

/* 详情风格：宽卡，图标在左、标题描述在右 */
.grid.is-info {
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
}

.grid.is-info .site {
  flex-direction: row;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  text-align: left;
}

.grid.is-info .site-name {
  text-align: left;
  -webkit-line-clamp: 1;
  color: var(--text);
  font-weight: 600;
}

.site-desc {
  font-size: 11.5px;
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

/* 系统状态：组件内部自带 mt-50px 和白色标题，压成跟分组一致 */
.group.is-monitor :deep(.system-monitor > div) {
  margin-top: 0 !important;
}

.group.is-monitor :deep(.system-monitor-header) {
  margin-bottom: 13px !important;
  margin-left: 0 !important;
  font-size: 15px !important;
  letter-spacing: 0.2px;
}

.group.is-monitor :deep(.system-monitor-header .text-shadow) {
  text-shadow: none;
}

/* 保存排序 */
.sort-bar {
  display: flex;
  margin-top: 12px;
}

.btn-save {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 14px;
  border: 0;
  border-radius: var(--r-sm);
  background: var(--brand);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
}

.btn-save:hover {
  background: var(--brand-hi);
}

.empty {
  padding: 60px 0;
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
}

.foot {
  padding: 10px 22px 26px;
  font-size: 12px;
  color: var(--text-3);
  text-align: center;
}

.foot :deep(a) {
  color: var(--text-3);
}

/* 搜索框照 nav 的样子收一下 */
.search-wrap :deep(.search-container) {
  height: 44px;
  padding: 0 12px;
  border-radius: 12px;
  border: 1px solid var(--line-strong);
  background: var(--panel) !important;
  box-shadow: none;
  transition: border-color 0.18s, box-shadow 0.18s;
}

.search-wrap :deep(.search-container:hover),
.search-wrap :deep(.search-container.focused) {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(91, 108, 255, 0.18);
}

.search-wrap :deep(input) {
  height: 42px;
  font-size: 13.5px;
  color: var(--text);
}

.search-wrap :deep(input::placeholder) {
  color: var(--text-3);
}

.search-wrap :deep(.search-box-btn-engine),
.search-wrap :deep(.search-box-btn-search),
.search-wrap :deep(.search-box-btn-clear) {
  color: var(--text-3);
}

/* ── 窄屏：侧栏横过来当一排标签 ────────────────────── */
@media (max-width: 900px) {
  .nav-shell {
    flex-direction: column;
  }

  .side {
    width: 100%;
    flex: 0 0 auto;
    flex-direction: row;
    align-items: center;
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }

  .brand {
    padding: 10px 12px;
  }

  .brand-text {
    display: none;
  }

  .cats {
    flex-direction: row;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 8px;
    gap: 4px;
  }

  .cat {
    width: auto;
    white-space: nowrap;
    padding: 6px 10px;
  }

  .cat-num {
    display: none;
  }

  .side-foot {
    border-top: 0;
    padding: 8px 12px;
  }

  .stat {
    display: none;
  }

  .top {
    padding: 10px 14px;
  }

  .content {
    padding: 4px 14px 8px;
  }

  .grid {
    grid-template-columns: repeat(auto-fill, minmax(84px, 1fr));
    gap: 10px;
  }
}
</style>
