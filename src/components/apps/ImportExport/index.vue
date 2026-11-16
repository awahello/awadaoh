<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { UploadFileInfo } from 'naive-ui'
import { NAlert, NButton, NCheckbox, NCheckboxGroup, NDivider, NInput, NSpace, NUpload, useMessage } from 'naive-ui'
import { RoundCardModal, SvgIcon } from '@/components/common'
import type { IconGroup, ImportJsonResult } from '@/utils/jsonImportExport'
import { ConfigVersionLowError, FormatError, exportJson, importJsonString } from '@/utils/jsonImportExport'
import { get as getAbout } from '@/api/system/about'
import { edit as addGroup, getList as getGroupList } from '@/api/panel/itemIconGroup'
import { addMultiple as addMultipleIcons, getListByGroupId } from '@/api/panel/itemIcon'
import { exportBookmarks } from '@/api/panel/exportBookmarks'
import { isBookmarkHtml, isChromeBookmarksJson, parseBookmarkHtml, parseChromeBookmarksJson } from '@/utils/bookmarkHtml'
import type { BookmarkHtmlGroup } from '@/utils/bookmarkHtml'

import { t } from '@/locales'

interface ItemGroup extends Panel.ItemIconGroup {
  items?: Panel.ItemInfo[]
}

const ms = useMessage()

const jsonData = ref<string | null>(null)
const importWarning = ref<string[]>([])
const importRoundModalShow = ref(false)
const exportRoundModalShow = ref(false)
const loading = ref(false)
const uploadLoading = ref(false)
const version = ref('') // 当前软件版本
const debug = ref(false)

const importObj = ref<ImportJsonResult | null> (null)

// 导入来源：json = 面板自己的配置文件；html = 浏览器「导出书签」得到的 HTML
const importMode = ref<'json' | 'html'>('json')
const htmlGroups = ref<BookmarkHtmlGroup[]>([])

// ── 导出书签 ────────────────────────────────────────
// 导出接口要 token，浏览器地址栏带不上，所以后端把内容塞进 JSON 返回，
// 这里自己拼 Blob 再点一个临时 <a download>。
const bookmarkBusy = ref(false)
const includeHidden = ref(true)

function downloadBookmarks(format: 'html' | 'json') {
  bookmarkBusy.value = true
  exportBookmarks<any>(format, includeHidden.value)
    .then(({ data }) => {
      const blob = new Blob([data.content], { type: data.mime || 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = data.filename || ('awadaoh-bookmarks.' + format)
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 5000)
      ms.success('已导出 ' + (data.filename || ''))
    })
    .catch(e => ms.error(e?.message || '导出失败'))
    .finally(() => { bookmarkBusy.value = false })
}

const importItems = ref<string[]>(['icons']) // 当前软件版本支持导入导出的项目
const checkedItems = ref<string[]>(['icons']) // 当前准备导入的项目

// 导入图标
async function importIcons(): Promise<string | null> {
  const groups = importObj.value?.geticons()
  const batchSize = 50

  if (!groups)
    return null

  try {
    for (let i = 0; i < groups.length; i++) {
      const element = groups[i]

      // 创建组得到组id
      const createGroupResponse = await addGroup<Panel.ItemIconGroup>({
        title: element.title,
        sort: element.sort,
      })

      if (createGroupResponse.code === 0) {
        const groupId = createGroupResponse.data?.id

        if (groupId) {
          let addIcons: Panel.ItemInfo[] = []

          // 批量添加子项
          for (let iconI = 0; iconI < element.children.length; iconI++) {
            const iconElement = element.children[iconI]

            addIcons.push({
              title: iconElement.title,
              sort: iconElement.sort,
              icon: iconElement.icon,
              url: iconElement.url,
              lanUrl: iconElement.lanUrl,
              description: iconElement.description,
              openMethod: iconElement.openMethod,
              itemIconGroupId: groupId,
            })

            // 每 batchSize 个添加一次
            if (addIcons.length === batchSize || iconI === element.children.length - 1) {
              const response = await addMultipleIcons(addIcons)

              if (response.code !== 0)
                return response.msg

              addIcons = []
            }
          }
        }
      }
      else {
        return createGroupResponse.msg
      }
    }

    return null
  }
  catch (error) {
    if (error instanceof Error)
      return `${t('common.failed')}: ${error.message}`
    else
      return t('common.unknownError')
  }
}

// 浏览器书签 HTML → 分组 + 站点。
// 走的是同一套接口（先建组拿 id，再批量加站点），只是数据源从 JSON 换成了 HTML。
async function importHtmlGroups(): Promise<string | null> {
  const groups = htmlGroups.value
  if (!groups.length)
    return '没有解析到书签'

  try {
    for (const g of groups) {
      const createGroupResponse = await addGroup<Panel.ItemIconGroup>({
        title: g.title,
        sort: g.sort,
      })
      if (createGroupResponse.code !== 0)
        return createGroupResponse.msg

      const groupId = createGroupResponse.data?.id
      if (!groupId)
        continue

      let addIcons: Panel.ItemInfo[] = []
      for (let i = 0; i < g.children.length; i++) {
        const s = g.children[i]
        const first = (s.title || s.url || '?').trim().charAt(0).toUpperCase() || '?'
        addIcons.push({
          title: s.title,
          sort: i + 1,
          url: s.url,
          lanUrl: '',
          description: s.description,
          openMethod: 2, // 新窗口打开，和浏览器书签的习惯一致
          // 书签 HTML 里没有图标信息，先给个首字母方块，后台可以再改
          icon: { itemType: 1, text: first },
          itemIconGroupId: groupId,
        })

        if (addIcons.length === 50 || i === g.children.length - 1) {
          const response = await addMultipleIcons(addIcons)
          if (response.code !== 0)
            return response.msg
          addIcons = []
        }
      }
    }
    return null
  }
  catch (error) {
    if (error instanceof Error)
      return `${t('common.failed')}: ${error.message}`
    return t('common.unknownError')
  }
}

// 导出图标
async function exportIcons(): Promise<IconGroup[]> {
  const iconGroups: IconGroup[] = []

  // 获取组数据
  const { code, data } = await getGroupList<Common.ListResponse<ItemGroup[]>>()

  if (code === 0) {
    // 使用 Promise.all 等待所有异步操作完成
    await Promise.all(data.list.map(async (element) => {
      const group: IconGroup = {
        title: element.title as string,
        sort: element.sort as 0,
        children: [],
      }

      const res = await getListByGroupId<Common.ListResponse<Panel.ItemInfo[]>>(element.id)

      if (res.code === 0) {
        for (const iconElement of res.data.list) {
          group.children.push({
            icon: iconElement.icon,
            sort: iconElement.sort || 99999,
            title: iconElement.title,
            url: iconElement.url,
            lanUrl: iconElement.lanUrl || '',
            description: iconElement.description || '',
            openMethod: iconElement.openMethod || 1,
          })
        }
      }

      iconGroups.push(group)
    }))

    return iconGroups
  }
  else {
    return []
  }
}

onMounted(() => {
  interface Version {
    versionName: string
    versionCode: number
  }

  getAbout<Version>().then((res) => {
    if (res.code === 0)
      version.value = res.data.versionName
  })
})

function handleFileChange(options: { file: UploadFileInfo; fileList: Array<UploadFileInfo> }) {
  uploadLoading.value = true
  console.log(options.file.file)
  if (options.file.file) {
    const reader = new FileReader()
    reader.onload = () => {
      if (reader.result) {
        const text = reader.result as string
        // 浏览器导出的书签 HTML 和面板自己的 JSON 是两种格式，
        // 先认一下：是 HTML 就走 HTML 导入，别再报「配置文件格式不正确」
        jsonData.value = text
        if (isBookmarkHtml(text)) {
          openBookmarkImport(parseBookmarkHtml(text), '浏览器书签 HTML')
        }
        else if (isChromeBookmarksJson(text)) {
          // chrome://bookmarks 导出的 Bookmarks JSON，或者直接拷的 profile 文件
          openBookmarkImport(parseChromeBookmarksJson(text), 'Chrome 书签 JSON')
        }
        else {
          importMode.value = 'json'
          htmlGroups.value = []
          importCheck()
        }
      }
      else {
        ms.error(`${t('common.failed')}: ${t('common.repeatLater')}`)
      }
      uploadLoading.value = false
    }
    reader.readAsText(options.file.file)
  }
}

// 浏览器书签（HTML / Chrome JSON）解析成功后统一走这里
function openBookmarkImport(groups: BookmarkHtmlGroup[], sourceLabel: string) {
  htmlGroups.value = groups
  importMode.value = 'html'
  importWarning.value = []
  importObj.value = null
  if (!groups.length) {
    ms.error(`${sourceLabel} 里没解析到书签`)
    return
  }
  const n = groups.reduce((a, g) => a + g.children.length, 0)
  importItems.value = ['icons']
  checkedItems.value = ['icons']
  importRoundModalShow.value = true
  ms.success(`${sourceLabel}：${groups.length} 个分组 / ${n} 个站点`)
}

// 验证导入文件
function importCheck() {
  importWarning.value = []
  if (jsonData.value) {
    try {
      importObj.value = importJsonString(jsonData.value)
      if (importObj.value) {
        if (!importObj.value.isPassCheckMd5())
          importWarning.value.push(t('apps.exportImport.fileModified'))

        if (!importObj.value.isPassCheckConfigVersionOld())
          importWarning.value.push(t('apps.exportImport.warnConfigFileLow'))

        if (!importObj.value.isPassCheckConfigVersionNew())
          importWarning.value.push(t('apps.exportImport.softwareVersionLow'))

        // （暂时不做）此处可以判断，当前的配置文件是否存在的导入项目（不存在隐藏importItems里面的值）操作变量：importItems

        // 通过了验证,打开弹窗
        importRoundModalShow.value = !importRoundModalShow.value

        // console.log(importObj.value.geticons())
      }
    }
    catch (error) {
      if (error instanceof ConfigVersionLowError) {
        ms.error(t('apps.exportImport.errorConfigFileLow'))
        console.error('The configuration file version is too low to be compatible')
      }
      else if (error instanceof FormatError) {
        ms.error(t('apps.exportImport.errorConfigFileFormat'))
        console.error('The format is incorrect and cannot be imported')
      }
    }
  }
  else {
    ms.error(t('apps.exportImport.errorConfigFileFormat'))
  }
}

// 开始导出
async function handleStartExport() {
  loading.value = true
  // console.log('要导出的项目', checkedItems.value)
  // 获取软件版本号
  const exportResult = exportJson(version.value)
  if (checkedItems.value.includes('icons')) {
    console.log('export icons ...')
    const iconGroups = await exportIcons()
    exportResult.addIconsData(iconGroups)
    console.log('export icons finish', iconGroups)
  }

  // console.log('导出结果')

  jsonData.value = exportResult.string()
  exportResult.exportFile()
  loading.value = false
  exportRoundModalShow.value = false
  // ms.success(t('common.success'))
}

// 开始导入
async function handleStartImport() {
  loading.value = true
  if (checkedItems.value.includes('icons')) {
    const errMsg = importMode.value === 'html' ? await importHtmlGroups() : await importIcons()
    if (errMsg !== null) {
      loading.value = false
      ms.error(`${t('common.failed')}:${errMsg}`)
      return
    }
  }

  loading.value = false
  importRoundModalShow.value = false
  ms.success(`${t('common.success')}, ${t('common.refreshPage')}`)
}
</script>

<template>
  <div class="pt-2">
    <NAlert type="info" :bordered="false">
      <p>{{ $t('apps.exportImport.tip') }}</p>
    </NAlert>
    <div class="flex justify-center m-[50px]">
      <div class="m-[10px]">
        <NUpload
          accept=".awadaoh.json,.sunpanel.json,.html,.htm,.json"
          directory-dnd
          :default-upload="false"
          :show-file-list="false"
          @change="handleFileChange"
        >
          <NButton type="info" size="large" :loading="uploadLoading">
            <template #icon>
              <SvgIcon icon="fa6:solid-file-import" />
            </template>
            {{ $t('apps.exportImport.import') }}
          </NButton>
        </NUpload>
      </div>
      <div class="m-[10px]">
        <NButton type="info" size="large" @click="exportRoundModalShow = !exportRoundModalShow">
          <template #icon>
            <SvgIcon icon="fa6:solid-file-export" />
          </template>
          {{ $t('apps.exportImport.export') }}
        </NButton>
      </div>
    </div>

    <NDivider />

    <div class="m-[10px]">
      <div class="mb-[8px] text-sm opacity-70">导出书签（和浏览器「导出书签」同一种格式，Chrome / Edge / Firefox 都能直接导入）</div>
      <NSpace>
        <NButton :loading="bookmarkBusy" @click="downloadBookmarks('html')">
          <template #icon>
            <SvgIcon icon="fa6:solid-file-export" />
          </template>
          导出书签 HTML
        </NButton>
        <NButton :loading="bookmarkBusy" @click="downloadBookmarks('json')">
          <template #icon>
            <SvgIcon icon="fa6:solid-file-export" />
          </template>
          导出 JSON 备份
        </NButton>
        <NCheckbox v-model:checked="includeHidden">包含前台隐藏的分组</NCheckbox>
      </NSpace>
    </div>

    <div class="flex justify-center">
      <a href="/tools/bookmark.html" target="_blank">{{ $t('apps.exportImport.transmuteStandard') }}</a>
    </div>

    <!-- 调试模式 -->
    <div v-if="debug">
      <NButton @click="importCheck">
        检查导入
      </NButton>

      <!-- <NButton @click="exportJsonS">
      导出JSON
    </NButton> -->

      <NButton @click="jsonData = ''">
        清空导入数据
      </NButton>

      <NInput
        v-model:value="jsonData"
        type="textarea"
        placeholder="基本的 Textarea"
      />

      <div v-if="jsonData">
        <h2>JSON 数据</h2>
        <pre>{{ jsonData }}</pre>
      </div>
    </div>

    <RoundCardModal v-model:show="importRoundModalShow" style="max-width: 400px;" :title=" $t('apps.exportImport.import')">
      <template v-if="importMode === 'html'">
        <div class="text-sm opacity-80" style="line-height:1.8">
          识别到浏览器书签文件：<br>
          <b>{{ htmlGroups.length }}</b> 个分组 /
          <b>{{ htmlGroups.reduce((a, g) => a + g.children.length, 0) }}</b> 个站点
        </div>
        <div class="text-xs opacity-50 mt-[10px]" style="line-height:1.7">
          会新建同名分组并写入站点，不会覆盖已有的分组。<br>
          书签里没有图标信息，先按首字母生成，后台可以再改。
        </div>
        <NSpace justify="center">
          <div class="mt-[30px]">
            <NButton type="success" :loading="loading" @click="handleStartImport">
              {{ $t('common.continue') }}
            </NButton>
          </div>
        </NSpace>
      </template>

      <template v-else>
      <div v-if="importWarning.length > 0">
        <NAlert :title="$t('common.warning')" type="warning">
          <div v-for="(text, index) in importWarning " :key="index">
            {{ text }}
          </div>
        </NAlert>
      </div>
      <NDivider title-placement="left">
        {{ $t('apps.exportImport.selectImportData') }}
      </NDivider>

      <NSpace justify="center" style="margin-top: 20px;">
        <NCheckboxGroup v-model:value="checkedItems">
          <NCheckbox v-if="importItems.includes('icons')" value="icons" :label="$t('apps.exportImport.moduleIcon')" />
          <NCheckbox v-if="importItems.includes('style')" value="style" :label="$t('apps.exportImport.moduleStyle')" />
        </NCheckboxGroup>
      </NSpace>
      <NSpace justify="center">
        <div class="mt-[50px]">
          <NButton type="success" :disabled="checkedItems.length === 0" :loading="loading" @click="handleStartImport">
            {{ $t('common.continue') }}
          </NButton>
        </div>
      </NSpace>
      </template>
    </RoundCardModal>

    <RoundCardModal v-model:show="exportRoundModalShow" style="max-width: 400px;" :title=" $t('apps.exportImport.export')">
      <NDivider title-placement="left">
        {{ $t('apps.exportImport.selectExportData') }}
      </NDivider>

      <NSpace justify="center" style="margin-top: 20px;">
        <NCheckboxGroup v-model:value="checkedItems">
          <NCheckbox v-if="importItems.includes('icons')" value="icons" :label="$t('apps.exportImport.moduleIcon')" />
          <NCheckbox v-if="importItems.includes('style')" value="style" :label="$t('apps.exportImport.moduleStyle')" />
        </NCheckboxGroup>
      </NSpace>
      <NSpace justify="center">
        <div class="mt-[50px]">
          <NButton type="success" :disabled="checkedItems.length === 0" :loading="loading" @click="handleStartExport">
            {{ $t('common.continue') }}
          </NButton>
        </div>
      </NSpace>
    </RoundCardModal>
  </div>
</template>
