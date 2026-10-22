// Staff manage view. Uses API_BASE, getJson, and formatWhen from common.js.

const list = document.getElementById("bookings");
const statusEl = document.getElementById("bookings-status");

let servicesById = new Map();

function setStatus(message) {
  statusEl.textContent = message;
  statusEl.hidden = !message;
}

function serviceName(serviceId) {
  const service = servicesById.get(serviceId);
  return service ? service.name : `Service #${serviceId}`;
}

function renderBooking(booking) {
  const li = document.createElement("li");
  li.className = "card booking";
  li.dataset.id = booking.id;

  const info = document.createElement("div");
  const when = document.createElement("div");
  when.className = "booking-when";
  when.textContent = formatWhen(booking.starts_at);
  const service = document.createElement("div");
  service.className = "booking-service";
  service.textContent = serviceName(booking.service_id);
  const customer = document.createElement("div");
  customer.className = "booking-customer";
  customer.textContent = `${booking.customer_name} · ${booking.customer_contact} · #${booking.id}`;
  info.append(when, service, customer);

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "danger";
  cancel.textContent = "Cancel";
  cancel.setAttribute("aria-label", `Cancel booking #${booking.id} for ${booking.customer_name}`);
  cancel.addEventListener("click", () => cancelBooking(booking, li, cancel));

  li.append(info, cancel);
  return li;
}

function showEmptyIfNeeded() {
  if (list.children.length === 0) setStatus("No bookings yet.");
}

async function loadBookings() {
  setStatus("Loading bookings…");
  try {
    const [services, bookings] = await Promise.all([getJson("/services"), getJson("/bookings")]);
    servicesById = new Map(services.map((s) => [s.id, s]));
    list.replaceChildren(...bookings.map(renderBooking));
    setStatus("");
    showEmptyIfNeeded();
  } catch (err) {
    list.replaceChildren();
    setStatus("Couldn't load bookings. Please try again.");
  }
}

async function cancelBooking(booking, item, button) {
  const ok = window.confirm(
    `Cancel ${serviceName(booking.service_id)} for ${booking.customer_name} ` +
      `on ${formatWhen(booking.starts_at)}?`,
  );
  if (!ok) return;

  button.disabled = true;
  try {
    const response = await fetch(`${API_BASE}/bookings/${booking.id}`, { method: "DELETE" });
    // 404 means it's already gone (e.g. cancelled in another tab): drop it either way.
    if (response.ok || response.status === 404) {
      item.remove();
      setStatus(
        response.ok
          ? `Cancelled booking #${booking.id}.`
          : `Booking #${booking.id} was already cancelled.`,
      );
      if (list.children.length === 0) setStatus(`${statusEl.textContent} No bookings left.`);
    } else {
      throw new Error(`DELETE returned ${response.status}`);
    }
  } catch (err) {
    button.disabled = false;
    setStatus(`Couldn't cancel booking #${booking.id}. Please try again.`);
  }
}

document.getElementById("refresh").addEventListener("click", loadBookings);

loadBookings();
