import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: 'var(--bg)',
          2: 'var(--bg-2)',
        },
        surface: {
          DEFAULT: 'var(--surface)',
          2: 'var(--surface-2)',
        },
        border: {
          DEFAULT: 'var(--border)',
          2: 'var(--border-2)',
        },
        text: {
          DEFAULT: 'var(--text)',
          2: 'var(--text-2)',
          3: 'var(--text-3)',
        },
        nav: {
          bg: 'var(--nav-bg)',
          surface: 'var(--nav-surface)',
          border: 'var(--nav-border)',
          text: 'var(--nav-text)',
          'text-2': 'var(--nav-text-2)',
          'text-3': 'var(--nav-text-3)',
        },
        paper: 'var(--bg)',
        card: 'var(--surface)',
        wash: 'var(--surface-2)',
        ink: {
          DEFAULT: 'var(--text)',
          2: 'var(--text-2)',
          3: 'var(--text-3)',
        },
        rule: {
          DEFAULT: 'var(--border)',
          2: 'var(--border-2)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          2: 'var(--accent-2)',
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
        info: {
          DEFAULT: 'var(--info)',
          tint: 'var(--info-tint)',
        },
        wb: { DEFAULT: 'var(--wb)', tint: 'var(--wb-tint)' },
        ozon: { DEFAULT: 'var(--ozon)', tint: 'var(--ozon-tint)' },
        lamoda: {
          DEFAULT: 'var(--lamoda)', tint: 'var(--lamoda-tint)',
        },
        retail: {
          DEFAULT: 'var(--retail)', tint: 'var(--retail-tint)',
        },
        unknown: {
          DEFAULT: 'var(--unknown)', tint: 'var(--unknown-tint)',
        },
      },
      borderRadius: {
        DEFAULT: 'var(--radius)',
        sm: 'var(--radius-sm)',
        md: 'var(--radius)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
      },
      fontFamily: {
        display: [
          'Bricolage Grotesque', 'Manrope', 'system-ui', 'sans-serif',
        ],
        sans: ['Manrope', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '10': ['10.5px', { lineHeight: '14px' }],
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
        '40': ['40px', { lineHeight: '44px', letterSpacing: '-0.02em' }],
        '56': ['56px', { lineHeight: '60px', letterSpacing: '-0.03em' }],
        '72': ['72px', { lineHeight: '76px', letterSpacing: '-0.03em' }],
      },
      boxShadow: {
        xs: 'var(--shadow-xs)',
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
      },
    },
  },
  plugins: [],
};

export default config;
