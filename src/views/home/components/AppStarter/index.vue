<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useAuthStore } from '@/store'
import { AppLoader, RoundCardModal, SvgIcon } from '@/components/common'
import { t } from '@/locales'

interface App {
  name: string
  componentName: string
  icon: string
  auth?: number
}
const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', visible: boolean): void
}>()

const componentName = ref('UserInfo')
const collapsed = ref(false)
const screenWidth = ref(0)
const isSmallScreen = ref(false)
const defaultTitle = t('appLauncher.title')
const title = ref('')

const apps = ref<App[]>([
  {
    name: t('apps.userInfo.appName'),
    componentName: 'UserInfo',
    icon: 'material-symbols-person-edit-outline-rounded',
  },
  {
    name: t('apps.baseSettings.appName'),
    componentName: 'Style',
    icon: 'ion-color-palette-outline',
  },
  {
    name: t('apps.itemGroupManage.appName'),
    componentName: 'ItemGroupManage',
    icon: 'material-symbols-ad-group-outline-rounded',
  },
  {
    name: t('apps.uploadsFileManager.appName'),
    componentName: 'UploadFileManager',
    icon: 'tabler:file-upload',
  },
  {
    name: t('apps.exportImport.appName'),
    componentName: 'ImportExport',
    icon: 'icon-park-outline-import-and-export',
  },
  {
    name: t('apps.sync.appName'),
    componentName: 'Sync',
    icon: 'material-symbols-sync-rounded',
  },
  {
    name: t('apps.about.appName'),
    componentName: 'About',
    icon: 'lucide-info',
  },
])

const authStore = useAuthStore()

const show = computed({
  get: () => props.visible,
  set: (visible: boolean) => {
    emit('update:visible', visible)
  },
})

function handleClickApp(item: App) {
  componentName.value = item.componentName
  // 小屏时侧栏是盖在内容上的，点完要收起来，否则内容被挡住
  if (isSmallScreen.value)
    collapsed.value = true
}

function getScreenWidth() {
  return window.innerWidth
}

function handleResize() {
  screenWidth.value = getScreenWidth()
  if (screenWidth.value < 640) {
    collapsed.value = true
    isSmallScreen.value = true
  }
  else {
    collapsed.value = false
    isSmallScreen.value = false
  }
}

onMounted(() => {
  const adminApp: App = {
    name: t('adminSettingUsers.appName'),
    componentName: 'Users',
    icon: 'lucide-users',
    auth: 1,
  }
  // 初始化
  if (authStore.userInfo?.role === 1)
    apps.value.push(adminApp)

  window.addEventListener('resize', handleResize)
  handleResize()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div>
    <RoundCardModal
      v-model:show="show"
      class="awadaoh-admin"
      style="max-width: 940px;"
      size="small"
    >
      <template #header>
        <div class="admin-head">
          <div class="admin-mark">A</div>
          <div class="admin-title">
            {{ title === '' ? defaultTitle : title }}
          </div>
          <button class="admin-collapse" :title="collapsed ? '展开侧栏' : '收起侧栏'" @click="collapsed = !collapsed">
            <SvgIcon :icon="collapsed ? 'tabler-layout-sidebar-right-collapse-filled' : 'tabler-layout-sidebar-left-collapse-filled'" />
          </button>
        </div>
      </template>

      <div class="admin-shell">
        <aside class="admin-side" :class="{ 'is-collapsed': collapsed }">
          <button
            v-for="item in apps"
            :key="item.componentName"
            class="admin-nav"
            :class="{ 'is-on': componentName === item.componentName }"
            @click="handleClickApp(item)"
          >
            <SvgIcon :icon="item.icon" class="admin-nav-ico" />
            <span>{{ item.name }}</span>
          </button>
        </aside>

        <section class="admin-body" :class="{ 'is-wide': collapsed }">
          <AppLoader :component-name="componentName" class="h-full" />
        </section>
      </div>
    </RoundCardModal>
  </div>
</template>

<style scoped>
/* ══ 后台 = nav 后台的视觉语言 ═══════════════════════════════
   左边一列菜单（透明底、当前项品牌色块），右边内容区，卡片 #121927、
   圆角 13、1px 白 7% 描边 —— 和 nav/static/admin.html 对齐。 */

.admin-head {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  user-select: none;
}

.admin-mark {
  width: 28px;
  height: 28px;
  border-radius: 9px;
  background: linear-gradient(135deg, #5B6CFF, #22D3C5);
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  box-shadow: 0 6px 16px rgba(91, 108, 255, 0.4);
  flex-shrink: 0;
}

.admin-title {
  font-size: 15px;
  font-weight: 700;
  color: #E9EDF7;
  letter-spacing: 0.2px;
}

.admin-collapse {
  margin-left: auto;
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #65708D;
  font-size: 18px;
  cursor: pointer;
}

.admin-collapse:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #E9EDF7;
}

.admin-shell {
  display: flex;
  gap: 14px;
  height: min(600px, 72vh);
  min-height: 380px;
  padding: 2px;
}

.admin-side {
  width: 168px;
  flex: 0 0 168px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.2s, flex-basis 0.2s, opacity 0.2s;
}

.admin-side.is-collapsed {
  width: 0;
  flex-basis: 0;
  opacity: 0;
  pointer-events: none;
}

.admin-nav {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: #99A3BE;
  font-size: 13px;
  font-family: inherit;
  text-align: left;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.admin-nav:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #E9EDF7;
}

.admin-nav.is-on {
  background: rgba(91, 108, 255, 0.16);
  color: #E9EDF7;
  font-weight: 600;
}

.admin-nav-ico {
  font-size: 15px;
  flex-shrink: 0;
  opacity: 0.9;
}

.admin-body {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding-right: 2px;
}

/* ── 把 naive-ui 的默认配色压成 nav 那套 ─────────────────
   naive-ui 每个组件都读一组 --n-* CSS 变量，直接改变量比逐个覆盖
   .n-input__border 之类的内部节点稳，也不会误伤组件自己的状态色。 */
.admin-body :deep(.n-input),
.admin-body :deep(.n-base-selection) {
  --n-color: #182033 !important;
  --n-color-focus: #182033 !important;
  --n-color-active: #182033 !important;
  --n-text-color: #E9EDF7 !important;
  --n-text-color-focus: #E9EDF7 !important;
  --n-placeholder-color: #65708D !important;
  --n-border: 1px solid rgba(255, 255, 255, 0.14) !important;
  --n-border-hover: 1px solid rgba(91, 108, 255, 0.5) !important;
  --n-border-focus: 1px solid #5B6CFF !important;
  --n-border-active: 1px solid #5B6CFF !important;
  --n-box-shadow-focus: 0 0 0 3px rgba(91, 108, 255, 0.18) !important;
  --n-border-radius: 9px !important;
}

.admin-body :deep(.n-card) {
  --n-color: #121927 !important;
  --n-border-color: rgba(255, 255, 255, 0.075) !important;
  --n-border-radius: 13px !important;
  --n-title-text-color: #E9EDF7 !important;
  --n-text-color: #99A3BE !important;
}

.admin-body :deep(.n-form-item-label) {
  --n-label-text-color: #99A3BE !important;
}

.admin-body :deep(.n-button) {
  --n-border-radius: 9px !important;
}

.admin-body :deep(.n-button--primary-type) {
  --n-color: #5B6CFF !important;
  --n-color-hover: #7C8AFF !important;
  --n-color-pressed: #3F4FE0 !important;
  --n-color-focus: #7C8AFF !important;
  --n-border: 0 solid transparent !important;
  --n-border-hover: 0 solid transparent !important;
}

.admin-body :deep(.n-button:not(.n-button--primary-type)) {
  --n-color: #182033 !important;
  --n-color-hover: #1E2740 !important;
  --n-color-pressed: #1E2740 !important;
  --n-text-color: #99A3BE !important;
  --n-text-color-hover: #E9EDF7 !important;
  --n-border: 1px solid rgba(255, 255, 255, 0.14) !important;
}

.admin-body :deep(.n-switch) {
  --n-rail-color: #1E2740 !important;
  --n-rail-color-active: rgba(91, 108, 255, 0.55) !important;
}

.admin-body :deep(.n-data-table),
.admin-body :deep(.n-table) {
  --n-td-color: transparent !important;
  --n-th-color: transparent !important;
  --n-td-color-hover: rgba(255, 255, 255, 0.04) !important;
  --n-border-color: rgba(255, 255, 255, 0.075) !important;
  --n-th-text-color: #65708D !important;
  --n-td-text-color: #99A3BE !important;
  --n-th-font-weight: 500 !important;
}

.admin-body :deep(.n-tabs) {
  --n-tab-text-color: #99A3BE !important;
  --n-tab-text-color-active: #E9EDF7 !important;
  --n-tab-text-color-hover: #E9EDF7 !important;
  --n-bar-color: #5B6CFF !important;
}

.admin-body :deep(.n-divider) {
  --n-color: rgba(255, 255, 255, 0.075) !important;
}

.admin-body :deep(.n-empty) {
  --n-text-color: #65708D !important;
  --n-icon-color: #65708D !important;
}

/* 小屏：侧栏盖在内容上，收起后内容占满 */
@media (max-width: 640px) {
  .admin-shell {
    height: min(520px, 76vh);
  }

  .admin-side {
    position: absolute;
    z-index: 5;
    left: 12px;
    top: 12px;
    bottom: 12px;
    width: 160px;
    flex-basis: 160px;
    padding: 6px;
    border-radius: 12px;
    background: #0D121E;
    border: 1px solid rgba(255, 255, 255, 0.075);
    box-shadow: 0 14px 34px rgba(3, 6, 16, 0.55);
  }
}
</style>

<style>
/* 弹窗本体（NModal preset=card）在 teleport 出去的容器里，够不到 scoped，
   只能全局按传进去的 class 打。 */
.awadaoh-admin.n-card,
.n-modal.awadaoh-admin {
  background: #0D121E !important;
  border: 1px solid rgba(255, 255, 255, 0.075) !important;
  border-radius: 18px !important;
  box-shadow: 0 24px 60px rgba(3, 6, 16, 0.62) !important;
}

.awadaoh-admin .n-card-header {
  border-bottom: 1px solid rgba(255, 255, 255, 0.075);
  padding: 14px 16px;
}

.awadaoh-admin .n-card__content {
  padding: 14px 16px 16px;
}
</style>
