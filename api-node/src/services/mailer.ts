import { config } from "../config.js";

export type MailPayload = {
  to: string;
  subject: string;
  html: string;
  text: string;
};

export function mailerConfigured(): boolean {
  if ((process.env.MAILER_ENABLED ?? "true").trim().toLowerCase() === "false") {
    return false;
  }
  return Boolean(
    (process.env.RESEND_API_KEY ?? "").trim() ||
      ((process.env.SMTP_HOST ?? "").trim() && (process.env.MAIL_FROM ?? "").trim()),
  );
}

function fromAddress(): string {
  return (process.env.MAIL_FROM ?? "Прогуляй <noreply@progulyai.ru>").trim();
}

/** Отправка через Resend HTTP API (предпочтительно) или лог в dev без ключа. */
export async function sendMail(payload: MailPayload): Promise<void> {
  const apiKey = (process.env.RESEND_API_KEY ?? "").trim();
  if (apiKey) {
    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: fromAddress(),
        to: [payload.to],
        subject: payload.subject,
        html: payload.html,
        text: payload.text,
      }),
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`Resend failed: ${res.status} ${body.slice(0, 300)}`);
    }
    return;
  }

  // Dev fallback: не ломаем регистрацию без mailer
  if (!mailerConfigured() || process.env.NODE_ENV !== "production") {
    console.info(
      `[mailer:dev] to=${payload.to} subject=${payload.subject}\n${payload.text}`,
    );
    return;
  }
  throw new Error("Mailer not configured (set RESEND_API_KEY or SMTP)");
}

export function buildVerifyEmailMail(params: {
  email: string;
  token: string;
}): MailPayload {
  const base = config.frontendUrl;
  const url = `${base}/verify-email?token=${encodeURIComponent(params.token)}`;
  return {
    to: params.email,
    subject: "Подтвердите email — Прогуляй",
    text: `Подтвердите адрес: ${url}\n\nСсылка действует ограниченное время.`,
    html: `<p>Подтвердите email для аккаунта в <strong>Прогуляй</strong>.</p>
<p><a href="${url}">Подтвердить email</a></p>
<p style="color:#666;font-size:12px">${url}</p>`,
  };
}

export function buildOsrmPrepareResultMail(params: {
  email: string;
  cityName: string;
  ok: boolean;
  error?: string;
}): MailPayload {
  if (params.ok) {
    return {
      to: params.email,
      subject: `Город ${params.cityName} готов на карте — Прогуляй`,
      text: `Пеший граф для «${params.cityName}» готов. Можно собирать маршруты с MapLibre.`,
      html: `<p>Пеший граф для <strong>${params.cityName}</strong> готов.</p>
<p>Можно собирать маршруты с картой MapLibre.</p>`,
    };
  }
  return {
    to: params.email,
    subject: `Не удалось подготовить ${params.cityName} — Прогуляй`,
    text: `Подготовка «${params.cityName}» не удалась.${params.error ? ` ${params.error}` : ""} Квота возвращена.`,
    html: `<p>Подготовка <strong>${params.cityName}</strong> не удалась.</p>
${params.error ? `<p>${params.error}</p>` : ""}
<p>Квота возвращена — можно попробовать снова позже.</p>`,
  };
}
