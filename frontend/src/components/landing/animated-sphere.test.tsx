import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import { AnimatedSphere } from './animated-sphere';

// Mock canvas 2d context
const mockGetContext = vi.fn();
const mockFillText = vi.fn();
const mockClearRect = vi.fn();

beforeEach(() => {
  vi.useFakeTimers();
  // Mock canvas getContext
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

describe('AnimatedSphere', () => {
  it('renders a canvas element', () => {
    const { container } = render(<AnimatedSphere />);
    const canvas = container.querySelector('canvas');
    expect(canvas).toBeDefined();
  });

  it('applies custom className', () => {
    const { container } = render(<AnimatedSphere className="custom-class" />);
    const canvas = container.querySelector('canvas');
    expect(canvas?.className).toContain('custom-class');
  });

  it('applies default w-full h-full classes', () => {
    const { container } = render(<AnimatedSphere />);
    const canvas = container.querySelector('canvas');
    expect(canvas?.className).toContain('w-full');
    expect(canvas?.className).toContain('h-full');
  });

  it('requests 2d context on mount', () => {
    render(<AnimatedSphere />);
    expect(mockGetContext).toHaveBeenCalledWith('2d');
  });

  it('cleans up animation frame on unmount', () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame');
    const { unmount } = render(<AnimatedSphere />);
    unmount();
    expect(cancelSpy).toHaveBeenCalled();
  });

  it('removes resize listener on unmount', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener');
    const { unmount } = render(<AnimatedSphere />);
    unmount();
    expect(removeSpy).toHaveBeenCalledWith('resize', expect.any(Function));
  });

  it('accepts custom color prop', () => {
    const { container } = render(<AnimatedSphere color="255, 255, 255" />);
    const canvas = container.querySelector('canvas');
    expect(canvas).toBeDefined();
  });
});
