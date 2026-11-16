// Package netguard 判定地址是不是内网 / 本机 / 保留地址。
//
// 移植自 nav/server.py 的 is_private_url()，两边规则保持一致：
//
//	1. file:// smb:// \\host 这类天生只能内网访问的协议
//	2. hostname 是 IP 字面量 → 私有段 / 回环 / 链路本地 / 保留 / CGNAT 100.64/10 / 0.0.0.0/8
//	3. hostname 是 localhost 或 .local .lan .internal 等后缀
//	4. hostname 没有点（单标签，如 http://nas/）→ 内网
//
// 不做 DNS 复查（批量导入时会被拖慢），要开就显式调 IsPrivateURLWithDNS。
package netguard

import (
	"net"
	"net/url"
	"strings"
)

var privateTLDs = map[string]bool{
	"local": true, "localhost": true, "lan": true, "internal": true,
	"intranet": true, "intra": true, "corp": true, "home": true,
	"localdomain": true, "svc": true, "cluster": true, "priv": true, "private": true,
}

// IsPrivateURL 快速判定（纯字符串 + IP 段，不发 DNS 请求）。
func IsPrivateURL(raw string) bool {
	low := strings.ToLower(strings.TrimSpace(raw))
	if low == "" {
		return false
	}
	// 本机 / 局域网共享协议
	if strings.HasPrefix(low, "file://") || strings.HasPrefix(low, "smb://") || strings.HasPrefix(low, "\\\\") {
		return true
	}

	h := hostOf(low)
	if h == "" {
		return false
	}
	if v, ok := ipPrivate(h); ok {
		return v
	}
	switch h {
	case "localhost", "localhost.localdomain", "ip6-localhost":
		return true
	}
	if !strings.Contains(h, ".") {
		return true // http://nas/ 、http://router/
	}
	last := h[strings.LastIndex(h, ".")+1:]
	if privateTLDs[last] {
		return true
	}
	if strings.HasSuffix(h, ".home.arpa") || strings.HasSuffix(h, ".in-addr.arpa") {
		return true
	}
	return false
}

// IsPrivateURLWithDNS 域名看着像公网时再查一次解析结果，命内网段也算内网。
// 公司内网域名（nas.corp.example.com 解析到 10.x）只能靠这一步抓出来。
func IsPrivateURLWithDNS(raw string) bool {
	if IsPrivateURL(raw) {
		return true
	}
	h := hostOf(strings.ToLower(strings.TrimSpace(raw)))
	if h == "" {
		return false
	}
	if _, ok := ipPrivate(h); ok {
		return false // 已经是 IP 字面量，上面判过了
	}
	addrs, err := net.LookupHost(h)
	if err != nil {
		return false // 解析不了就当公网，不阻断
	}
	for _, a := range addrs {
		if v, ok := ipPrivate(a); ok && v {
			return true
		}
	}
	return false
}

// IsPrivateIP 判定一个裸 IP 是不是内网 / 回环 / 保留地址。
// 用来判「访问面板的人自己是不是在内网」——c.ClientIP() 直接丢进来即可。
func IsPrivateIP(s string) bool {
	s = strings.TrimSpace(strings.Trim(s, "[]"))
	if s == "" {
		return false
	}
	if v, ok := ipPrivate(s); ok {
		return v
	}
	return false
}

// MaskURL 给访客看的地址：内网就返回空串（前端据此渲染 🔒 锁卡），否则原样返回。
func MaskURL(raw string) (masked string, isPrivate bool) {
	if IsPrivateURL(raw) {
		return "", true
	}
	return raw, false
}

func hostOf(raw string) string {
	u, err := url.Parse(raw)
	if err != nil || u.Hostname() == "" {
		// 没有协议的裸地址（nas.local:5000）补一个再解析
		if u2, err2 := url.Parse("http://" + strings.TrimPrefix(raw, "//")); err2 == nil {
			return strings.Trim(strings.ToLower(u2.Hostname()), ".")
		}
		return ""
	}
	return strings.ToLower(strings.Trim(u.Hostname(), "."))
}

// ipPrivate 返回 (是否内网, 是否 IP 字面量)
func ipPrivate(s string) (bool, bool) {
	ip := net.ParseIP(s)
	if ip == nil {
		return false, false
	}
	if ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast() ||
		ip.IsLinkLocalMulticast() || ip.IsInterfaceLocalMulticast() ||
		ip.IsUnspecified() || ip.IsMulticast() {
		return true, true
	}
	if v4 := ip.To4(); v4 != nil {
		// 保留段自己补：CGNAT 100.64.0.0/10、0.0.0.0/8
		if v4[0] == 100 && v4[1] >= 64 && v4[1] <= 127 {
			return true, true
		}
		if v4[0] == 0 {
			return true, true
		}
		return false, true
	}
	return false, true
}
