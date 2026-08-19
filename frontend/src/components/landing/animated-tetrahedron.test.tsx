import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import { AnimatedTetrahedron } from './animated-tetrahedron';

// Mock canvas 2d context
const mockGetContext = vi.fn();
const mockFillText = vi.fn();
const mockClearRect = vi.fn();

beforeEach(() => {
  vi.useFakeTimers();
  HTMLCanvasElement.prototype.getContext = mockGetContext;
  mockGetContext.mockReturnValue({
    clearRect: mockClearRect,
    fillText: mockFillText,
    font: '',
    textAlign: '',
    textBaseline: '',
    fillStyle: '',
    scale: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('AnimatedTetrahedron', () => {
  it('renders a canvas element', () => {
    const { container } = render(<AnimatedTetrahedron />);
    const canvas = container.querySelector('canvas');
    expect(canvas).toBeDefined();
  });

  it('applies w-full h-full classes', () => {
    const { container } = render(<AnimatedTetrahedron />);
    const canvas = container.querySelector('canvas');
    expect(canvas?.className).toContain('w-full');
    expect(canvas?.className).toContain('h-full');
  });

  it('requests 2d context on mount', () => {
    render(<AnimatedTetrahedron />);
    expect(mockGetContext).toHaveBeenCalledWith('2d');
  });

  it('cleans up animation frame on unmount', () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame');
    const { unmount } = render(<AnimatedTetrahedron />);
    unmount();
    expect(cancelSpy).toHaveBeenCalled();
  });

  it('removes resize listener on unmount', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener');
    const { unmount } = render(<AnimatedTetrahedron />);
    unmount();
    expect(removeSpy).toHaveBeenCalledWith('resize', expect.any(Function));
  });
});
