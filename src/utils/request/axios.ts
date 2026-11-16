import axios, { type AxiosResponse } from 'axios'
import { useAuthStore } from '@/store'

const service = axios.create({
  baseURL: import.meta.env.VITE_GLOB_API_URL,
})

service.interceptors.request.use(
  (config) => {
    const token = useAuthStore().token
    if (token)
      config.headers.Authorization = `Bearer ${token}`
    // 前台访问密码的解锁凭据。和后台 token 分开放：它只够浏览，
    // 拿不到任何写接口，所以不塞进 authStore。
    try {
      const frontToken = localStorage.getItem('awadaoh-front-token')
      if (frontToken)
        config.headers['X-Front-Token'] = frontToken
    }
    catch (e) {
      // localStorage 被禁用就当作没解锁，服务端会回 1008
    }
    return config
  },
  (error) => {
    return Promise.reject(error.response)
  },
)

service.interceptors.response.use(
  (response: AxiosResponse): AxiosResponse => {
    if (response.status === 200)
      return response

    throw new Error(response.status.toString())
  },
  (error) => {
    return Promise.reject(error)
  },
)

export default service
