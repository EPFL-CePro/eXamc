import { manageTabs } from "@examc/helpers/tabs";

document.addEventListener("DOMContentLoaded", () => {
    manageTabs({ 
        tabListSelector: "#general-stats-tabs",
        additionalTabs: [
            {
                tabListSelectors: ["#stats-by-exam-tabs", "#stats-by-section-tabs", "#stats-com-vs-ind-tabs"],
                tabKey: "scale"
            },
            {
                tabListSelectors: ["#stats-comVsInd-pills-tabContent", ],
                tabKey: "by"
            }
        ]
     });
});