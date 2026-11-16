import { post } from '@/utils/request'

// 谷歌书签同步：后端盯着 Chrome 的 Bookmarks JSON 文件，
// 一变就重新解析入库，等价于「和收藏夹同步」，不需要 Google 授权。
export function getSync<T>() {
  return post<T>({
    url: '/panel/sync/get',
  })
}

export function saveSync<T>(req: Panel.SyncSetting) {
  return post<T>({
    url: '/panel/sync/save',
    data: req,
  })
}

export function runSync<T>() {
  return post<T>({
    url: '/panel/sync/run',
  })
}

export function testSync<T>(path?: string) {
  return post<T>({
    url: '/panel/sync/test',
    data: { path: path || '' },
  })
}
