# assets_raw — AI에서 받은 원본을 여기에 넣으세요

배경이 **흰색인 채로** 받은 PNG를 이 폴더에 그냥 넣으면 됩니다. 투명하게 만들 필요 없습니다.

## 1. 파일 이름

`유물.md`에 있는 **한글 이름** 그대로 쓰면 됩니다.

```
개간.png        왕관.png        체리 편애.png
```

영문 id도 됩니다 (`reclaim.png`, `crown.png`). 둘 다 알아봅니다.

## 2. 변환

```
python3 tools/cutout.py --all
```

`assets_raw/` 의 모든 PNG에서 배경을 지우고 `assets_new/relic_<id>.png` 로 저장합니다.
원본은 그대로 남으니 다시 돌려도 됩니다.

결과 표시:

```
  ✓ 개간.png              → relic_reclaim.png  (71% 제거)
  ! 왕관.png              체크무늬 배경 (프롬프트에서 transparent 를 빼세요)
  ? 이상한이름.png         이름을 못 알아봤습니다
```

## 3. 잘 안 지워질 때

| 증상 | 대처 |
|---|---|
| `⚠️ 거의 안 지워졌습니다` | `python3 tools/cutout.py --all --tol 90` — 배경이 완전 단색이 아닐 때 |
| `⚠️ 너무 많이 지워졌습니다` | `--tol 35` — 그림에 배경색과 비슷한 밝은 부분이 있을 때 |
| 주제가 온통 흰색 (설탕·클로버) | 프롬프트 배경을 `flat solid magenta background` 로 바꿔서 다시 생성 |
| 안쪽이 뚫렸다 | 외곽선이 끊긴 것 — 프롬프트에 `thick continuous dark navy outline` 강조 |

한 장씩 하려면:

```
python3 tools/cutout.py ~/Downloads/무엇.png assets_new/relic_crown.png --tol 70
```

> 이미 투명한 파일은 건드리지 않고 그대로 복사합니다. 다시 처리하면 그림이 망가지기 때문입니다.
