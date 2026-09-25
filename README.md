# esim.ltd

中文 eSIM 选型与比价站点。使用 Hugo 静态生成，部署在 Cloudflare Pages。

## 快速开始

```bash
# 安装 Hugo（单二进制，无需包管理器）
# macOS:   brew install hugo
# Ubuntu:  见下方"安装 Hugo"
# 其他:    https://gohugo.io/installation/

make build     # 构建到 public/
make serve     # 本地预览 http://localhost:1313
make test      # 运行比价逻辑测试
make check     # 提交前跑这个（构建 + 测试）
```

## 技术栈

| 层 | 选择 | 为什么 |
|---|---|---|
| 静态生成 | Hugo (extended) | 单个二进制，零依赖，34 页秒级构建 |
| 模板 | Go template | 概念比 React 少，维护成本低 |
| 样式 | 原生 CSS 单文件 | 无 Tailwind，无构建链 |
| 交互 | 原生 JS | 全站只有比价工具一个组件 |
| 数据 | `data/plans.json` | 人工维护，版本可控 |
| 部署 | Cloudflare Pages | 免费，自动 HTTPS，全球 CDN |

**核心原则：不引入任何 npm 依赖。** 整个项目 clone 下来，
只要有 hugo 二进制就能构建，不需要 `npm install`。

## 目录结构

```
.
├── hugo.toml              站点配置（多语言、SEO、输出格式）
├── data/
│   └── plans.json         ★ 资费数据库（唯一数据源）
├── content/
│   ├── destinations/      目的地页（10 个）
│   ├── providers/         品牌评测页（6 个）
│   ├── guide/             教程页
│   ├── compare/index.md   比价工具页正文
│   ├── deals/index.md     优惠页
│   └── about.md           关于 + 合规声明
├── layouts/
│   ├── _default/
│   │   ├── baseof.html    全站骨架
│   │   ├── single.html    文章页
│   │   ├── list.html      列表页（按区域分组）
│   │   └── tool.html      ★ 比价工具页
│   ├── destinations/
│   │   └── single.html    目的地页（内嵌比价表）
│   ├── index.html         首页
│   ├── index.plansjson.json  ★ 输出 /plans.json
│   └── partials/          页头页脚
├── assets/
│   ├── css/main.css       全站样式
│   └── js/compare.js      ★ 比价组件
└── scripts/
    └── test_compare.py    比价逻辑测试（26 项）
```

## 关键机制

### 数据流

```
data/plans.json
    ├─→ 构建时经 index.plansjson.json → public/plans.json
    └─→ 前端 compare.js fetch('/plans.json') → 渲染表格
```

**资费数据只有一份来源。** 改 `data/plans.json` 后重新构建即可，
不需要同时改代码和页面。

### 比价组件

`assets/js/compare.js` 分两层：

- **纯函数层**（`pricePerGb` / `matches` / `sortPlans` / `analyze`）——
  不碰 DOM，可单测
- **渲染层** —— 操作 DOM，读表单状态

纯函数通过 `window.__esimCompare` 导出，供 `scripts/test_compare.py` 测试。

### 页面级预设

目的地页的容器带 `data-dest="japan"`，组件读取后自动锁定该国，
并隐藏目的地选择器 —— 用户在目的地页不需要再选一次国家。

筛选状态同步到 URL（`?dest=japan&days=7&gb=5`），
**结果页可以直接分享给别人**。

## 日常维护

### 更新资费数据

1. 编辑 `data/plans.json`
2. **必须更新 `_updated` 字段**（合规要求，页脚和比价页都会显示）
3. `make check` 验证数据一致性
4. 提交

测试会校验：所有 `brand` 和 `dest` 引用都存在于对应的 brands / destinations 列表中。

### 新增目的地

```bash
# 1. 在 content/destinations/ 新建 markdown
#    front matter 必须有 region 字段（用于列表页分组）
# 2. 在 data/plans.json 的 destinations 数组加一条
# 3. 加对应的套餐数据
# 4. make check
```

### 新增品牌

在 `data/plans.json` 的 `brands` 数组加一条，
并在 `content/providers/` 建对应的评测页。
`url_slug` 字段决定比价表里品牌链接指向哪里。

### 新增文章

在 `content/` 对应目录放 `.md`。
Front matter 参考已有文件。

## 部署到 Cloudflare Pages

### 首次部署

1. 把项目推到 GitHub / GitLab 仓库

```bash
git init
git add .
git commit -m "初始化 esim.ltd"
git remote add origin <你的仓库地址>
git push -u origin main
```

2. 到 Cloudflare Dashboard → Workers & Pages → Create → Pages
3. 连接你的仓库
4. 构建设置：

| 项 | 值 |
|---|---|
| Framework preset | Hugo |
| Build command | `hugo --gc --minify` |
| Build output directory | `public` |
| 环境变量 | `HUGO_VERSION` = `0.140.2` |

> ⚠️ **必须设置 `HUGO_VERSION` 环境变量。**
> Cloudflare 默认的 Hugo 版本较旧，会导致构建失败。

5. 部署后，到 Pages → Custom domains 绑定 `esim.ltd`

### 后续更新

```bash
make check          # 本地验证
git push            # 自动触发部署
```

### 域名 DNS

如果 DNS 也在 Cloudflare：
Pages 会自动添加 CNAME 记录，无需手动配置。

如果 DNS 在别处：添加 CNAME 指向 `<project>.pages.dev`。

## 联盟链接接入

**怎么做**：见 [`docs/联盟链接接入指南.md`](docs/联盟链接接入指南.md)（含申请顺序、平台入口、合规红线）。

**技术操作只要一条命令**——所有购买链接都来自 `data/plans.json` 的 `brands[].buy_url`：

```bash
make aff-list                                     # 看当前接入状态

python3 scripts/set_affiliate.py saily "https://saily.com/aff/xxxx"
# → 替换 buy_url + 自动把 affiliate_link_ready 置 true
# → 品牌页那句「联盟链接接入中」提示会自动消失

python3 scripts/set_affiliate.py --revert saily   # 撤销，退回官网原址
```

改完跑 `make check`（构建 + 测试 + 联盟体检），再手动在浏览器点一遍购买按钮。

⚠️ 上线前需补 **隐私政策页**（见指南第四节）——这是目前唯一的合规缺口，
联盟平台审核时会看。

## 合规检查清单

发布前必须确认：

- [ ] 每个涉及联盟链接的页面都有披露（`has_affiliate = true` 会触发）
- [ ] 页脚有全局披露声明
- [ ] `about.md` 的合规声明有效
- [ ] **有隐私政策页**（联盟平台审核会查）
- [ ] 所有价格标注了核对日期
- [ ] 联盟链接都有 `rel="sponsored nofollow"`（`make audit` 会扫产物）
- [ ] **内容不含任何规避网络管理的表述**

## 安装 Hugo（Ubuntu）

```bash
HUGO_VERSION=0.140.2
curl -sL -o /tmp/hugo.tar.gz \
  "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.tar.gz"
tar xzf /tmp/hugo.tar.gz -C /tmp
mkdir -p ~/.local/bin
cp /tmp/hugo ~/.local/bin/hugo
chmod +x ~/.local/bin/hugo
hugo version   # 确认输出含 "extended"
```

## 测试

```bash
make test
```

覆盖 26 项断言：

- `pricePerGb` 的边界情况（无限流量、gb=0）
- `matches` 的全部筛选维度
- `sortPlans` 三种排序模式 + 不修改原数组
- `analyze` 的最优值计算
- **真实数据校验**：品牌/目的地引用完整性、`_updated` 字段存在

## 已知待办

- [ ] 图片资源（目前全站无图，可加目的地配图与装机截图）
- [ ] 英文版（`hugo.toml` 里 `languages.en` 已预留，取消注释即可）
- [ ] 邮件订阅（出境前提醒）
- [ ] Cloudflare Web Analytics token（部署后填入 `hugo.toml` 的 `cfAnalyticsToken`）
- [ ] sitemap 提交到 Google Search Console
