import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { Button, buttonVariants } from './button';

afterEach(() => {
  cleanup();
});

describe('Button component', () => {
  it('renders children text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: 'Click me' })).toBeDefined();
  });

  it('applies default variant classes', () => {
    render(<Button>Default</Button>);
    const button = screen.getByRole('button', { name: 'Default' });
    expect(button.className).toContain('bg-primary');
  });

  it('applies outline variant classes', () => {
    render(<Button variant="outline">Outline</Button>);
    const button = screen.getByRole('button', { name: 'Outline' });
    expect(button.className).toContain('border');
  });

  it('applies size classes', () => {
    render(<Button size="lg">Large</Button>);
    const button = screen.getByRole('button', { name: 'Large' });
    expect(button.className).toContain('h-10');
  });

  it('applies custom className', () => {
    render(<Button className="custom-class">Custom</Button>);
    const button = screen.getByRole('button', { name: 'Custom' });
    expect(button.className).toContain('custom-class');
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled</Button>);
    const button = screen.getByRole('button', { name: 'Disabled' });
    expect(button).toBeDisabled();
  });

  it('exports buttonVariants function', () => {
    expect(typeof buttonVariants).toBe('function');
    const classes = buttonVariants({ variant: 'default' });
    expect(classes).toContain('bg-primary');
  });
});
