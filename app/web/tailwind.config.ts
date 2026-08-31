import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        paper: 'var(--paper)',
        card: 'var(--card)',
        wash: 'var(--wash)',
        ink: {
          DEFAULT: 'var(--ink)',
          2: 'var(--ink-2)',
          3: 'var(--ink-3)',
        },
        rule: {
          DEFAULT: 'var(--rule)',
          2: 'var(--rule-2)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
          tint: 'var(--accent-tint)',
          fg: 'var(--accent-fg)',
        },
        positive: {
          DEFAULT: 'var(--positive)',
          tint: 'var(--positive-tint)',
        },
        negative: {
          DEFAULT: 'var(--negative)',
          tint: 'var(--negative-tint)',
        },
        warning: {
          DEFAULT: 'var(--warning)',
          tint: 'var(--warning-tint)',
        },
        wb: {
          DEFAULT: 'var(--wb)',
          tint: 'var(--wb-tint)',
        },
        ozon: {
          DEFAULT: 'var(--ozon)',
          tint: 'var(--ozon-tint)',
        },
        lamoda: {
          DEFAULT: 'var(--lamoda)',
          tint: 'var(--lamoda-tint)',
        },
        retail: {
          DEFAULT: 'var(--retail)',
          tint: 'var(--retail-tint)',
        },
        unknown: {
          DEFAULT: 'var(--unknown)',
          tint: 'var(--unknown-tint)',
        },
      },
      borderRadius: {
        DEFAULT: 'var(--radius)',
        sm: '2px',
        md: '4px',
        lg: '6px',
      },
      fontSize: {
        '11': ['11px', { lineHeight: '16px' }],
        '12': ['12px', { lineHeight: '16px' }],
        '13': ['13px', { lineHeight: '18px' }],
        '13.5': ['13.5px', { lineHeight: '20px' }],
        '14': ['14px', { lineHeight: '20px' }],
        '16': ['16px', { lineHeight: '22px' }],
        '18': ['18px', { lineHeight: '26px' }],
        '22': ['22px', { lineHeight: '28px' }],
        '28': ['28px', { lineHeight: '32px' }],
        '32': ['32px', { lineHeight: '36px' }],
      },
    },
  },
  plugins: [],
};

export default config;
