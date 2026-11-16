package global

import (
	"sync"
	"time"
)

// 前台访问密码的解锁凭据。
//
// 为什么不复用后台 token：
//   后台 token 能改配置、能看内网真实地址，权限大得多；
//   前台锁的密码往往更简单（很多人直接设成 1234），
//   拿到它不该等于拿到后台。所以两套凭据分开存。
//
// 为什么只放内存：
//   这是「这台浏览器这次解锁了」的会话状态，不是配置。
//   重启即失效，正好和后台 token 一个待遇，也不用担心落库泄露。
var frontTokens sync.Map // token -> 过期时间戳(int64)

// FrontTokenIssue 发一个解锁凭据
func FrontTokenIssue(token string, ttl time.Duration) {
	frontTokens.Store(token, time.Now().Add(ttl).Unix())
}

// FrontTokenOK 校验解锁凭据是否有效
func FrontTokenOK(token string) bool {
	if token == "" {
		return false
	}
	v, ok := frontTokens.Load(token)
	if !ok {
		return false
	}
	exp, _ := v.(int64)
	if exp < time.Now().Unix() {
		frontTokens.Delete(token)
		return false
	}
	return true
}
