const search = document.querySelector("#order-search");
const statusFilter = document.querySelector("#status-filter");
const rows = [...document.querySelectorAll("#orders-body tr")];
const toast = document.querySelector("#toast");

function filterRows() {
  const query = search.value.toLowerCase();
  const status = statusFilter.value;
  rows.forEach((row) => {
    row.hidden = !row.dataset.search.includes(query) || (status && row.dataset.status !== status);
  });
}

function notify(message) {
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2500);
}

search.addEventListener("input", filterRows);
statusFilter.addEventListener("change", filterRows);

document.querySelector("#seed-demo").addEventListener("click", () => {
  document.querySelector("#metric-total").textContent = "2,921";
  document.querySelector("#metric-success").innerHTML = "80.1<sup>%</sup>";
  document.querySelector("#metric-synced").textContent = "2,338 synchronized";
  document.querySelector("#metric-value").textContent = "431,557";
  notify("Four representative orders replayed locally");
  document.querySelector("#workflow").scrollIntoView({ behavior: "smooth" });
});

document.querySelector(".retry").addEventListener("click", (event) => {
  const row = event.currentTarget.closest("tr");
  const status = row.querySelector(".status");
  event.currentTarget.remove();
  status.className = "status routed";
  status.innerHTML = "<i></i>routed";
  row.dataset.status = "routed";
  row.querySelector("td:last-child small").textContent = "Retry accepted · dispatch queued";
  document.querySelector("#metric-failed").textContent = "0";
  document.querySelector("#metric-flight").textContent = "3";
  notify("Retry queued safely in portfolio mode");
});
