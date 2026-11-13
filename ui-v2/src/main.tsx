import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { setDefaultOptions } from "date-fns";
import { zhCN } from "date-fns/locale";
import { App } from "./app";
import { getLanguage } from "./i18n";

document.documentElement.lang = getLanguage();
if (getLanguage() === "zh-CN") setDefaultOptions({ locale: zhCN });

// Render the app
const rootElement = document.getElementById("root");
if (rootElement && !rootElement.innerHTML) {
	const root = ReactDOM.createRoot(rootElement);
	root.render(
		<StrictMode>
			<App />
		</StrictMode>,
	);
}
