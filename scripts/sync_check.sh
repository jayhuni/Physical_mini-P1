#!/usr/bin/env bash
# 충돌 사전 점검 스크립트. 작업 트리와 브랜치를 전혀 바꾸지 않는다.
#
#   bash scripts/sync_check.sh          # 기준 브랜치 main
#   bash scripts/sync_check.sh develop  # 기준 브랜치 지정
#
# 1) 내 브랜치가 origin/<base> 보다 몇 커밋 뒤처졌는지
# 2) 지금 origin/<base> 와 합치면 충돌이 나는 파일 (git merge-tree, Git 2.38 이상)
# 3) 팀원이 작업 중인 다른 원격 브랜치와 내가 같은 파일을 고치고 있는지 (충돌 조기 경보)
set -euo pipefail

base="${1:-main}"
git fetch origin --prune --quiet

me=$(git rev-parse --abbrev-ref HEAD)
behind=$(git rev-list --count "HEAD..origin/$base")
ahead=$(git rev-list --count "origin/$base..HEAD")
echo "== [$me] origin/$base 대비: ${ahead}커밋 앞섬, ${behind}커밋 뒤처짐"
if [ "$behind" -gt 0 ]; then
  echo "   -> PR 전에 'git merge origin/$base' 로 최신 main을 반영하세요."
fi

status=0
echo "== origin/$base 와 합쳤을 때 충돌 예상 파일"
# --name-only 출력: 첫 줄은 트리 ID, 이어서 충돌 파일 목록, 빈 줄 뒤에 상세 메시지
if out=$(git merge-tree --write-tree --name-only "origin/$base" HEAD 2>/dev/null); then
  echo "   없음"
else
  echo "$out" | sed -n '2,/^$/p' | sed '/^$/d; s/^/   ! /'
  status=1
fi

# 내가 바꾼 파일 목록 (origin/<base> 와 갈라진 지점 기준)
mine=$(git diff --name-only "$(git merge-base HEAD "origin/$base")" HEAD | sort)

echo "== 팀원 원격 브랜치와 겹치는 파일"
found=0
for ref in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin); do
  case "$ref" in origin/HEAD|origin|"origin/$base"|"origin/$me") continue ;; esac
  # 이미 base에 병합된 브랜치는 건너뛴다
  if git merge-base --is-ancestor "$ref" "origin/$base"; then continue; fi
  # 내 브랜치 위에 쌓인 브랜치(내 커밋을 포함)는 겹치는 게 당연하므로 건너뛴다
  if git merge-base --is-ancestor HEAD "$ref"; then continue; fi
  theirs=$(git diff --name-only "$(git merge-base "$ref" "origin/$base")" "$ref" | sort)
  both=$(comm -12 <(echo "$mine") <(echo "$theirs") | sed '/^$/d')
  if [ -n "$both" ]; then
    found=1
    echo "   $ref 와 겹침:"
    echo "$both" | sed 's/^/     - /'
  fi
done
[ "$found" -eq 0 ] && echo "   없음"

if [ "$status" -ne 0 ]; then
  echo
  echo "충돌이 예상됩니다. docs/collaboration.md 의 '충돌이 났을 때' 절차를 따르세요."
fi
exit "$status"
