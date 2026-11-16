package panel

import (
	"awadaoh/api/api_v1/middleware"
	"awadaoh/api/api_v1/panel"

	"github.com/gin-gonic/gin"
)

// 前台访问密码 + 书签同步 + 导出
func InitFrontLockRouter(router *gin.RouterGroup) {
	api := panel.FrontLockApi{}

	// 这两个不能挂 PublicModeInterceptor：
	// 闸门就在那个中间件里，挂上去等于「要先解锁才能解锁」，直接死锁。
	router.POST("/panel/frontLock/get", api.Get)
	router.POST("/panel/frontLock/unlock", api.Unlock)

	// 改设置要管理员
	rAdmin := router.Group("", middleware.LoginInterceptor, middleware.AdminInterceptor)
	{
		rAdmin.POST("/panel/frontLock/save", api.Save)
	}
}

func InitSyncRouter(router *gin.RouterGroup) {
	api := panel.SyncApi{}
	rAdmin := router.Group("", middleware.LoginInterceptor, middleware.AdminInterceptor)
	{
		rAdmin.POST("/panel/sync/get", api.Get)
		rAdmin.POST("/panel/sync/save", api.Save)
		rAdmin.POST("/panel/sync/run", api.Run)
		rAdmin.POST("/panel/sync/test", api.Test)
	}
}

func InitExportRouter(router *gin.RouterGroup) {
	api := panel.ExportApi{}
	// 导出等于把整份配置带走，要管理员
	rAdmin := router.Group("", middleware.LoginInterceptor, middleware.AdminInterceptor)
	{
		rAdmin.POST("/panel/export/bookmarks", api.Bookmarks)
	}
}
