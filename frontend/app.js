// The backend serves this page, so API calls are same-origin.
const API_BASE = "/api";

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
    list.replaceChildren(...services.map(renderService));
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

checkHealth();
loadServices();
