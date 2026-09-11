#!/bin/bash
# akshareios 发布脚本：版本校验 → 构建 wheel → 解包自检 → 同步 MianShu Skill
#
# 用法：uv run --with build bash scripts/release.sh  或直接 bash scripts/release.sh（需 uv 在 PATH）
# 假设：本仓库位于 ~/Desktop/akshareios，MianShu 位于 ~/Desktop/MianShu
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
INIT_VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' akshareios/__init__.py)
SKILL_DIR="$HOME/Desktop/MianShu/MianshuAgent/MianshuAgentClient/MianshuAgentClient/Skills/akshareios"

# 1. 版本一致性：防「源码一个版本、元数据另一个版本」
[ "$VERSION" = "$INIT_VERSION" ] || { echo "❌ 版本不一致: pyproject=$VERSION vs __init__=$INIT_VERSION"; exit 1; }

# 2. 工作区提示：防打包脏（构建内容与提交不一致的 wheel 是 0.5.1 事故排查时的头号嫌疑）
if [ -n "$(git status --short . 2>/dev/null)" ]; then
    echo "⚠️  工作区有未提交改动，wheel 内容可能与 git 提交不一致："
    git status --short .
fi

# 3. 构建
rm -rf dist/
uv build --wheel 2>&1 | tail -1
WHEEL="dist/akshareios-${VERSION}-py3-none-any.whl"
[ -f "$WHEEL" ] || { echo "❌ 未生成 $WHEEL"; exit 1; }

# 4. 解包自检：版本号、关键模块齐全
# 注意：不用 `unzip | grep -q`——pipefail 下 grep 提前退出会让 unzip 吃 SIGPIPE 误报失败
INIT_SRC=$(unzip -p "$WHEEL" akshareios/__init__.py)
case "$INIT_SRC" in
    *"__version__ = \"$VERSION\""*) ;;
    *) echo "❌ wheel 内 __init__.py 版本号不是 $VERSION"; exit 1 ;;
esac
LISTING=$(unzip -l "$WHEEL")
for mod in _convert _datacenter _fallback _fallback_sina _fallback_tx _http _pagination _symbols \
           board_industry index_hist stock_finance stock_fund_flow stock_hist stock_holders \
           stock_info stock_list stock_min stock_spot stock_zt; do
    case "$LISTING" in
        *"akshareios/${mod}.py"*) ;;
        *) echo "❌ wheel 缺少 ${mod}.py"; exit 1 ;;
    esac
done
echo "✅ 自检通过: $WHEEL ($(wc -c < "$WHEEL" | tr -d ' ') bytes)"

# 5. 同步 MianShu Skill：替换 wheel + SKILL.md 版本号同步
[ -d "$SKILL_DIR" ] || { echo "❌ 未找到 MianShu Skill 目录: $SKILL_DIR"; exit 1; }
rm -f "$SKILL_DIR"/wheels/akshareios-*.whl
cp "$WHEEL" "$SKILL_DIR/wheels/"

# BSD sed 不支持 \?，用整行锚定匹配 version: "x.y.z"
OLD_VERSION=$(sed -n 's/^version: "\(.*\)"$/\1/p' "$SKILL_DIR/SKILL.md" | head -1)
if [ -n "$OLD_VERSION" ] && [ "$OLD_VERSION" != "$VERSION" ]; then
    sed -i '' "s/$OLD_VERSION/$VERSION/g" "$SKILL_DIR/SKILL.md"
    echo "✅ SKILL.md 版本已同步: $OLD_VERSION → $VERSION"
elif [ -z "$OLD_VERSION" ]; then
    echo "❌ SKILL.md 缺少可解析的 version: 行，未做版本同步"; exit 1
fi
echo "✅ 已同步到 $SKILL_DIR/wheels/（记得两仓库分别提交）"
