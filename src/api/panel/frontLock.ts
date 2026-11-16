import { post } from '@/utils/request'

// 前台访问密码：开了之后访客打开首页先看到一把锁，
// 服务端在公开模式中间件里直接回 1008，分组和站点一个都不下发。
export function getFrontLock<T>() {
  return post<T>({
    url: '/panel/frontLock/get',
  })
}

export function unlockFrontLock<T>(password: string) {
  return post<T>({
    url: '/panel/frontLock/unlock',
    data: { password },
  })
}

export function saveFrontLock<T>(enabled: boolean, password: string) {
  return post<T>({
    url: '/panel/frontLock/save',
    data: { enabled, password },
  })
}
