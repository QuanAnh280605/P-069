import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ConnectDbModal } from '@/components/modals/ConnectDbModal';

const connectMock = vi.fn();

vi.mock('@/context/AuthContext', () => ({ useAuth: () => ({ token: null }) }));
vi.mock('@/lib/jwt', () => ({ getStoredToken: () => 'stored-access-token' }));
vi.mock('@/lib/api', () => ({
  connectLiveTargetDb: (...args: unknown[]) => connectMock(...args),
  uploadSqlDumpPreview: vi.fn(),
  saveImportedSchema: vi.fn(),
  updateLayer: vi.fn(),
  convertRawSchemaToLayer: () => ({ id: '9', db_name: 'Sales', db_type: 'postgresql', status: 'Draft', updated_at: '', tables: [], metrics: [], semantic_db_id: 12, source_type: 'live' }),
}));

describe('ConnectDbModal authentication', () => {
  beforeEach(() => {
    connectMock.mockReset();
    connectMock.mockResolvedValue({ id: 9, display_name: 'Sales', dialect: 'postgresql', raw_schema: { tables: [] }, updated_at: '', semantic_db_id: 12 });
  });

  it('uses a persisted access token while AuthContext is still hydrating', async () => {
    render(<ConnectDbModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('e.g. E-Commerce Production DB'), { target: { value: 'Sales' } });
    fireEvent.change(screen.getByPlaceholderText(/postgresql\+asyncpg/), { target: { value: 'postgresql+asyncpg://user:pass@localhost/sales' } });
    fireEvent.click(screen.getByText('Bắt Đầu Kết Nối & Introspect'));
    await waitFor(() => expect(connectMock).toHaveBeenCalledWith('Sales', 'auto', 'postgresql+asyncpg://user:pass@localhost/sales', 'stored-access-token'));
    expect(screen.queryByText(/Vui lòng đăng nhập/)).not.toBeInTheDocument();
  });
});
