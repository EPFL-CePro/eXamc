import { ErrorModal } from "@examc/modals";
import type { UserFacingError } from "@examc/types/errors";

function showUserError(userFacingError: UserFacingError) {
  new ErrorModal(userFacingError).show();
}

document.addEventListener("DOMContentLoaded", () => {
  const pending = document.querySelector<HTMLElement>("#user-error-messages [data-error]");
  if (pending && pending.dataset.error) showUserError(JSON.parse(pending.dataset.error));
});