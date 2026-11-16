package middleware

import (
	"awadaoh/api/api_v1/common/apiReturn"
	"awadaoh/api/api_v1/common/base"
	"awadaoh/global"
	"awadaoh/lib/cmn/systemSetting"
	"awadaoh/models"

	"github.com/gin-gonic/gin"
)

// 公开访问模式（访客模式）
// [有token将自动登录，无token/过期将使用公开账号，不可以与LoginInterceptor一起使用]
func PublicModeInterceptor(c *gin.Context) {

	// 获得token
	cToken := c.GetHeader("token")
	token := ""

	// 没有token信息视为未登录
	if cToken != "" {
		var ok bool
		token, ok = global.CUserToken.Get(cToken)
		if ok && token != "" {
			// 直接返回缓存的用户信息
			if userInfo, success := global.UserToken.Get(token); success {
				global.Logger.Debug("缓存的用户TOKEN:", token)
				c.Set("userInfo", userInfo)
				return
			} else {
				global.Logger.Debug("数据库查询TOKEN:", token)
				mUser := models.User{}
				// 去库中查询是否存在该用户
				if info, err := mUser.GetUserInfoByToken(token); err == nil && info.Token != "" && info.ID != 0 {
					global.Logger.Debug("数据库查询用户:", info.ID)
					// 通过 设置当前用户信息
					global.UserToken.SetDefault(info.Token, info)
					global.CUserToken.SetDefault(cToken, token)
					c.Set("userInfo", info)
					return
				} else {
					global.Logger.Debug("数据库查询用户失败", token)
				}
			}
		} else {
			global.Logger.Debug("token为空或者不OK")
		}
	} else {
		global.Logger.Debug("cToken不存在")
	}

	// 获取公开账号的信息
	var userId *uint
	if err := global.SystemSetting.GetValueByInterface(systemSetting.PANEL_PUBLIC_USER_ID, &userId); err == nil && userId != nil {
		userInfo := models.User{}
		if err := global.Db.First(&userInfo, "id=?", userId).Error; err != nil {
			apiReturn.ErrorCode(c, 1001, global.Lang.Get("login.err_token_expire"), nil)
			c.Abort()
			return
		}
		global.Logger.Debug("访客用户TOKEN:", token)
		global.Logger.Debug("访客用户ID:", userInfo.ID)
		c.Set("userInfo", userInfo)
		c.Set(base.GIN_GET_VISIT_MODE, base.VISIT_MODE_PUBLIC)
		return
	}

	// 没配公开账号 —— 兜底用第一个管理员。
	// panel_public_user_id 默认是空的，以前这里直接回 1001，前端就只剩一片空白导航：
	// 新装实例打开域名没内容，还得先进后台手动选一次「公开访问账号」才有东西。
	// 「打开就是导航」要求零配置可用，所以这里自己挑一个管理员顶上。
	// 管理员想换访客身份时，后台选一次就会写入 panel_public_user_id，走上面那条分支。
	fallback := models.User{}
	if err := global.Db.Where("role = ?", 1).Where("status = ?", 1).
		Order("id asc").First(&fallback).Error; err == nil && fallback.ID != 0 {
		global.Logger.Debug("未配置访客账号，兜底使用第一个管理员，ID:", fallback.ID)
		c.Set("userInfo", fallback)
		c.Set(base.GIN_GET_VISIT_MODE, base.VISIT_MODE_PUBLIC)
		return
	}

	global.Logger.Debug("访客用户不存在:", userId, " ", token)
	apiReturn.ErrorCode(c, 1001, global.Lang.Get("login.err_token_expire"), nil)
	c.Abort()
}
