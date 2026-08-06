import { config, isPlaceholderSecret } from "../config.js";
import {
  createAccessToken,
  decryptSecret,
  encryptSecret,
  maskApiKey,
} from "../lib/crypto.js";
import { hashPassword, verifyPassword } from "../lib/passwords.js";
import {
  clearUserLlmKey,
  createUser,
  getUserByEmail,
  getUserById,
  getUserSettings,
  upsertUserSettings,
  type User,
} from "../repos/users.js";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export type LlmMode = "none" | "platform" | "byok";
const VALID_LLM_MODES = new Set<LlmMode>(["none", "platform", "byok"]);

export class AuthError extends Error {
  readonly statusCode: number;
  constructor(message: string, statusCode = 400) {
    super(message);
    this.statusCode = statusCode;
  }
}

function validateEmail(email: string): string {
  const normalized = email.trim().toLowerCase();
  if (!EMAIL_RE.test(normalized)) {
    throw new AuthError("Некорректный email");
  }
  return normalized;
}

function validatePassword(password: string): void {
  if (password.length < 8) {
    throw new AuthError("Пароль должен быть не короче 8 символов");
  }
}

export function normalizeLlmMode(raw: string | null | undefined): LlmMode {
  const value = (raw ?? "none").trim().toLowerCase();
  if (VALID_LLM_MODES.has(value as LlmMode)) {
    return value as LlmMode;
  }
  return "none";
}

export async function getUserLlmMode(userId: number): Promise<LlmMode> {
  const row = await getUserSettings(userId);
  return normalizeLlmMode(row?.llm_mode);
}

function assertByokConfigured(userId: number, row: Awaited<ReturnType<typeof getUserSettings>>): void {
  if (!row?.llm_api_key_enc) {
    throw new AuthError(
      "Добавьте API-ключ LLM в настройках профиля",
      428,
    );
  }
  try {
    const apiKey = decryptSecret(row.llm_api_key_enc).trim();
    if (!apiKey) {
      throw new AuthError(
        "Сохранённый LLM-ключ пустой — укажите ключ заново в настройках",
        428,
      );
    }
    if (isPlaceholderSecret(apiKey)) {
      throw new AuthError(
        "Сохранённый LLM-ключ недействителен — укажите реальный ключ провайдера",
        428,
      );
    }
  } catch (err) {
    if (err instanceof AuthError) {
      throw err;
    }
    throw new AuthError(
      "Сохранённый LLM-ключ повреждён — укажите ключ заново в настройках",
      428,
    );
  }
}

/** @deprecated use assertCanStartRun */
export async function requireUserLlmConfigured(userId: number): Promise<void> {
  await assertCanStartRun(userId);
}

export async function assertCanStartRun(userId: number): Promise<LlmMode> {
  const mode = await getUserLlmMode(userId);
  if (mode === "none") {
    return "none";
  }
  if (mode === "platform") {
    throw new AuthError(
      "Оплата AI из приложения скоро будет доступна. "
        + "Пока используйте бесплатный режим или свой API-ключ.",
      503,
    );
  }
  const row = await getUserSettings(userId);
  assertByokConfigured(userId, row);
  return "byok";
}

export async function registerUser(
  email: string,
  password: string,
): Promise<{ user: User; token: string }> {
  const normalized = validateEmail(email);
  validatePassword(password);
  if (await getUserByEmail(normalized)) {
    throw new AuthError("Пользователь с таким email уже существует", 409);
  }
  const user = await createUser({
    email: normalized,
    password_hash: await hashPassword(password),
  });
  const token = createAccessToken(user.id, user.email);
  return { user, token };
}

export async function loginUser(
  email: string,
  password: string,
): Promise<{ user: User; token: string }> {
  const normalized = validateEmail(email);
  const user = await getUserByEmail(normalized);
  if (!user?.password_hash) {
    throw new AuthError("Неверный email или пароль", 401);
  }
  if (!(await verifyPassword(password, user.password_hash))) {
    throw new AuthError("Неверный email или пароль", 401);
  }
  const token = createAccessToken(user.id, user.email);
  return { user, token };
}

export async function userFromTokenSub(sub: string): Promise<User> {
  const user = await getUserById(Number(sub));
  if (!user) {
    throw new AuthError("Пользователь не найден", 401);
  }
  return user;
}

export async function getLlmSettingsView(userId: number) {
  const row = await getUserSettings(userId);
  const configured = Boolean(row?.llm_api_key_enc);
  let preview: string | null = null;
  if (configured && row?.llm_api_key_enc) {
    try {
      preview = maskApiKey(decryptSecret(row.llm_api_key_enc));
    } catch {
      preview = "***";
    }
  }
  const llm_mode = normalizeLlmMode(row?.llm_mode);
  return {
    llm_mode,
    llm_key_configured: configured,
    llm_key_preview: preview,
    llm_base_url: row?.llm_base_url || config.defaultLlmBaseUrl,
    llm_model: row?.llm_model || config.defaultLlmModel,
    estimated_ai_run_cost_rub: config.estimatedAiRunCostRub,
  };
}

export async function saveLlmSettings(
  userId: number,
  fields: {
    llm_mode?: LlmMode | null;
    llm_api_key?: string | null;
    llm_base_url?: string | null;
    llm_model?: string | null;
  },
): Promise<void> {
  let enc: string | undefined;
  if (fields.llm_api_key !== undefined && fields.llm_api_key !== null) {
    const key = fields.llm_api_key.trim();
    if (!key) throw new AuthError("LLM API key не может быть пустым");
    if (isPlaceholderSecret(key)) {
      throw new AuthError("Укажите реальный API-ключ LLM, не плейсхолдер");
    }
    enc = encryptSecret(key);
  }
  let llm_mode: LlmMode | undefined;
  if (fields.llm_mode !== undefined && fields.llm_mode !== null) {
    llm_mode = normalizeLlmMode(fields.llm_mode);
    if (llm_mode === "byok" && enc === undefined) {
      const existing = await getUserSettings(userId);
      if (!existing?.llm_api_key_enc) {
        throw new AuthError(
          "Для режима «свой ключ» сначала укажите API key",
          428,
        );
      }
    }
  }
  await upsertUserSettings(userId, {
    llm_api_key_enc: enc,
    llm_base_url: fields.llm_base_url ?? undefined,
    llm_model: fields.llm_model ?? undefined,
    llm_mode,
  });
}

export async function removeLlmKey(userId: number): Promise<void> {
  await clearUserLlmKey(userId);
}
