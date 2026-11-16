import { get, post } from '@/utils/request'

// 客户端环境：intranet=true 表示访问者自己就在内网，内网地址可以直接连
export interface ClientEnv {
  intranet: boolean
  clientIp: string
  visitMode: number
}

export function getClientEnv() {
  return get<ClientEnv>({
    url: '/panel/env',
  })
}

export function addMultiple<T>(req: Panel.ItemInfo[]) {
  return post<T>({
    url: '/panel/itemIcon/addMultiple',
    data: req,
  })
}

export function edit<T>(req: Panel.ItemInfo) {
  return post<T>({
    url: '/panel/itemIcon/edit',
    data: req,
  })
}

// export function getInfo<T>(id: number) {
//   return post<T>({
//     url: '/aiApplet/getInfo',
//     data: { id },
//   })
// }

export function getListByGroupId<T>(itemIconGroupId: number | undefined) {
  return post<T>({
    url: '/panel/itemIcon/getListByGroupId',
    data: { itemIconGroupId },
  })
}

export function deletes<T>(ids: number[]) {
  return post<T>({
    url: '/panel/itemIcon/deletes',
    data: { ids },
  })
}

export function saveSort<T>(data: Panel.ItemIconSortRequest) {
  return post<T>({
    url: '/panel/itemIcon/saveSort',
    data,
  })
}

export function getSiteFavicon<T>(url: string) {
  return post<T>({
    url: '/panel/itemIcon/getSiteFavicon',
    data: { url },
  })
}
