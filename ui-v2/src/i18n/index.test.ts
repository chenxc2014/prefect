import { afterEach, describe, expect, it } from "vitest";
import { pluralize } from "@/utils/utils";
import { getLanguage, setLanguage, translateState, translateUi } from ".";

afterEach(() => setLanguage("en"));

describe("界面语言", () => {
	it("中文覆盖导航、操作和状态，并保留未知业务文本", () => {
		setLanguage("zh-CN");
		expect(getLanguage()).toBe("zh-CN");
		expect(translateUi("Dashboard")).toBe("概览");
		expect(translateUi("Work Pools")).toBe("工作池");
		expect(translateUi("Cancel")).toBe("取消");
		expect(translateState("Completed")).toBe("已完成");
		expect(translateState("Custom business state")).toBe(
			"Custom business state",
		);
		expect(translateUi("crawler-dev-probe")).toBe("crawler-dev-probe");
		expect(pluralize(2, "Deployment")).toBe("部署");
		expect(pluralize(2, "custom business name")).toBe("custom business names");
	});
	it("可切回英文", () => {
		setLanguage("en");
		expect(translateUi("Dashboard")).toBe("Dashboard");
		expect(translateState("Completed")).toBe("Completed");
	});
});
