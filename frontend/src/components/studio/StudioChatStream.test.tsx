import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { StudioChatStream } from '@/components/studio/StudioChatStream';

describe('StudioChatStream', () => {
  it('shows the server YAML preview directly below an AI suggestion', () => {
    render(<StudioChatStream messages={[{ id: '1', sender: 'assistant', text: 'Gợi ý', timestamp: '10:00', suggestions: [{ definition: { metric: { name: 'Doanh thu', formula: { function: 'SUM', expression: 'quantity * unit_price' }, base_entity: 'OrderItem', filters: [], status: 'pending_approval', confidence: 'high', excluded_notes: '' } }, yaml_preview: 'metric:\n  name: Doanh thu\n' }] }]} onSendMessage={vi.fn()} isLoading={false} tableNames={[]} />);
    expect(screen.getByText('YAML preview')).toBeInTheDocument();
    expect(screen.getByText(/name: Doanh thu/)).toBeInTheDocument();
    expect(screen.queryByText(/SQL Compiled/)).not.toBeInTheDocument();
  });
});
