document.addEventListener("DOMContentLoaded", () => {
  const rows = document.getElementById("sale-lines");
  const add = document.getElementById("add-line");
  if (!rows || !add) return;
  add.addEventListener("click", () => {
    const first = rows.querySelector(".sale-line");
    const clone = first.cloneNode(true);
    clone.querySelectorAll("input").forEach(input => { input.value = "1"; });
    clone.querySelectorAll("select").forEach(select => { select.selectedIndex = 0; });
    rows.appendChild(clone);
  });
  rows.addEventListener("click", event => {
    const button = event.target.closest(".remove-line");
    if (!button) return;
    if (rows.querySelectorAll(".sale-line").length > 1) button.closest(".sale-line").remove();
  });
});
