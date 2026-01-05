# 추론 방식 선택 기능 (WAN vs Runway)

**목적**: Admin이 각 비디오 생성 task마다 추론 방식을 선택할 수 있도록 함
- **WAN 로컬**: life_is_short_wan_inference worker (로컬 GPU 추론)
- **Runway**: Runway Gen-4.5 API (클라우드 API)

---

## 1. 데이터베이스 스키마 변경

### 1.1 새 컬럼 추가

**video_items 테이블에 `inference_provider` 컬럼 추가**:

```sql
-- Supabase SQL Editor에서 실행

-- 1. Enum 타입 생성
CREATE TYPE inference_provider AS ENUM ('wan_local', 'runway_gen4_turbo', 'runway_veo3.1');

-- 2. video_items 테이블에 컬럼 추가
ALTER TABLE video_items
  ADD COLUMN inference_provider inference_provider DEFAULT 'runway_gen4_turbo';

-- 3. 기존 레코드 업데이트 (선택)
UPDATE video_items
  SET inference_provider = 'wan_local'
  WHERE created_at < '2025-01-06';  -- 기존 레코드는 WAN으로

-- 4. 인덱스 추가 (성능 최적화)
CREATE INDEX idx_video_items_inference_provider
  ON video_items(inference_provider)
  WHERE status = 'pending';
```

### 1.2 업데이트된 스키마

```typescript
// lib/supabase/database.ts (npm run gen:types 후 자동 생성)

export type Database = {
  public: {
    Tables: {
      video_items: {
        Row: {
          id: string
          group_id: string | null
          photo_id: string | null
          prompt: string
          status: "pending" | "processing" | "completed" | "failed"
          inference_provider: "wan_local" | "runway_gen4_turbo" | "runway_veo3.1"  // 🆕
          // ... 기타 컬럼
        }
        Insert: {
          // inference_provider는 기본값 있으므로 선택적
          inference_provider?: "wan_local" | "runway_gen4_turbo" | "runway_veo3.1"
          // ...
        }
      }
    }
    Enums: {
      processing_status: "pending" | "processing" | "completed" | "failed"
      inference_provider: "wan_local" | "runway_gen4_turbo" | "runway_veo3.1"  // 🆕
    }
  }
}
```

---

## 2. API 수정

### 2.1 Task 생성 API (Admin)

**app/api/admin/tasks/add/route.ts** 수정:

```typescript
interface TaskAddRequest {
  group_id: string;
  tasks: Array<{
    photo_id: string;
    prompt: string;
    frame_num?: number;
    inference_provider?: 'wan_local' | 'runway_gen4_turbo' | 'runway_veo3.1';  // 🆕
  }>;
}

export async function POST(req: NextRequest) {
  const body: TaskAddRequest = await req.json();

  const tasksToInsert = body.tasks.map((task) => ({
    group_id: body.group_id,
    photo_id: task.photo_id,
    prompt: task.prompt,
    frame_num: task.frame_num || null,
    inference_provider: task.inference_provider || 'runway_gen4_turbo',  // 🆕 기본값
    status: 'pending',
    retry_count: 0,
  }));

  const { data, error } = await supabaseAdmin
    .from('video_items')
    .insert(tasksToInsert)
    .select();

  // ...
}
```

### 2.2 Worker Next Task API

**app/api/worker/next-task/route.ts** 수정:

```typescript
interface NextTaskData {
  item_id: string;
  group_id: string;
  photo_id: string;
  prompt: string;
  leased_until: string;
  photo_storage_path: string;
  frame_num: number | null;
  inference_provider: string;  // 🆕 Worker에 추론 방식 전달
}

export async function POST(req: NextRequest) {
  // ...

  // Worker별 필터링 (선택 사항)
  const { worker_type } = body;  // 'wan' or 'runway'

  // 추론 방식에 맞는 task만 가져오기
  const providerFilter = worker_type === 'wan'
    ? 'inference_provider.eq.wan_local'
    : 'inference_provider.in.(runway_gen4_turbo,runway_veo3.1)';

  const { data: availableTasks, error: findError } = await supabaseAdmin
    .from('video_items')
    .select('id, status, leased_until, retry_count, inference_provider')  // 🆕
    .or('status.eq.pending,and(status.eq.processing,leased_until.lt.now())')
    .or(providerFilter)  // 🆕 추론 방식 필터
    .lt('retry_count', 3)
    .order('created_at', { ascending: true })
    .limit(1);

  // ...

  const responseData: NextTaskData = {
    item_id: updatedTask.id,
    group_id: updatedTask.group_id,
    photo_id: updatedTask.photo_id,
    prompt: updatedTask.prompt,
    leased_until: updatedTask.leased_until!,
    photo_storage_path: photoData.storage_path,
    frame_num: updatedTask.frame_num || null,
    inference_provider: updatedTask.inference_provider,  // 🆕
  };

  return NextResponse.json<ApiResponse<NextTaskData>>({
    success: true,
    data: responseData,
  });
}
```

---

## 3. UI 수정 (Admin Dashboard)

### 3.1 Task 생성 UI

**app/admin/groups/[groupId]/page.tsx** (또는 새 컴포넌트):

```tsx
'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Label } from '@/components/ui/label';

export default function GroupTaskManager({ groupId }: { groupId: string }) {
  const [inferenceProvider, setInferenceProvider] = useState<'wan_local' | 'runway_gen4_turbo' | 'runway_veo3.1'>('runway_gen4_turbo');

  const handleCreateTasks = async () => {
    const response = await fetch('/api/admin/tasks/add', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        group_id: groupId,
        tasks: photos.map((photo) => ({
          photo_id: photo.id,
          prompt: photo.generatedPrompt || '',
          frame_num: 121,
          inference_provider: inferenceProvider,  // 🆕
        })),
      }),
    });

    // ...
  };

  return (
    <div className="space-y-4">
      {/* 추론 방식 선택 */}
      <div className="space-y-2">
        <Label htmlFor="inference-provider">추론 방식</Label>
        <Select
          value={inferenceProvider}
          onValueChange={(value) => setInferenceProvider(value as any)}
        >
          <SelectTrigger id="inference-provider">
            <SelectValue placeholder="추론 방식 선택" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="wan_local">
              🖥️ WAN 로컬 (GPU 서버)
            </SelectItem>
            <SelectItem value="runway_gen4_turbo">
              ⚡ Runway Gen-4 Turbo (빠름)
            </SelectItem>
            <SelectItem value="runway_veo3.1">
              ✨ Runway Veo 3.1 (최고 품질)
            </SelectItem>
          </SelectContent>
        </Select>

        {/* 설명 텍스트 */}
        <p className="text-sm text-muted-foreground">
          {inferenceProvider === 'wan_local' && '로컬 GPU 서버에서 추론 (무료, 느림)'}
          {inferenceProvider === 'runway_gen4_turbo' && 'Runway API 사용 (빠름, 비용 발생)'}
          {inferenceProvider === 'runway_veo3.1' && 'Runway API 사용 (최고 품질, 비용 높음)'}
        </p>
      </div>

      {/* Task 생성 버튼 */}
      <Button onClick={handleCreateTasks}>
        비디오 생성 Task 추가 ({photos.length}개)
      </Button>
    </div>
  );
}
```

### 3.2 Task 목록 UI (상태 표시)

**app/admin/queue/page.tsx**:

```tsx
function TaskQueueTable({ tasks }: { tasks: VideoTask[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ID</TableHead>
          <TableHead>Photo</TableHead>
          <TableHead>Prompt</TableHead>
          <TableHead>추론 방식</TableHead> {/* 🆕 */}
          <TableHead>Status</TableHead>
          <TableHead>Worker</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tasks.map((task) => (
          <TableRow key={task.id}>
            <TableCell className="font-mono text-xs">
              {task.id.slice(0, 8)}...
            </TableCell>
            <TableCell>
              <img src={task.photoUrl} className="h-10 w-10 object-cover rounded" />
            </TableCell>
            <TableCell className="max-w-xs truncate">
              {task.prompt}
            </TableCell>

            {/* 추론 방식 표시 🆕 */}
            <TableCell>
              {task.inference_provider === 'wan_local' && (
                <span className="inline-flex items-center gap-1 text-sm">
                  🖥️ WAN
                </span>
              )}
              {task.inference_provider === 'runway_gen4_turbo' && (
                <span className="inline-flex items-center gap-1 text-sm">
                  ⚡ Gen-4
                </span>
              )}
              {task.inference_provider === 'runway_veo3.1' && (
                <span className="inline-flex items-center gap-1 text-sm">
                  ✨ Veo 3.1
                </span>
              )}
            </TableCell>

            <TableCell>
              <StatusBadge status={task.status} />
            </TableCell>
            <TableCell className="font-mono text-xs">
              {task.worker_id || '-'}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

---

## 4. Worker 수정

### 4.1 WAN Worker (기존)

**worker/worker.py** (변경 불필요):

```python
# next-task 요청 시 worker_type 전달
def get_next_task(self):
    payload = {
        "worker_id": self.worker_id,
        "worker_type": "wan",  # 🆕 WAN worker임을 명시
        "lease_duration_seconds": 600
    }
    # ...
```

### 4.2 Runway Worker (새 프로젝트)

**worker/worker.py**:

```python
# next-task 요청 시 worker_type 전달
def get_next_task(self):
    payload = {
        "worker_id": self.worker_id,
        "worker_type": "runway",  # 🆕 Runway worker임을 명시
        "lease_duration_seconds": 600
    }
    # ...

def process_task(self, task: Dict):
    item_id = task["item_id"]
    inference_provider = task["inference_provider"]  # 🆕

    # Runway 모델 선택
    if inference_provider == "runway_gen4_turbo":
        model = "gen4_turbo"
    elif inference_provider == "runway_veo3.1":
        model = "veo3"
    else:
        raise ValueError(f"Unsupported provider: {inference_provider}")

    # Runway API 호출
    self.runway_client.generate_video(
        input_image_path=temp_input,
        output_video_path=temp_output,
        prompt=task["prompt"],
        model=model,  # 🆕 동적으로 모델 선택
        duration=5.0
    )
    # ...
```

---

## 5. 마이그레이션 순서

### 5.1 Supabase 스키마 변경

```bash
# 1. Supabase SQL Editor에서 실행
CREATE TYPE inference_provider AS ENUM ('wan_local', 'runway_gen4_turbo', 'runway_veo3.1');

ALTER TABLE video_items
  ADD COLUMN inference_provider inference_provider DEFAULT 'runway_gen4_turbo';

CREATE INDEX idx_video_items_inference_provider
  ON video_items(inference_provider)
  WHERE status = 'pending';
```

### 5.2 TypeScript 타입 재생성

```bash
cd life_is_short_landing
npm run gen:types
```

### 5.3 코드 수정 및 배포

```bash
# Next.js API 수정
# - app/api/admin/tasks/add/route.ts
# - app/api/worker/next-task/route.ts

# UI 수정
# - app/admin/groups/[groupId]/page.tsx (task 생성)
# - app/admin/queue/page.tsx (task 목록)

# 배포
git add .
git commit -m "feat: Add inference provider selection (WAN/Runway)"
git push origin dev
```

### 5.4 Worker 업데이트

```bash
# WAN Worker
cd life_is_short_wan_inference
git pull
# worker.py에서 worker_type: "wan" 추가

# Runway Worker
cd life_is_short_runway_worker
# worker.py에서 worker_type: "runway" 추가
# inference_provider에 따라 모델 선택 로직 추가
```

---

## 6. 사용 시나리오

### 시나리오 1: 빠른 테스트 (Runway Gen-4 Turbo)

```
Admin → Group 생성 → 사진 업로드
     → 추론 방식 선택: "⚡ Runway Gen-4 Turbo"
     → Task 생성
     → Runway Worker가 처리 (2-5분 완료)
```

### 시나리오 2: 최고 품질 (Runway Veo 3.1)

```
Admin → 추론 방식 선택: "✨ Runway Veo 3.1"
     → Task 생성
     → Runway Worker가 처리 (5-10분 완료, 최고 품질)
```

### 시나리오 3: 무료 추론 (WAN 로컬)

```
Admin → 추론 방식 선택: "🖥️ WAN 로컬"
     → Task 생성
     → WAN Worker가 처리 (20-40분 완료, 무료)
```

---

## 7. 통계 및 모니터링

### 7.1 추론 방식별 통계

**app/api/admin/stats/route.ts** (새로 생성):

```typescript
export async function GET(req: NextRequest) {
  const { data: stats, error } = await supabaseAdmin
    .from('video_items')
    .select('inference_provider, status')
    .returns<Array<{ inference_provider: string; status: string }>>();

  const grouped = stats.reduce((acc, item) => {
    const key = item.inference_provider;
    if (!acc[key]) {
      acc[key] = { total: 0, pending: 0, processing: 0, completed: 0, failed: 0 };
    }
    acc[key].total++;
    acc[key][item.status]++;
    return acc;
  }, {} as Record<string, any>);

  return NextResponse.json({
    success: true,
    data: grouped,
  });
}
```

**결과 예시**:
```json
{
  "wan_local": {
    "total": 150,
    "pending": 10,
    "processing": 5,
    "completed": 130,
    "failed": 5
  },
  "runway_gen4_turbo": {
    "total": 80,
    "pending": 2,
    "processing": 3,
    "completed": 70,
    "failed": 5
  },
  "runway_veo3.1": {
    "total": 20,
    "pending": 0,
    "processing": 1,
    "completed": 18,
    "failed": 1
  }
}
```

---

## 8. 비용 최적화 전략

### 전략 1: 기본값을 WAN으로

```sql
ALTER TABLE video_items
  ALTER COLUMN inference_provider SET DEFAULT 'wan_local';
```

→ 비용 절감 (무료 GPU 서버 사용)

### 전략 2: 중요한 그룹만 Runway 사용

```tsx
// Admin UI에서 그룹 중요도에 따라 기본값 설정
const getDefaultProvider = (groupPriority: string) => {
  if (groupPriority === 'urgent') return 'runway_gen4_turbo';
  if (groupPriority === 'high_quality') return 'runway_veo3.1';
  return 'wan_local';
};
```

### 전략 3: 자동 Fallback

```typescript
// Task 생성 시 WAN이 busy하면 자동으로 Runway 사용
const { data: wanQueueSize } = await supabaseAdmin
  .from('video_items')
  .select('id', { count: 'exact' })
  .eq('inference_provider', 'wan_local')
  .eq('status', 'pending');

const provider = wanQueueSize.count > 50
  ? 'runway_gen4_turbo'  // WAN 큐가 길면 Runway 사용
  : 'wan_local';
```

---

## 9. 체크리스트

### Backend
- [ ] Supabase SQL 실행 (enum + 컬럼 추가)
- [ ] `npm run gen:types` 실행
- [ ] `app/api/admin/tasks/add/route.ts` 수정
- [ ] `app/api/worker/next-task/route.ts` 수정 (worker_type 필터)

### Frontend
- [ ] Admin Task 생성 UI에 Select 추가
- [ ] Admin Queue UI에 추론 방식 컬럼 추가
- [ ] 통계 페이지에 추론 방식별 통계 추가 (선택)

### Worker
- [ ] WAN Worker: `worker_type: "wan"` 추가
- [ ] Runway Worker: `worker_type: "runway"` 추가
- [ ] Runway Worker: `inference_provider`에 따라 모델 선택 로직 추가

### 테스트
- [ ] WAN Worker가 wan_local task만 가져오는지 확인
- [ ] Runway Worker가 runway task만 가져오는지 확인
- [ ] UI에서 추론 방식 선택이 DB에 정확히 저장되는지 확인
- [ ] Gen-4 Turbo vs Veo 3.1 모델이 올바르게 호출되는지 확인

---

## 📚 참고

- **video_items 스키마**: `lib/supabase/database.ts`
- **Admin Dashboard**: `app/admin/queue/page.tsx`
- **Worker API**: `app/api/worker/next-task/route.ts`

---

**작성일**: 2025-01-05
**버전**: 1.0
