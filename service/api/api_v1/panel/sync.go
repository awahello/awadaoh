package panel

import (
	"os"

	"awadaoh/api/api_v1/common/apiReturn"
	"awadaoh/global"
	"awadaoh/lib/cmn/systemSetting"
	"awadaoh/lib/panelSync"
	"awadaoh/models"

	"github.com/gin-gonic/gin"
)

// 谷歌书签同步的接口层。真正的活都在 lib/panelSync 里：
// 解析 Chrome 的 Bookmarks JSON、写库、后台线程盯文件。
type SyncApi struct {
}

// 同步到哪个账号下：优先用「公开访问账号」，没配就用第一个管理员。
// 导航站是单用户的，面板可能是多用户，所以必须挑一个固定的目标。
func syncTargetUser() models.User {
	var uid *uint
	if err := global.SystemSetting.GetValueByInterface(systemSetting.PANEL_PUBLIC_USER_ID, &uid); err == nil && uid != nil {
		u := models.User{}
		if err := global.Db.First(&u, "id = ?", *uid).Error; err == nil {
			return u
		}
	}
	u := models.User{}
	_ = global.Db.Where("role = ?", 1).Order("id asc").First(&u).Error
	return u
}

// Get 当前同步配置 + 运行时状态
func (a SyncApi) Get(c *gin.Context) {
	s := panelSync.GetSetting()
	path := panelSync.ResolvePath(s)
	st := panelSync.GetState()

	info := gin.H{
		"enabled":     s.Enabled,
		"path":        s.Path,
		"pathDisplay": panelSync.DisplayPath(path),
		"resolved":    path,
		"exists":      false,
		"interval":    s.Interval,
		"mode":        s.Mode,
		"lastSync":    s.LastSync,
		"lastResult":  s.LastResult,
		"state":       st,
		"candidates":  panelSync.DefaultPaths()[:6],
	}
	if path != "" {
		if fi, err := os.Stat(path); err == nil && !fi.IsDir() {
			info["exists"] = true
			info["size"] = fi.Size()
			info["mtime"] = fi.ModTime().Unix()
		}
	}
	apiReturn.SuccessData(c, info)
}

// Save 保存配置。开了就立刻跑一次，省得用户还要点「立即同步」。
func (a SyncApi) Save(c *gin.Context) {
	var req systemSetting.PanelSync
	if err := c.ShouldBindJSON(&req); err != nil {
		apiReturn.ErrorParamFomat(c, err.Error())
		return
	}
	if err := panelSync.SaveSetting(req); err != nil {
		apiReturn.ErrorDatabase(c, err.Error())
		return
	}
	res := gin.H{"saved": true}
	if req.Enabled {
		if u := syncTargetUser(); u.ID != 0 {
			res["sync"] = panelSync.RunOnce(u.ID, true)
		}
	}
	apiReturn.SuccessData(c, res)
}

// Run 立即同步一次（force=true，不看 hash）
func (a SyncApi) Run(c *gin.Context) {
	u := syncTargetUser()
	if u.ID == 0 {
		apiReturn.Error(c, "没有可用的账号，先创建管理员")
		return
	}
	apiReturn.SuccessData(c, panelSync.RunOnce(u.ID, true))
}

// Test 只检测文件，不写库。用来告诉用户「我到底读的是哪个文件」
func (a SyncApi) Test(c *gin.Context) {
	s := panelSync.GetSetting()
	var req struct {
		Path string `json:"path"`
	}
	_ = c.ShouldBindJSON(&req)
	if req.Path != "" {
		s.Path = req.Path
	}
	path := panelSync.ResolvePath(s)
	if path == "" {
		apiReturn.SuccessData(c, gin.H{"ok": false, "error": "没有配置路径，也没自动探测到 Chrome 的 Bookmarks 文件"})
		return
	}
	fi, err := os.Stat(path)
	if err != nil || fi.IsDir() {
		apiReturn.SuccessData(c, gin.H{
			"ok": false, "error": "文件不存在",
			"pathDisplay": panelSync.DisplayPath(path), "resolved": path,
		})
		return
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		apiReturn.SuccessData(c, gin.H{
			"ok": false, "error": "读取失败：" + err.Error(),
			"pathDisplay": panelSync.DisplayPath(path),
		})
		return
	}
	groups, err := panelSync.ParseChromeBookmarks(raw)
	if err != nil {
		apiReturn.SuccessData(c, gin.H{
			"ok": false, "error": "解析失败：" + err.Error(),
			"pathDisplay": panelSync.DisplayPath(path),
		})
		return
	}
	n := 0
	names := make([]string, 0, len(groups))
	for _, g := range groups {
		n += len(g.Sites)
		if len(names) < 40 {
			names = append(names, g.Name)
		}
	}
	apiReturn.SuccessData(c, gin.H{
		"ok":          true,
		"pathDisplay": panelSync.DisplayPath(path),
		"resolved":    path,
		"groups":      len(groups),
		"sites":       n,
		"names":       names,
		"mtime":       fi.ModTime().Unix(),
		"size":        fi.Size(),
	})
}
