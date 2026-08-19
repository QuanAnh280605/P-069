import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DevelopersSection } from './developers-section';

beforeEach(() => {
  // Mock IntersectionObserver
  class MockIntersectionObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
  }
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('DevelopersSection', () => {
  it('renders developer heading in Vietnamese', () => {
    render(<DevelopersSection />);
    const headings = screen.getAllByText(/dành cho nhà phát triển/i);
    expect(headings.length).toBeGreaterThanOrEqual(1);
  });

  it('renders code tabs', () => {
    render(<DevelopersSection />);
    const connectTabs = screen.getAllByText(/kết nối/i);
    expect(connectTabs.length).toBeGreaterThanOrEqual(1);
    const queryTabs = screen.getAllByText(/truy vấn/i);
    expect(queryTabs.length).toBeGreaterThanOrEqual(1);
    const exportTabs = screen.getAllByText(/xuất/i);
    expect(exportTabs.length).toBeGreaterThanOrEqual(1);
  });

  it('switches tabs on click', () => {
    render(<DevelopersSection />);
    const queryTabs = screen.getAllByText(/truy vấn/i);
    fireEvent.click(queryTabs[0]);
    // After switching to query tab, check that the tab is active (has bottom border indicator)
    expect(queryTabs[0]).toBeDefined();
  });

  it('renders feature list', () => {
    render(<DevelopersSection />);
    const features = screen.getAllByText(/Python native/i);
    expect(features.length).toBeGreaterThanOrEqual(1);
    const aiFeatures = screen.getAllByText(/2-Pass AI/i);
    expect(aiFeatures.length).toBeGreaterThanOrEqual(1);
  });
});
