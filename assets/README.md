# 아트 에셋 (PNG) 가이드

여기에 PNG를 올리면 게임이 **자동으로** 그 PNG를 씁니다. 파일이 없으면 코드 안의 SVG로 대체돼요.
(GitHub에서 `assets/` 폴더 → Add file → Upload files → 드래그 → Commit)

## PNG 양식
- **정사각형 투명 PNG** (배경 투명, 바둑판 X)
- **512 × 512 px** 권장 (256 이상)
- 오브젝트 **가운데 정렬, 대략 80% 크기** (사방 여백 ~10%)
- **바닥 그림자 없음(또는 아주 약하게)**, 글자/워터마크 없음, 오브젝트 1개만

## 파일명 ↔ 과일 ↔ 색
| 파일명 | 과일 | 색(과즙·이펙트 기준) |
|---|---|---|
| `fruit0.png` | 🍒 체리 | 빨강 `#ff5a7a` |
| `fruit1.png` | 🍊 오렌지 | 주황 `#f45b00` |
| `fruit2.png` | 🥝 키위 | 초록 `#43d17a` |
| `fruit3.png` | 🍋 레몬 | 노랑 `#ffc93c` |
| `fruit4.png` | 🍇 포도 | 보라 `#a66cff` |
| `fruit5.png` | 🍐 배 | 연녹/흰 `#c4d8be` |
| `fruit6.png` | 🍌 바나나 | 파랑 `#00b4d8` |

> 과일 종류를 바꿔도 되지만, **색은 슬롯 색과 맞추는 게 좋아요**(안 그러면 과즙 색이 어긋남). 색을 크게 바꾸려면 "몇 번 슬롯 색을 XX로" 알려주세요.

## 파일명 ↔ 아이템 / 벽돌
| 파일명 | 설명 |
|---|---|
| `bird.png` | 참새 — **옆모습, 왼쪽을 보게** (오른쪽 이동 시 자동 좌우반전) |
| `line.png` | 라인 — **가로 방향** 아이콘 (세로는 자동 90° 회전) |
| `star.png` | 별 |
| `bomb.png` | (선택) 폭탄 아이콘 — 없으면 "과일+심지"로 자동 처리 |
| `brick3.png` | 벽돌 HP3 — 온전한 벽 |
| `brick2.png` | 벽돌 HP2 — 금 간 벽 |
| `brick1.png` | 벽돌 HP1 — 부서지기 직전 |

---

## AI 이미지 프롬프트 (일관된 스타일용)
모든 프롬프트 끝에 이 **공통 스타일**을 붙이세요:

> `, cute chibi cartoon mobile game icon, thick dark navy outline, glossy 2.5D cel-shading, soft specular highlights, bold simple silhouette, centered single object, transparent background, no ground shadow, no text, 512x512`

### 과일
- **fruit0 체리:** `two shiny red cherries (#ff5a7a) joined by a green stem with a small leaf`
- **fruit1 오렌지:** `a whole round orange fruit (#f45b00) with a small green leaf on top`
- **fruit2 키위:** `a green kiwi cross-section slice, bright green flesh (#43d17a), pale center, ring of tiny black seeds, thin brown skin edge`
- **fruit3 레몬:** `a bright yellow lemon (#ffc93c), oval with small nubs, slightly tilted`
- **fruit4 포도:** `a bunch of purple grapes (#a66cff) with a small green leaf on top`
- **fruit5 배:** `a plump pale green-white pear (#c4d8be) with a short brown stem and a leaf`
- **fruit6 바나나:** `a single upright blue banana (#00b4d8), thick and plump, small brown stem`

### 아이템
- **bird 참새:** `a cute plump brown sparrow, side profile FACING LEFT, small orange beak, folded wing`
- **line 라인:** `a horizontal double-headed arrow (pointing left and right), glossy golden-orange, power-up icon`
- **star 별:** `a shiny golden five-point star (#ffd000) with a sparkle`
- **bomb 폭탄(선택):** `a cartoon round bomb with a lit sparkling fuse`

### 벽돌 (같은 벽을 3단계로, 색/스타일 통일)
- **brick3 온전:** `an intact solid brick wall block, red-brown bricks with dark mortar lines`
- **brick2 파손:** `the same red-brown brick wall block but cracked and damaged, visible cracks and a chip`
- **brick1 직전:** `the same brick wall block heavily shattered and crumbling, big cracks, holes, about to fall apart`

> 벽돌 3장은 **같은 벽에서 점점 부서지는** 느낌으로 통일하면 좋아요 (같은 seed/스타일 권장).
