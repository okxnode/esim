# esim.ltd 常用命令
# 依赖：hugo (extended) 0.140+、node 18+、python3

HUGO ?= hugo
PORT ?= 1313

.PHONY: help build serve test check audit aff-list deploy-check clean

help:
	@echo "可用命令："
	@echo "  make build        构建到 public/"
	@echo "  make serve        本地预览 (http://localhost:$(PORT))"
	@echo "  make test         运行比价逻辑测试"
	@echo "  make audit        联盟链接体检（只读）"
	@echo "  make aff-list     查看各品牌联盟链接接入状态"
	@echo "  make check        构建 + 测试 + 体检，提交前跑这个"
	@echo "  make deploy-check 检查 Cloudflare Pages 部署配置"
	@echo "  make clean        清理构建产物"
	@echo ""
	@echo "接入联盟链接："
	@echo "  python3 scripts/set_affiliate.py saily \"https://saily.com/aff/xxxx\""
	@echo "  python3 scripts/set_affiliate.py --revert saily"

build:
	$(HUGO) --gc --minify

serve:
	$(HUGO) server --port $(PORT) --bind 127.0.0.1

test:
	python3 scripts/test_compare.py

audit:
	python3 scripts/audit_affiliate.py --dist public

aff-list:
	python3 scripts/set_affiliate.py --list

# 提交前固定跑这一串
check: build test audit
	@echo "✓ 构建、测试、联盟体检全部通过"

deploy-check:
	@echo "→ 检查必要文件"
	@test -f hugo.toml && echo "  ✓ hugo.toml"
	@test -f data/plans.json && echo "  ✓ data/plans.json"
	@test -f .gitignore && echo "  ✓ .gitignore"
	@echo "→ 检查 plans.json 是否会被生成"
	@grep -q '"PlansJSON"' hugo.toml && echo "  ✓ PlansJSON 输出已配置" || echo "  ✗ PlansJSON 未配置"
	@echo "→ 检查公开域名"
	@grep -q 'baseURL = "https://esim.ltd/"' hugo.toml && echo "  ✓ baseURL 指向 esim.ltd" || echo "  ⚠ baseURL 需确认"
	@echo "→ 联盟链接状态"
	@python3 scripts/set_affiliate.py --list | tail -1

clean:
	rm -rf public resources/_gen .hugo_build.lock
