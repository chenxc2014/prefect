import { useNavigate } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";
import { useAuth } from "@/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PrefectLogo } from "@/components/ui/prefect-logo";
import { getLanguage, setLanguage, translateUi } from "@/i18n";

interface LoginPageProps {
	redirectTo?: string;
}

export function LoginPage({ redirectTo = "/dashboard" }: LoginPageProps) {
	const [password, setPassword] = useState("");
	const [error, setError] = useState("");
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { login } = useAuth();
	const navigate = useNavigate();

	const handleSubmit = (e: FormEvent) => {
		e.preventDefault();
		if (isSubmitting || !password.trim()) return;

		setIsSubmitting(true);
		setError("");

		void login(password).then((result) => {
			if (result.success) {
				void navigate({ to: redirectTo });
			} else {
				setError(translateUi(result.error ?? "Authentication failed"));
				setIsSubmitting(false);
			}
		});
	};

	return (
		<div className="flex items-center justify-center min-h-screen">
			<Card className="w-full max-w-[400px]">
				<CardHeader className="flex flex-col items-center gap-4">
					<PrefectLogo className="size-16" />
					<CardTitle>Login</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="mb-4 flex justify-end">
						<Button
							type="button"
							size="sm"
							variant="ghost"
							onClick={() => {
								setLanguage(getLanguage() === "zh-CN" ? "en" : "zh-CN");
								window.location.reload();
							}}
						>
							中文 / English
						</Button>
					</div>
					<form onSubmit={handleSubmit} className="flex flex-col gap-4">
						<Input
							type="password"
							placeholder="admin:pass"
							value={password}
							onChange={(e) => setPassword(e.target.value)}
							autoFocus
							disabled={isSubmitting}
						/>
						{error && <p className="text-sm text-destructive">{error}</p>}
						<Button type="submit" disabled={isSubmitting} className="w-full">
							{isSubmitting ? "Logging in..." : "Login"}
						</Button>
					</form>
				</CardContent>
			</Card>
		</div>
	);
}
