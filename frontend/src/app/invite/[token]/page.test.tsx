import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { mockPush, previewInvite, acceptInvite } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  previewInvite: vi.fn(),
  acceptInvite: vi.fn(),
}));
let authToken: string | null = null;

vi.mock('next/navigation', () => ({
  useParams: () => ({ token: 'invite-token' }),
  useRouter: () => ({ push: mockPush }),
}));

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ token: authToken }),
}));

vi.mock('@/lib/api', () => ({
  previewWorkspaceInviteApi: previewInvite,
  acceptWorkspaceInviteApi: acceptInvite,
}));

import InvitePage from '@/app/invite/[token]/page';

describe('InvitePage', () => {
  beforeEach(() => {
    authToken = null;
    mockPush.mockReset();
    previewInvite.mockResolvedValue({
      organization_name: 'Acme Analytics',
      organization_slug: 'acme-analytics',
      role: 'member',
      expires_at: '2026-08-26T00:00:00Z',
    });
    acceptInvite.mockResolvedValue({ id: 7 });
    window.localStorage.clear();
  });

  afterEach(() => cleanup());

  it('preserves the token and redirects unauthenticated invitees to login', async () => {
    render(<InvitePage />);
    await waitFor(() => expect(screen.getByText('Acme Analytics')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập để tham gia' }));

    expect(window.localStorage.getItem('pending_invite_token')).toBe('invite-token');
    expect(mockPush).toHaveBeenCalledWith('/login?returnTo=/invite/invite-token');
  });

  it('accepts the invitation for an authenticated user and selects the Workspace', async () => {
    authToken = 'access-token';
    render(<InvitePage />);
    await waitFor(() => expect(screen.getByText('Acme Analytics')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Tham gia ngay' }));

    await waitFor(() => expect(acceptInvite).toHaveBeenCalledWith('invite-token'));
    expect(window.localStorage.getItem('current_organization_id')).toBe('7');
    expect(mockPush).toHaveBeenCalledWith('/');
  });
});
