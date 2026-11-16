import type { AxiosProgressEvent, AxiosResponse, GenericAbortSignal } from 'axios'
import request from './axios'
import { apiRespErrMsg, message } from './apiMessage'
import { t } from '@/locales'
import { useAppStore, useAuthStore } from '@/store'
import { router } from '@/router'

let loginMessageShow = false

// 前台页面（首页导航 / 面板）不因为「未登录」被打回登录页。
// 访客模式没配公开账号时后端返回 1001，这里以前直接 router.push('/login')，
// 结果打开域名第一眼就是登录框 —— 不是我们要的产品形态。
function isFrontStage() {
  const path = router.currentRoute.value?.path || '/'
  return path === '/' || path === '/index.html' || path.startsWith('/panel')
}

export interface HttpOption {
  url: string
  data?: any
  method?: string
  headers?: any
  onDownloadProgress?: (progressEvent: AxiosProgressEvent) => void
  signal?: GenericAbortSignal
  beforeRequest?: () => void
  afterRequest?: () => void
}

export interface Response<T = any> {
  data: T
  // message: string | null
  // status: string
  msg: string
  code: number
}

function http<T = any>(
  { url, data, method, headers, onDownloadProgress, signal, beforeRequest, afterRequest }: HttpOption,
) {
  const authStore = useAuthStore()
  const appStore = useAppStore()
  const successHandler = (res: AxiosResponse<Response<T>>) => {
    if (res.data.code === 0)
      return res.data

    // 1000 / 1001：未登录或 token 过期。
    // 前台（首页）只清 token，不跳登录、不弹「登录过期」—— 访客就该直接看到导航。
    if (res.data.code === 1001) {
      authStore.removeToken()

      if (isFrontStage())
        return res.data

      // 避免重复弹窗
      if (loginMessageShow === false) {
        loginMessageShow = true
        message.warning(t('api.loginExpires'), {
          onLeave() {
            loginMessageShow = false
          },
        })
      }

      router.push({ path: '/login' })
      return res.data
    }

    if (res.data.code === 1000) {
      authStore.removeToken()

      if (isFrontStage())
        return res.data

      router.push({ path: '/login' })
      return res.data
    }

    if (res.data.code === 1005) {
      message.warning(res.data.msg)
      return res.data
    }

    if (res.data.code === -1) {
      // message.warning(res.data.msg)
      // router.push({ path: '/login' })
      // authStore.removeToken()
      return res.data
    }

    if (!apiRespErrMsg(res.data))
      return Promise.reject(res.data)
    else
      return res.data
  }

  const failHandler = (error: Response<Error>) => {
    afterRequest?.()
    message.error(t('common.networkError'), {
      duration: 50000,
      closable: true,
    })
    throw new Error(error?.msg || 'Error')
  }

  beforeRequest?.()

  method = method || 'GET'

  const params = Object.assign(typeof data === 'function' ? data() : data ?? {}, {})
  if (!headers)
    headers = {}

  headers.token = authStore.token
  headers.lang = appStore.language
  return method === 'GET'
    ? request.get(url, { params, signal, onDownloadProgress }).then(successHandler, failHandler)
    : request.post(url, params, { headers, signal, onDownloadProgress }).then(successHandler, failHandler)
}

export function get<T = any>(
  { url, data, method = 'GET', onDownloadProgress, signal, beforeRequest, afterRequest }: HttpOption,
): Promise<Response<T>> {
  return http<T>({
    url,
    method,
    data,
    onDownloadProgress,
    signal,
    beforeRequest,
    afterRequest,
  })
}

export function post<T = any>(
  { url, data, method = 'POST', headers, onDownloadProgress, signal, beforeRequest, afterRequest }: HttpOption,
): Promise<Response<T>> {
  return http<T>({
    url,
    method,
    data,
    headers,
    onDownloadProgress,
    signal,
    beforeRequest,
    afterRequest,
  })
}

export default post
