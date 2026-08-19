import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import { AnimatedWave } from './animated-wave';

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

describe('AnimatedWave', () => {
  it('renders a canvas element', () => {
    const { container } = render(<AnimatedWave />);
    const canvas = container.querySelector('canvas');
    expect(canvas).toBeDefined();
  });

  it('applies w-full h-full classes', () => {
    const { container } = render(<AnimatedWave />);
    const canvas = container.querySelector('canvas');
    expect(canvas?.className).toContain('w-full');
    expect(canvas?.className).toContain('h-full');
  });

  it('requests 2d context on mount', () => {
    render(<AnimatedWave />);
    expect(mockGetContext).toHaveBeenCalledWith('2d');
  });

  it('cleans up animation frame on unmount', () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame');
    const { unmount } = render(<AnimatedWave />);
    unmount();
    expect(cancelSpy).toHaveBeenCalled();
  });

  it('removes resize listener on unmount', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener');
    const { unmount } = render(<AnimatedWave />);
    unmount();
    expect(removeSpy).toHaveBeenCalledWith('resize', expect.any(Function));
  });
});
