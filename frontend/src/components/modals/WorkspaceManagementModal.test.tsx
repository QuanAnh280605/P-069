import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspaceManagementModal } from '@/components/modals/WorkspaceManagementModal';

const { listMembers, listInvites, createInvite, revokeInvite, updateMember, removeMember } = vi.hoisted(() => ({
  listMembers: vi.fn(),
  listInvites: vi.fn(),
  createInvite: vi.fn(),
  revokeInvite: vi.fn(),
  updateMember: vi.fn(),
  removeMember: vi.fn(),
}));

const workspacePermissions = vi.hoisted(() => ({
  current: { can_manage_members: true, can_manage_invitations: true },
  reload: vi.fn(),
}));

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ user: { id: '1' } }),
}));

vi.mock('@/context/WorkspaceContext', () => ({
  useWorkspace: () => ({
    permissions: workspacePermissions.current,
    reloadWorkspaces: workspacePermissions.reload,
  }),
}));

vi.mock('@/lib/api', () => ({
  listWorkspaceMembersApi: listMembers,
  listWorkspaceInvitesApi: listInvites,
  createWorkspaceInviteApi: createInvite,
  revokeWorkspaceInviteApi: revokeInvite,
  updateWorkspaceMemberApi: updateMember,
  removeWorkspaceMemberApi: removeMember,
}));

describe('WorkspaceManagementModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    workspacePermissions.current = { can_manage_members: true, can_manage_invitations: true };
    listMembers.mockResolvedValue([
      { user_id: 1, email: 'admin@example.com', username: 'admin', full_name: 'Workspace Admin', role: 'admin', joined_at: '2026-01-01' },
    ]);
    listInvites.mockResolvedValue([]);
    createInvite.mockResolvedValue({
      id: 7,
      org_id: 3,
      role: 'member',
      status: 'pending',
      expires_at: '2026-08-26T00:00:00Z',
      invite_url: 'https://app.example.com/invite/token',
    });
    revokeInvite.mockResolvedValue(undefined);
    updateMember.mockResolvedValue(undefined);
    removeMember.mockResolvedValue(undefined);
    workspacePermissions.reload.mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  afterEach(() => cleanup());

  it('creates a link-only invitation with the deployed URL', async () => {
    render(<WorkspaceManagementModal isOpen onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText('Workspace Admin')).toBeInTheDocument());

    expect(screen.queryByLabelText('Email người nhận')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Tạo link mời' }));

    await waitFor(() => expect(createInvite).toHaveBeenCalledWith('member'));
    const inviteLink = await screen.findByRole('link', { name: 'https://app.example.com/invite/token' });
    expect(inviteLink).toHaveAttribute('href', 'https://app.example.com/invite/token');
    expect(inviteLink).toHaveAttribute('target', '_blank');

    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Đã copy' })).toBeInTheDocument());
  });

  it('does not render or call management clients without management permissions', async () => {
    workspacePermissions.current = { can_manage_members: false, can_manage_invitations: false };

    render(<WorkspaceManagementModal isOpen onClose={vi.fn()} />);

    expect(screen.queryByText('Quản lý Workspace')).not.toBeInTheDocument();
    await waitFor(() => {
      expect(listMembers).not.toHaveBeenCalled();
      expect(listInvites).not.toHaveBeenCalled();
    });
  });

  it.each([
    [{ can_manage_members: true, can_manage_invitations: false }, listMembers, listInvites],
    [{ can_manage_members: false, can_manage_invitations: true }, listInvites, listMembers],
  ])('calls only the client allowed by its management capability', async (permissions, allowed, denied) => {
    workspacePermissions.current = permissions;

    render(<WorkspaceManagementModal isOpen onClose={vi.fn()} />);

    await waitFor(() => expect(allowed).toHaveBeenCalledOnce());
    expect(denied).not.toHaveBeenCalled();
  });

  it('refetches when a management capability is granted while the modal stays open', async () => {
    workspacePermissions.current = { can_manage_members: false, can_manage_invitations: true };
    const view = render(<WorkspaceManagementModal isOpen onClose={vi.fn()} />);
    await waitFor(() => expect(listInvites).toHaveBeenCalledOnce());
    expect(listMembers).not.toHaveBeenCalled();

    workspacePermissions.current = { can_manage_members: true, can_manage_invitations: true };
    view.rerender(<WorkspaceManagementModal isOpen onClose={vi.fn()} />);

    await waitFor(() => expect(listMembers).toHaveBeenCalledOnce());
  });

  it('offers Admin, Data Lead, and Member roles for invitations and members', async () => {
    render(<WorkspaceManagementModal isOpen onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText('Workspace Admin')).toBeInTheDocument());

    const inviteRole = screen.getByLabelText('Vai trò lời mời');
    expect(inviteRole).toHaveTextContent('Admin');
    expect(inviteRole).toHaveTextContent('Data Lead');
    expect(inviteRole).toHaveTextContent('Member');

    const memberRole = screen.getByLabelText('Vai trò của admin@example.com');
    expect(memberRole).toHaveTextContent('Admin');
    expect(memberRole).toHaveTextContent('Data Lead');
    expect(memberRole).toHaveTextContent('Member');
    expect(screen.getByText(/luôn phải còn ít nhất một Admin/i)).toBeInTheDocument();
  });

  it('shows the backend conflict and keeps the last Admin unchanged', async () => {
    updateMember.mockRejectedValueOnce(new Error('Workspace must retain at least one admin'));
    render(<WorkspaceManagementModal isOpen onClose={vi.fn()} />);
    const memberRole = await screen.findByLabelText('Vai trò của admin@example.com');

    fireEvent.change(memberRole, { target: { value: 'member' } });

    expect(await screen.findByRole('alert')).toHaveTextContent('Workspace must retain at least one admin');
    expect(memberRole).toHaveValue('admin');
    expect(listMembers).toHaveBeenCalledTimes(1);
  });

  it('refreshes workspace permissions and closes after a successful self-demotion', async () => {
    const onClose = vi.fn();
    render(<WorkspaceManagementModal isOpen onClose={onClose} />);
    const memberRole = await screen.findByLabelText('Vai trò của admin@example.com');

    fireEvent.change(memberRole, { target: { value: 'data_lead' } });

    await waitFor(() => expect(workspacePermissions.reload).toHaveBeenCalledOnce());
    expect(onClose).toHaveBeenCalledOnce();
    expect(listMembers).toHaveBeenCalledTimes(1);
  });

  it('refreshes workspace permissions and closes after removing yourself', async () => {
    vi.spyOn(window, 'confirm').mockReturnValueOnce(true);
    const onClose = vi.fn();
    render(<WorkspaceManagementModal isOpen onClose={onClose} />);
    await screen.findByLabelText('Vai trò của admin@example.com');

    fireEvent.click(screen.getByRole('button', { name: 'Xóa' }));

    await waitFor(() => expect(workspacePermissions.reload).toHaveBeenCalledOnce());
    expect(onClose).toHaveBeenCalledOnce();
    expect(listMembers).toHaveBeenCalledTimes(1);
  });

  it('revokes a pending invitation and reloads the list', async () => {
    listInvites.mockResolvedValueOnce([
      { id: 9, org_id: 3, role: 'member', status: 'pending', expires_at: '2026-08-26T00:00:00Z' },
    ]);
    render(<WorkspaceManagementModal isOpen onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText('Link mời #9')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Thu hồi' }));
    await waitFor(() => expect(revokeInvite).toHaveBeenCalledWith(9));
    expect(listInvites.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it('can collapse and expand members and invitations independently', async () => {
    listInvites.mockResolvedValueOnce([
      { id: 9, org_id: 3, role: 'member', status: 'pending', expires_at: '2026-08-26T00:00:00Z' },
    ]);
    render(<WorkspaceManagementModal isOpen onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText('Link mời #9')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /Thành viên/i }));
    expect(screen.queryByText('owner@example.com')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^Invitation/i }));
    expect(screen.queryByText('Link mời #9')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Thành viên/i }));
    expect(screen.getByText('admin@example.com')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Invitation/i }));
    expect(screen.getByText('Link mời #9')).toBeInTheDocument();
  });
});
