import { post } from '@/utils/request'

// 导出书签：后端把内容塞进 JSON 返回，前端自己拼 Blob 下载。
// 不直接开附件地址是因为鉴权走 token 请求头，浏览器地址栏带不上。
export function exportBookmarks<T>(format: 'html' | 'json', includeHidden: boolean) {
  return post<T>({
    url: '/panel/export/bookmarks',
    data: { format, includeHidden },
  })
}
