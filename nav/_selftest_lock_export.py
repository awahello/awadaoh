# -*- coding: utf-8 -*-
"""nav/server.py 自测：前台访问锁 + 导出。

跑法（项目根）：
    python nav/_selftest_lock_export.py

会起一个临时实例（临时 DATA_DIR / 随机端口），跑完自己删干净。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = 31877
ROOT = "http://127.0.0.1:%d" % PORT
ADMIN_PASS = "test-admin-pass"
FRONT_PASS = "front-8888"

ok_n = 0
bad_n = 0


def check(name, cond, extra=""):
    global ok_n, bad_n
    if cond:
        ok_n += 1
        print("  PASS  %s" % name)
    else:
        bad_n += 1
        print("  FAIL  %s  %s" % (name, extra))


def req(path, method="GET", body=None, headers=None, raw=False):
    h = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(ROOT + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=8) as resp:
            b = resp.read()
            return resp.status, (b if raw else json.loads(b or b"{}")), dict(resp.headers)
    except urllib.error.HTTPError as e:
        b = e.read()
        try:
            j = json.loads(b or b"{}")
        except Exception:
            j = {"raw": b[:200].decode("utf-8", "ignore")}
        return e.code, j, dict(e.headers)


def main():
    data_dir = tempfile.mkdtemp(prefix="navtest-")
    env = dict(os.environ)
    env.update({"DATA_DIR": data_dir, "PORT": str(PORT), "HOST": "127.0.0.1",
                "ADMIN_PASS": ADMIN_PASS, "BOOKMARK_FILE": ""})
    p = subprocess.Popen([sys.executable, os.path.join(BASE, "server.py")],
                         env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        # 等端口起来
        for _ in range(60):
            try:
                req("/api/health")
                break
            except Exception:
                time.sleep(0.15)
        else:
            raise SystemExit("服务没起来")

        print("\n[1] 默认状态：前台公开")
        st, d, _ = req("/api/config")
        cfg = d["config"]
        check("HTTP 200", st == 200, st)
        check("没锁", cfg.get("locked") is not True)
        check("有分组", len(cfg.get("groups") or []) > 0)
        check("不下发 password", "password" not in cfg)
        check("不下发 frontPass", "frontPass" not in cfg)
        check("frontLock=false", cfg.get("frontLock") is False)

        print("\n[2] 后台登录 + 打开前台锁")
        st, d, _ = req("/api/login", "POST", {"password": ADMIN_PASS})
        check("登录成功", d.get("ok") is True, d)
        admin_tok = d.get("token") or ""
        A = {"Authorization": "Bearer " + admin_tok}

        st, d, _ = req("/api/config", "PUT", {
            "frontLock": True,
            "frontPass": FRONT_PASS,
            "title": "测试导航",
        }, A)
        check("保存成功", d.get("ok") is True, d)
        check("回包 frontLock=true", d["config"].get("frontLock") is True)
        check("回包 frontPassSet=true", d["config"].get("frontPassSet") is True)
        check("回包不含 frontPass", "frontPass" not in d["config"])

        print("\n[3] 未解锁访客：只拿到锁屏字段")
        st, d, _ = req("/api/config")
        c = d["config"]
        check("locked=true", c.get("locked") is True, c)
        check("groups 为空", c.get("groups") == [])
        check("没有任何站点 url", "127.0.0.1" not in json.dumps(c) and "github.com" not in json.dumps(c))
        check("标题照给（锁屏要用）", c.get("title") == "测试导航")
        check("没有 engines", "engines" not in c)
        check("没有 sync", "sync" not in c)
        check("没有 password/frontPass", "password" not in c and "frontPass" not in c)

        print("\n[4] 解锁")
        st, d, _ = req("/api/unlock", "POST", {"password": "wrong"})
        check("错密码 401", st == 401, (st, d))
        st, d, _ = req("/api/unlock", "POST", {"password": FRONT_PASS})
        check("对密码 ok", d.get("ok") is True, d)
        ftok = d.get("token") or ""
        check("拿到 token", bool(ftok))

        st, d, _ = req("/api/config", headers={"X-Front-Token": ftok})
        c = d["config"]
        check("解锁后不是 locked", c.get("locked") is not True)
        check("解锁后分组回来了", len(c.get("groups") or []) > 0)
        check("解锁后仍不含 password", "password" not in c)

        st, d, _ = req("/api/config?ft=" + ftok)
        check("?ft= 也能解锁", d["config"].get("locked") is not True)

        print("\n[5] 前台 token 不能当后台用")
        st, d, _ = req("/api/config", "PUT", {"title": "hacked"},
                       {"Authorization": "Bearer " + ftok})
        check("PUT 被拒 401", st == 401, (st, d))
        st, d, _ = req("/api/export?format=json", headers={"Authorization": "Bearer " + ftok})
        check("导出被拒 401", st == 401, (st, d))

        print("\n[6] 导出书签 HTML")
        st, body, hdr = req("/api/export?format=html", headers=A, raw=True)
        txt = body.decode("utf-8")
        check("HTTP 200", st == 200, st)
        check("Content-Disposition attachment", "attachment" in hdr.get("Content-Disposition", ""), hdr)
        check("文件名 .html", ".html" in hdr.get("Content-Disposition", ""))
        check("Netscape 头", txt.startswith("<!DOCTYPE NETSCAPE-Bookmark-file-1>"), txt[:60])
        check("有 DL 结构", "<DL><p>" in txt and "</DL><p>" in txt)
        check("有 H3 分组", "<H3" in txt)
        check("有 A 链接", '<A HREF="https://github.com"' in txt)
        check("带 emoji 分组名", "⭐ 常用" in txt)
        check("不泄露后台密码", ADMIN_PASS not in txt)
        check("不泄露前台密码", FRONT_PASS not in txt)

        print("\n[7] 导出时排除隐藏分组")
        # 先把「工具」组设成 hidden
        st, d, _ = req("/api/config", headers=A)
        cur = d["config"]
        groups = cur["groups"]
        groups[1]["hidden"] = True
        req("/api/config", "PUT", {"groups": groups}, A)

        st, body, _ = req("/api/export?format=html&hidden=0", headers=A, raw=True)
        t2 = body.decode("utf-8")
        check("hidden=0 时不写隐藏分组", "工具" not in t2, t2[-300:])
        check("hidden=0 时还留可见分组", "常用" in t2)
        st, body, _ = req("/api/export?format=html&hidden=1", headers=A, raw=True)
        check("hidden=1 时包含隐藏分组", "工具" in body.decode("utf-8"))

        print("\n[8] 导出 JSON 备份")
        st, body, hdr = req("/api/export?format=json", headers=A, raw=True)
        j = json.loads(body.decode("utf-8"))
        check("是合法 JSON", isinstance(j, dict))
        check("app 字段", j.get("app") == "awadaoh-nav")
        check("有 groups", len(j.get("groups") or []) == len(groups))
        check("JSON 不含 password", "password" not in body.decode("utf-8"))
        check("JSON 不含 frontPass 值", FRONT_PASS not in body.decode("utf-8"))
        check("文件名 .json", ".json" in hdr.get("Content-Disposition", ""))

        print("\n[9] 关掉前台锁 + 清空前台密码")
        st, d, _ = req("/api/config", "PUT", {"frontLock": False, "frontPass": ""}, A)
        check("保存成功", d.get("ok") is True, d)
        check("frontLock=false", d["config"].get("frontLock") is False)
        check("frontPassSet=false", d["config"].get("frontPassSet") is False)
        st, d, _ = req("/api/config")
        check("访客直接拿到分组", len(d["config"].get("groups") or []) > 0)
        st, d, _ = req("/api/unlock", "POST", {"password": "x"})
        check("锁关着时 unlock 直接放行", d.get("ok") is True and d.get("locked") is False, d)

        print("\n[10] 前台密码留空 = 用后台密码")
        req("/api/config", "PUT", {"frontLock": True, "frontPass": ""}, A)
        st, d, _ = req("/api/unlock", "POST", {"password": ADMIN_PASS})
        check("后台密码能解锁", d.get("ok") is True, d)
        st, d, _ = req("/api/unlock", "POST", {"password": FRONT_PASS})
        check("旧前台密码失效", st == 401, (st, d))

    finally:
        p.terminate()
        try:
            out = p.communicate(timeout=5)[0].decode("utf-8", "ignore")
        except Exception:
            out = ""
        shutil.rmtree(data_dir, ignore_errors=True)
        print("\n---- 服务日志（尾部） ----")
        print("\n".join(out.strip().splitlines()[-8:]))

    print("\n==== %d passed / %d failed ====" % (ok_n, bad_n))
    return 1 if bad_n else 0


if __name__ == "__main__":
    sys.exit(main())
