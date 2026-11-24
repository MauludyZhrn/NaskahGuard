/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  corePlugins: {
    // Keep existing NaskahGuard typography, table, and form resets intact
    preflight: false,
  },
  theme: {
  	extend: {
  		colors: {
  			border: 'hsl(var(--tw-border))',
  			input: 'hsl(var(--tw-input))',
  			ring: 'hsl(var(--tw-ring))',
  			background: 'hsl(var(--tw-background))',
  			foreground: 'hsl(var(--tw-foreground))',
  			primary: {
  				DEFAULT: 'hsl(var(--tw-primary))',
  				foreground: 'hsl(var(--tw-primary-foreground))'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--tw-secondary))',
  				foreground: 'hsl(var(--tw-secondary-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--tw-destructive))',
  				foreground: 'hsl(var(--tw-destructive-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--tw-muted))',
  				foreground: 'hsl(var(--tw-muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--tw-accent))',
  				foreground: 'hsl(var(--tw-accent-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--tw-popover))',
  				foreground: 'hsl(var(--tw-popover-foreground))'
  			},
  			card: {
  				DEFAULT: 'hsl(var(--tw-card))',
  				foreground: 'hsl(var(--tw-card-foreground))'
  			}
  		},
  		borderRadius: {
  			lg: 'var(--radius-md)',
  			md: 'calc(var(--radius-md) - 2px)',
  			sm: 'var(--radius-sm)'
  		},
  		keyframes: {
  			'accordion-down': {
  				from: {
  					height: '0'
  				},
  				to: {
  					height: 'var(--radix-accordion-content-height)'
  				}
  			},
  			'accordion-up': {
  				from: {
  					height: 'var(--radix-accordion-content-height)'
  				},
  				to: {
  					height: '0'
  				}
  			}
  		},
  		animation: {
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out'
  		}
  	}
  },
  plugins: [],
};
