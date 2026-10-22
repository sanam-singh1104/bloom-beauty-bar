// The backend serves this page, so API calls are same-origin.
const API_BASE = "/api";

let servicesById = new Map();

async function getJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(`${path} returned ${response.status}`);
  return response.json();
}

async function checkHealth() {
  const el = document.getElementById("api-status");
  try {
    const { status } = await getJson("/health");
    el.textContent = `API: ${status}`;
  } catch (err) {
    el.textContent = "API: unreachable";
  }
}

async function loadServices() {
  const status = document.getElementById("services-status");
  const list = document.getElementById("services");
  try {
    const services = await getJson("/services");
    servicesById = new Map(services.map((s) => [s.id, s]));
    list.replaceChildren(...services.map(renderService));
    fillServiceSelect(services);
    status.hidden = true;
  } catch (err) {
    status.textContent = "Couldn't load services. Please try again later.";
  }
}

function renderService(service) {
  const li = document.createElement("li");
  li.className = "service";

  const info = document.createElement("div");
  const name = document.createElement("div");
  name.className = "service-name";
  name.textContent = service.name;
  const meta = document.createElement("div");
  meta.className = "service-meta";
  meta.textContent = `${service.duration_minutes} min`;
  info.append(name, meta);

  const price = document.createElement("div");
  price.className = "service-price";
  price.textContent = `R${service.price_rand}`;

  li.append(info, price);
  return li;
}

function fillServiceSelect(services) {
  const select = document.getElementById("service");
  const options = services.map((s) => {
    const option = document.createElement("option");
    option.value = s.id;
    option.textContent = `${s.name} (${s.duration_minutes} min, R${s.price_rand})`;
    return option;
  });
  select.append(...options);
}

// --- Booking form ---

const form = document.getElementById("booking-form");
const errorBox = document.getElementById("booking-error");
const confirmation = document.getElementById("booking-confirmation");

// Maps API field names to the form controls that hold them.
const FIELD_INPUTS = {
  service_id: ["service"],
  starts_at: ["date", "time"],
  customer_name: ["name"],
  customer_contact: ["contact"],
};

function todayIso() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

function readForm() {
  const value = (id) => document.getElementById(id).value.trim();
  const date = value("date");
  const time = value("time");
  return {
    // null rather than "" so the API reports these as missing.
    service_id: value("service") ? Number(value("service")) : null,
    starts_at: date && time ? `${date}T${time}` : null,
    customer_name: value("name"),
    customer_contact: value("contact"),
  };
}

function showErrors(message, fields = []) {
  for (const ids of Object.values(FIELD_INPUTS)) {
    ids.forEach((id) => document.getElementById(id).removeAttribute("aria-invalid"));
  }
  for (const field of fields) {
    (FIELD_INPUTS[field] || []).forEach((id) =>
      document.getElementById(id).setAttribute("aria-invalid", "true"),
    );
  }
  errorBox.textContent = message || "";
  errorBox.hidden = !message;
}

function formatWhen(startsAt) {
  return new Date(startsAt).toLocaleString("en-ZA", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function showConfirmation(booking) {
  const service = servicesById.get(booking.service_id);
  const serviceName = service ? service.name : "Your appointment";
  document.getElementById("confirmation-text").textContent =
    `${serviceName} on ${formatWhen(booking.starts_at)}, booked for ` +
    `${booking.customer_name} (${booking.customer_contact}). ` +
    `Your booking reference is #${booking.id}.`;
  form.hidden = true;
  confirmation.hidden = false;
  confirmation.focus();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showErrors("");
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const response = await fetch(`${API_BASE}/bookings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(readForm()),
    });
    const body = await response.json().catch(() => ({}));
    if (response.ok) {
      showConfirmation(body);
    } else {
      const fields = (body.errors || []).map((e) => e.field);
      showErrors(body.detail || "Something went wrong. Please try again.", fields);
    }
  } catch (err) {
    showErrors("Couldn't reach the salon's booking system. Please try again.");
  } finally {
    button.disabled = false;
  }
});

document.getElementById("book-another").addEventListener("click", () => {
  form.reset();
  confirmation.hidden = true;
  form.hidden = false;
  document.getElementById("service").focus();
});

confirmation.tabIndex = -1;
document.getElementById("date").min = todayIso();

checkHealth();
loadServices();
