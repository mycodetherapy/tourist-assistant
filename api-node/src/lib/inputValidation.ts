/** Санитизация ввода (parity с input_validation.py). */

const MAX_LENGTHS: Record<string, number> = {
  city: 500,
  dates: 500,
  message: 2000,
};

const INJECTION_PATTERNS: RegExp[] = [
  /ignore\s+(all\s+)?(previous|prior)\s+instructions/i,
  /disregard\s+(all\s+)?(previous|prior)/i,
  /system\s*:/i,
  /assistant\s*:/i,
  /<\|/i,
  /\{\{/i,
  /```/i,
  /jailbreak/i,
  /you\s+are\s+now/i,
  /новые\s+инструкции/i,
  /забудь\s+(все|предыдущ)/i,
  /игнорируй\s+(все|предыдущ)/i,
];

export class InputValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InputValidationError";
  }
}

export function sanitizeAndValidate(
  text: string,
  fieldName: string,
): string {
  const cleaned = text.trim();
  if (!cleaned) {
    throw new InputValidationError(
      `Поле «${fieldName}» не может быть пустым.`,
    );
  }
  const maxLen = MAX_LENGTHS[fieldName] ?? 2000;
  if (cleaned.length > maxLen) {
    throw new InputValidationError(
      `Поле «${fieldName}» слишком длинное (максимум ${maxLen} символов).`,
    );
  }
  for (const pattern of INJECTION_PATTERNS) {
    if (pattern.test(cleaned)) {
      throw new InputValidationError(
        `Поле «${fieldName}» содержит подозрительные конструкции и отклонено.`,
      );
    }
  }
  return cleaned;
}
