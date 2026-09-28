/**
 * Returns a function that provides a reusable HTMLSpanElement as a separator.
 * The separator contains the "|" character as its content.
 *
 * @return {function(): HTMLSpanElement} A function that returns the pre-created separator span element.
 */
export function getLayoutElementsSeparator(): () => HTMLSpanElement {
    let separator = document.createElement('span');
    separator.innerText = "|";

    return function() {
        return separator;
    };
}
