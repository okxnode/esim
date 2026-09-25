#!/usr/bin/env python3
"""联盟链接体检。只读，不修改任何文件。

检查项：
  1. 每个品牌都有 buy_url，且是 https
  2. buy_url 与 review_url 不混用（购买不得指回站内）
  3. affiliate_link_ready=true 的品牌，链接必须已带追踪特征
     （追踪参数 / 短域名 / 非官网原址）—— 防止"标记了但忘了换链接"
  4. 站内评测页必须存在对应的 content/providers/<id>.md
  5. 声明要做联盟的品牌，commission / cookie_days / network 必须齐全
  6. 构建产物里的 <a> 是否都带 rel="sponsored"

用法：python3 scripts/audit_affiliate.py [--dist public]
退出码：0 = 无问题；1 = 有警告
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "plans.json"

# 判断"不是官网原址"的追踪特征
TRACK_PATTERNS = [
    r"[?&](aff|ref|referral|partner|utm_source|irclickid|clickid|pxf_|sjv_)=",
    r"//[a-z0-9-]+\.(pxf|sjv|dpbolvw|jdoqocy|kqzyfj|anrdoezrs|tkqlhce|awin1|linksynergy)\.",
]

problems = []
warnings = []


def bad(msg):
    problems.append(msg)


def warn(msg):
    warnings.append(msg)


def looks_tracked(url):
    return any(re.search(p, url, re.I) for p in TRACK_PATTERNS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", default="", help="构建产物目录，给了就顺带做 rel 检查")
    args = ap.parse_args()

    doc = json.loads(DATA.read_text(encoding="utf-8"))
    brands = doc["brands"]

    if not doc.get("_updated"):
        bad("data/plans.json 缺少 _updated 字段")

    ready = 0
    for b in brands:
        bid = b["id"]
        name = b.get("name", bid)

        # 1. buy_url 形态
        url = b.get("buy_url", "")
        if not url:
            bad(f"{name}: 缺少 buy_url")
        elif not url.startswith("https://"):
            bad(f"{name}: buy_url 不是 https（{url}）")

        # 2. 职责不混用
        if url and url.rstrip("/") == b.get("review_url", "").rstrip("/"):
            bad(f"{name}: buy_url 与 review_url 相同，用户会绕回站内")

        # 3. 标记与实际一致
        if b.get("affiliate_link_ready"):
            ready += 1
            if not looks_tracked(url):
                warn(f"{name}: 标记为已接入，但链接看不出追踪特征（{url}）")

        # 4. 测评页存在
        if b.get("review_url"):
            slug = b["review_url"].strip("/").split("/")[-1]
            if not (ROOT / "content" / "providers" / f"{slug}.md").exists():
                bad(f"{name}: 评测页 content/providers/{slug}.md 不存在")

        # 5. 联盟字段完整
        if b.get("affiliate"):
            for k in ("commission", "cookie_days", "network"):
                if not b.get(k):
                    warn(f"{name}: 声明联盟但没有 {k}")

    # 6. 产物里的外链 rel
    if args.dist:
        dist = ROOT / args.dist
        if not dist.exists():
            warn(f"产物目录不存在：{dist}")
        else:
            ext = re.findall(r"<a\s[^>]*href=[\"']?(https?://[^\"'\s>]+)[^>]*>", "", )
            # 抓所有 http(s) 外链的整个 a 标签
            tags = re.findall(r"<a\s[^>]*?href=[\"']?https?://[^>]*>", "\n".join(
                p.read_text(encoding="utf-8", errors="ignore")
                for p in dist.rglob("*.html")
            ))
            brand_hosts = tuple(
                re.sub(r"^https?://", "", b.get("buy_url", "")).split("/")[0]
                for b in brands if b.get("buy_url")
            )
            for tag in tags:
                if any(h and h in tag for h in brand_hosts):
                    if "sponsored" not in tag:
                        warn(f"产物中品牌链接缺少 rel=sponsored：{tag[:110]}")

    # 输出
    print("=" * 66)
    print(f"联盟链接体检 · 品牌 {len(brands)} 个 · 已接入 {ready} 个")
    print("=" * 66)
    if problems:
        print("\n【必须修】")
        for m in problems:
            print(f"  ✗ {m}")
    if warnings:
        print("\n【建议修】")
        for m in warnings:
            print(f"  ! {m}")
    if not problems and not warnings:
        print("\n✓ 全部通过")

    print()
    return 1 if problems else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
