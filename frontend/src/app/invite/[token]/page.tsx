'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ArrowRight, CheckCircle2, Clock3, Users } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/AuthContext';
import { acceptWorkspaceInviteApi, previewWorkspaceInviteApi, WorkspaceInvitePreview } from '@/lib/api';

const roleLabels = { member: 'Member', data_lead: 'Data Lead' } as const;

export default function InvitePage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const { token: authToken } = useAuth();
  const [invite, setInvite] = useState<WorkspaceInvitePreview | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState(false);

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
    setAccepting(true);
    setError('');
    try {
      const workspace = await acceptWorkspaceInviteApi(params.token);
      window.localStorage.setItem('current_organization_id', String(workspace.id));
      router.push('/');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể tiếp nhận lời mời');
    } finally {
      setAccepting(false);
    }
  };

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-6 text-foreground">
      <div className="ws-grid-bg pointer-events-none absolute inset-0" aria-hidden="true" />
      <section className="relative w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-2xl sm:p-8">
        <div className="mb-8 flex items-center justify-between">
          <span className="font-display text-xl tracking-tight">AI Semantic Layer</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Invitation</span>
        </div>

        {loading && <p className="text-sm text-muted-foreground">Đang kiểm tra link mời...</p>}
        {error && (
          <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {invite && (
          <div className="space-y-6">
            <div>
              <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Workspace access</p>
              <h1 className="font-display text-4xl leading-none tracking-tight">Tham gia Workspace.</h1>
              <p className="mt-3 text-sm text-muted-foreground">
                Bạn được mời vào Workspace <strong className="text-foreground">{invite.organization_name}</strong>.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-border bg-secondary/30 p-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground"><Users className="h-4 w-4" /> Vai trò</div>
                <p className="mt-2 text-sm font-semibold">{roleLabels[invite.role]}</p>
              </div>
              <div className="rounded-xl border border-border bg-secondary/30 p-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground"><Clock3 className="h-4 w-4" /> Có hiệu lực đến</div>
                <p className="mt-2 text-sm font-semibold">{new Date(invite.expires_at).toLocaleDateString('vi-VN')}</p>
              </div>
            </div>

            <Button type="button" onClick={() => void accept()} disabled={accepting} className="h-11 w-full rounded-full">
              {accepting ? 'Đang tham gia...' : authToken ? 'Tham gia ngay' : 'Đăng nhập để tham gia'}
              {!accepting && <ArrowRight className="h-4 w-4" />}
            </Button>

            <p className="flex items-center justify-center gap-1.5 text-center text-[11px] text-muted-foreground">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
              Invitation chỉ có thể được sử dụng một lần.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
