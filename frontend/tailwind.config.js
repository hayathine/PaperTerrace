/** @type {import('tailwindcss').Config} */
export default {
	content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
	theme: {
		extend: {
			colors: {
				brand: {
					DEFAULT: "#f97316", // orange-500
					light: "#fb923c", // orange-400
					lighter: "#fdba74", // orange-300
					soft: "#fff7ed", // orange-50
				},
			},
			animation: {
				"fade-in-up": "fadeInUp 0.5s ease-out",
			},
			keyframes: {
				fadeInUp: {
					"0%": { opacity: "0", transform: "translateY(10px)" },
					"100%": { opacity: "1", transform: "translateY(0)" },
				},
			},
		},
	},
	plugins: [require("@tailwindcss/typography")],
};
