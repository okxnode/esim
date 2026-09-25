#!/usr/bin/env python3
"""把 data/plans.json 里的 buy_url 批量替换为联盟追踪链接。

用法：
    # 看当前状态（不改任何东西）
    python3 scripts/set_affiliate.py --list

    # 替换单个品牌的链接（自动把 affiliate_link_ready 置为 true）
    python3 scripts/set_affiliate.py saily "https://saily.com/aff/xxxx"

    # 一次替换多个
    python3 scripts/set_affiliate.py airalo "https://airalo.pxf.io/xxxx" \
                                     holafly "https://holafly.sjv.io/xxxx"

    # 撤销：改回官网原址并标记未接入
    python3 scripts/set_affiliate.py --revert saily

    # 撤销全部
    python3 scripts/set_affiliate.py --revert all

设计说明：
- 只改 buy_url 和 affiliate_link_ready 两个字段，其余键原样保留。
- 用 json + 有序写入（indent=2, ensure_ascii=False），保持文件可读 diff。
- 会校验新链接是 https 且与 review_url 不同，拦住手滑。
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "plans.json"

# 官网原址，供 --revert 使用。与首次建库时写入的值一致。
OFFICIAL = {
    "airalo": "https://www.airalo.com/",
    "holafly": "https://esim.holafly.com/",
    "saily": "https://saily.com/",
    "nomad": "https://www.getnomad.app/",
    "ubigi": "https://www.transatel.com/ubigi/",
    "gigago": "https://www.gigago.com/",
}


def load():
    with DATA.open(encoding="utf-8") as f:
        return json.load(f)


def save(doc):
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    DATA.write_text(text, encoding="utf-8")


def find(doc, bid):
    for b in doc["brands"]:
        if b["id"] == bid:
            return b
    return None


def cmd_list(doc):
    print(f"{'品牌':<10} {'接入':<6} {'buy_url'}")
    print("-" * 72)
    for b in doc["brands"]:
        ready = "✓ 已接入" if b.get("affiliate_link_ready") else "· 官网原址"
        print(f"{b['name']:<10} {ready:<6} {b['buy_url']}")
    n = sum(1 for b in doc["brands"] if b.get("affiliate_link_ready"))
    print("-" * 72)
    print(f"{n}/{len(doc['brands'])} 个品牌已接入联盟链接")


def validate(brand, url):
    # 先判站内路径，否则错误原因会被 https 检查遮住，报错信息误导
    if url.startswith("/"):
        return "这是站内路径，buy_url 必须指向品牌方域名"
    if not re.match(r"^https://", url):
        return "链接必须以 https:// 开头"
    if url.rstrip("/") == brand["review_url"].rstrip("/"):
        return "不能把 buy_url 指到站内评测页"
    if url == brand["buy_url"]:
        return "与现有链接相同，没有变化"
    return None


def cmd_set(doc, pairs):
    changed, failed = [], []
    for bid, url in pairs:
        b = find(doc, bid)
        if not b:
            failed.append((bid, "品牌不存在"))
            continue
        err = validate(b, url)
        if err:
            failed.append((bid, err))
            continue
        old = b["buy_url"]
        b["buy_url"] = url
        b["affiliate_link_ready"] = True
        changed.append((b["name"], old, url))

    if not changed:
        for bid, why in failed:
            print(f"✗ {bid}: {why}")
        return 1

    save(doc)
    for name, old, new in changed:
        print(f"✓ {name}")
        print(f"    {old}")
        print(f" →  {new}  (affiliate_link_ready = true)")
    for bid, why in failed:
        print(f"✗ {bid}: {why}")
    print()
    print("下一步：make test && make build")
    return 0


def cmd_revert(doc, targets):
    if targets == ["all"]:
        targets = [b["id"] for b in doc["brands"]]

    changed, failed = [], []
    for bid in targets:
        b = find(doc, bid)
        if not b:
            failed.append((bid, "品牌不存在"))
            continue
        if bid not in OFFICIAL:
            failed.append((bid, "没有记录官网原址，请手动改"))
            continue
        b["buy_url"] = OFFICIAL[bid]
        b["affiliate_link_ready"] = False
        changed.append(b["name"])

    if not changed:
        for bid, why in failed:
            print(f"✗ {bid}: {why}")
        return 1

    save(doc)
    for name in changed:
        print(f"↩ {name} 已改回官网原址（affiliate_link_ready = false）")
    return 0


def main(argv):
    doc = load()

    if not argv or argv[0] in ("--list", "-l", "list"):
        cmd_list(doc)
        return 0

    if argv[0] == "--revert":
        if len(argv) < 2:
            print("用法: --revert <品牌id|all>", file=sys.stderr)
            return 2
        return cmd_revert(doc, argv[1:])

    # 成对解析 <品牌id> <链接>
    if len(argv) % 2 != 0:
        print("用法: set_affiliate.py <品牌id> <链接> [<品牌id> <链接> ...]", file=sys.stderr)
        print("      set_affiliate.py --list", file=sys.stderr)
        print("      set_affiliate.py --revert <品牌id|all>", file=sys.stderr)
        return 2

    pairs = list(zip(argv[0::2], argv[1::2]))
    return cmd_set(doc, pairs)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
