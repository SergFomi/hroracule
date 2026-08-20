/**
 * Приёмник заявок с лендинга hr-oracul.ru/call/
 *
 * Работает на Cloudflare Workers. Принимает JSON, проверяет его, заводит
 * сделку с контактом в amoCRM и присылает уведомление в Telegram.
 *
 * Секреты живут в переменных окружения Cloudflare, в коде и в репозитории их
 * нет и быть не должно: репозиторий публичный, любой файл из него отдаётся как
 * страница сайта.
 *
 *   BOT_TOKEN        обязательный, токен бота от @BotFather
 *   CHAT_ID          обязательный, куда слать уведомления
 *   AMO_SUBDOMAIN    необязательный, например mycompany (без .amocrm.ru)
 *   AMO_TOKEN        необязательный, долгосрочный токен интеграции
 *   AMO_PIPELINE_ID  необязательный, иначе воронка по умолчанию
 *   AMO_STATUS_ID    необязательный, иначе первый этап воронки
 *
 * Пока AMO_SUBDOMAIN и AMO_TOKEN не заданы, заявки уходят только в Telegram.
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

const clean = (v, max) => String(v == null ? "" : v).trim().slice(0, max);
const digits = (s) => s.replace(/\D/g, "");
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** Сделка с контактом одним запросом, затем примечание с подробностями. */
async function toAmo(env, lead) {
  const base = "https://" + env.AMO_SUBDOMAIN + ".amocrm.ru/api/v4";
  const headers = {
    Authorization: "Bearer " + env.AMO_TOKEN,
    "Content-Type": "application/json",
  };

  const deal = {
    name: "Проверка отдела продаж: " + (lead.company || lead.phone),
    _embedded: {
      contacts: [
        {
          first_name: lead.company || "Заявка с сайта",
          custom_fields_values: [
            { field_code: "PHONE", values: [{ enum_code: "WORK", value: lead.phone }] },
          ],
        },
      ],
    },
  };
  if (env.AMO_PIPELINE_ID) deal.pipeline_id = Number(env.AMO_PIPELINE_ID);
  if (env.AMO_STATUS_ID) deal.status_id = Number(env.AMO_STATUS_ID);

  const res = await fetch(base + "/leads/complex", {
    method: "POST",
    headers,
    body: JSON.stringify([deal]),
  });

  if (!res.ok) {
    return { ok: false, detail: "HTTP " + res.status + " " + (await res.text()).slice(0, 300) };
  }

  const body = await res.json();
  const id = Array.isArray(body) && body[0] ? body[0].id : null;
  if (!id) return { ok: true, id: null };

  const note = [
    "Заявка с лендинга «Позвоню в отдел продаж»",
    "Телефон: " + lead.phone,
    lead.company ? "Компания и город: " + lead.company : "",
    lead.tg ? "Телеграм: " + lead.tg : "",
    "Страница: " + lead.page,
    "IP: " + lead.ip + " " + lead.country,
  ]
    .filter(Boolean)
    .join("\n");

  await fetch(base + "/leads/" + id + "/notes", {
    method: "POST",
    headers,
    body: JSON.stringify([{ note_type: "common", params: { text: note } }]),
  });

  return { ok: true, id };
}

async function toTelegram(env, lead, amo) {
  const lines = [
    "<b>Заявка: проверка отдела продаж</b>",
    "Телефон: " + esc(lead.phone),
    "Компания и город: " + esc(lead.company),
  ];
  if (lead.tg) lines.push("Телеграм: " + esc(lead.tg));
  lines.push("");
  if (!amo) lines.push("amoCRM не подключена");
  else if (amo.ok) lines.push("Сделка в amoCRM создана" + (amo.id ? ", номер " + amo.id : ""));
  else lines.push("Сделка в amoCRM НЕ создана: " + esc(amo.detail));
  lines.push("IP: " + esc(lead.ip) + " " + esc(lead.country));

  const res = await fetch("https://api.telegram.org/bot" + env.BOT_TOKEN + "/sendMessage", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: env.CHAT_ID,
      text: lines.join("\n"),
      parse_mode: "HTML",
      disable_web_page_preview: true,
    }),
  });
  return res.ok;
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

    const lead = {
      phone: clean(data.phone, LIMITS.phone),
      company: clean(data.company, LIMITS.company),
      tg: clean(data.tg, LIMITS.tg),
      page: clean(data.page, LIMITS.page),
      ip: request.headers.get("CF-Connecting-IP") || "",
      country: (request.cf && request.cf.country) || "",
    };

    if (digits(lead.phone).length < 10) return json({ ok: false, error: "phone" }, 400, origin);
    if (!lead.company) return json({ ok: false, error: "company" }, 400, origin);
    if (data.consent !== true) return json({ ok: false, error: "consent" }, 400, origin);

    let amo = null;
    if (env.AMO_SUBDOMAIN && env.AMO_TOKEN) {
      try {
        amo = await toAmo(env, lead);
      } catch (e) {
        amo = { ok: false, detail: String(e).slice(0, 200) };
      }
    }

    let sent = false;
    try {
      sent = await toTelegram(env, lead, amo);
    } catch (e) {
      sent = false;
    }

    // Заявка считается принятой, если её получил хоть один канал.
    if (!sent && !(amo && amo.ok)) {
      return json({ ok: false, error: "delivery" }, 502, origin);
    }
    return json({ ok: true }, 200, origin);
  },
};
