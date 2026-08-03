import {
  createCipheriv,
  createDecipheriv,
  createHmac,
  randomBytes,
  timingSafeEqual,
} from "node:crypto";
import jwt from "jsonwebtoken";
import { config } from "../config.js";

export interface JwtPayload {
  sub: string;
  email: string;
}

export function createAccessToken(userId: number, email: string): string {
  return jwt.sign(
    { sub: String(userId), email },
    config.jwtSecret(),
    { algorithm: "HS256", expiresIn: config.jwtTtlMinutes * 60 },
  );
}

export function decodeAccessToken(token: string): JwtPayload {
  const payload = jwt.verify(token, config.jwtSecret(), {
    algorithms: ["HS256"],
  }) as jwt.JwtPayload;
  if (!payload.sub || !payload.email) {
    throw new Error("invalid token");
  }
  return { sub: String(payload.sub), email: String(payload.email) };
}

function fernetKeys(): { signingKey: Buffer; encKey: Buffer } {
  const key = Buffer.from(config.settingsEncryptionKey(), "base64url");
  if (key.length !== 32) {
    throw new Error("SETTINGS_ENCRYPTION_KEY invalid");
  }
  return { signingKey: key.subarray(0, 16), encKey: key.subarray(16) };
}

function toFernetBase64(buf: Buffer): string {
  return buf
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

function fromFernetBase64(value: string): Buffer {
  let normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  while (normalized.length % 4 !== 0) {
    normalized += "=";
  }
  return Buffer.from(normalized, "base64");
}

function fernetSign(data: Buffer, signingKey: Buffer): Buffer {
  return createHmac("sha256", signingKey).update(data).digest();
}

/** Fernet (compatible with Python cryptography.fernet). */
export function encryptSecret(value: string): string {
  const { signingKey, encKey } = fernetKeys();
  const iv = randomBytes(16);
  const cipher = createCipheriv("aes-128-cbc", encKey, iv);
  const ciphertext = Buffer.concat([
    cipher.update(value, "utf8"),
    cipher.final(),
  ]);
  const version = Buffer.from([0x80]);
  const timestamp = Buffer.alloc(8);
  timestamp.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 1000)));
  const token = Buffer.concat([version, timestamp, iv, ciphertext]);
  const sig = fernetSign(token, signingKey);
  return toFernetBase64(Buffer.concat([token, sig]));
}

export function decryptSecret(ciphertext: string): string {
  const { signingKey, encKey } = fernetKeys();
  const raw = fromFernetBase64(ciphertext);
  if (raw.length < 57) {
    throw new Error("invalid ciphertext");
  }
  const token = raw.subarray(0, raw.length - 32);
  const sig = raw.subarray(raw.length - 32);
  const expected = fernetSign(token, signingKey);
  if (!timingSafeEqual(sig, expected)) {
    throw new Error("invalid signature");
  }
  const iv = token.subarray(9, 25);
  const encrypted = token.subarray(25);
  const decipher = createDecipheriv("aes-128-cbc", encKey, iv);
  return Buffer.concat([decipher.update(encrypted), decipher.final()]).toString(
    "utf8",
  );
}

export function maskApiKey(apiKey: string): string {
  const key = apiKey.trim();
  if (key.length <= 12) return "***";
  return `${key.slice(0, 7)}...${key.slice(-4)}`;
}
