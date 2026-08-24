import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { ChatQueryResultCard } from './ChatQueryResultCard';
import { ChatSemanticQueryResult } from '@/lib/api';

describe('ChatQueryResultCard', () => {
  beforeEach(() => {
    cleanup();
  });

  const sampleResult: ChatSemanticQueryResult = {
    spec: {
      metric_ids: [1],
      dimensions: [{ column_id: 10 }],
      filters: [],
      limit: 100,
    },
    columns: ['customer_name', 'revenue'],
    rows: [
      ['Công ty A', 1500000],
      ['Công ty B', 2300000],
    ],
    row_count: 2,
    explanation: 'Số liệu được tính từ chỉ số Doanh thu với công thức SUM(amount).',
    sql: 'SELECT customer_name, SUM(amount) AS revenue FROM orders GROUP BY customer_name LIMIT 100',
    metadata: { base_table: 'orders' },
  };

  it('renders explanation, columns, and rows correctly', () => {
    render(<ChatQueryResultCard result={sampleResult} />);

    expect(screen.getByText(/Giải thích số liệu/i)).toBeInTheDocument();
    expect(screen.getByText(/Số liệu được tính từ chỉ số Doanh thu/i)).toBeInTheDocument();
    expect(screen.getByText('customer_name')).toBeInTheDocument();
    expect(screen.getByText('revenue')).toBeInTheDocument();
    expect(screen.getByText('Công ty A')).toBeInTheDocument();
    expect(screen.getByText('1,500,000')).toBeInTheDocument();
    expect(screen.getByText('Công ty B')).toBeInTheDocument();
    expect(screen.getByText('2,300,000')).toBeInTheDocument();
    expect(screen.getByText(/Hiển thị/i)).toBeInTheDocument();
    expect(screen.getByText(/LIMIT 100 applied/i)).toBeInTheDocument();
    expect(screen.getByText('Read-only')).toBeInTheDocument();
  });

  it('toggles SQL disclosure button when SQL is available', () => {
    render(<ChatQueryResultCard result={sampleResult} />);

    const toggleBtn = screen.getByRole('button', { name: /Xem SQL đã biên dịch/i });
    expect(toggleBtn).toBeInTheDocument();

    // SQL viewer not visible initially
    expect(screen.queryByText(/Compiled SQL/i)).not.toBeInTheDocument();

    // Click to open
    fireEvent.click(toggleBtn);
    expect(screen.getByText(/Ẩn SQL đã biên dịch/i)).toBeInTheDocument();
    expect(screen.getByText(/Compiled SQL/i)).toBeInTheDocument();

    // Click to close
    fireEvent.click(screen.getByRole('button', { name: /Ẩn SQL đã biên dịch/i }));
    expect(screen.queryByText(/Compiled SQL/i)).not.toBeInTheDocument();
  });

  it('does not render SQL disclosure button when SQL is redacted (null)', () => {
    const memberResult: ChatSemanticQueryResult = {
      ...sampleResult,
      sql: null,
    };
    render(<ChatQueryResultCard result={memberResult} />);

    expect(screen.queryByRole('button', { name: /SQL đã biên dịch/i })).not.toBeInTheDocument();
  });

  it('renders empty state message when rows array is empty', () => {
    const emptyResult: ChatSemanticQueryResult = {
      ...sampleResult,
      rows: [],
      row_count: 0,
    };
    render(<ChatQueryResultCard result={emptyResult} />);

    expect(screen.getByText('Không có dữ liệu phù hợp')).toBeInTheDocument();
    expect(screen.getByText(/trả về 0 dòng kết quả/i)).toBeInTheDocument();
  });
});
