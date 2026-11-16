package panel

import (
	"awadaoh/api/api_v1"
	"awadaoh/api/api_v1/middleware"

	"github.com/gin-gonic/gin"
)

func InitItemIcon(router *gin.RouterGroup) {
	itemIcon := api_v1.ApiGroupApp.ApiPanel.ItemIcon
	r := router.Group("", middleware.LoginInterceptor)
	{
		r.POST("/panel/itemIcon/edit", itemIcon.Edit)
		r.POST("/panel/itemIcon/deletes", itemIcon.Deletes)
		r.POST("/panel/itemIcon/saveSort", itemIcon.SaveSort)
		r.POST("/panel/itemIcon/addMultiple", itemIcon.AddMultiple)
		r.POST("/panel/itemIcon/getSiteFavicon", itemIcon.GetSiteFavicon)
	}

	// 公开模式
	rPublic := router.Group("", middleware.PublicModeInterceptor)
	{
		rPublic.POST("/panel/itemIcon/getListByGroupId", itemIcon.GetListByGroupId)
		// 点一次 +1，用来「按使用频率排序」。访客也会调，所以放公开这组
		rPublic.POST("/panel/itemIcon/click", itemIcon.Click)
		// 客户端自己在不在内网（首页据此决定内网地址能不能直接连）
		rPublic.GET("/panel/env", itemIcon.GetClientEnv)
		rPublic.POST("/panel/env", itemIcon.GetClientEnv)
	}
}
