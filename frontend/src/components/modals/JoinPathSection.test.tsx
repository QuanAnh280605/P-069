import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import * as api from '@/lib/api';
import { JoinPathSection } from '@/components/modals/JoinPathSection';
import { MetricJoinPathOptions } from '@/lib/api';

const options: MetricJoinPathOptions = {
  '20': [
    {
      relationship_ids: [5],
      entity_ids: [10, 20],
      labels: ['Đơn thuộc khách'],
      descriptions: ['Mỗi đơn hàng thuộc về một khách hàng'],
    },
    {
      relationship_ids: [6],
      entity_ids: [10, 20],
      labels: ['Đơn giao cho khách'],
      descriptions: ['Giao dịch được gán cho khách hàng'],
    },
  ],
};

describe('JoinPathSection', () => {
  afterEach(() => cleanup());

  it('fetches governed options and surfaces a stale selection with a clear action', async () => {
    vi.spyOn(api, 'getMetricJoinPathOptionsApi').mockResolvedValue(options);
    const onChange = vi.fn();
    // Stable reference avoids re-render loops from a fresh object literal each render.
    const value = { '20': [99] };
    render(
      <JoinPathSection
        dbId="1"
        catalog={null}
        baseEntity="orders"
        baseEntityId={10}
        value={value}
        onChange={onChange}
      />,
    );

    const alert = await screen.findByText(/Một số ngữ cảnh quan hệ đã lưu/);
    expect(alert).toHaveTextContent(/không còn hợp lệ/);
    fireEvent.click(screen.getByText(/Xoá lựa chọn không hợp lệ/));
    expect(onChange).toHaveBeenCalledWith({});
  });

  it('renders nothing when dbId is absent', () => {
    const { container } = render(
      <JoinPathSection dbId={null} catalog={null} baseEntity="orders" value={{}} onChange={vi.fn()} />,
    );
    expect(container.querySelector('[data-testid="join-path-selector"]')).toBeNull();
  });

  it('clears stale options when baseEntityId becomes null without a new API call', async () => {
    const spy = vi.spyOn(api, 'getMetricJoinPathOptionsApi').mockResolvedValue(options);
    const onChange = vi.fn();
    const value = { '20': [99] };
    const { rerender } = render(
      <JoinPathSection dbId="1" catalog={null} baseEntity="orders" baseEntityId={10} value={value} onChange={onChange} />,
    );
    await screen.findByText(/Một số ngữ cảnh quan hệ đã lưu/);
    const callsAfterLoad = spy.mock.calls.length;
    expect(callsAfterLoad).toBeGreaterThan(0);

    rerender(
      <JoinPathSection dbId="1" catalog={null} baseEntity="orders" baseEntityId={null} value={value} onChange={onChange} />,
    );
    await waitFor(() => expect(screen.queryByText(/Một số ngữ cảnh quan hệ đã lưu/)).toBeNull());
    // No additional API call after the base entity is cleared.
    expect(spy.mock.calls.length).toBe(callsAfterLoad);
  });
});
