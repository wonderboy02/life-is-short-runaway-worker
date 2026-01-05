# Runway Worker 통합 - 구현 요약

**작성일**: 2025-01-05
**목적**: WAN 로컬 추론 + Runway API 통합

---

## 📋 전체 구조

```
┌─────────────────────────────────────────────┐
│  Next.js API (life_is_short_landing)       │
│  - video_items 테이블에 inference_provider │
│  - Admin UI에서 모델 선택                   │
│  - Worker API (next-task, report 등)       │
└──────────┬──────────────────────────────────┘
           │
           ├─ WAN Worker (기존)
           │  - inference_provider = 'wan_local'
           │  - 로컬 GPU 추론
           │
           └─ Runway Worker (신규)
              - inference_provider = 'gen4_turbo', 'veo3.1', etc.
              - Runway API 호출
```

---

## 🎯 핵심 변경사항

### 1. **DB 스키마** (text 타입, enum 아님)

```sql
ALTER TABLE video_items
  ADD COLUMN inference_provider text DEFAULT 'gen4_turbo';
```

### 2. **코드 레벨 Enum** (TypeScript)

```typescript
export const INFERENCE_PROVIDERS = {
  wan_local: { name: 'WAN Local (GPU)', speed: 'very-slow', quality: 'good', cost: 'free' },
  gen4_turbo: { name: 'Gen-4 Turbo', speed: 'fast', quality: 'good', cost: 'low' },
  'gen4.5_turbo': { name: 'Gen-4.5 Turbo', speed: 'fast', quality: 'better', cost: 'medium' },
  gen3a_turbo: { name: 'Gen-3 Alpha Turbo', speed: 'very-fast', quality: 'ok', cost: 'very-low' },
  veo3: { name: 'Veo 3', speed: 'slow', quality: 'best', cost: 'high' },
  'veo3.1': { name: 'Veo 3.1', speed: 'medium', quality: 'best', cost: 'high' },
  'veo3.1_fast': { name: 'Veo 3.1 Fast', speed: 'fast', quality: 'good', cost: 'medium' },
} as const;

export type InferenceProvider = keyof typeof INFERENCE_PROVIDERS;
```

### 3. **UI 컴포넌트**

✅ **생성 완료**: `components/admin/InferenceProviderSelect.tsx`
- Select 드롭다운 (아이콘 + 설명)
- Badge 컴포넌트 (Queue UI용)

---

## 📂 작업 완료 파일

### ✅ 완료된 파일

| 파일 | 상태 | 설명 |
|------|------|------|
| `docs/database-migration.sql` | ✅ | Supabase SQL (inference_provider 컬럼 추가) |
| `lib/supabase/types.ts` | ✅ | InferenceProvider enum + 인터페이스 수정 |
| `components/admin/InferenceProviderSelect.tsx` | ✅ | UI 컴포넌트 |
| `docs/WORKER_TEAM_GUIDE.md` | ✅ | Worker 개발팀 전달 가이드 |
| `docs/runway-worker-implementation-guide.md` | ✅ | Runway Worker 전체 코드 |

### 🔄 수정 필요 파일 (Todo 참고)

| 파일 | 작업 | 우선순위 |
|------|------|----------|
| Supabase SQL | `docs/database-migration.sql` 실행 | ⭐⭐⭐ 최우선 |
| `app/api/admin/tasks/add/route.ts` | inference_provider 추가 | ⭐⭐⭐ |
| `app/api/worker/next-task/route.ts` | worker_type 필터링 | ⭐⭐⭐ |
| Admin UI (Task 생성) | InferenceProviderSelect 사용 | ⭐⭐ |
| Admin UI (Queue) | InferenceProviderBadge 사용 | ⭐⭐ |

---

## 🚀 구현 순서 (이 레포)

### Step 1: DB 마이그레이션 ⭐⭐⭐

```bash
# Supabase SQL Editor에서 실행
# 파일: docs/database-migration.sql
```

**내용**:
```sql
ALTER TABLE video_items
  ADD COLUMN IF NOT EXISTS inference_provider text DEFAULT 'gen4_turbo';

CREATE INDEX IF NOT EXISTS idx_video_items_inference_provider
  ON video_items(inference_provider)
  WHERE status = 'pending';
```

### Step 2: TypeScript 타입 재생성

```bash
npm run gen:types
```

이미 `lib/supabase/types.ts`는 수정했으므로, `lib/supabase/database.ts`만 재생성됨.

### Step 3: API 수정

#### `app/api/admin/tasks/add/route.ts`

**Before**:
```typescript
const tasksToInsert = body.tasks.map((task) => ({
  group_id: body.group_id,
  photo_id: task.photo_id,
  prompt: task.prompt,
  // ...
}));
```

**After**:
```typescript
import { INFERENCE_PROVIDERS, InferenceProvider } from '@/lib/supabase/types';

const tasksToInsert = body.tasks.map((task) => ({
  group_id: body.group_id,
  photo_id: task.photo_id,
  prompt: task.prompt,
  inference_provider: task.inference_provider || 'gen4_turbo', // 🆕
  // ...
}));

// 검증 (선택)
if (task.inference_provider && !(task.inference_provider in INFERENCE_PROVIDERS)) {
  throw new Error(`Invalid inference_provider: ${task.inference_provider}`);
}
```

#### `app/api/worker/next-task/route.ts`

**Before**:
```typescript
const { data: availableTasks } = await supabaseAdmin
  .from('video_items')
  .select('...')
  .or('status.eq.pending,...')
  .limit(1);
```

**After**:
```typescript
interface NextTaskRequest {
  worker_id: string;
  worker_type?: string; // 🆕 'wan' or 'runway'
  lease_duration_seconds?: number;
}

const { worker_type } = body;

// Worker 타입에 따라 필터링 🆕
let query = supabaseAdmin
  .from('video_items')
  .select('...')
  .or('status.eq.pending,...');

if (worker_type === 'wan') {
  query = query.eq('inference_provider', 'wan_local');
} else if (worker_type === 'runway') {
  query = query.not('inference_provider', 'eq', 'wan_local');
}

const { data: availableTasks } = await query.limit(1);

// Response에 inference_provider 추가 🆕
const responseData = {
  item_id: updatedTask.id,
  // ...
  inference_provider: updatedTask.inference_provider, // 🆕
};
```

### Step 4: Admin UI 수정

#### Task 생성 화면

**파일 찾기**:
```bash
# Admin에서 task 생성하는 페이지 찾기
# 예: app/admin/groups/[groupId]/page.tsx
```

**추가**:
```tsx
import { InferenceProviderSelect } from '@/components/admin/InferenceProviderSelect';
import { InferenceProvider } from '@/lib/supabase/types';

export default function GroupTaskPage({ params }: { params: { groupId: string } }) {
  const [inferenceProvider, setInferenceProvider] = useState<InferenceProvider>('gen4_turbo');

  const handleCreateTasks = async () => {
    await fetch('/api/admin/tasks/add', {
      method: 'POST',
      headers: { /* ... */ },
      body: JSON.stringify({
        group_id: params.groupId,
        tasks: photos.map((photo) => ({
          photo_id: photo.id,
          prompt: photo.generatedPrompt,
          repeat_count: 1,
          inference_provider: inferenceProvider, // 🆕
        })),
      }),
    });
  };

  return (
    <div className="space-y-4">
      {/* 추론 방식 선택 🆕 */}
      <InferenceProviderSelect
        value={inferenceProvider}
        onChange={setInferenceProvider}
        showDescription={true}
      />

      <Button onClick={handleCreateTasks}>
        비디오 생성 Task 추가
      </Button>
    </div>
  );
}
```

#### Queue UI

**파일 찾기**:
```bash
# Admin Queue 페이지
# 예: app/admin/queue/page.tsx
```

**추가**:
```tsx
import { InferenceProviderBadge } from '@/components/admin/InferenceProviderSelect';

<TableCell>
  <InferenceProviderBadge provider={task.inference_provider} showLabel={false} />
</TableCell>
```

---

## 🔧 Worker 팀 가이드

### 전달 문서

**`docs/WORKER_TEAM_GUIDE.md`** 전달
- 전체 구현 순서
- API 스펙
- Runway 모델 정보
- 테스트 방법
- 배포 가이드

### 핵심 전달 사항

1. **레포 생성**: `life_is_short_runway_worker`
2. **기존 코드 재사용**: WAN Worker에서 95% 복사
3. **교체 파일**: `inference.py` → `runway_client.py`
4. **추가 파라미터**: `worker_type: "runway"`
5. **모델 매핑**:
   ```python
   if inference_provider == "gen4_turbo":
       model = "gen4_turbo"
   elif inference_provider == "veo3.1":
       model = "veo3.1"
   ```

---

## ✅ 체크리스트

### Backend (이 레포)

- [x] DB 스키마 SQL 작성 (`docs/database-migration.sql`)
- [x] TypeScript enum 정의 (`lib/supabase/types.ts`)
- [x] UI 컴포넌트 생성 (`components/admin/InferenceProviderSelect.tsx`)
- [ ] Supabase SQL 실행
- [ ] `npm run gen:types` 실행
- [ ] `app/api/admin/tasks/add/route.ts` 수정
- [ ] `app/api/worker/next-task/route.ts` 수정
- [ ] Admin UI Task 생성 화면 수정
- [ ] Admin Queue UI 수정

### Worker 팀

- [ ] 새 레포 생성 (`life_is_short_runway_worker`)
- [ ] 기존 코드 복사 (logger, storage, api_client)
- [ ] `runway_client.py` 작성
- [ ] `worker.py` 수정
- [ ] Docker 설정
- [ ] 로컬 테스트
- [ ] 배포

---

## 📊 모델 비교표

| 모델 | 속도 | 품질 | 비용 | 용도 |
|------|------|------|------|------|
| `wan_local` | 🐌 매우 느림 | ⭐⭐ 좋음 | 🆓 무료 | 비용 절감 |
| `gen3a_turbo` | 🚀 매우 빠름 | ⭐ 보통 | 💵 매우 저렴 | 빠른 테스트 |
| `gen4_turbo` ⭐ | ⚡ 빠름 | ⭐⭐ 좋음 | 💵💵 저렴 | **프로덕션 기본** |
| `gen4.5_turbo` ⭐ | ⚡ 빠름 | ⭐⭐⭐ 더 좋음 | 💵💵💵 보통 | **프로덕션 권장** |
| `veo3.1_fast` | ⚡ 빠름 | ⭐⭐ 좋음 | 💵💵💵 보통 | 빠른 고품질 |
| `veo3.1` | 🏃 중간 | ⭐⭐⭐⭐ 최고 | 💵💵💵💵 비쌈 | 중요한 작업 |
| `veo3` | 🚶 느림 | ⭐⭐⭐⭐ 최고 | 💵💵💵💵 비쌈 | 최고 품질 필요 시 |

---

## 🔍 작동 원리

### 1. Admin이 Task 생성

```
Admin UI
  → 추론 방식 선택: "gen4_turbo"
  → POST /api/admin/tasks/add
  → video_items 테이블에 저장
     {
       inference_provider: "gen4_turbo",
       status: "pending"
     }
```

### 2. Worker가 Task 처리

```
Runway Worker (worker_type: "runway")
  → POST /api/worker/next-task
  → Next.js가 필터링:
     WHERE inference_provider != 'wan_local'
  → Task 받음:
     { inference_provider: "gen4_turbo" }
  → Runway API 호출 (model: "gen4_turbo")
  → 결과 업로드 및 보고
```

### 3. WAN Worker는 별도 처리

```
WAN Worker (worker_type: "wan")
  → POST /api/worker/next-task
  → Next.js가 필터링:
     WHERE inference_provider = 'wan_local'
  → wan_local task만 처리
```

---

## 📞 문의

- **Backend 팀**: Slack #backend-team
- **Worker 팀**: Slack #worker-team
- **긴급**: @backend-lead

---

## 📚 관련 문서

1. **`docs/WORKER_TEAM_GUIDE.md`** - Worker 개발팀 전달 가이드 (최우선 읽기)
2. **`docs/runway-worker-implementation-guide.md`** - Runway Worker 전체 코드
3. **`docs/runway-worker-architecture.md`** - 아키텍처 설계
4. **`docs/inference-provider-selection.md`** - 추론 방식 선택 기능 설계
5. **`docs/database-migration.sql`** - DB 마이그레이션 SQL

---

**작성자**: Backend Team
**버전**: 1.0
**최종 수정**: 2025-01-05
