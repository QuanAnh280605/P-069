'use client';

import { useEffect, useState } from 'react';

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

export function WorkspaceManagementModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [invites, setInvites] = useState<WorkspaceInvite[]>([]);
  const [role, setRole] = useState<'member' | 'data_lead'>('member');
  const [email, setEmail] = useState('');
  const [inviteUrl, setInviteUrl] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    try {
      const [nextMembers, nextInvites] = await Promise.all([
        listWorkspaceMembersApi(),
        listWorkspaceInvitesApi(),
      ]);
      setMembers(nextMembers);
      setInvites(nextInvites);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể tải dữ liệu Workspace');
    }
  };

  useEffect(() => {
    if (isOpen) void load();
  }, [isOpen]);

  if (!isOpen) return null;

  const invite = async () => {
    try {
      const created = await createWorkspaceInviteApi(role, email || undefined);
      setInviteUrl(created.invite_url || '');
      setEmail('');
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể tạo lời mời');
    }
  };

  const changeRole = async (member: WorkspaceMember, nextRole: WorkspaceRole) => {
    setError('');
    try {
      await updateWorkspaceMemberApi(member.user_id, nextRole);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể thay đổi quyền thành viên');
      await load();
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
      <section className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl dark:bg-slate-900">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">Quản lý Workspace</h2>
          <button type="button" onClick={onClose} className="text-slate-500">Đóng</button>
        </div>
        {error && <p className="mt-3 rounded-lg bg-red-50 p-2 text-xs text-red-700">{error}</p>}

        <div className="mt-5 rounded-xl border p-4">
          <h3 className="text-sm font-bold">Mời thành viên</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email (tuỳ chọn)" className="rounded-lg border px-3 py-2 text-sm" />
            <select value={role} onChange={(event) => setRole(event.target.value as 'member' | 'data_lead')} className="rounded-lg border px-3 py-2 text-sm">
              <option value="member">Member</option>
              <option value="data_lead">Data Lead</option>
            </select>
            <button type="button" onClick={() => void invite()} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white">Tạo link</button>
          </div>
          {inviteUrl && <button type="button" onClick={() => void navigator.clipboard.writeText(inviteUrl)} className="mt-3 break-all text-left text-xs text-indigo-600">Copy link: {inviteUrl}</button>}
        </div>

        <div className="mt-5">
          <h3 className="text-sm font-bold">Thành viên</h3>
          <div className="mt-2 divide-y rounded-xl border">
            {members.map((member) => (
              <div key={member.user_id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
                <div><p className="font-semibold">{member.full_name || member.username}</p><p className="text-xs text-slate-500">{member.email}</p></div>
                <div className="flex items-center gap-2">
                  <select value={member.role} onChange={(event) => void changeRole(member, event.target.value as WorkspaceRole)} className="rounded border px-2 py-1 text-xs">
                    <option value="admin">Admin</option><option value="data_lead">Data Lead</option><option value="member">Member</option>
                  </select>
                  <button type="button" onClick={() => void remove(member)} className="text-xs text-red-600">Xóa</button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-5">
          <h3 className="text-sm font-bold">Link đang mở</h3>
          <div className="mt-2 divide-y rounded-xl border">
            {invites.map((item) => (
              <div key={item.id} className="flex items-center justify-between p-3 text-xs">
                <span>{item.invitee_email || 'Link mở'} · {item.role} · hết hạn {new Date(item.expires_at).toLocaleDateString('vi-VN')}</span>
                <button
                  type="button"
                  onClick={() => {
                    setError('');
                    void revokeWorkspaceInviteApi(item.id)
                      .then(load)
                      .catch((reason: unknown) => {
                        setError(reason instanceof Error ? reason.message : 'Không thể thu hồi link mời');
                      });
                  }}
                  className="text-red-600"
                >
                  Thu hồi
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
