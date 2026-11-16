#!/usr/bin/env python3
"""CI 里构建并推送多架构镜像（amd64 + arm64）。

为什么不用 docker/build-push-action：
  action 失败时 GitHub 只把 buildx 那句
    process "/bin/sh -c set -eu; go build ..." did not complete successfully: exit code: 1
  写进 annotation，编译器到底报了什么一个字都看不到；job log 又要 admin 权限才给读。
  这里自己跑 buildx，把完整日志 tee 到文件，失败时把尾部同时写进
    - annotation（匿名可读，单条 4KB）
    - job summary（跟着 check-run 一起上传）
  这样「为什么挂」这件事不用再猜。

为什么用 Python 而不是 bash：
  上一版是 bash，`set -e` 从 runner 注入进来，数组拼参数 + heredoc 一有风吹草动
  整个 step 就以 exit 2 死掉，日志一个字没写出来 —— 比不知道原因更糟。
"""

import os
import subprocess
import sys

LOG_PATH = "/tmp/build.log"
TAIL_SUMMARY = 6000
TAIL_ANNOTATION = 3500


def env_lines(name):
    return [l.strip() for l in os.environ.get(name, "").splitlines() if l.strip()]


def write_summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 写 job summary 失败: {exc}", flush=True)


def error_excerpt(data, limit=3000):
    """从完整日志里挑出真正的报错行。

    只截尾部是不够的：编译器报错前面往往有十几行 note，尾部窗口里只剩
    `note: in expansion of macro ...`，看不出到底哪一行错了。这里按
    error / Error / FAILED / undefined reference 抓关键行，再带上它前 2 行上下文。
    """
    lines = data.splitlines()
    keys = ("error:", "Error:", "ERROR:", "FAILED:", "undefined reference", "cannot find", "No such file")
    picked = []
    seen = set()
    for i, line in enumerate(lines):
        if any(k in line for k in keys):
            for j in range(max(0, i - 2), min(len(lines), i + 1)):
                if j in seen:
                    continue
                seen.add(j)
                picked.append(lines[j][:300])
            if len(picked) > 60:
                break
    if not picked:
        return ""
    return "\n".join(picked)[:limit]


def emit_annotation(tail, rc):
    # GitHub 的 workflow command 里 %、\r、\n 都要转义，否则整条消息被丢掉
    msg = tail.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    sys.stdout.write(f"::error title=镜像构建失败 (exit {rc})::{msg}\n")
    sys.stdout.flush()


def dump(reason, rc):
    """把日志尾部倒到 summary + annotation。任何异常都不许再往外抛。"""
    print(f"[fail] {reason} (exit={rc})", flush=True)
    data = ""
    try:
        if os.path.isfile(LOG_PATH):
            with open(LOG_PATH, encoding="utf-8", errors="replace") as f:
                data = f.read()
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 读日志失败: {exc}", flush=True)

    tail = data[-TAIL_SUMMARY:]
    if not tail:
        tail = f"(没有拿到 buildx 日志)\n原因: {reason}\n"

    excerpt = error_excerpt(data)

    write_summary(
        "### 镜像构建失败\n\n"
        f"原因: {reason} (exit={rc})\n\n"
        "#### 报错行\n\n```\n" + (excerpt or "(没匹配到 error 行)").replace("```", "'''") + "\n```\n\n"
        "#### 日志尾部\n\n```\n" + tail.replace("```", "'''") + "\n```\n"
    )

    # annotation 单条上限 4KB：优先放报错行，剩下的位置补尾部
    body = excerpt
    if body:
        room = TAIL_ANNOTATION - len(body) - 40
        if room > 200:
            body = body + "\n\n---- 日志尾部 ----\n" + data[-room:]
    else:
        body = data[-TAIL_ANNOTATION:]
    emit_annotation(body[:TAIL_ANNOTATION], rc)


def main():
    tags = env_lines("TAGS")
    labels = env_lines("LABELS")
    if not tags:
        dump("TAGS 为空，metadata 步骤没产出标签", 1)
        return 1

    cmd = [
        "docker", "buildx", "build",
        "--file", "./Dockerfile",
        "--platform", "linux/amd64,linux/arm64",
        # --no-cache 是故意的：上一版 amd64 与 arm64 共用一份 type=gha 缓存，
        # 推出来的 arm64 镜像里躺着 amd64 二进制，用户 docker compose up 直接
        # exec format error。宁可慢，也不要串架构。
        "--no-cache",
        "--provenance=false",
        "--output", "type=image,push=true",
    ]
    for t in tags:
        cmd += ["-t", t]
    for l in labels:
        cmd += ["--label", l]
    cmd.append(".")

    print("+ " + " ".join(cmd), flush=True)

    try:
        ver = subprocess.run(["docker", "buildx", "version"], capture_output=True, text=True)
        print(ver.stdout.strip() or ver.stderr.strip(), flush=True)
    except Exception as exc:  # noqa: BLE001
        dump(f"buildx 不可用: {exc}", 127)
        return 127

    rc = 1
    try:
        with open(LOG_PATH, "w", encoding="utf-8", errors="replace") as log:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log.write(line)
            rc = proc.wait()
    except Exception as exc:  # noqa: BLE001
        dump(f"启动 buildx 失败: {exc}", 1)
        return 1

    if rc != 0:
        dump("buildx build 返回非零", rc)
        return rc

    print("[ok] buildx 构建并推送成功", flush=True)
    for t in tags:
        print(f"  -> {t}", flush=True)

    try:
        out = subprocess.run(
            ["docker", "buildx", "imagetools", "inspect", tags[0]],
            capture_output=True, text=True, timeout=120,
        )
        print(out.stdout or out.stderr, flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] imagetools inspect 失败: {exc}", flush=True)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        dump(f"脚本自身异常: {exc}", 1)
        sys.exit(1)
