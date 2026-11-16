// 浏览器书签 HTML（Netscape Bookmark）解析
//
// Chrome / Edge / Firefox 的「导出书签」都是这个格式：
//   <DL><p>
//     <DT><H3>文件夹名</H3>
//     <DL><p>
//       <DT><A HREF="..." ADD_DATE="...">标题</A>
//     </DL><p>
//   </DL><p>
// 浏览器会把内层 <DL> 解析成外层 <DT> 的子节点，所以递归时优先找
// DT 里的 dl；找不到再看下一个兄弟节点（有些工具导出的结构是平铺的）。

export interface BookmarkHtmlSite {
  title: string
  url: string
  description: string
}

export interface BookmarkHtmlGroup {
  title: string
  sort: number
  children: BookmarkHtmlSite[]
}

// 先看头部特征，避免把 JSON 配置误判成 HTML
export function isBookmarkHtml(text: string): boolean {
  const head = (text || '').slice(0, 500).toLowerCase()
  if (head.includes('netscape-bookmark'))
    return true
  return head.includes('<dl') && head.includes('<dt')
}

export function parseBookmarkHtml(text: string): BookmarkHtmlGroup[] {
  const doc = new DOMParser().parseFromString(text, 'text/html')
  const root = doc.querySelector('dl')
  if (!root)
    return []

  const groups: BookmarkHtmlGroup[] = []
  // 根 DL 下的直接链接（没有文件夹的平铺书签）先攒着
  const loose: BookmarkHtmlSite[] = []

  const readSite = (a: Element): BookmarkHtmlSite | null => {
    const href = (a.getAttribute('href') || '').trim()
    if (!href || href.toLowerCase().startsWith('javascript:'))
      return null
    const title = (a.textContent || '').trim() || href
    return {
      title: title.length > 50 ? title.slice(0, 50) : title,
      url: href,
      description: (a.getAttribute('description') || '').trim(),
    }
  }

  const walk = (dl: Element, group: BookmarkHtmlGroup | null) => {
    Array.from(dl.children).forEach((el) => {
      const tag = el.tagName.toUpperCase()
      if (tag === 'DT') {
        const h3 = el.querySelector('h3')
        const a = el.querySelector('a')
        if (h3) {
          const g: BookmarkHtmlGroup = {
            title: ((h3.textContent || '').trim() || '未命名').slice(0, 40),
            sort: groups.length + 1,
            children: [],
          }
          groups.push(g)
          const sub = el.querySelector('dl')
            || (el.nextElementSibling && el.nextElementSibling.tagName.toUpperCase() === 'DL'
              ? el.nextElementSibling
              : null)
          if (sub)
            walk(sub, g)
        }
        else if (a) {
          const site = readSite(a)
          if (site) {
            if (group)
              group.children.push(site)
            else
              loose.push(site)
          }
        }
      }
      else if (tag === 'DL') {
        walk(el, group)
      }
    })
  }

  walk(root, null)

  // 顶层散链接归到「书签栏」，和浏览器自己显示的一致
  if (loose.length)
    groups.unshift({ title: '书签栏', sort: 1, children: loose })

  // 重排 sort，丢掉空分组
  const out = groups.filter(g => g.children.length > 0)
  out.forEach((g, i) => { g.sort = i + 1 })
  return out
}
