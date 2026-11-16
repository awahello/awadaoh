package base

import (
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

// ClientIsIntranet 决定「内网地址下发还是给一把锁」，判定错了要么泄露内网地址、
// 要么内网用户点不开自己的 NAS，所以这里把直连和反代两种情况都钉住。
func TestClientIsIntranet(t *testing.T) {
	gin.SetMode(gin.TestMode)

	cases := []struct {
		name   string
		remote string
		xff    string
		want   bool
	}{
		{"内网直连", "192.168.1.20:5555", "", true},
		{"十段内网直连", "10.0.0.8:5555", "", true},
		{"回环直连", "127.0.0.1:5555", "", true},
		{"公网直连", "8.8.8.8:5555", "", false},
		{"IPv6 回环", "[::1]:5555", "", true},
		// 反代场景：对端是 docker 网桥（私网），真实客户端放在 X-Forwarded-For
		{"反代透传内网客户端", "172.17.0.1:5555", "192.168.1.20", true},
		{"反代透传公网客户端", "172.17.0.1:5555", "1.2.3.4", false},
	}

	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			r := gin.New()
			got := false
			r.GET("/", func(gc *gin.Context) {
				got = ClientIsIntranet(gc)
			})
			req := httptest.NewRequest("GET", "/", nil)
			req.RemoteAddr = c.remote
			if c.xff != "" {
				req.Header.Set("X-Forwarded-For", c.xff)
			}
			r.ServeHTTP(httptest.NewRecorder(), req)
			if got != c.want {
				t.Errorf("remote=%s xff=%s => %v, want %v", c.remote, c.xff, got, c.want)
			}
		})
	}
}
