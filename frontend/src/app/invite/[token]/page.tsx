'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { useAuth } from '@/context/AuthContext';
import { acceptWorkspaceInviteApi, previewWorkspaceInviteApi, WorkspaceInvitePreview } from '@/lib/api';

export default function InvitePage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const { token: authToken } = useAuth();
  const [invite, setInvite] = useState<WorkspaceInvitePreview | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!params.token) return;
    void previewWorkspaceInviteApi(params.token)
      .then(setInvite)
      .catch((reason) => setError(reason instanceof Error ? reason.message : 'Invitation không hợp lệ'))
      .finally(() => setLoading(false));
  }, [params.token]);

  const accept = async () => {
    if (!authToken) {
      window.localStorage.setItem('pending_invite_token', params.token);
      router.push(`/login?returnTo=/invite/${params.token}`);
      return;
    }
    try {
      const workspace = await acceptWorkspaceInviteApi(params.token);
      window.localStorage.setItem('current_organization_id', String(workspace.id));
      router.push('/');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể tiếp nhận invitation');
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6 dark:bg-slate-950">
      <section className="w-full max-w-md rounded-2xl border bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-slate-900">
        <h1 className="text-xl font-bold">Lời mời tham gia Workspace</h1>
        {loading && <p className="mt-4 text-sm text-slate-500">Đang kiểm tra link...</p>}
        {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {invite && (
          <div className="mt-4 space-y-2 text-sm">
            <p>Bạn được mời vào <strong>{invite.organization_name}</strong>.</p>
            <p>Vai trò: <strong>{invite.role}</strong></p>
            {invite.invitee_email && <p>Email được chỉ định: {invite.invitee_email}</p>}
            <button type="button" onClick={() => void accept()} className="mt-4 w-full rounded-xl bg-indigo-600 px-4 py-3 font-semibold text-white">
              {authToken ? 'Tham gia ngay' : 'Đăng nhập để tham gia'}
            </button>
          </div>
        )}
      </section>
    </main>
  );
}
