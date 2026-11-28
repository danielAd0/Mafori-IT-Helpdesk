// Phone menu for the sidebar (owner: Sifiso).
// On narrow screens the sidebar becomes a top bar with a Menu button.
// Without JavaScript the button stays hidden and the menu stays open.
(function () {
  var sidebar = document.getElementById("sidebar");
  var button = sidebar && sidebar.querySelector(".sidebar__toggle");
  if (!button) return;
  var narrow = window.matchMedia("(max-width: 56rem)");

  function setOpen(open) {
    sidebar.classList.toggle("sidebar--closed", !open);
    button.setAttribute("aria-expanded", String(open));
  }

  button.hidden = false;
  setOpen(!narrow.matches); // closed on phones, open on wider screens
  narrow.addEventListener("change", function (e) { setOpen(!e.matches); });
  button.addEventListener("click", function () {
    setOpen(sidebar.classList.contains("sidebar--closed"));
  });
})();
