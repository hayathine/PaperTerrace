"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
function App() {
    const [config, setConfig] = (0, react_1.useState)(null);
    const [loading, setLoading] = (0, react_1.useState)(true);
    (0, react_1.useEffect)(() => {
        fetch('/api/config')
            .then(res => res.json())
            .then(data => {
            setConfig(data);
            setLoading(false);
        })
            .catch(err => {
            console.error('Failed to fetch config', err);
            setLoading(false);
        });
    }, []);
    return ((0, jsx_runtime_1.jsx)("div", { className: "min-h-screen bg-gray-100 flex items-center justify-center", children: (0, jsx_runtime_1.jsxs)("div", { className: "bg-white p-8 rounded-lg shadow-md max-w-md w-full", children: [(0, jsx_runtime_1.jsx)("h1", { className: "text-2xl font-bold mb-4 text-blue-600", children: "PaperTerrace React" }), (0, jsx_runtime_1.jsx)("p", { className: "mb-4 text-gray-700", children: "frontend migration in progress..." }), (0, jsx_runtime_1.jsxs)("div", { className: "bg-gray-50 p-4 rounded border border-gray-200", children: [(0, jsx_runtime_1.jsx)("h2", { className: "font-semibold mb-2", children: "Backend Connection Status:" }), loading ? ((0, jsx_runtime_1.jsx)("p", { className: "text-gray-500", children: "Connecting..." })) : config ? ((0, jsx_runtime_1.jsxs)("div", { className: "text-green-600", children: [(0, jsx_runtime_1.jsx)("p", { children: "\u2705 Connected to FastAPI" }), (0, jsx_runtime_1.jsx)("pre", { className: "text-xs mt-2 text-gray-500 overflow-auto", children: JSON.stringify(config, null, 2) })] })) : ((0, jsx_runtime_1.jsx)("p", { className: "text-red-500", children: "\u274C Failed to connect" }))] })] }) }));
}
exports.default = App;
//# sourceMappingURL=App.js.map