'use client';

import { FormEvent, useEffect, useState } from 'react';
import { CalendarClock, Check, ChevronDown, Copy, Link2, Shield, UserPlus, X } from 'lucide-react';

import {
  createWorkspaceInviteApi,
  listWorkspaceInvitesApi,
  listWorkspaceMembersApi,
  removeWorkspaceMemberApi,
  revokeWorkspaceInviteApi,
  updateWorkspaceMemberApi,
  WorkspaceInvite,
  WorkspaceMember,
  WorkspaceRole,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

const inviteRoleLabels: Record<WorkspaceInvite['role'], string> = {
  member: 'Member',
  data_lead: 'Data Lead',
};

export function WorkspaceManagementModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [invites, setInvites] = useState<WorkspaceInvite[]>([]);
  const [role, setRole] = useState<'member' | 'data_lead'>('member');
  const [inviteUrl, setInviteUrl] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [inviting, setInviting] = useState(false);
  const [revokingId, setRevokingId] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const [membersExpanded, setMembersExpanded] = useState(true);
  const [invitesExpanded, setInvitesExpanded] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [nextMembers, nextInvites] = await Promise.all([
        listWorkspaceMembersApi(),
        listWorkspaceInvitesApi(),
      ]);
      setMembers(nextMembers);
      setInvites(nextInvites);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể tải dữ liệu Workspace');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) void load();
  }, [isOpen]);

  const invite = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setInviteUrl('');
    setCopied(false);
    setInviting(true);
    try {
      const created = await createWorkspaceInviteApi(role);
      setInviteUrl(created.invite_url || '');
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể tạo link mời');
    } finally {
      setInviting(false);
    }
  };

  const copyInviteUrl = async () => {
    if (!inviteUrl) return;
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('Không thể copy link. Hãy bôi đen và copy thủ công.');
    }
  };

  const changeRole = async (member: WorkspaceMember, nextRole: WorkspaceRole) => {
    setError('');
    try {
      await updateWorkspaceMemberApi(member.user_id, nextRole);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể thay đổi quyền thành viên');
    }
  };

  const remove = async (member: WorkspaceMember) => {
    if (!window.confirm(`Xóa ${member.email} khỏi Workspace?`)) return;
    setError('');
    try {
      await removeWorkspaceMemberApi(member.user_id);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể xóa thành viên');
    }
  };

  const revoke = async (invitationId: number) => {
    setError('');
    setRevokingId(invitationId);
    try {
      await revokeWorkspaceInviteApi(invitationId);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể thu hồi link mời');
    } finally {
      setRevokingId(null);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto bg-background sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-display text-2xl">
            <UserPlus className="h-5 w-5" /> Quản lý Workspace
          </DialogTitle>
          <DialogDescription>
            Tạo link mời, quản lý vai trò và kiểm soát các invitation đang hoạt động.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
            {error}
          </div>
        )}

        <section className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
              <Link2 className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Mời thành viên bằng link</h3>
              <p className="mt-1 text-xs text-muted-foreground">
                Tạo link dùng một lần và gửi link cho thành viên cần tham gia Workspace.
              </p>
            </div>
          </div>

          <form className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end" onSubmit={invite}>
            <label className="space-y-1.5">
              <span className="text-sm font-medium">Vai trò</span>
              <select
                id="invite-role"
                aria-label="Vai trò lời mời"
                value={role}
                onChange={(event) => setRole(event.target.value as 'member' | 'data_lead')}
                disabled={inviting}
                className="border-input bg-background text-foreground focus-visible:border-ring focus-visible:ring-ring/50 h-9 w-full rounded-md border px-3 text-sm outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="member">Member</option>
                <option value="data_lead">Data Lead</option>
              </select>
            </label>
            <Button type="submit" disabled={inviting} className="h-9">
              <Link2 className="h-4 w-4" />
              {inviting ? 'Đang tạo...' : 'Tạo link mời'}
            </Button>
          </form>

          {inviteUrl && (
            <div className="mt-4 space-y-3 rounded-lg border border-border bg-secondary/30 p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold">Link mời vừa tạo</p>
                <span className="text-xs text-muted-foreground">Có thể mở và copy</span>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <a
                  href={inviteUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="min-w-0 flex-1 break-all rounded-md border border-border bg-background px-3 py-2 font-mono text-[11px] text-primary underline-offset-2 hover:underline"
                >
                  {inviteUrl}
                </a>
                <Button type="button" variant="outline" size="sm" onClick={() => void copyInviteUrl()}>
                  {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
                  {copied ? 'Đã copy' : 'Copy'}
                </Button>
              </div>
            </div>
          )}
        </section>

        <section>
          <div className="mb-2 flex items-center justify-between gap-3">
            <button
              type="button"
              aria-expanded={membersExpanded}
              aria-controls="workspace-members-panel"
              onClick={() => setMembersExpanded((expanded) => !expanded)}
              className="group flex min-w-0 items-center gap-2 text-left text-sm font-semibold"
            >
              <Shield className="h-4 w-4" />
              <span>Thành viên</span>
              <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${membersExpanded ? 'rotate-180' : ''}`} />
            </button>
            {loading && <span className="text-xs text-muted-foreground">Đang tải...</span>}
          </div>
          {membersExpanded && (
            <div id="workspace-members-panel" className="divide-y divide-border rounded-xl border border-border bg-card">
              {members.map((member) => (
                <div key={member.user_id} className="flex flex-wrap items-center justify-between gap-3 p-3 text-sm">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{member.full_name || member.username}</p>
                    <p className="truncate text-xs text-muted-foreground">{member.email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      aria-label={`Vai trò của ${member.email}`}
                      value={member.role}
                      onChange={(event) => void changeRole(member, event.target.value as WorkspaceRole)}
                      className="border-input bg-background text-foreground h-8 rounded-md border px-2 text-xs"
                    >
                      <option value="data_lead">Data Lead</option>
                      <option value="member">Member</option>
                    </select>
                    <Button type="button" variant="ghost" size="sm" onClick={() => void remove(member)} className="text-destructive hover:text-destructive">
                      <X className="h-3.5 w-3.5" /> Xóa
                    </Button>
                  </div>
                </div>
              ))}
              {!loading && members.length === 0 && <p className="p-4 text-xs text-muted-foreground">Chưa có thành viên.</p>}
            </div>
          )}
        </section>

        <section>
          <div className="mb-2 flex items-center justify-between gap-3">
            <button
              type="button"
              aria-expanded={invitesExpanded}
              aria-controls="workspace-invites-panel"
              onClick={() => setInvitesExpanded((expanded) => !expanded)}
              className="group flex min-w-0 items-center gap-2 text-left"
            >
              <h3 className="flex items-center gap-2 text-sm font-semibold">
                <Link2 className="h-4 w-4" /> Invitation
              </h3>
              <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${invitesExpanded ? 'rotate-180' : ''}`} />
            </button>
            <div className="flex items-center gap-2">
              <p className="mt-1 text-xs text-muted-foreground">
                Link chưa sử dụng sẽ tự hết hạn sau 7 ngày.
              </p>
              <span className="rounded-full bg-secondary px-2.5 py-1 text-xs font-semibold text-secondary-foreground">
                {invites.length}
              </span>
            </div>
          </div>

          {invitesExpanded && <div id="workspace-invites-panel" className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="hidden grid-cols-[1fr_auto_auto] items-center gap-4 border-b border-border bg-secondary/30 px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground sm:grid">
              <span>Vai trò</span>
              <span>Hết hạn</span>
              <span className="text-right">Thao tác</span>
            </div>
            <div className="divide-y divide-border">
              {invites.map((item) => (
                <div key={item.id} className="grid gap-2 px-4 py-3 text-xs sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <Link2 className="h-3.5 w-3.5" />
                    </span>
                    <div className="min-w-0">
                      <p className="font-semibold">{inviteRoleLabels[item.role]}</p>
                      <p className="truncate font-mono text-[10px] text-muted-foreground">Link mời #{item.id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 text-muted-foreground sm:justify-self-end">
                    <CalendarClock className="h-3.5 w-3.5" />
                    <span>Hết hạn {new Date(item.expires_at).toLocaleDateString('vi-VN')}</span>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={revokingId === item.id}
                    onClick={() => void revoke(item.id)}
                    className="justify-self-start px-2 text-destructive hover:text-destructive sm:justify-self-end"
                  >
                    {revokingId === item.id ? 'Đang thu hồi...' : 'Thu hồi'}
                  </Button>
                </div>
              ))}
              {!loading && invites.length === 0 && (
                <div className="px-4 py-8 text-center text-xs text-muted-foreground">
                  Chưa có invitation đang mở.
                </div>
              )}
            </div>
          </div>}
        </section>
      </DialogContent>
    </Dialog>
  );
}
