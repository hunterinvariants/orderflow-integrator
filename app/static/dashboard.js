const search = document.querySelector("#order-search");
const statusFilter = document.querySelector("#status-filter");
const rows = [...document.querySelectorAll("#orders-body tr[data-search]")];
const toast = document.querySelector("#toast");

function filterRows() {
  const query = search.value.toLowerCase();
  const status = statusFilter.value;
  rows.forEach((row) => {
    row.hidden = !row.dataset.search.toLowerCase().includes(query) || (status && row.dataset.status !== status);
  });
}

function notify(message) {
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2400);
}

search?.addEventListener("input", filterRows);
statusFilter?.addEventListener("change", filterRows);

document.querySelector("#seed-demo")?.addEventListener("click", async (event) => {
  event.currentTarget.disabled = true;
  notify("Loading demo order flow…");
  const response = await fetch("/v1/demo/seed", { method: "POST" });
  if (response.ok) location.reload();
  else notify("Could not load demo data");
});

document.querySelectorAll(".retry").forEach((button) => {
  button.addEventListener("click", async () => {
    const response = await fetch(`/v1/orders/${button.dataset.orderId}/retry`, { method: "POST" });
    notify(response.ok ? "Retry queued" : "Retry could not be queued");
    if (response.ok) setTimeout(() => location.reload(), 700);
  });
});
