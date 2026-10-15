# 06. 개발 워크플로 (브랜치·커밋·PR·릴리스)

혼자 진행하는 프로젝트지만 **팀 개발과 같은 루틴**으로 운영한다. 방식은 GitHub Flow(짧은 수명의 브랜치 + PR + squash merge)이며, `main`은 항상 보여줄 수 있는 상태를 유지한다.

## 1. 브랜치
| 브랜치 | 용도 |
|---|---|
| `main` | 항상 안정. 직접 push 금지, PR로만 병합 |
| `feat/<phase>-<주제>` | 기능·작업 (예: `feat/p1-usd-rack`) |
| `fix/<주제>` | 버그 수정 |
| `docs/<주제>` | 문서만 변경 |
| `chore/<주제>` | 설정, 도구, 정리 |
| `exp/<E번호>-<주제>` | 비교 실험 (예: `exp/e1-usd-import-loss`) |
| `spike/<주제>` | 버리거나 보관용 탐색. 병합하지 않아도 됨 |

- 수명은 **짧게**(며칠 이내), 한 브랜치에 **한 가지 목적**.
- `main`에서 분기하고, 작업 중 `main`이 앞서가면 `git rebase origin/main`(또는 merge)으로 따라간다.
- 병합 후 브랜치는 삭제한다(GitHub의 "자동 삭제" 설정 사용).

## 2. 커밋 (Conventional Commits)
```
<type>(<scope>): <요약, 명령형, 50자 내외>

<본문: 왜 바꿨는지, 선택 이유, 측정값>
```
- type: `feat` `fix` `docs` `chore` `refactor` `perf` `test` `build` `exp`
- scope 예: `usd`, `sim`, `gateway`, `ue`, `ui`, `stream`, `docs`, `harness`
- 예: `feat(sim): add cooling_failure scenario generator`
- 의미 있는 단위로 자주 커밋한다. 깨진 상태로 커밋하지 않는다.

## 3. Pull Request
- 모든 변경은 PR로 `main`에 병합한다(혼자라도 자기 리뷰를 위해).
- 제목은 커밋 규칙과 동일, 본문은 `.github/pull_request_template.md`를 채운다(목적, 변경, 검증, 클린룸 체크).
- 병합 방식은 **Squash and merge** → `main`은 PR당 커밋 1개의 선형 이력.
- 병합 전 체크: 클린룸 점검, 대용량/바이너리 파일 LFS 여부, 문서 갱신.

## 4. 이슈·마일스톤
- Phase(`02_roadmap.md`)마다 GitHub **Milestone**을 만들고, 작업 단위를 **Issue**로 쪼갠다.
- PR 본문에 `Closes #번호`로 연결한다.
- 라벨: `phase:1`~`phase:8`, `type:feat|fix|docs|exp`, `area:usd|sim|gateway|ue|ui|stream`.

## 5. 릴리스
- Phase 완료 시 `main`에 태그: `v0.<phase>.0` (예: Phase 1 완료 → `v0.1.0`)
- GitHub Release 노트에 산출물(영상, 결과표 링크)을 남긴다. 포트폴리오에서 진행 이력을 보여주는 용도.

## 6. 바이너리·대용량 파일
- UE 에셋(`.uasset`, `.umap`), USD(`.usd`, `.usdc`), Blender(`.blend`), 이미지, 영상 등은 **Git LFS**로 관리한다(`.gitattributes`).
- GitHub 무료 LFS 한도(저장 1GB, 월 대역폭 1GB)를 고려해 **필요한 최소 에셋만 커밋**한다. 생성 가능한 데이터(VDB, 시뮬레이션 출력)는 커밋하지 않고 생성 스크립트와 설정만 둔다.
- 첫 LFS 파일을 커밋하기 전에 한 번 `git lfs install`을 실행한다.

## 7. main 보호 (GitHub 설정, 1회)
Settings → Branches → Add rule (`main`):
- Require a pull request before merging (승인 수는 0, 혼자이므로)
- Require linear history
- Do not allow force pushes / deletions
Settings → General: "Automatically delete head branches" 켜기, 병합 방식은 Squash만 허용.

## 8. 하루 루틴 예시
```
git switch main && git pull
git switch -c feat/p1-usd-rack
# 작업 → 작은 단위 커밋 (feat(usd): ...)
git push -u origin feat/p1-usd-rack
# PR 생성 → 자기 리뷰 → Squash merge → 브랜치 삭제
git switch main && git pull && git branch -d feat/p1-usd-rack
```

## 9. AI(Claude Code) 사용 규칙
- 작업 시작 시 항상 브랜치를 먼저 만든다. `main`에서 직접 커밋하지 않는다.
- 사용자가 요청할 때만 commit/push/PR을 만든다. force push와 `main` 이력 변경은 하지 않는다.
- 커밋 메시지 끝에 공동 작성자 표기를 남긴다.
