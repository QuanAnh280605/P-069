---
title: "Frontend Code Style & Rules (Next.js & TypeScript)"
description: "Quy tắc chuẩn hóa toàn diện cho phần phát triển Frontend dự án AI Semantic Layer"
weight: 2
---

# Frontend Code Style & Architecture Rules (Next.js 14+ / TypeScript)

Tài liệu này chi tiết hóa toàn bộ **Quy tắc thiết kế code, kiến trúc và UX/UI** áp dụng cho Frontend (Next.js App Router, TypeScript, Tailwind CSS, Shadcn UI) trong dự án.

---

## 1. Kiến trúc & Rendering Rules (Server Component First)

1. **React Server Components (RSC) Mặc định**:
   * Mọi component trong `app/` mặc định là Server Component để tối ưu bundle size và render trực tiếp tại server.
   * Chỉ khai báo chỉ thị `'use client'` ở đầu file khi component thực sự cần:
     * Hook state (`useState`, `useReducer`, `useEffect`, `useContext`).
     * Browser Event Listeners (`onClick`, `onChange`, `onSubmit`).
     * Browser APIs (`window`, `localStorage`, `document`).
2. **Cấu trúc thư mục theo Domain (Feature-First Architecture)**:
   * `src/components/ui/`: Chỉ chứa các UI primitives dùng chung độc lập nghiệp vụ (Button, Input, Modal, Badge...).
   * `src/components/features/`: Chứa các component gắn liền với domain nghiệp vụ (SchemaViewer, MetricEditor, HITLReviewTable...).
   * `src/context/`: Quản lý state toàn cục (`AuthContext`, `ThemeContext`).
   * `src/lib/`: Chứa utility, helper và API client (`api.ts`, `jwt.ts`).

---

## 2. Quy tắc TypeScript (Strict Type Safety)

1. **Cấm dùng `any`**:
   * Mọi props, state, API payload đều phải định nghĩa `interface` hoặc `type` tường minh.
   * Sử dụng `@typescript-eslint/no-explicit-any` warning/error để tự động bắt lỗi.
2. **Không sử dụng `React.FC`**:
   * Khai báo Component với kiểu Props tường minh:
   ```typescript
   // ✅ TỐT — Khai báo kiểu Props tường minh
   interface ButtonProps extends React.ComponentProps<"button"> {
     variant?: "primary" | "secondary" | "outline";
     isLoading?: boolean;
   }

   export function Button({ variant = "primary", isLoading, children, ...props }: ButtonProps) {
     return <button {...props}>{children}</button>;
   }

   // ❌ TỆ — Không dùng React.FC (che lấp generic types và implicit children)
   export const Button: React.FC<ButtonProps> = (props) => { ... };
   ```
3. **`import type` cho DTO & Interfaces**:
   * Sử dụng `import type { UserProfile } from '@/types'` để giảm dung lượng file JavaScript bundle sinh ra.

---

## 3. Quy tắc Đặt tên (Naming Conventions)

| Đối tượng | Quy chuẩn | Ví dụ |
|-----------|-----------|-------|
| Component File | PascalCase | `MetricEditorTable.tsx` |
| Hook / Utility File | camelCase | `useAuth.ts`, `jwt.ts` |
| Component Function | PascalCase | `export function SchemaCard() {}` |
| Helper Function | camelCase | `const formatDateTime = (val: string) => {}` |
| Interface / Type | PascalCase | `interface SemanticTableDTO {}` |
| Custom Hook | `use` + PascalCase | `function useSemanticSchema()` |
| Constant | UPPER_SNAKE | `DEFAULT_TIMEOUT_MS = 5000` |

---

## 4. API Layer, State & Error Handling

1. **Centralized API Client (`src/lib/api.ts`)**:
   * Mọi request tới Backend FastAPI phải thông qua Axios Instance tập trung.
   * **Request Interceptor**: Tự động chèn Bearer Token từ `js-cookie` / Auth Context.
   * **Response Interceptor**: Bắt lỗi `401 Unauthorized` để tự động refresh JWT token hoặc điều hướng về `/login`. Bắt lỗi `500` để hiển thị Toast thông báo.
2. **Handling Loading States**:
   * Luôn dùng **Skeleton Loaders** (UI giữ chỗ) khi fetch dữ liệu bất đồng bộ. Không để màn hình trắng hoặc giật lag layout (Cumulative Layout Shift).
3. **Form Validation & Client-side Checks**:
   * Thực hiện validate dữ liệu ở client trước khi gọi API (khớp 1-1 với Pydantic Schema ở Backend).

---

## 5. Quy tắc Bảo mật Frontend (Security Rules)

1. **Bảo vệ Secret & Biến môi trường**:
   * Chỉ những biến môi trường có tiền tố `NEXT_PUBLIC_` mới được phép sử dụng ở Frontend (ví dụ `NEXT_PUBLIC_API_URL`).
   * Không bao giờ hardcode API Keys, Secret tokens hoặc Private Passwords trong mã nguồn Frontend.
2. **Phòng chống XSS (Cross-Site Scripting)**:
   * Không sử dụng `dangerouslySetInnerHTML` trừ khi dữ liệu đã được làm sạch (sanitized).

---

## 6. Quy tắc UX/UI Đặc thù Dự án (Project-Specific UX Rules)

1. **AI Progress Feedback**: Hiển thị Step Progress Bar rõ ràng theo 3 bước khi AI introspect & enrich DB Schema:
   * `Step 1: Introspecting Schema` (`✅ Done`)
   * `Step 2: Enriching Business Names & Descriptions` (`⏳ Processing`)
   * `Step 3: Suggesting Business Metrics` (`⏸ Waiting Review`)
2. **Indicator Phân biệt Nguồn gốc Metric**:
   * Chỉ số do AI đề xuất: `<Badge variant="purple">AI Suggested</Badge>`
   * Chỉ số do User tự tạo: `<Badge variant="outline">Manual</Badge>`
3. **1-Click HITL Interactive**: Mọi thông tin tên nghiệp vụ, mô tả cột, business metrics cho phép sửa trực tiếp (inline edit với icon ✏️) không mở popup/trang mới.
4. **Badge phân biệt Trạng thái Lưu**: Hiển thị rõ bản nháp chưa commit (`Draft`) và bản đã lưu vào Metadata Store (`Saved`).

---

## 7. Quy tắc Viết Test cho Frontend (Frontend Testing Rules)

1. **Bắt buộc viết Unit / Integration Test khi implement Component / Hook mới (Code + Test Mandatory)**:
   * Mọi feature, component (trong `src/components/features/` và `src/components/ui/`), custom hook (`src/hooks/`), hoặc utility function (`src/lib/`) khi tạo mới hoặc sửa đổi logic **bắt buộc phải đi kèm file test tương ứng**.
   * File test phải nằm trong thư mục `__tests__/` đồng cấp hoặc đặt kế bên file component với đuôi `.test.tsx` / `.test.ts` (ví dụ: `MetricEditorTable.test.tsx`).

2. **Công cụ Kiểm thử Chuẩn hoá**:
   * Sử dụng **Vitest** / **Jest** kết hợp với **React Testing Library (`@testing-library/react`)** và `@testing-library/user-event`.

3. **Mặt hàng & Tiêu chí Test (Coverage Focus)**:
   * **UI Components**: Verify rendering đúng elements/text, test các trạng thái `Loading` (Skeleton), `Error` alert, và `Empty` state.
   * **Interactive UI**: Test tương tác người dùng (user action: `click`, `change`, `inline edit`, `submit form`).
   * **Custom Hooks / Lib Utilities**: Test logic hàm, data transformers, validation với đầy đủ edge cases.
   * **API / Context Mocking**: Sử dụng Mock Service Worker (MSW) hoặc `vi.fn()` / `jest.fn()` để mock API responses. **Tuyệt đối không gọi API backend thật trong unit tests**.

4. **Định nghĩa Hoàn thành (Definition of Done - DoD)**:
   * Một component hay tính năng UI chỉ được coi là hoàn thành (Ready for Review/Merge) khi:
     * Không có lỗi Lint (`npm run lint`).
     * Không có lỗi Type check (`tsc --noEmit`).
     * Tất cả các Unit Tests frontend chạy qua thành công (`npm run test`).

