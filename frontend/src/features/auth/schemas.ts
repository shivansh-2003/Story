import { z } from "zod";
import { ApiError } from "@/lib/apiFetch";

export const loginSchema = z.object({
  email: z.string().email("Enter a valid email."),
  password: z.string().min(1, "Enter your password."),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const signupSchema = z.object({
  email: z.string().email("Enter a valid email."),
  password: z.string().min(8, "At least 8 characters."),
});
export type SignupValues = z.infer<typeof signupSchema>;

export function authErrorMessage(err: unknown, mode: "login" | "signup"): string {
  if (err instanceof ApiError) {
    if (err.status === 401 && mode === "login") return "That email and password don't match. Try again.";
    if (err.status === 409 && mode === "signup") return "That email already has an account. Sign in instead.";
    return err.message;
  }
  return "Can't reach the server. Check your connection and try again.";
}
