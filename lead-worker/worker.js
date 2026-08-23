/**
 * Приёмник заявок с лендингов hr-oracul.ru/call/ и hr-oracul.ru/rca/
 *
 * Работает на Cloudflare Workers. Принимает JSON, проверяет его, заводит
 * сделку с контактом в amoCRM и присылает уведомление в Telegram.
 *
 * Отвечает страницe сразу после того, как сделка создана. Примечание к сделке
 * и уведомление в Telegram доделываются фоном через ctx.waitUntil, чтобы
 * человек не ждал три с лишним секунды на кнопке.
 *
 * Секреты живут в переменных окружения Cloudflare, в коде и в репозитории их
 * нет и быть не должно: репозиторий публичный, любой файл из него отдаётся как
 * страница сайта.
 *
 *   BOT_TOKEN        обязательный, токен бота от @BotFather
 *   CHAT_ID          обязательный, куда слать уведомления
 *   AMO_SUBDOMAIN    поддомен amoCRM, задан в wrangler.toml
 *   AMO_TOKEN        долгосрочный токен интеграции amoCRM
 *   AMO_PIPELINE_ID  необязательный, иначе воронка по умолчанию
 *   AMO_STATUS_ID    необязательный, иначе первый этап воронки
 */

const ALLOWED = ["https://hr-oracul.ru", "http://localhost:8788"];
const LIMITS = { phone: 32, company: 120, tg: 64, task: 200, page: 200 };

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

const amoBase = (env) => "https://" + env.AMO_SUBDOMAIN + ".amocrm.ru/api/v4";
const amoHeaders = (env) => ({
  Authorization: "Bearer " + env.AMO_TOKEN,
  "Content-Type": "application/json",
});

/**
 * С какого лендинга пришла заявка. Страницы разбора вложены в /rca/, и у
 * каждой своя тема: с человеком из /content/ и человеком из /docs/ идёт
 * разный разговор, поэтому тема попадает и в название сделки, и в Telegram.
 */
const isRazbor = (lead) => lead.page.indexOf("/rca/") !== -1;

const RAZBOR = [
  ["/rca/content/", "разбор: тексты"],
  ["/rca/docs/", "разбор: документы"],
  ["/rca/leads/", "разбор: входящие"],
  ["/rca/mama/", "разбор: вечера"],
];

function leadTitle(lead) {
  if (!isRazbor(lead)) return "проверка отдела продаж";
  const hit = RAZBOR.find((r) => lead.page.indexOf(r[0]) !== -1);
  return hit ? hit[1] : "разбор рутины";
}

const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);

/** Сделка вместе с контактом одним запросом. Этого ответа мы ждём. */
async function createLead(env, lead) {
  const contact = { first_name: lead.company || lead.tg || lead.phone || "Заявка с сайта" };
  // Телефон кладём только когда это действительно телефон: на лендинге
  // разбора человек может оставить вместо номера имя в Telegram.
  if (digits(lead.phone).length >= 10) {
    contact.custom_fields_values = [
      { field_code: "PHONE", values: [{ enum_code: "WORK", value: lead.phone }] },
    ];
  }
  const deal = {
    name: capital(leadTitle(lead)) + " — " + (lead.company || lead.phone || lead.tg),
    _embedded: { contacts: [contact] },
  };
  if (env.AMO_PIPELINE_ID) deal.pipeline_id = Number(env.AMO_PIPELINE_ID);
  if (env.AMO_STATUS_ID) deal.status_id = Number(env.AMO_STATUS_ID);

  const res = await fetch(amoBase(env) + "/leads/complex", {
    method: "POST",
    headers: amoHeaders(env),
    body: JSON.stringify([deal]),
  });
  if (!res.ok) {
    return { ok: false, detail: "HTTP " + res.status + " " + (await res.text()).slice(0, 200) };
  }
  const body = await res.json();
  return { ok: true, id: (Array.isArray(body) && body[0] && body[0].id) || null };
}

/** Подробности заявки. Уходит фоном, человек этого не ждёт. */
async function addNote(env, id, lead) {
  const text = [
    "Заявка: " + leadTitle(lead),
    lead.phone ? "Телефон: " + lead.phone : "",
    lead.tg ? "Телеграм: " + lead.tg : "",
    lead.company ? "Компания и город: " + lead.company : "",
    lead.task ? "Рутина: " + lead.task : "",
    "Страница: " + lead.page,
    "IP: " + lead.ip + " " + lead.country,
  ]
    .filter(Boolean)
    .join("\n");

  await fetch(amoBase(env) + "/leads/" + id + "/notes", {
    method: "POST",
    headers: amoHeaders(env),
    body: JSON.stringify([{ note_type: "common", params: { text } }]),
  });
}

async function toTelegram(env, lead, amo) {
  const lines = ["<b>Заявка: " + esc(leadTitle(lead)) + "</b>"];
  if (lead.phone) lines.push("Телефон: " + esc(lead.phone));
  if (lead.tg) lines.push("Телеграм: " + esc(lead.tg));
  if (lead.company) lines.push("Компания и город: " + esc(lead.company));
  if (lead.task) lines.push("Рутина: " + esc(lead.task));
  lines.push("Страница: " + esc(lead.page));
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
  async fetch(request, env, ctx) {
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
      task: clean(data.task, LIMITS.task),
      page: clean(data.page, LIMITS.page),
      ip: request.headers.get("CF-Connecting-IP") || "",
      country: (request.cf && request.cf.country) || "",
    };

    // Связаться можно либо по телефону, либо через Telegram: на лендинге
    // разбора человек сам выбирает, что оставить.
    const byPhone = digits(lead.phone).length >= 10;
    const byTg = /^@?[a-zA-Z][a-zA-Z0-9_]{3,30}[a-zA-Z0-9]$/.test(lead.tg);
    if (!byPhone && !byTg) return json({ ok: false, error: "phone" }, 400, origin);
    if (data.consent !== true) return json({ ok: false, error: "consent" }, 400, origin);

    const amoOn = Boolean(env.AMO_SUBDOMAIN && env.AMO_TOKEN);
    let amo = null;

    if (amoOn) {
      try {
        amo = await createLead(env, lead);
      } catch (e) {
        amo = { ok: false, detail: String(e).slice(0, 200) };
      }
      if (amo.ok && amo.id) ctx.waitUntil(addNote(env, amo.id, lead));
    }

    // Сделка уже в CRM, поэтому уведомление можно дослать фоном.
    if (amo && amo.ok) {
      ctx.waitUntil(toTelegram(env, lead, amo));
      return json({ ok: true, status: { amo: "ok " + (amo.id || ""), telegram: "фоном" } }, 200, origin);
    }

    // amoCRM выключена или упала: тогда ждём Telegram, иначе заявку потеряем.
    let sent = false;
    try {
      sent = await toTelegram(env, lead, amo);
    } catch (e) {
      sent = false;
    }
    const status = {
      amo: !amoOn ? "off" : "fail " + (amo && amo.detail ? amo.detail.slice(0, 120) : ""),
      telegram: sent ? "ok" : "fail",
    };
    if (!sent) return json({ ok: false, error: "delivery", status }, 502, origin);
    return json({ ok: true, status }, 200, origin);
  },
};
