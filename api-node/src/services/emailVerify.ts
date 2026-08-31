import { config } from "../config.js";
import { AuthError } from "./auth.js";
import { buildVerifyEmailMail, sendMail } from "./mailer.js";
import {
  getEmailVerifySentAt,
  getUserById,
  hashEmailVerifyToken,
  isEmailVerified,
  markEmailVerifiedByToken,
  newEmailVerifyToken,
  setEmailVerifyToken,
  type User,
} from "../repos/users.js";

const RESEND_COOLDOWN_MS = 5 * 60 * 1000;

export async function issueAndSendEmailVerification(user: User): Promise<void> {
  if (isEmailVerified(user)) {
    return;
  }
  const token = newEmailVerifyToken();
  await setEmailVerifyToken(user.id, hashEmailVerifyToken(token));
  await sendMail(buildVerifyEmailMail({ email: user.email, token }));
}

export async function resendEmailVerification(userId: number): Promise<void> {
  const user = await getUserById(userId);
  if (!user) {
    throw new AuthError("Пользователь не найден", 401);
  }
  if (isEmailVerified(user)) {
    throw new AuthError("Email уже подтверждён", 400);
  }
  const sentAt = await getEmailVerifySentAt(userId);
  if (sentAt && Date.now() - sentAt.getTime() < RESEND_COOLDOWN_MS) {
    throw new AuthError("Письмо уже отправлено — подождите несколько минут", 429);
  }
  await issueAndSendEmailVerification(user);
}

export async function verifyEmailToken(token: string): Promise<User> {
  const raw = token.trim();
  if (!raw || raw.length < 16) {
    throw new AuthError("Некорректная ссылка подтверждения", 400);
  }
  const user = await markEmailVerifiedByToken(hashEmailVerifyToken(raw));
  if (!user) {
    throw new AuthError("Ссылка недействительна или уже использована", 400);
  }
  return user;
}

export function assertEmailVerified(user: User): void {
  if (!isEmailVerified(user)) {
    throw new AuthError(
      "Подтвердите email, чтобы добавлять города на карту",
      403,
    );
  }
}

export function verifyEmailEnabled(): boolean {
  return !["0", "false", "no", "off"].includes(
    (process.env.EMAIL_VERIFY_ENABLED ?? "true").trim().toLowerCase(),
  );
}

/** В тестах/локально без mailer можно отключить обязательную верификацию. */
export function requireVerifiedForOsrm(): boolean {
  if (!verifyEmailEnabled()) return false;
  return config.osrmPrepareRequireEmailVerified;
}
