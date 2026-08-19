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
    listMembers.mockResolvedValue([
      { user_id: 1, email: 'owner@example.com', username: 'owner', full_name: 'Owner', role: 'data_lead', joined_at: '2026-01-01' },
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
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  afterEach(() => cleanup());

  it('creates a link-only invitation with the deployed URL', async () => {
    render(<WorkspaceManagementModal isOpen onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText('Owner')).toBeInTheDocument());

    expect(screen.queryByLabelText('Email người nhận')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Tạo link mời' }));

    await waitFor(() => expect(createInvite).toHaveBeenCalledWith('member'));
    const inviteLink = await screen.findByRole('link', { name: 'https://app.example.com/invite/token' });
    expect(inviteLink).toHaveAttribute('href', 'https://app.example.com/invite/token');
    expect(inviteLink).toHaveAttribute('target', '_blank');

    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Đã copy' })).toBeInTheDocument());
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
    expect(screen.getByText('owner@example.com')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Invitation/i }));
    expect(screen.getByText('Link mời #9')).toBeInTheDocument();
  });
});
