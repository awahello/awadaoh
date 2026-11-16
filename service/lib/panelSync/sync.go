package panelSync

import (
	"crypto/sha1"
	"fmt"
	"encoding/hex"
	"encoding/json"
	"net/url"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"sync"
	"time"

	"awadaoh/global"
	"awadaoh/lib/cmn/systemSetting"
	"awadaoh/models"
	"awadaoh/models/datatype"
)

// 谷歌书签同步
//
// 原理：Chrome 登录 Google 账号后的书签，最终都会落到本地 profile 的
// "Bookmarks" JSON 文件里 —— Google 同步只是把这个文件改掉。
// 所以盯住这个文件的 sha1，一变就重新解析入库，效果就等于「和收藏夹同步」，
// 不需要任何 Google API / OAuth，也不用让用户在浏览器里装东西。
//
// 和 nav 那边（nav/server.py 的 sync_watcher）是同一套思路，
// 只是这边要写进数据库，所以多了「同名分组保留 id / 可见性」的处理。

const (
	ModeMerge   = "merge"   // 并入：保留手动建的分组
	ModeReplace = "replace" // 整表替换：只留书签里的
)

// Site 解析出来的一个书签
type Site struct {
	Title string
	URL   string
}

// Group 解析出来的一个分组
type Group struct {
	Name  string
	Sites []Site
}

// 运行时状态。和配置分开：配置在 system_setting 里，这个是「这一轮跑了没」
type State struct {
	Hash      string `json:"hash"`
	LastCheck int64  `json:"lastCheck"`
	LastSync  int64  `json:"lastSync"`
	LastError string `json:"lastError"`
	Found     bool   `json:"found"`
}

var (
	mu    sync.Mutex
	state = State{}
	lock  sync.Mutex // 同一时间只允许一个同步在跑
)

func GetState() State {
	mu.Lock()
	defer mu.Unlock()
	return state
}

func setState(f func(s *State)) {
	mu.Lock()
	defer mu.Unlock()
	f(&state)
}

// ── 配置读写 ──────────────────────────────────────────

func GetSetting() systemSetting.PanelSync {
	s := systemSetting.PanelSync{Interval: 300, Mode: ModeMerge}
	if err := global.SystemSetting.GetValueByInterface(systemSetting.PANEL_SYNC, &s); err != nil {
		return s
	}
	if s.Interval < 30 {
		s.Interval = 30
	}
	if s.Mode != ModeReplace {
		s.Mode = ModeMerge
	}
	return s
}

func SaveSetting(s systemSetting.PanelSync) error {
	if s.Interval < 30 {
		s.Interval = 30
	}
	if s.Mode != ModeReplace {
		s.Mode = ModeMerge
	}
	return global.SystemSetting.Set(systemSetting.PANEL_SYNC, s)
}

// ── 路径探测 ──────────────────────────────────────────

// DefaultPaths 常见 Chrome / Edge / Chromium 的 Bookmarks 位置
func DefaultPaths() []string {
	out := []string{}
	if runtime.GOOS == "windows" {
		bases := []string{os.Getenv("LOCALAPPDATA"), filepath.Join(os.Getenv("USERPROFILE"), "AppData", "Local")}
		for _, b := range bases {
			if b == "" {
				continue
			}
			out = append(out,
				filepath.Join(b, "Google", "Chrome", "User Data", "Default", "Bookmarks"),
				filepath.Join(b, "Google", "Chrome Beta", "User Data", "Default", "Bookmarks"),
				filepath.Join(b, "Microsoft", "Edge", "User Data", "Default", "Bookmarks"),
				filepath.Join(b, "Chromium", "User Data", "Default", "Bookmarks"),
			)
		}
	} else {
		h, _ := os.UserHomeDir()
		out = append(out,
			filepath.Join(h, ".config", "google-chrome", "Default", "Bookmarks"),
			filepath.Join(h, ".config", "chromium", "Default", "Bookmarks"),
			filepath.Join(h, ".config", "microsoft-edge", "Default", "Bookmarks"),
			filepath.Join(h, "Library", "Application Support", "Google", "Chrome", "Default", "Bookmarks"),
		)
	}
	// docker 常见挂载点
	out = append(out, "/bookmarks/Bookmarks", "/data/Bookmarks", "/chrome/Bookmarks")
	return out
}

// ResolvePath 决定这次读哪个文件：配置里有就用配置的，否则自动探测
func ResolvePath(s systemSetting.PanelSync) string {
	p := strings.TrimSpace(s.Path)
	if p != "" {
		p = os.ExpandEnv(p)
		if st, err := os.Stat(p); err == nil {
			if st.IsDir() {
				for _, name := range []string{"Bookmarks", "bookmarks"} {
					q := filepath.Join(p, name)
					if fi, e := os.Stat(q); e == nil && !fi.IsDir() {
						return q
					}
				}
			}
			return p
		}
	}
	for _, c := range DefaultPaths() {
		if fi, err := os.Stat(c); err == nil && !fi.IsDir() {
			return c
		}
	}
	return p
}

// DisplayPath 把绝对路径折成可展示的形式，别把本机目录结构贴到界面上
func DisplayPath(p string) string {
	if p == "" {
		return ""
	}
	ap, err := filepath.Abs(p)
	if err != nil {
		return p
	}
	home, _ := os.UserHomeDir()
	if home != "" && strings.HasPrefix(ap, home) {
		return "~" + strings.TrimPrefix(ap, home)
	}
	if wd, err := os.Getwd(); err == nil && strings.HasPrefix(ap, wd) {
		return "." + strings.TrimPrefix(ap, wd)
	}
	return p
}

// ── 解析 Chrome Bookmarks JSON ────────────────────────

type chromeNode struct {
	Type     string       `json:"type"`
	Name     string       `json:"name"`
	URL      string       `json:"url"`
	Children []chromeNode `json:"children"`
}

type chromeRoot struct {
	Roots map[string]chromeNode `json:"roots"`
}

var rootNames = map[string]string{
	"bookmark_bar": "书签栏",
	"other":        "其他书签",
	"synced":       "移动设备书签",
}

// ParseChromeBookmarks Chrome 的 Bookmarks JSON → 分组。
// 规则和 nav 一致：根节点下的直接链接归到根名分组，每个子文件夹独立成组。
func ParseChromeBookmarks(raw []byte) ([]Group, error) {
	var b chromeRoot
	if err := json.Unmarshal(raw, &b); err != nil {
		return nil, err
	}

	out := []Group{}
	var walk func(n chromeNode, name string)
	walk = func(n chromeNode, name string) {
		g := Group{Name: name}
		subs := []chromeNode{}
		for _, ch := range n.Children {
			switch ch.Type {
			case "url":
				if strings.TrimSpace(ch.URL) != "" {
					g.Sites = append(g.Sites, Site{Title: ch.Name, URL: ch.URL})
				}
			case "folder":
				subs = append(subs, ch)
			}
		}
		if len(g.Sites) > 0 {
			out = append(out, g)
		}
		// 递归放在 append 之后：这里不取 &out[i]，避免切片扩容后指针失效
		for _, sub := range subs {
			nm := strings.TrimSpace(sub.Name)
			if nm == "" {
				nm = "未命名"
			}
			walk(sub, nm)
		}
	}

	for _, key := range []string{"bookmark_bar", "other", "synced"} {
		root, ok := b.Roots[key]
		if !ok {
			continue
		}
		walk(root, rootNames[key])
	}
	return out, nil
}

// ── 入库 ──────────────────────────────────────────────

// defaultIcon 给同步来的站点配个默认图标：favicon.im 按域名取，取不到前端会退化成首字母
func defaultIcon(u string) string {
	host := ""
	if p, err := url.Parse(u); err == nil {
		host = p.Hostname()
	}
	if host == "" {
		return ""
	}
	info := datatype.ItemIconIconInfo{
		ItemType:        2,
		Src:             "https://favicon.im/" + host + "?larger=true",
		BackgroundColor: "#2a2a2a6b",
	}
	b, err := json.Marshal(info)
	if err != nil {
		return ""
	}
	return string(b)
}

// ApplyGroups 把解析结果写进库。
// merge：同名分组保留 id / 可见性，只换里面的站点；手动建的分组不动
// replace：这个用户的分组和站点整表重建
func ApplyGroups(userId uint, groups []Group, mode string) (int, int, error) {
	db := global.Db
	if len(groups) == 0 {
		return 0, 0, nil
	}

	if mode == ModeReplace {
		var ids []uint
		if err := db.Model(&models.ItemIconGroup{}).Where("user_id = ?", userId).Pluck("id", &ids).Error; err != nil {
			return 0, 0, err
		}
		if len(ids) > 0 {
			if err := db.Where("item_icon_group_id in ? AND user_id = ?", ids, userId).
				Delete(&models.ItemIcon{}).Error; err != nil {
				return 0, 0, err
			}
		}
		if err := db.Where("user_id = ?", userId).Delete(&models.ItemIconGroup{}).Error; err != nil {
			return 0, 0, err
		}
	}

	// 现有分组按标题索引
	exist := []models.ItemIconGroup{}
	if err := db.Where("user_id = ?", userId).Find(&exist).Error; err != nil {
		return 0, 0, err
	}
	byTitle := map[string]models.ItemIconGroup{}
	for _, g := range exist {
		byTitle[g.Title] = g
	}

	nGroup, nSite := 0, 0
	sortIdx := 0
	for _, g := range groups {
		sortIdx++
		var groupId uint
		if old, ok := byTitle[g.Name]; ok {
			// 同名：保留 id 和可见性，只把里面的站点换掉
			groupId = old.ID
			if err := db.Where("item_icon_group_id = ? AND user_id = ?", groupId, userId).
				Delete(&models.ItemIcon{}).Error; err != nil {
				return nGroup, nSite, err
			}
		} else {
			ng := models.ItemIconGroup{
				Title:   g.Name,
				Sort:    sortIdx,
				Visible: models.GROUP_VISIBLE_PUBLIC,
				UserId:  userId,
			}
			if err := db.Create(&ng).Error; err != nil {
				return nGroup, nSite, err
			}
			groupId = ng.ID
			nGroup++
		}

		for i, s := range g.Sites {
			title := strings.TrimSpace(s.Title)
			if title == "" {
				title = s.URL
			}
			if len(title) > 50 {
				title = title[:50]
			}
			item := models.ItemIcon{
				IconJson:        defaultIcon(s.URL),
				Title:           title,
				Url:             s.URL,
				OpenMethod:      2, // 新窗口打开，和浏览器书签的习惯一致
				Sort:            i + 1,
				ItemIconGroupId: int(groupId),
				UserId:          userId,
			}
			if err := db.Create(&item).Error; err != nil {
				return nGroup, nSite, err
			}
			nSite++
		}
	}

	return nGroup, nSite, nil
}

// ── 跑一次 ────────────────────────────────────────────

// RunOnce 读文件 → 解析 → 入库。force=false 时文件没变就直接跳过。
func RunOnce(userId uint, force bool) map[string]interface{} {
	lock.Lock()
	defer lock.Unlock()

	s := GetSetting()
	path := ResolvePath(s)
	setState(func(st *State) { st.LastCheck = time.Now().Unix() })

	if path == "" {
		msg := "没有配置书签文件，也没自动探测到 Chrome / Edge 的 Bookmarks"
		setState(func(st *State) { st.Found = false; st.LastError = msg })
		s.LastResult = msg
		_ = SaveSetting(s)
		return map[string]interface{}{"ok": false, "error": msg, "pathDisplay": ""}
	}

	fi, err := os.Stat(path)
	if err != nil || fi.IsDir() {
		msg := "找不到书签文件：" + DisplayPath(path)
		setState(func(st *State) { st.Found = false; st.LastError = msg })
		s.LastResult = msg
		_ = SaveSetting(s)
		return map[string]interface{}{"ok": false, "error": msg, "pathDisplay": DisplayPath(path)}
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		msg := "读取失败：" + err.Error()
		setState(func(st *State) { st.LastError = msg })
		s.LastResult = msg
		_ = SaveSetting(s)
		return map[string]interface{}{"ok": false, "error": msg, "pathDisplay": DisplayPath(path)}
	}

	sum := sha1.Sum(raw)
	h := hex.EncodeToString(sum[:])
	if !force && h == GetState().Hash {
		return map[string]interface{}{"ok": true, "skipped": true, "pathDisplay": DisplayPath(path)}
	}

	groups, err := ParseChromeBookmarks(raw)
	if err != nil {
		msg := "解析失败：" + err.Error()
		setState(func(st *State) { st.LastError = msg })
		s.LastResult = msg
		_ = SaveSetting(s)
		return map[string]interface{}{"ok": false, "error": msg, "pathDisplay": DisplayPath(path)}
	}
	if len(groups) == 0 {
		msg := "文件里没解析到书签"
		setState(func(st *State) { st.LastError = msg })
		s.LastResult = msg
		_ = SaveSetting(s)
		return map[string]interface{}{"ok": false, "error": msg, "pathDisplay": DisplayPath(path)}
	}

	nG, nS, err := ApplyGroups(userId, groups, s.Mode)
	if err != nil {
		msg := "写库失败：" + err.Error()
		setState(func(st *State) { st.LastError = msg })
		s.LastResult = msg
		_ = SaveSetting(s)
		return map[string]interface{}{"ok": false, "error": msg, "pathDisplay": DisplayPath(path)}
	}

	s.Path = path
	s.LastSync = time.Now().Unix()
	s.LastResult = "同步成功"
	setState(func(st *State) {
		st.Hash = h
		st.Found = true
		st.LastSync = s.LastSync
		st.LastError = ""
	})
	_ = SaveSetting(s)

	return map[string]interface{}{
		"ok":         true,
		"pathDisplay": DisplayPath(path),
		"groups":     len(groups),
		"sites":      nS,
		"newGroups":  nG,
		"skipped":    false,
	}
}

// StartWatcher 后台线程：10 秒一拍，按配置里的 interval 决定这一拍要不要真去读文件。
// 这样在后台改间隔立刻生效，不用等上一轮睡完。
func StartWatcher(userId func() uint) {
	go func() {
		for {
			func() {
				defer func() {
					if r := recover(); r != nil {
						global.Logger.Error("书签同步线程异常: ", r)
					}
				}()
				s := GetSetting()
				if !s.Enabled {
					return
				}
				last := GetState().LastCheck
				if last != 0 && time.Since(time.Unix(last, 0)) < time.Duration(s.Interval)*time.Second {
					return
				}
				if uid := userId(); uid != 0 {
					RunOnce(uid, false)
				}
			}()
			time.Sleep(10 * time.Second)
		}
	}()
}

// SortedGroups 给导出用：按 sort 排好
func SortedGroups(groups []models.ItemIconGroup) []models.ItemIconGroup {
	sort.SliceStable(groups, func(i, j int) bool { return groups[i].Sort < groups[j].Sort })
	return groups
}

// MarkPushed 记一次「扩展推过来」的结果，让后台「当前状态」里能看到，
// 不用去翻日志确认扩展到底推没推。
func MarkPushed(groups, sites int) {
	s := GetSetting()
	s.LastSync = time.Now().Unix()
	s.LastResult = fmt.Sprintf("扩展推送：%d 个分组 / %d 个站点", groups, sites)
	_ = SaveSetting(s)
	setState(func(st *State) {
		st.LastSync = s.LastSync
		st.LastError = ""
	})
}
