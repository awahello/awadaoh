package panel

import (
	"crypto/subtle"
	"time"

	"awadaoh/api/api_v1/common/apiReturn"
	"awadaoh/global"
	"awadaoh/lib/cmn"
	"awadaoh/lib/cmn/systemSetting"

	"github.com/gin-gonic/gin"
)

// 前台访问密码
//
// 语义和 nav 那边一致：开了之后，访客打开首页先看到一把锁，
// 服务端在 PublicModeInterceptor 里直接回 1008，分组和站点一个都不下发。
type FrontLockApi struct {
}

// 读设置。读不到就当没开 —— 新装实例不该被一个空配置挡住。
func getFrontLockSetting() systemSetting.FrontLockSetting {
	s := systemSetting.FrontLockSetting{}
	if err := global.SystemSetting.GetValueByInterface(systemSetting.PANEL_FRONT_LOCK, &s); err != nil {
		return systemSetting.FrontLockSetting{}
	}
	return s
}

// 公开接口：前端只需要知道「要不要挂锁」和「我这次解没解锁」。
// 密码本身绝不下发，连长度都不给。
func (a FrontLockApi) Get(c *gin.Context) {
	s := getFrontLockSetting()
	apiReturn.SuccessData(c, gin.H{
		"enabled":  s.Enabled && s.Password != "",
		"unlocked": global.FrontTokenOK(c.GetHeader("X-Front-Token")),
	})
}

// 解锁：密码对了就发一个只够浏览的凭据，12 小时有效。
func (a FrontLockApi) Unlock(c *gin.Context) {
	var req struct {
		Password string `json:"password"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		apiReturn.ErrorParamFomat(c, err.Error())
		return
	}

	s := getFrontLockSetting()
	if !s.Enabled || s.Password == "" {
		// 锁没开就直接放行，免得前端缓存了旧状态卡在锁屏上
		apiReturn.SuccessData(c, gin.H{"token": "", "enabled": false})
		return
	}

	// 定长比较，别用 == 泄露前缀匹配长度
	if subtle.ConstantTimeCompare([]byte(req.Password), []byte(s.Password)) != 1 {
		time.Sleep(400 * time.Millisecond) // 简单限速，和后台登录一致
		apiReturn.ErrorCode(c, 1008, "访问密码不正确", nil)
		return
	}

	token := cmn.BuildRandCode(32, cmn.RAND_CODE_MODE2)
	global.FrontTokenIssue(token, 12*time.Hour)
	apiReturn.SuccessData(c, gin.H{"token": token, "enabled": true})
}

// 管理端：改设置。
// Password 传空表示「不改」，避免前端每次保存都把密码清掉。
func (a FrontLockApi) Save(c *gin.Context) {
	var req struct {
		Enabled  bool   `json:"enabled"`
		Password string `json:"password"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		apiReturn.ErrorParamFomat(c, err.Error())
		return
	}

	s := getFrontLockSetting()
	s.Enabled = req.Enabled
	if p := req.Password; p != "" {
		s.Password = p
	}
	if s.Enabled && s.Password == "" {
		apiReturn.Error(c, "开启前请先设置访问密码")
		return
	}

	if err := global.SystemSetting.Set(systemSetting.PANEL_FRONT_LOCK, s); err != nil {
		apiReturn.ErrorDatabase(c, err.Error())
		return
	}
	apiReturn.SuccessData(c, gin.H{
		"enabled":     s.Enabled,
		"hasPassword": s.Password != "",
	})
}
