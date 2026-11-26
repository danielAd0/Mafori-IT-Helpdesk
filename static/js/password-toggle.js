// Show / hide password button (owner: Sifiso).
// Any <button data-password-toggle="input-id" hidden> becomes visible and works.
// Without JavaScript the button stays hidden and the form works as normal.
(function () {
  document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
    var input = document.getElementById(button.getAttribute("data-password-toggle"));
    if (!input) return;
    button.hidden = false;
    button.addEventListener("click", function () {
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      button.setAttribute("aria-pressed", String(show));
      button.setAttribute("aria-label", show ? "Hide password" : "Show password");
      input.focus();
    });
  });
  // Never submit the password as visible text, so the browser doesn't save it as plain text
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function () {
      form.querySelectorAll("[data-password-toggle]").forEach(function (button) {
        var input = document.getElementById(button.getAttribute("data-password-toggle"));
        if (input) input.type = "password";
      });
    });
  });
})();
