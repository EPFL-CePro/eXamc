type AlertType = "primary" | "secondary" | "success" | "danger" | "warning" | "info" | "light" | "dark";

export function createAlert(options: { 
    alertType: AlertType;
    content: HTMLElement;
}): HTMLDivElement {
    const { alertType, content } = options;

    const alert = document.createElement('div');
    alert.className = `alert alert-${alertType} d-flex align-items-center gap-2 mb-0`;
    alert.role = 'alert';

    const icon = document.createElement('i');
    icon.className = "fa-solid ";

    switch (alertType) {
        case "success" : icon.className += 'fa-circle-check';
        break;
        
        case "danger": icon.className += 'fa-skull-crossbones';
        break;

        case "warning": icon.className += 'fa-triangle-exclamation';
        break;

        default: icon.className += 'fa-circle-check';
        break;
    }
    icon.ariaHidden = 'true';

    const textDiv = document.createElement('div');
    textDiv.appendChild(content);

    alert.append(icon, textDiv);

    return alert;
}