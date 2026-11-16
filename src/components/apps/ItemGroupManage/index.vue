<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { FormInst, FormRules } from 'naive-ui'
import { NButton, NCard, NDropdown, NForm, NFormItem, NInput, useDialog, useMessage } from 'naive-ui'
import { VueDraggable } from 'vue-draggable-plus'
import { deletes, edit, getList, saveSort } from '@/api/panel/itemIconGroup'
import { edit as editItem, getListByGroupId } from '@/api/panel/itemIcon'
import { RoundCardModal, SvgIcon } from '@/components/common'
import { t } from '@/locales'

interface EditModalArg {
  show: boolean
  editStatus: number // 1.添加 2.编辑
  model: Panel.ItemIconGroup
  rules: FormRules
}

const formRef = ref<FormInst | null>(null)
const ms = useMessage()
const dialog = useDialog()
const sortStatus = ref(false)

const defaultMNodal = {
  title: '',
  icon: 'material-symbols:folder-outline',
  sort: 9999,
}

const editModalArg = ref<EditModalArg>({
  show: false,
  editStatus: 1,
  model: defaultMNodal,
  rules: {
    title: [
      {
        required: true,
        trigger: 'blur',
        message: t('form.required'),
      },
    ],
  },
})

const groups = ref<Panel.ItemIconGroup[]>([])

// 分类可见性：0 公开（谁都能看）/ 1 登录后可见（访客看不到）/ 2 隐藏（前台不渲染）
// 后端 GetList 对访客只下发 0 的分组，所以这里改完访客那边是真的拿不到，不是前端藏。
const visibilityOptions = [
  { label: '公开：谁都能看', key: 0 },
  { label: '登录后可见：访客看不到', key: 1 },
  { label: '隐藏：前台不显示（配置保留）', key: 2 },
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
    return '登录可见'
  if (v === 2)
    return '隐藏'
  return '公开'
}

// 补全站点图标：导入浏览器书签时拿不到图标，先按首字母生成了方块。
// 这个按钮把「还是首字母」的站点批量换成按域名取的 favicon。
// 只动 itemType===1（字母块）的，用户自己上传过图标的不会被覆盖。
const fixingIcons = ref(false)

function faviconOf(u?: string): string {
  if (!u)
    return ''
  try {
    const host = new URL(u).hostname
    return host ? `https://favicon.im/${host}?larger=true` : ''
  }
  catch {
    return ''
  }
}

async function handleFixIcons() {
  if (fixingIcons.value)
    return
  fixingIcons.value = true
  let done = 0
  let skipped = 0
  try {
    for (const g of groups.value) {
      if (!g.id)
        continue
      const res = await getListByGroupId<Common.ListResponse<Panel.ItemInfo[]>>(g.id)
      if (res.code !== 0)
        continue
      for (const item of res.data.list) {
        // 已经有真实图标的跳过
        if (item.icon && item.icon.itemType !== 1)
          continue
        const fav = faviconOf(item.url)
        if (!fav) {
          skipped++
          continue
        }
        await editItem({ ...item, icon: { itemType: 2, src: fav, backgroundColor: '#2a2a2a6b' } })
        done++
      }
    }
    ms.success(`已补全 ${done} 个图标${skipped ? `，${skipped} 个地址取不到域名跳过` : ''}`)
  }
  catch (e: any) {
    ms.error(`补图标中断：${e?.message || '未知错误'}`)
  }
  finally {
    fixingIcons.value = false
  }
}

async function handleSetVisible(groupInfo: Panel.ItemIconGroup, visible: number) {
  const res = await edit({ ...groupInfo, visible })
  if (res.code === 0) {
    groupInfo.visible = visible
    ms.success(`「${groupInfo.title}」已设为${visibilityLabel(visible)}`)
  }
  else {
    ms.error(`${t('common.saveFail')}:${res.msg}`)
  }
}

function handleAddGroup() {
  editModalArg.value.show = !editModalArg.value.show
}

function handleEditGroup(groupInfo: Panel.ItemIconGroup) {
  editModalArg.value.show = true
  editModalArg.value.model = groupInfo
  editModalArg.value.editStatus = 2
}

function handleDragSort() {
  sortStatus.value = true
}

function handleSaveSort() {
  const saveItems: Common.SortItemRequest[] = []
  for (let i = 0; i < groups.value.length; i++) {
    const element = groups.value[i]
    saveItems.push({
      id: element.id as number,
      sort: i + 1,
    })
  }
  saveSort(saveItems).then(({ code, msg }) => {
    if (code === 0) {
      ms.success(t('common.saveSuccess'))
      sortStatus.value = false
    }
    else {
      ms.error(`${t('common.saveFail')}:${msg}`)
    }
  })
}

function handleDelete(groupInfo: Panel.ItemIconGroup) {
  dialog.warning({
    title: t('common.warning'),
    content: t('apps.itemGroupManage.deleteWarnText', { name: groupInfo.title }),
    positiveText: t('common.confirm'),
    negativeText: t('common.cancel'),
    onPositiveClick: () => {
      if (groupInfo.id) {
        deletes([groupInfo.id]).then(({ code, msg }) => {
          if (code !== 0)
            ms.error(t('common.deleteFail'))
          else
            refreshList()
        })
      }
    },

  })
}

function handleSaveGroup() {
  formRef.value?.validate((errors) => {
    if (!errors) {
      edit(editModalArg.value.model).then(({ code, msg }) => {
        if (code !== 0)
          ms.error(msg)

        refreshList()
        editModalArg.value.show = false
        editModalArg.value.model = { ...defaultMNodal }
      })
    }
    else { console.log(errors) }
  })
}

function refreshList() {
  getList<Common.ListResponse<Panel.ItemIconGroup[]>>().then(({ code, data }) => {
    groups.value = data.list
  })
}

onMounted(() => {
  refreshList()
})
</script>

<template>
  <div class="h-full">
    <div class="p-2">
      <NButton type="success" size="small" style="margin-right: 10px;" @click="handleAddGroup">
        {{ $t('common.add') }}
      </NButton>

      <NButton v-if="!sortStatus" size="small" @click="handleDragSort">
        {{ $t('common.sort') }}
      </NButton>

      <NButton v-else type="warning" size="small" @click="handleSaveSort">
        {{ $t('common.saveSort') }}
      </NButton>

      <NButton size="small" style="margin-left:10px" :loading="fixingIcons" @click="handleFixIcons">
        补全站点图标
      </NButton>

      <div class="text-xs opacity-50 mt-[8px]" style="line-height:1.7">
        每一行的「公开 / 登录可见 / 隐藏」是分类可见性：设成后两种，访客拿到的分组列表里就没有它，
        站点数据也不会下发（不是前端藏起来）。
      </div>
    </div>

    <div class=" overflow-auto w-full mt-[20px]  bg-slate-200 dark:bg-zinc-900 rounded-xl" style="height:calc(100% - 65px)">
      <VueDraggable
        v-model="groups"
        item-key="sort" :animation="300"
        :style="{ padding: sortStatus ? '20px' : '10px' }"
        :disabled="!sortStatus"
      >
        <div v-for="(item, index) in groups" :key="index" class="w-full">
          <NCard size="small" style="border-radius:10px;margin-bottom: 10px;">
            <div class="flex" :class="sortStatus ? 'cursor-move' : ''">
              <div class="flex items-center">
                <span class="mr-[10px]">
                  <SvgIcon class="text-[20px]" icon="material-symbols:ad-group-outline-rounded" />
                  <!-- <SvgIcon class="text-[20px]" :icon="item.icon" /> -->
                </span>
                <span>
                  {{ item.title }}
                </span>
              </div>
              <div class="ml-auto flex items-center">
                <span class="mr-[10px]">
                  <NDropdown
                    trigger="click" :options="visibilityOptions"
                    @select="(v: any) => handleSetVisible(item, Number(v))"
                  >
                    <NButton
                      strong secondary size="small"
                      :type="item.visible === 2 ? 'warning' : (item.visible === 1 ? 'info' : 'default')"
                    >
                      <template #icon>
                        <SvgIcon :icon="visibilityIcon(item.visible)" />
                      </template>
                      {{ visibilityLabel(item.visible) }}
                    </NButton>
                  </NDropdown>
                </span>
                <span>
                  <NButton strong secondary type="success" size="small" @click="handleEditGroup(item)">
                    <template #icon>
                      <SvgIcon icon="basil:edit-solid" />
                    </template>
                  </NButton>
                </span>
                <span class="ml-[10px]">
                  <NButton strong secondary type="error" size="small" class="ml-[10px]" @click="handleDelete(item)">
                    <template #icon>
                      <SvgIcon icon="material-symbols:delete" />
                    </template>
                  </NButton>
                </span>
              </div>
            </div>
          </NCard>
        </div>
      </VueDraggable>
    </div>

    <RoundCardModal v-model:show="editModalArg.show" size="small" type="small" :title="editModalArg.editStatus === 1 ? '添加' : '编辑'" style="width: 400px;">
      <NForm ref="formRef" :model="editModalArg.model" :rules="editModalArg.rules">
        <NFormItem path="title" :label="$t('apps.itemGroupManage.groupName')">
          <NInput v-model:value="editModalArg.model.title" type="text" :maxlength="20" show-count />
        </NFormItem>

        <!-- <NFormItem path="name" label="昵称">
          <NInput v-model:value="editModalArg.model" type="text" placeholder="请输入昵称" />
        </NFormItem> -->
      </NForm>
      <template #footer>
        <NButton type="success" size="small" class="float-right" @click="handleSaveGroup">
          {{ $t('common.confirm') }}
        </NButton>
      </template>
    </RoundCardModal>
  </div>
</template>
