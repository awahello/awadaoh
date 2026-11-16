import type { GlobalThemeOverrides } from 'naive-ui'
import { computed, watch } from 'vue'
import { darkTheme, useOsTheme } from 'naive-ui'
import { useAppStore } from '@/store'

// ── AKKdaoh 品牌色板 ───────────────────────────────────────────────
const BRAND = {
  primary: '#5B6CFF',
  primaryHover: '#7C8AFF',
  primaryPressed: '#3F4FE0',
  accent: '#22D3C5',
  radius: '12px',
}

const FONT = `"Inter", "PingFang SC", "HarmonyOS Sans SC", "Microsoft YaHei",
  -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`

export function useTheme() {
  const appStore = useAppStore()

  const OsTheme = useOsTheme()

  const isDark = computed(() => {
    if (appStore.theme === 'auto')
      return OsTheme.value === 'dark'
    else
      return appStore.theme === 'dark'
  })

  const theme = computed(() => {
    return isDark.value ? darkTheme : undefined
  })

  const themeOverrides = computed<GlobalThemeOverrides>(() => ({
    common: {
      primaryColor: BRAND.primary,
      primaryColorHover: BRAND.primaryHover,
      primaryColorPressed: BRAND.primaryPressed,
      primaryColorSuppl: BRAND.primaryHover,
      infoColor: BRAND.primary,
      infoColorHover: BRAND.primaryHover,
      infoColorPressed: BRAND.primaryPressed,
      borderRadius: BRAND.radius,
      borderRadiusSmall: '8px',
      fontFamily: FONT,
      ...(isDark.value
        ? {
            bodyColor: '#0B1020',
            cardColor: '#151A2E',
            modalColor: '#151A2E',
            popoverColor: '#1A2036',
            tableColor: '#151A2E',
            inputColor: '#0F1424',
            borderColor: 'rgba(255,255,255,0.10)',
          }
        : {
            bodyColor: '#F6F7FB',
            cardColor: '#FFFFFF',
            modalColor: '#FFFFFF',
            popoverColor: '#FFFFFF',
            borderColor: 'rgba(15,20,40,0.08)',
          }),
    },
    Button: {
      fontWeight: '600',
      borderRadiusMedium: BRAND.radius,
      borderRadiusLarge: BRAND.radius,
    },
    Card: {
      borderRadius: '16px',
    },
    Dialog: {
      borderRadius: '18px',
    },
    Modal: {
      borderRadius: '18px',
    },
    Input: {
      borderRadius: BRAND.radius,
    },
    Tag: {
      borderRadius: '8px',
    },
    Tooltip: {
      borderRadius: '10px',
    },
  }))

  watch(
    () => isDark.value,
    (dark) => {
      if (dark)
        document.documentElement.classList.add('dark')
      else
        document.documentElement.classList.remove('dark')
    },
    { immediate: true },
  )

  return { theme, themeOverrides }
}
