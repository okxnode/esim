#!/usr/bin/env python3
"""esim.ltd 比价逻辑测试。

compare.js 的核心计算是纯函数，这里用 node 加载并验证。
不依赖任何测试框架，直接 python 驱动 node 执行断言脚本。

用法: python3 scripts/test_compare.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS_PATH = ROOT / "assets" / "js" / "compare.js"
DATA_PATH = ROOT / "data" / "plans.json"

# 在 node 里执行测试：桩掉浏览器 API，加载 compare.js，取出纯函数
TEST_HARNESS = r"""
// ---- 桩浏览器环境 ----
global.window = { location: { pathname: '/compare/', search: '' } };
global.document = {
  readyState: 'complete',
  addEventListener: function () {},
  getElementById: function () { return null; },
  createElement: function () { return { setAttribute: function(){}, appendChild: function(){} }; },
  createTextNode: function () { return {}; },
};
global.URLSearchParams = class {
  constructor() { this.m = {}; }
  has(k) { return k in this.m; }
  get(k) { return this.m[k]; }
};

// 通过环境变量传路径，避免 -e 模式的 argv 索引陷阱
const JS_FILE = process.env.TEST_JS;
const DATA_FILE = process.env.TEST_DATA;

// 加载被测代码（IIFE 会挂在 window 上）
const fs = require('fs');
eval(fs.readFileSync(JS_FILE, 'utf8'));

const C = global.window.__esimCompare;
if (!C) { console.error('FAIL: 未导出 __esimCompare'); process.exit(1); }

let pass = 0, fail = 0;
function check(name, cond) {
  if (cond) { pass++; console.log('  ok   ' + name); }
  else { fail++; console.log('  FAIL ' + name); }
}

// ================================================================ 用例

console.log('\n[pricePerGb]');
check('有限流量: 10 / 5GB = 2',
  C.pricePerGb({ price: 10, gb: 5, unlimited: false }) === 2);
check('无限流量返回 null',
  C.pricePerGb({ price: 27.5, gb: 0, unlimited: true }) === null);
check('gb=0 且非无限也返回 null',
  C.pricePerGb({ price: 10, gb: 0, unlimited: false }) === null);

console.log('\n[matches]');
const p = { dest: 'japan', days: 7, gb: 5, price: 12, unlimited: false, hotspot: true };
const f = { dest: 'japan', days: 7, needGb: 5, unlimitedOk: true, hotspotOnly: false };

check('完全匹配', C.matches(p, f) === true);
check('目的地不符被排除',
  C.matches(p, Object.assign({}, f, { dest: 'korea' })) === false);
check('需求天数超过套餐时长被排除',
  C.matches(p, Object.assign({}, f, { days: 10 })) === false);
check('需求流量超过套餐流量被排除',
  C.matches(p, Object.assign({}, f, { needGb: 10 })) === false);
check('不接受无限流量时无限套餐被排除',
  C.matches({ dest:'japan', days:7, gb:0, price:27, unlimited:true, hotspot:false },
            Object.assign({}, f, { unlimitedOk: false })) === false);
check('无限流量套餐通过流量检查',
  C.matches({ dest:'japan', days:7, gb:0, price:27, unlimited:true, hotspot:false }, f) === true);
check('要求热点时不支持热点的被排除',
  C.matches({ dest:'japan', days:7, gb:0, price:27, unlimited:true, hotspot:false },
            Object.assign({}, f, { hotspotOnly: true })) === false);

console.log('\n[sortPlans]');
const plans = [
  { brand:'holafly', price:27.5, gb:0,   unlimited:true  },
  { brand:'airalo',  price:21.0, gb:10,  unlimited:false },
  { brand:'saily',   price:12.99, gb:5,  unlimited:false },
];
const byValue = C.sortPlans(plans, 'value');
check('按性价比: 每GB最低的排最前',
  byValue[0].brand === 'airalo');           // 2.1/GB 最低
check('按性价比: 无限流量排最后',
  byValue[byValue.length - 1].brand === 'holafly');

const byPrice = C.sortPlans(plans, 'price');
check('按总价: 最便宜的排最前', byPrice[0].brand === 'saily');
check('按总价: 最贵的排最后', byPrice[2].brand === 'holafly');

check('排序不修改原数组', plans[0].brand === 'holafly');

console.log('\n[analyze]');
const a = C.analyze([
  { brand:'saily',  price:8.99,  gb:3,  unlimited:false },
  { brand:'airalo', price:21.0,  gb:10, unlimited:false },
  { brand:'holafly',price:27.5,  gb:0,  unlimited:true  },
]);
check('count 正确', a.count === 3);
check('cheapest 是最低总价', a.cheapest.brand === 'saily');
check('bestValue 是最低每GB (airalo 2.1)', a.bestValue.brand === 'airalo');
check('unlimited 数量为 1', a.unlimited.length === 1);
check('空数组返回 null', C.analyze([]) === null);

console.log('\n[真实数据]');
const data = JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
const realPlans = data.plans;
check('数据非空', realPlans.length > 0);

const jp7 = realPlans.filter(function (x) {
  return C.matches(x, { dest:'japan', days:7, needGb:5, unlimitedOk:true, hotspotOnly:false });
});
check('日本 7天 5GB 能筛出结果', jp7.length > 0);
console.log('       → 筛出 ' + jp7.length + ' 个套餐');

const jpHotspot = jp7.filter(function (x) { return x.hotspot; });
check('日本 7天 5GB 要求热点后结果减少', jpHotspot.length < jp7.length);
console.log('       → 要求热点后剩 ' + jpHotspot.length + ' 个');

const brandIds = data.brands.map(function (b) { return b.id; });
const orphan = realPlans.filter(function (x) { return brandIds.indexOf(x.brand) === -1; });
check('所有套餐引用的品牌都存在', orphan.length === 0);

const destIds = data.destinations.map(function (d) { return d.id; });
const orphanDest = realPlans.filter(function (x) { return destIds.indexOf(x.dest) === -1; });
check('所有套餐引用的目的地都存在', orphanDest.length === 0);

// 数据时间戳必须存在（合规要求）
check('数据带 _updated 字段', typeof data._updated === 'string' && data._updated.length === 10);

// 每个品牌必须有可用的购买链接（否则比价表会出现空按钮）
const noBuy = data.brands.filter(function (b) {
  return !b.buy_url || !/^https:\/\//.test(b.buy_url);
});
check('所有品牌都有 https 购买链接', noBuy.length === 0);
if (noBuy.length) console.log('       → 缺失: ' + noBuy.map(function(b){return b.id;}).join(', '));

// 购买链接与站内评测页必须是两个不同的地址
const sameUrl = data.brands.filter(function (b) {
  return b.buy_url === b.review_url;
});
check('购买链接未与评测页混淆', sameUrl.length === 0);

// 评测页路径必须存在
const noReview = data.brands.filter(function (b) {
  return !b.review_url || b.review_url.indexOf('/providers/') !== 0;
});
check('所有品牌有站内评测页路径', noReview.length === 0);

console.log('\n' + '='.repeat(46));
console.log('通过 ' + pass + ' / 失败 ' + fail);
process.exit(fail === 0 ? 0 : 1);
"""


def main() -> int:
    if not JS_PATH.exists():
        print(f"找不到 {JS_PATH}", file=sys.stderr)
        return 1
    if not DATA_PATH.exists():
        print(f"找不到 {DATA_PATH}", file=sys.stderr)
        return 1

    proc = subprocess.run(
        ["node", "-e", TEST_HARNESS],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "TEST_JS": str(JS_PATH),
            "TEST_DATA": str(DATA_PATH),
        },
    )
    print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
