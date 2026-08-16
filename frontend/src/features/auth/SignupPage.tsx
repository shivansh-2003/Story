import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth } from "@/lib/auth";
import { AuthLayout } from "@/components/shells/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { cn } from "@/lib/utils";
import { signupSchema, authErrorMessage, type SignupValues } from "./schemas";

function passwordStrength(password: string): number {
  let score = 0;
  if (password.length >= 8) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^\w\s]/.test(password)) score++;
  return score;
}

function StrengthMeter({ password }: { password: string }) {
  const score = passwordStrength(password);
  return (
    <div className="flex gap-1" aria-hidden="true">
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          className={cn(
            "h-1 flex-1 rounded-full transition-colors duration-200",
            i < score ? "bg-primary" : "bg-border",
          )}
        />
      ))}
    </div>
  );
}

export function SignupPage() {
  const { signup, status } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { email: "", password: "" },
  });
  const password = form.watch("password");

  if (status === "signed-in") return <Navigate to="/library" replace />;

  async function onSubmit(values: SignupValues) {
    setServerError(null);
    try {
      await signup(values.email, values.password);
      navigate("/library");
    } catch (err) {
      setServerError(authErrorMessage(err, "signup"));
    }
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-medium">Start writing</h1>
      <p className="mt-1 text-sm text-muted-foreground">Create an account for your writing room.</p>

      <Form {...form}>
        <form className="mt-6 space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input type="email" autoComplete="email" inputMode="email" autoFocus {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Password</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="new-password" {...field} />
                </FormControl>
                <StrengthMeter password={password} />
                <FormMessage />
              </FormItem>
            )}
          />

          {serverError && (
            <p role="alert" className="font-mono text-xs uppercase tracking-wide text-destructive">
              {serverError}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Creating your account…" : "Create account"}
          </Button>
        </form>
      </Form>

      <p className="mt-6 text-sm text-muted-foreground">
        Already have an account? <Link to="/login" className="text-primary hover:underline">Sign in</Link>
      </p>
    </AuthLayout>
  );
}
