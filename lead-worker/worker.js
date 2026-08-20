/**
 * Приёмник заявок с лендинга hr-oracul.ru/call/
 *
 * Работает на Cloudflare Workers. Принимает JSON, проверяет его и отправляет
 * сообщение в Telegram. Токен бота и идентификатор чата живут в секретах
 * Cloudflare, в коде и в репозитории их нет и быть не должно: репозиторий
 * публичный, любой файл из него отдаётся как страница сайта.
 */

const ALLOWED = ["https://hr-oracul.ru", "http://localhost:8788"];
const LIMITS = { phone: 32, company: 120, tg: 64, page: 200 };

function cors(origin) {
  const allow = ALLOWED.includes(origin) ? origin : ALLOWED[0];
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

function json(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...cors(origin) },
  });
}

function clean(value, max) {
  return String(value == null ? "" : value).trim().slice(0, max);
}

function digits(s) {
  return s.replace(/\D/g, "");
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(origin) });
    }
    if (request.method !== "POST") {
      return json({ ok: false, error: "method" }, 405, origin);
    }
    if (origin && !ALLOWED.includes(origin)) {
      return json({ ok: false, error: "origin" }, 403, origin);
    }

    let data;
    try {
      data = await request.json();
    } catch (e) {
      return json({ ok: false, error: "json" }, 400, origin);
    }

    const phone = clean(data.phone, LIMITS.phone);
    const company = clean(data.company, LIMITS.company);
    const tg = clean(data.tg, LIMITS.tg);
    const page = clean(data.page, LIMITS.page);

    if (digits(phone).length < 10) return json({ ok: false, error: "phone" }, 400, origin);
    if (!company) return json({ ok: false, error: "company" }, 400, origin);
    if (data.consent !== true) return json({ ok: false, error: "consent" }, 400, origin);

    const ip = request.headers.get("CF-Connecting-IP") || "";
    const country = request.cf && request.cf.country ? request.cf.country : "";

    const lines = [
      "<b>Заявка на звонок в отдел продаж</b>",
      "Телефон: " + escapeHtml(phone),
      "Компания и город: " + escapeHtml(company),
    ];
    if (tg) lines.push("Телеграм: " + escapeHtml(tg));
    lines.push("");
    lines.push("Страница: " + escapeHtml(page));
    lines.push("IP: " + escapeHtml(ip) + " " + escapeHtml(country));

    const api = "https://api.telegram.org/bot" + env.BOT_TOKEN + "/sendMessage";
    const res = await fetch(api, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: env.CHAT_ID,
        text: lines.join("\n"),
        parse_mode: "HTML",
        disable_web_page_preview: true,
      }),
    });

    if (!res.ok) {
      return json({ ok: false, error: "telegram" }, 502, origin);
    }
    return json({ ok: true }, 200, origin);
  },
};
