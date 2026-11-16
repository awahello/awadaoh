package router

import (
	"awadaoh/global"
	// "awadaoh/router/admin"
	"awadaoh/router/openness"
	"awadaoh/router/panel"
	"awadaoh/router/system"

	"github.com/gin-gonic/gin"
)

// 初始化总路由
func InitRouters(addr string) error {
	router := gin.Default()
	rootRouter := router.Group("/")
	routerGroup := rootRouter.Group("api")

	// 接口
	system.Init(routerGroup)
	panel.Init(routerGroup)
	openness.Init(routerGroup)

	// WEB文件服务
	{
		webPath := "./web"
		router.StaticFile("/", webPath+"/index.html")
		router.Static("/assets", webPath+"/assets")
		router.Static("/custom", webPath+"/custom")
		router.StaticFile("/favicon.ico", webPath+"/favicon.ico")
		router.StaticFile("/favicon.svg", webPath+"/favicon.svg")
		// 书签转换工具是纯前端单页（public/tools/bookmark.html），
		// 以前这里挂的是 awahello.github.io 上一个并不存在的页面，
		// 点进去 404 —— 现在自己托管，离线也能用
		router.StaticFile("/tools/bookmark.html", webPath+"/tools/bookmark.html")
	}

	// 上传的文件
	sourcePath := global.Config.GetValueString("base", "source_path")
	router.Static(sourcePath[1:], sourcePath)

	global.Logger.Info("Awadaoh is Started.  Listening and serving HTTP on ", addr)
	return router.Run(addr)
}
