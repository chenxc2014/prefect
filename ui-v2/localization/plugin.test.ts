import { describe, expect, it } from "vitest";
import { translateSource } from "./plugin";

describe("中文构建转换", () => {
	it("翻译界面文本，同时保留路由、状态值和业务名称", () => {
		const source =
			'const options = [{value: "Running", label: "Running"}]; export const Page = () => <a href="/runs" title="Runs"><span>Dashboard</span><input value="Dashboard" placeholder="Search..." />{run.name}{pending ? "Loading..." : "Save"}</a>';
		const output = translateSource(source, "/project/src/components/page.tsx");
		expect(output.code).toContain('value: "Running"');
		expect(output.code).toContain('label: __prefectTranslate("Running")');
		expect(output.code).toContain('href="/runs"');
		expect(output.code).toContain('value="Dashboard"');
		expect(output.code).toContain("{run.name}");
		expect(output.code).toContain('__prefectTranslate("Dashboard")');
		expect(output.code).toContain('title={__prefectTranslate("Runs")}');
		expect(output.code).toContain('__prefectTranslate("Loading...")');
	});
	it("不转换 API 或测试源码，也不转换未知文案", () => {
		const source =
			'const value = "Dashboard"; <span>Custom business name</span>';
		expect(translateSource(source, "/project/src/api/file.tsx").count).toBe(0);
		expect(
			translateSource(source, "/project/src/components/file.test.tsx").count,
		).toBe(0);
		expect(
			translateSource(source, "/project/src/components/file.tsx").count,
		).toBe(0);
	});
});
