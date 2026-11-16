// Awadaoh · 内嵌静态资源
//
// 上游用 go-bindata-assetfs 生成 bindata.go：得先 go install 两个工具，
// 生成物几万行、不可读，还得单独生成 / 入库。这里换成标准库 //go:embed：
// 零外部工具、零生成步骤，go build 直接把配置模板 / 语言包 / 版本号烘进二进制。
//
// 调用方拼的路径带 "assets/" 前缀（见 lib/cmn/base.go 的 AssetsTakeFileToPath
// 与 GetSysVersionInfo），embed.FS 里的路径不带，读之前先剥掉。
package assets

import (
	"embed"
	"strings"
)

//go:embed conf.example.ini version lang
var embedded embed.FS

// Asset 保持与 go-bindata 版一致的签名，入参形如 "assets/conf.example.ini"。
func Asset(name string) ([]byte, error) {
	return embedded.ReadFile(strings.TrimPrefix(name, "assets/"))
}
