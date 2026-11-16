<script setup lang="ts">
import { NDivider, NGradientText, NTag } from 'naive-ui'
import { onMounted, ref } from 'vue'
import { get } from '@/api/system/about'
import srcSvglogo from '@/assets/logo.svg'

interface Version {
  versionName: string
  versionCode: number
}

const versionName = ref('')
const frontVersion = import.meta.env.VITE_APP_VERSION || 'unknown'

onMounted(() => {
  get<Version>().then((res) => {
    if (res.code === 0)
      versionName.value = res.data.versionName
  })
})
</script>

<template>
  <div class="pt-5">
    <div class="flex flex-col items-center justify-center">
      <img :src="srcSvglogo" width="100" height="100" alt="">
      <div class="text-3xl font-semibold">
        {{ $t('common.appName') }}
      </div>
      <div class="text-xl">
        <NGradientText type="info">
          <a href="https://github.com/akkdiy/akkdaoh/releases" class="font-semibold" :title="$t('apps.about.viewUpdateLog')" target="_blank">v{{ versionName }}</a>
        </NGradientText>
      </div>
      <div class="mt-2">
        <a href="https://github.com/akkdiy/akkdaoh/releases" target="_blank" class="link">{{ $t('apps.about.checkUpdate') }}</a>
      </div>
    </div>

    <NDivider style="margin:10px 0">
      •
    </NDivider>

    <div class="flex flex-col items-center justify-center text-base">
      <div>
        <a href="https://github.com/akkdiy/akkdaoh" target="_blank" class="link">github.com/akkdiy/akkdaoh</a>
      </div>
      <div class="mt-1">
        <a href="https://github.com/akkdiy/akkdaoh/issues" target="_blank" class="link">Issues</a>
      </div>
      <div class="mt-5">
        <NTag :bordered="false" size="small">
          {{ $t("apps.about.frontVersionText") }}: FV-{{ frontVersion }}
        </NTag>
      </div>
    </div>
  </div>
</template>

<style>
.link{
    color:rgb(0, 89, 255)
}
</style>
