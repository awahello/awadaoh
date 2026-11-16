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


// 同名分组合并。
// Chrome 的 "其他书签" 里经常也有一个叫「书签栏」的文件夹，
// 不合并就会出现两个同名分组，导进去看着像重复导入了一遍。
function mergeByTitle(groups: BookmarkHtmlGroup[]): BookmarkHtmlGroup[] {
  const index = new Map<string, BookmarkHtmlGroup>()
  const out: BookmarkHtmlGroup[] = []
  for (const g of groups) {
    const hit = index.get(g.title)
    if (hit)
      hit.children.push(...g.children)
    else {
      index.set(g.title, g)
      out.push(g)
    }
  }
  out.forEach((g, i) => { g.sort = i + 1 })
  return out.filter(g => g.children.length > 0)
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

  // 同名分组合并 + 重排 sort，丢掉空分组
  return mergeByTitle(groups)
}

// ── Chrome / Edge 的 Bookmarks JSON ────────────────────────────
//
// 用户在 chrome://bookmarks → 导出，或者直接拷 profile 里的
// "Bookmarks" 文件，拿到的就是这种结构：
//   { "roots": { "bookmark_bar": {children:[...]}, "other": {...}, "synced": {...} } }
// 每个节点 type=folder 有 children，type=url 有 url/name。
//
// 分组规则和 nav / 后端同步一致：根节点下的直接链接归到根名分组，
// 每个子文件夹独立成组（嵌套再深的文件夹也拍平成自己的组）。

export function isChromeBookmarksJson(text: string): boolean {
  const head = (text || '').trim().slice(0, 200)
  if (!head.startsWith('{'))
    return false
  // 面板自己的配置也是 JSON，靠这几个特征区分
  return text.includes('"bookmark_bar"') || (text.includes('"roots"') && text.includes('"children"'))
}

const ROOT_NAMES: Record<string, string> = {
  bookmark_bar: '书签栏',
  other: '其他书签',
  synced: '移动设备书签',
}

export function parseChromeBookmarksJson(text: string): BookmarkHtmlGroup[] {
  let data: any
  try {
    data = JSON.parse(text)
  }
  catch {
    return []
  }
  const roots = data?.roots
  if (!roots || typeof roots !== 'object')
    return []

  const out: BookmarkHtmlGroup[] = []

  const walk = (node: any, name: string) => {
    const sites: BookmarkHtmlSite[] = []
    const subs: { node: any, name: string }[] = []
    const children = Array.isArray(node?.children) ? node.children : []
    for (const ch of children) {
      if (ch?.type === 'url' && ch.url) {
        const title = String(ch.name || ch.url)
        sites.push({
          title: title.length > 50 ? title.slice(0, 50) : title,
          url: String(ch.url),
          description: '',
        })
      }
      else if (ch?.type === 'folder') {
        subs.push({ node: ch, name: (String(ch.name || '').trim() || '未命名').slice(0, 40) })
      }
    }
    if (sites.length)
      out.push({ title: name.slice(0, 40), sort: out.length + 1, children: sites })
    // 递归放在 append 之后，避免引用被扩容后的数组下标
    for (const sub of subs)
      walk(sub.node, sub.name)
  }

  for (const key of ['bookmark_bar', 'other', 'synced']) {
    if (roots[key])
      walk(roots[key], ROOT_NAMES[key])
  }

  return mergeByTitle(out)
}
