package netguard

import "testing"

func TestIsPrivateURL(t *testing.T) {
	cases := []struct {
		url  string
		want bool
	}{
		// 内网 / 本机
		{"http://192.168.1.10:5000/", true},
		{"http://10.0.0.5:8006/", true},
		{"https://172.16.3.4/", true},
		{"http://127.0.0.1:3055/", true},
		{"http://localhost:8080/", true},
		{"http://[::1]/", true},
		{"http://169.254.1.1/", true},
		{"http://100.64.0.1/", true},   // CGNAT
		{"http://0.0.0.0/", true},      // 0.0.0.0/8
		{"http://nas/", true},          // 单标签
		{"http://nas.local/", true},    // .local
		{"http://router.lan/", true},   // .lan
		{"http://wiki.corp/", true},    // .corp
		{"file:///D:/share/", true},    // 本机协议
		{"smb://nas/share", true},      // 局域网共享
		{"http://printer.localdomain/", true},

		// 公网
		{"https://www.baidu.com/", false},
		{"https://github.com/awahello/awadaoh", false},
		{"http://8.8.8.8/", false},
		{"https://www.akkdiy.cn", false},
		{"", false},
	}
	for _, c := range cases {
		if got := IsPrivateURL(c.url); got != c.want {
			t.Errorf("IsPrivateURL(%q) = %v, want %v", c.url, got, c.want)
		}
	}
}

func TestMaskURL(t *testing.T) {
	if got, p := MaskURL("http://192.168.1.1/"); got != "" || !p {
		t.Errorf("内网地址应打码为空串, got %q private=%v", got, p)
	}
	if got, p := MaskURL("https://www.akkdiy.cn"); got != "https://www.akkdiy.cn" || p {
		t.Errorf("公网地址应原样返回, got %q private=%v", got, p)
	}
}
