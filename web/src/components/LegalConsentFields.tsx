import { Checkbox, Form } from "antd";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface LegalConsentFieldsProps {
  /** Дополнительный текст под чекбоксами */
  hint?: ReactNode;
}

/** Чекбоксы оферты и согласия на обработку ПДн (обязательны в Form). */
export function LegalConsentFields({ hint }: LegalConsentFieldsProps) {
  return (
    <>
      <Form.Item
        name="accept_terms"
        valuePropName="checked"
        rules={[
          {
            validator: (_, value) =>
              value
                ? Promise.resolve()
                : Promise.reject(new Error("Примите пользовательское соглашение")),
          },
        ]}
        className="!mb-2"
      >
        <Checkbox>
          Я принимаю{" "}
          <Link to="/terms" target="_blank" className="text-sky-700 underline">
            Пользовательское соглашение
          </Link>
        </Checkbox>
      </Form.Item>
      <Form.Item
        name="accept_privacy"
        valuePropName="checked"
        rules={[
          {
            validator: (_, value) =>
              value
                ? Promise.resolve()
                : Promise.reject(new Error("Дайте согласие на обработку персональных данных")),
          },
        ]}
        className="!mb-2"
      >
        <Checkbox>
          Я даю согласие на обработку персональных данных в соответствии с{" "}
          <Link to="/privacy" target="_blank" className="text-sky-700 underline">
            Политикой конфиденциальности
          </Link>
        </Checkbox>
      </Form.Item>
      {hint ? <p className="mb-3 text-xs text-slate-500">{hint}</p> : null}
    </>
  );
}
