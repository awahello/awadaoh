import { defineStore } from 'pinia'
import { getStorage, removeToken as hRemoveToken, setStorage } from './helper'
import { VisitMode } from '@/enums/auth'

// interface SessionResponse {
//   auth: boolean
// }

export interface AuthState {
  token: string | null
  userInfo: User.Info | null
  // session: SessionResponse | null
  visitMode: VisitMode
}

const defaultState: AuthState = {
  token: null,
  userInfo: null,
  // 默认按访客处理：打开域名先看到导航前端，而不是登录框。
  // 有 token 时 updateLocalUserInfo() 会把真实的 visitMode 覆盖回来。
  visitMode: VisitMode.VISIT_MODE_PUBLIC,
}

export const useAuthStore = defineStore('auth-store', {
  state: (): AuthState => getStorage() || defaultState,

  actions: {
    setToken(token: string) {
      this.token = token
      this.saveStorage()
    },

    setUserInfo(userInfo: User.Info) {
      this.userInfo = userInfo
      this.saveStorage()
    },

    setVisitMode(visitMode: VisitMode) {
      this.visitMode = visitMode
      this.saveStorage()
    },

    saveStorage() {
      setStorage(this.$state)
    },

    removeToken() {
      // 用浅拷贝，别把 defaultState 这个模块级常量当可变对象改脏
      this.$state = { ...defaultState }
      hRemoveToken()
    },
  },

})
