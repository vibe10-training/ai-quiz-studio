# 개발 계획서 (Development Plan) — AI 퀴즈 생성 & 갤러리 웹앱

## 1. 시스템 아키텍처 및 기술 스택

### 1.1 권장 기술 스택 (Vercel 최적화)
| 영역 | 기술 | 선정 이유 |
| :--- | :--- | :--- |
| **프레임워크** | **Next.js (App Router, TypeScript)** | 프론트엔드 UI와 서버리스 API Route를 단일 프로젝트로 통합, Vercel 무설정(Zero-config) 배포 지원 |
| **스타일링** | **Tailwind CSS** | 빠른 반응형 UI 구현 및 일관된 디자인 시스템 유지 |
| **백엔드/API 프록시** | **Next.js Route Handlers (`/api/quiz/generate`)** | `env_local` / `.env.local`의 `endpoint`, `key`를 서버 측에서만 안전하게 사용 |
| **데이터 저장 (갤러리)** | **Browser `localStorage` + Storage Adapter 추상화** | 별도 DB 비용/설정 없이 로컬 및 Vercel에서 즉시 영속성 확보, 추후 DB 교체 용이 |
| **배포/형상관리** | **GitHub + Vercel** | `main` 브랜치 푸시 시 자동 빌드 및 배포 연동 |

> **참고 (대안 스택)**: 현재 PC에 `Node.js` 및 `Git`이 설치되어 있지 않고 `Python 3.12`만 확인된 상태입니다. 만약 Node.js 설치가 어려운 환경이라면 `Python (FastAPI) + 정적 HTML/CSS/JS` 조합으로도 개발 및 Vercel Python Runtime 배포가 가능합니다. 단, 장기적인 유지보수와 Vercel 호환성 면에서는 **Node.js + Git 설치 후 Next.js 진행**을 권장합니다.

### 1.2 환경 변수 로딩 전략 (`env_local` 대응)
- 사용자는 `env_local` 파일에 `endpoint`와 `key`를 보유하고 있음.
- **로컬 실행 시**:
  - 프로젝트 루트의 `.env.local` (Next.js 기본 지원) 또는 `env_local` 파일을 서버 시작/API 호출 시점에 안전하게 파싱·로드할 수 있도록 환경 변수 로더 유틸리티 구성
  - `.gitignore`에 `env_local` 및 `.env*.local`을 반드시 포함하여 GitHub 유출 방지
- **Vercel 배포 시**:
  - Vercel 대시보드 Environment Variables에 동일한 키 등록 (`process.env`에서 자동 참조)

---

## 2. 디렉토리 구조 (예정)
```text
quiz_prj/
├── PRD.md                    # 제품 요구사항 정의서
├── DEVELOPMENT_PLAN.md       # 개발 계획서
├── STATUS.md                 # 개발 진행 현황 및 이슈 트래킹
├── .gitignore                # env_local, .env*, node_modules 등 제외
├── package.json
├── next.config.*
├── src/
│   ├── app/
│   │   ├── layout.tsx        # 공통 레이아웃 및 네비게이션 (출제 / 갤러리)
│   │   ├── page.tsx          # 메인: 퀴즈 생성 및 풀이 화면
│   │   ├── gallery/
│   │   │   └── page.tsx      # 갤러리 목록, 필터, 상세보기/재풀이
│   │   └── api/
│   │       └── quiz/
│   │           └── generate/
│   │               └── route.ts  # AI API 호출 서버 엔드포인트
│   ├── components/
│   │   ├── Navbar.tsx        # 상단 메뉴
│   │   ├── QuizForm.tsx      # 과목, 단원, 유형, 문항 수 입력 폼
│   │   ├── QuizRunner.tsx    # 문제 풀이, 채점, 해설 표시 컴포넌트
│   │   └── GalleryList.tsx   # 갤러리 카드 목록, 검색/필터, 삭제
│   ├── lib/
│   │   ├── env.ts            # env_local / process.env 안전 로더
│   │   ├── aiClient.ts       # AI Endpoint 호출 및 JSON 응답 파싱/검증
│   │   └── storage.ts        # 갤러리 localStorage CRUD 및 JSON 내보내기
│   └── types/
│       └── quiz.ts           # Quiz, Question, GalleryItem 타입 정의
```

---

## 3. 단계별 개발 계획 (Milestones)

### Phase 0: 사전 준비 및 환경 확인 (코드 작성 전)
- [ ] `env_local` 파일 위치 확인 및 프로젝트 루트 배치 (내용 형식: 키 이름 및 AI 서비스 종류 확인)
- [ ] 기술 스택 확정 (Next.js vs Python FastAPI) 및 필요 도구(Node.js LTS, Git) 설치 확인
- [ ] 구현 허락 획득 후 개발 착수

### Phase 1: 프로젝트 초기화 및 API 백엔드 구축
1. 프로젝트 스캐폴딩 및 `.gitignore` 설정 (`env_local`, `.env*` 포함)
2. `src/types/quiz.ts` — 문항, 보기, 정답, 해설, 갤러리 스키마 정의
3. `src/lib/env.ts` — `process.env` 및 `env_local` fallback 로더 구현
4. `src/lib/aiClient.ts` & `src/app/api/quiz/generate/route.ts` 구현
   - 과목명, 단원명, 문제 유형(객관식/주관식), 문항 수, 난이도를 입력받아 구조화된 JSON(문제, 보기, 정답, **해설**) 반환
   - 응답 포맷 검증 및 예외 처리(400/500 에러, 타임아웃 처리)
5. `STATUS.md` 업데이트

### Phase 2: 프론트엔드 핵심 UI — 문제 출제, 풀이, 해설
1. 공통 레이아웃 및 상단 네비게이션 (`문제 출제` / `갤러리`)
2. `QuizForm`: 과목명, 단원명, 유형(객관식/주관식), 문항 수, 난이도 입력 및 유효성 검사
3. `QuizRunner`:
   - 객관식(라디오/카드 선택) 및 주관식(텍스트 입력) 풀이 UI
   - 제출 및 채점 결과 요약(점수/정답률)
   - 문항별 정답 및 **상세 해설** 표시 (교사용 정답 미리보기 토글 포함)
4. `STATUS.md` 업데이트

### Phase 3: 갤러리 메뉴 구현
1. `src/lib/storage.ts`: `localStorage` 기반 저장/조회/삭제/JSON 내보내기 구현
2. 퀴즈 생성/풀이 화면에 **갤러리에 저장** 버튼 및 저장 확인 피드백 추가
3. `src/app/gallery/page.tsx`:
   - 저장된 퀴즈 목록 카드 뷰
   - 과목/유형 필터 및 검색 기능
   - **다시 풀기**, **해설 포함 전체 보기**, **삭제** 기능 구현
4. `STATUS.md` 업데이트

### Phase 4: 로컬 동작 점검 및 오류 체크
1. 로컬 개발 서버 실행 (`npm run dev`)
2. 기능별 수동/자동 검증:
   - [ ] 객관식 문제 생성 및 해설 첨부 확인
   - [ ] 주관식 문제 생성 및 해설 첨부 확인
   - [ ] 채점 로직 및 오답 시 해설 표시 확인
   - [ ] 갤러리 저장, 새로고침 후 유지, 필터/검색, 재풀이, 삭제 확인
   - [ ] 잘못된 입력/네트워크 실패/키 누락 시 오류 메시지 확인
3. 프로덕션 빌드 테스트 (`npm run build`) 및 타입/린트 오류 `0`건 확인
4. `STATUS.md`에 점검 결과 기록

### Phase 5: GitHub 업로드 및 Vercel 배포
1. Git 저장소 초기화 및 커밋 (비밀키 파일 미포함 사전 검증)
2. GitHub 원격 저장소 생성 및 푸시
3. Vercel 프로젝트 연동, Environment Variables(`endpoint`, `key`) 등록
4. Vercel 배포 URL에서 퀴즈 생성·해설·갤러리 동작 최종 확인
5. `STATUS.md` 최종 완료 기록

---

## 4. `STATUS.md` 운영 원칙
- 코드 작성 및 작업 진행 시마다 `STATUS.md`를 즉시 갱신합니다.
- 기록 항목:
  1. 전체 진행률 및 Phase별 상태 (`대기` / `진행중` / `완료` / `차단됨`)
  2. 생성·수정된 파일 목록과 요약
  3. 로컬 테스트 및 빌드 검증 결과
  4. 발견된 오류 및 해결 방법
