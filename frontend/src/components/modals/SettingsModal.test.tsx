import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SettingsModal } from '@/components/modals/SettingsModal';

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: '1', name: 'Linh Tran', email: 'linh@example.com' },
    token: 'token',
  }),
}));

vi.mock('@/context/ThemeContext', () => ({
  useTheme: () => ({ theme: 'light', toggleTheme: vi.fn() }),
}));

vi.mock('@/context/WorkspaceContext', () => ({
  useWorkspace: () => ({ role: 'data_lead' }),
}));

describe('SettingsModal', () => {
  afterEach(() => cleanup());

  it('displays the active workspace role instead of an Owner label', () => {
    render(<SettingsModal isOpen onClose={vi.fn()} />);

    expect(screen.getByText('Data Lead')).toBeInTheDocument();
    expect(screen.queryByText('Owner')).not.toBeInTheDocument();
  });
});
