/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            animation: {
                'bounce-short': 'bounce 1s 1',
                'bounce-subtle': 'bounce-subtle 2s infinite'
            },
            keyframes: {
                'bounce-subtle': {
                    '0%, 100%': { transform: 'translateY(-2%)', animationTimingFunction: 'cubic-bezier(0.8,0,1,1)' },
                    '50%': { transform: 'none', animationTimingFunction: 'cubic-bezier(0,0,0.2,1)' }
                }
            }
        },
    },
    plugins: [
        require('@tailwindcss/typography'),
    ],
}
