import type { FastifyInstance } from "fastify";
import swagger from "@fastify/swagger";
import swaggerUi from "@fastify/swagger-ui";
import { openApiComponents } from "../openapi/components.js";

export type SwaggerOptions = {
  /** Живой Swagger UI на /docs (по умолчанию включён). */
  enableUi?: boolean;
};

export async function registerSwagger(
  app: FastifyInstance,
  options: SwaggerOptions = {},
): Promise<void> {
  const enableUi = options.enableUi ?? process.env.OPENAPI_UI !== "0";

  await app.register(swagger, {
    openapi: {
      openapi: "3.1.0",
      info: {
        title: "Туристический ассистент API",
        description:
          "REST API веб-интерфейса: multi-user SaaS, Postgres, асинхронная сборка LangGraph (worker), BYOK LLM.",
        version: "2.0.0",
      },
      servers: [
        {
          url: "http://localhost:8001",
          description: "api-node (локально)",
        },
      ],
      tags: [
        { name: "auth", description: "Регистрация, вход, Google OAuth" },
        { name: "profile", description: "Профиль и настройки BYOK" },
        { name: "trips", description: "Поездки, программа, геокодинг" },
        { name: "runs", description: "Статус фоновых прогонов" },
        { name: "health", description: "Проверка доступности" },
      ],
      components: openApiComponents,
    },
  });

  if (enableUi) {
    await app.register(swaggerUi, {
      routePrefix: "/docs",
      uiConfig: {
        docExpansion: "list",
        deepLinking: true,
      },
    });
  }

  for (const [name, schema] of Object.entries(openApiComponents.schemas)) {
    app.addSchema({ ...(schema as object), $id: name });
  }
}
