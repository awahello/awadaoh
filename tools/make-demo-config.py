#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成截图用的演示配置（不碰真实 data/config.json）"""
import json, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else ".shots/data/config.json"

# (分类名, 图标 emoji, [(站点名, 域名)])
DEMO = [
    ("工具", "🛠", [("控制台", "console.cloud.google.com"), ("面板", "vercel.com"), ("日志", "grafana.com"),
                    ("监控", "uptime.kuma.pet"), ("Docker", "hub.docker.com"), ("数据库", "supabase.com"),
                    ("NAS", "synology.com"), ("图表", "excalidraw.com"), ("终端", "iterm2.com"), ("代理", "clash.razord.top")]),
    ("服务器", "🖥", [("主机", "hetzner.com"), ("容器", "portainer.io"), ("用户", "auth0.com"), ("防火墙", "cloudflare.com"),
                      ("定时", "crontab.guru"), ("流量", "analytics.google.com"), ("镜像", "quay.io"), ("运维", "ansible.com"),
                      ("密钥", "1password.com"), ("备份", "restic.net")]),
    ("视频类", "🎬", [("影视", "youtube.com"), ("直播", "twitch.tv"), ("录制", "obsproject.com"), ("下载", "qbittorrent.org"),
                      ("媒体库", "jellyfin.org"), ("字幕", "subhd.tv"), ("播放器", "mpv.io"), ("追番", "bilibili.com"),
                      ("投屏", "kodi.tv"), ("合集", "imdb.com")]),
    ("游戏", "🎮", [("Steam", "store.steampowered.com"), ("Epic", "epicgames.com"), ("攻略", "gamefaqs.gamespot.com"),
                    ("联机", "playstation.com")]),
    ("大佬学习", "📚", [("MDN", "developer.mozilla.org"), ("Go 文档", "go.dev"), ("Python", "docs.python.org"),
                        ("Rust", "doc.rust-lang.org"), ("Kaggle", "kaggle.com"), ("论文", "arxiv.org"),
                        ("GitHub", "github.com")]),
    ("数据和可视化", "📊", [("Superset", "superset.apache.org"), ("Metabase", "metabase.com"),
                            ("Jupyter", "jupyter.org"), ("D3", "d3js.org")]),
    ("博物馆和艺术", "🏛", [("The Met", "metmuseum.org"), ("MoMA", "moma.org"), ("故宫", "dpm.org.cn")]),
    ("声音", "🎧", [("音乐", "music.163.com"), ("播客", "podcasts.apple.com"), ("电台", "radio.garden")]),
    ("服务站点", "☁️", [("Cloudflare", "dash.cloudflare.com"), ("GitHub Pages", "pages.github.com"),
                        ("Vercel", "vercel.com"), ("Netlify", "netlify.com"), ("对象存储", "console.aws.amazon.com"),
                        ("短信", "twilio.com")]),
    ("跨境", "🌏", [("Stripe", "dashboard.stripe.com"), ("PayPal", "business.paypal.com"), ("汇率", "xe.com")]),
    ("DIY", "🔧", [("树莓派", "raspberrypi.com"), ("ESPHome", "esphome.io"), ("Home Assistant", "home-assistant.io"),
                   ("3D 打印", "printables.com")]),
    ("建站与博客", "✍️", [("WordPress", "wordpress.org"), ("Halo", "halo.run"), ("Hexo", "hexo.io")]),
    ("杂项", "🗂", [("待办", "todoist.com"), ("笔记", "notion.so"), ("密码", "bitwarden.com")]),
]

groups = []
for gi, (gname, gicon, sites) in enumerate(DEMO):
    sl = []
    for si, (title, host) in enumerate(sites):
        sl.append({
            "id": "s%02d%02d" % (gi, si),
            "title": title,
            "url": "https://%s/" % host,
            "desc": "",
            "icon": "https://favicon.im/%s?larger=true" % host,
            "private": False,
        })
    groups.append({"id": "g%02d" % gi, "name": gname, "icon": gicon, "order": gi,
                   "hidden": False, "collapsed": False, "sites": sl})

# 内网服务：用来展示「访客端打码」效果，域名/IP 都是常见私有段
PRIVATE = [
    ("服务器", [("NAS 面板", "http://192.168.1.10:5000/"),
                ("路由器", "http://192.168.1.1/"),
                ("PVE", "https://10.0.0.5:8006/")]),
]
for gname, sites in PRIVATE:
    for g in groups:
        if g["name"] != gname:
            continue
        for title, url in sites:
            g["sites"].append({
                "id": "p" + title[:2],
                "title": title,
                "url": url,
                "desc": "",
                "icon": "",
                "private": True,
            })

cfg = {
    "title": "Awadaoh 导航",
    "subtitle": "自托管起始页",
    "footer": "www.akkdiy.cn",
    "footerUrl": "https://www.akkdiy.cn",
    "password": "demo",
    "theme": "dark",
    "engines": [
        {"id": "bing", "name": "Bing", "url": "https://www.bing.com/search?q=%s"},
        {"id": "google", "name": "Google", "url": "https://www.google.com/search?q=%s"},
        {"id": "baidu", "name": "百度", "url": "https://www.baidu.com/s?wd=%s"},
    ],
    "engine": "bing",
    "privateMode": "mask",
    "privateDns": False,
    "groups": groups,
    "sync": {"enabled": True, "path": "", "interval": 300, "mode": "merge",
             "lastSync": 0, "lastResult": ""},
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
print("写入 %s：%d 个分类 / %d 个站点" % (OUT, len(groups), sum(len(g["sites"]) for g in groups)))
