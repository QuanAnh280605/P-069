import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MetricExplorerView } from '@/components/views/MetricExplorerView';

describe('MetricExplorerView', () => {
  it('blocks query execution for SQL Dump sources', () => {
    render(<MetricExplorerView dbId={3} metrics={[]} catalog={{ db_id: 3, source_type: 'sql_dump', query_supported: false, tables: [], relationships: [] }} theme='light' />);
    expect(screen.getByText(/SQL Dump chỉ chứa metadata DDL/)).toBeInTheDocument();
    expect(screen.queryByText('Compile & Execute')).not.toBeInTheDocument();
  });
});
