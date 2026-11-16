package middleware

import (
	"strconv"
	"strings"

	"awadaoh/global"
	"awadaoh/lib/cmn"
	"awadaoh/models"
)

// 面板重启后，内存里的 cToken → bToken 映射就没了。
//
// 但 cToken 是构造出来的：uuid + "-" + md5(md5("userId" + 用户ID))。
// 尾巴那 32 位是用户 ID 的确定性哈希 —— 所以哪怕映射表空了，
// 也能拿它跟库里的用户比一遍把身份找回来。
//
// 不这么做的后果（已经踩过）：每次重启镜像，所有人静默变成访客，
// 内网地址全被打成 🔒，用户看到的是「我连了内网怎么还不行」。
func userFromCToken(cToken string) (models.User, bool) {
	idx := strings.LastIndex(cToken, "-")
	if idx < 0 || idx == len(cToken)-1 {
		return models.User{}, false
	}
	suffix := cToken[idx+1:]
	// 尾巴必须是 32 位小写 hex，否则不可能是 md5 —— 挡住伪造 token 触发的全表扫描
	if len(suffix) != 32 {
		return models.User{}, false
	}
	for _, r := range suffix {
		if !((r >= '0' && r <= '9') || (r >= 'a' && r <= 'f')) {
			return models.User{}, false
		}
	}

	users := []models.User{}
	if err := global.Db.Find(&users).Error; err != nil {
		return models.User{}, false
	}
	for _, u := range users {
		if u.Token == "" || u.ID == 0 {
			continue
		}
		if cmn.Md5(cmn.Md5("userId"+strconv.Itoa(int(u.ID)))) == suffix {
			// 顺手把映射补回缓存，下一个请求就不用再遍历了
			global.CUserToken.SetDefault(cToken, u.Token)
			global.UserToken.SetDefault(u.Token, u)
			return u, true
		}
	}
	return models.User{}, false
}
