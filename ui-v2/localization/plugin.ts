import ts from "typescript";
import type { Plugin } from "vite";
import { hasTranslation } from "./dictionary";

const displayAttributes = new Set([
	"placeholder",
	"title",
	"aria-label",
	"alt",
	"label",
	"description",
	"searchPlaceholder",
]);
const displayProperties = new Set([
	"label",
	"title",
	"description",
	"header",
	"placeholder",
	"emptyMessage",
]);

// 只识别可见文案位置，绝不批量替换路由、枚举值、接口参数和任意运行数据。
export function visibleText(node: ts.Node): string | undefined {
	if (ts.isJsxText(node)) return node.text.replace(/\s+/g, " ").trim();
	if (!ts.isStringLiteral(node)) return undefined;
	const parent = node.parent;
	if (
		ts.isBindingElement(parent) &&
		parent.initializer === node &&
		displayAttributes.has(parent.name.getText())
	)
		return node.text;
	if (ts.isJsxAttribute(parent) && displayAttributes.has(parent.name.getText()))
		return node.text;
	if (
		ts.isPropertyAssignment(parent) &&
		parent.initializer === node &&
		displayProperties.has(parent.name.getText().replace(/["']/g, ""))
	)
		return node.text;
	if (
		ts.isJsxExpression(parent) &&
		parent.expression === node &&
		!ts.isJsxAttribute(parent.parent)
	)
		return node.text;
	if (ts.isCallExpression(parent) && parent.arguments[0] === node) {
		const called = parent.expression.getText();
		if (
			/^(?:toast\.(?:success|error|info|warning)|setError|usePageTitle)$/.test(
				called,
			)
		)
			return node.text;
	}
	let branch: ts.Node = node;
	while (
		ts.isConditionalExpression(branch.parent) &&
		(branch.parent.whenTrue === branch || branch.parent.whenFalse === branch)
	)
		branch = branch.parent;
	if (
		ts.isJsxExpression(branch.parent) &&
		branch.parent.expression === branch &&
		!ts.isJsxAttribute(branch.parent.parent)
	)
		return node.text;
	return undefined;
}

export function translateSource(
	code: string,
	filename: string,
): { code: string; count: number } {
	if (
		!/\/src\/(?:components|routes)\/.*\.tsx$/.test(
			filename.replaceAll("\\", "/"),
		) ||
		/\.(?:test|stories)\.tsx$/.test(filename)
	)
		return { code, count: 0 };
	const source = ts.createSourceFile(
		filename,
		code,
		ts.ScriptTarget.Latest,
		true,
		ts.ScriptKind.TSX,
	);
	const replacements: { start: number; end: number; text: string }[] = [];
	function visit(node: ts.Node) {
		const text = visibleText(node);
		if (text && hasTranslation(text)) {
			const call = `__prefectTranslate(${JSON.stringify(text)})`;
			const jsx = ts.isJsxText(node) || ts.isJsxAttribute(node.parent);
			replacements.push({
				start: node.getStart(source),
				end: node.end,
				text: jsx ? `{${call}}` : call,
			});
		}
		ts.forEachChild(node, visit);
	}
	visit(source);
	let result = code;
	for (const replacement of replacements.sort((a, b) => b.start - a.start))
		result =
			result.slice(0, replacement.start) +
			replacement.text +
			result.slice(replacement.end);
	if (replacements.length)
		result =
			'import { translateUi as __prefectTranslate } from "@/i18n";\n' + result;
	return { code: result, count: replacements.length };
}

export function chineseUi(): Plugin {
	return {
		name: "prefect-chinese-ui",
		enforce: "pre",
		transform(code, id) {
			const result = translateSource(code, id.split("?")[0]);
			return result.count ? { code: result.code, map: null } : undefined;
		},
	};
}
