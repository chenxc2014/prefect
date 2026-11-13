import { chinese, normalizedChinese } from "../../localization/dictionary";

export type Language = "zh-CN" | "en";
const storageKey = "prefect-ui-language";
let selectedLanguage: Language | undefined;

export function getLanguage(): Language {
	if (selectedLanguage) return selectedLanguage;
	try {
		const stored = localStorage.getItem(storageKey);
		if (stored === "zh-CN" || stored === "en") return stored;
	} catch {
		/* 浏览器限制存储时仍可使用默认语言。 */
	}
	return import.meta.env.VITE_DEFAULT_LOCALE === "en" ? "en" : "zh-CN";
}

export function setLanguage(language: Language): void {
	selectedLanguage = language;
	document.documentElement.lang = language;
	try {
		localStorage.setItem(storageKey, language);
	} catch {
		/* 当前会话仍然生效。 */
	}
}

export function translateUi(message: string): string {
	if (getLanguage() === "en") return message;
	const normalized = message.replace(/\s+/g, " ").trim();
	return (
		chinese[normalized] ??
		normalizedChinese.get(normalized.toLowerCase()) ??
		message
	);
}

// 仅翻译 Prefect 内置状态名，保留自定义状态名称。
export function translateState(name: string): string {
	const states = new Set([
		"Completed",
		"Failed",
		"Running",
		"Pending",
		"Scheduled",
		"Cancelled",
		"Cancelling",
		"Crashed",
		"Paused",
		"Late",
		"Retrying",
		"AwaitingRetry",
		"AwaitingConcurrencySlot",
		"Suspended",
		"Resuming",
	]);
	return states.has(name) ? translateUi(name) : name;
}
