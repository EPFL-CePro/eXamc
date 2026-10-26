import { byId } from '@examc/helpers/dom.ts';
import { postForm, postText } from '@examc/helpers/http.ts';
import { LoadingModal } from '@examc/modals';

interface UsersConfig {
    searchUrl: string;
    updateUrl: string;
    csrfToken: string;
}

interface UserInfo {
    username: string;
    firstName: string;
    lastName: string;
    email: string;
}

/** The users of both lists, in order: current users first. */
function userItems(...lists: HTMLElement[]): HTMLElement[] {
    return lists.flatMap((list) => [...list.querySelectorAll<HTMLElement>('[data-username]')]);
}

function userInfo(item: HTMLElement): UserInfo {
    return {
        username: item.dataset['username'] ?? '',
        firstName: item.dataset['firstName'] ?? '',
        lastName: item.dataset['lastName'] ?? '',
        email: item.dataset['email'] ?? '',
    };
}

/**
 * One user as update_exam_users reads it: "username;first name;last name;email;group".
 * Users removed from the exam are sent as "delete_username", without a group.
 */
function userEntry(item: HTMLElement): string {
    const { username, firstName, lastName, email } = userInfo(item);
    const deleted = item.dataset['deleted'] === 'true';
    const group = item.querySelector<HTMLInputElement>('input[type="radio"]:checked')?.value ?? 'null';
    return [deleted ? `delete_${username}` : username, firstName, lastName, email, deleted ? 'null' : group].join(';');
}

/**
 * Marks a current user as removed (or keeps them again). Removals are only saved by "Validate".
 *
 * @param {HTMLElement} item - The user's list item.
 * @param {boolean} deleted - Whether the user is removed.
 */
function setDeleted(item: HTMLElement, deleted: boolean): void {
    item.dataset['deleted'] = String(deleted);
    item.classList.toggle('opacity-50', deleted);
    item.querySelector('[data-user-label]')?.classList.toggle('text-decoration-line-through', deleted);
    for (const radio of item.querySelectorAll<HTMLInputElement>('input[type="radio"]')) radio.disabled = deleted;

    const button = item.querySelector<HTMLElement>('[data-remove-user]');
    if (button) {
        button.title = deleted ? 'Keep this user' : 'Remove this user';
        button.classList.toggle('text-danger', !deleted);
        button.innerHTML = deleted
            ? '<i class="fa-solid fa-rotate-left fa-lg" aria-hidden="true"></i>'
            : '<i class="fa-solid fa-circle-minus fa-lg" aria-hidden="true"></i>';
    }
}

/**
 * The list item of a user found in the LDAP, with the group choices of the page.
 *
 * @param {UserInfo} user - The user.
 * @param {HTMLTemplateElement} groupsTemplate - The group radios.
 * @return {HTMLLIElement} The item.
 */
function newUserItem(user: UserInfo, groupsTemplate: HTMLTemplateElement): HTMLLIElement {
    const item = document.createElement('li');
    item.className = 'list-group-item d-flex flex-wrap align-items-center gap-2';
    Object.assign(item.dataset, user);

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'btn btn-link btn-sm p-0 text-danger';
    remove.dataset['removeUser'] = '';
    remove.title = 'Remove this user';
    remove.setAttribute('aria-label', `Remove ${user.username}`);
    remove.innerHTML = '<i class="fa-solid fa-circle-minus fa-lg" aria-hidden="true"></i>';

    const label = document.createElement('span');
    label.className = 'me-auto';
    label.textContent = `${user.username} - ${user.firstName} ${user.lastName} - ${user.email}`;

    const groups = document.createElement('div');
    groups.append(groupsTemplate.content.cloneNode(true));
    for (const check of groups.querySelectorAll('.form-check')) {
        const input = check.querySelector('input')!;
        input.name = `user-group-${user.username}`;
        input.id = `user-group-${user.username}-${input.value}`;
        check.querySelector('label')!.htmlFor = input.id;
    }

    item.append(remove, label, groups);
    return item;
}

/**
 * The users section: remove current users, add users found in the LDAP, choose their groups,
 * then save everything with "Validate".
 */
export function initUsers({ searchUrl, updateUrl, csrfToken }: UsersConfig): void {
    const currentList = byId('current-users');
    const newUsers = byId('new-users');
    const newUsersList = byId('new-users-list');
    const searchForm = byId<HTMLFormElement>('ldap-search-form');
    const emailInput = byId<HTMLInputElement>('ldap-email');
    const errorBox = byId('users-error');
    const groupsTemplate = byId<HTMLTemplateElement>('user-groups-template');

    const showError = (message: string | null): void => {
        errorBox.hidden = message === null;
        errorBox.textContent = message ?? '';
    };

    currentList.addEventListener('click', (event) => {
        const item = (event.target as Element).closest('[data-remove-user]')?.closest<HTMLElement>('[data-username]');
        if (item) setDeleted(item, item.dataset['deleted'] !== 'true');
    });

    newUsersList.addEventListener('click', (event) => {
        (event.target as Element).closest('[data-remove-user]')?.closest('[data-username]')?.remove();
        if (newUsersList.childElementCount === 0) newUsers.style.display = 'none';
    });

    searchForm.addEventListener('submit', (event) => {
        event.preventDefault();
        showError(null);
        const email = emailInput.value.trim();

        void (async () => {
            let result: string;
            try {
                result = await postText(searchUrl, { csrfmiddlewaretoken: csrfToken, email });
            } catch (error) {
                console.error(error);
                showError('Cannot find a user with this email address in the EPFL LDAP!');
                return;
            }

            // "exist", or "username;first name;last name;email"
            const [username = '', firstName = '', lastName = '', userEmail = ''] = result.split(';');
            const listed = userItems(currentList, newUsersList).some((item) => item.dataset['username'] === username);
            if (result === 'exist' || listed) {
                showError('This user is already a user of this exam!');
                return;
            }

            // show the div
            newUsers.style.display = 'block';
            newUsersList.append(
                newUserItem({ username, firstName, lastName, email: userEmail }, groupsTemplate)
            );
            emailInput.value = '';
        })();
    });

    byId('btn-cancel-users').addEventListener('click', () => {
        for (const item of userItems(currentList)) setDeleted(item, false);
        newUsersList.replaceChildren();
        emailInput.value = '';
        showError(null);
    });

    byId('btn-validate-users').addEventListener('click', () => {
        const body = new FormData();
        body.append('csrfmiddlewaretoken', csrfToken);
        // 'users_list[]' is the key jQuery used for arrays, which the view reads
        for (const item of userItems(currentList, newUsersList)) body.append('users_list[]', userEntry(item));

        void (async () => {
            try {
                await new LoadingModal(() => postForm(updateUrl, {}, body)).result;
                window.location.reload();
            } catch (error) {
                console.error(error);
                showError('The users could not be saved. Please try again.');
            }
        })();
    });
}