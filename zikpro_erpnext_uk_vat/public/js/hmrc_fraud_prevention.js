// Collect and send real-time client information
function updateClientInfo() {
    const now = new Date();
    
    const clientInfo = {
        screen_width: Math.max(window.innerWidth, screen.width, 1),
        screen_height: Math.max(window.innerHeight, screen.height, 1),
        color_depth: Math.max(screen.colorDepth, 24),
        pixel_ratio: Math.max(window.devicePixelRatio || 1, 0.5),
        timezone_offset: now.getTimezoneOffset() / -60,
        timestamp: now.toISOString()
    };

    if (frappe.session && frappe.session.user && frappe.session.user !== "Guest") {
        frappe.call({
            method: 'zikpro_erpnext_uk_vat.utils.update_client_info',
            args: {
                screen_width: clientInfo.screen_width,
                screen_height: clientInfo.screen_height,
                color_depth: clientInfo.color_depth,
                pixel_ratio: clientInfo.pixel_ratio,
                timezone_offset: clientInfo.timezone_offset
            },
            callback: function (r) {
                if (!r.exc) {
                    console.debug('✅ HMRC Client Info Updated', clientInfo);
                    console.log("Session user:", frappe.session.user);
                } else {
                    console.error('❌ Client Info Update Failed', r);
                    console.log("Session user:", frappe.session.user);
                }
            }
        });
    } else {
        console.warn("⚠️ User is Guest. Skipping client info update.");
        console.log("Session user:", frappe.session.user);
    }
}

frappe.after_ajax(() => {
    if (frappe.session.user !== "Guest") {
        updateClientInfo();
    }
});

// Run on initial load
// document.addEventListener('DOMContentLoaded', updateClientInfo);


// window.addEventListener('resize', frappe.utils.throttle(updateClientInfo, 500));
// window.addEventListener('orientationchange', frappe.utils.throttle(updateClientInfo, 500));

window.addEventListener('resize', frappe.utils.throttle(() => {
    if (frappe.session.user !== "Guest") {
        updateClientInfo();
    }
}, 500));

window.addEventListener('orientationchange', frappe.utils.throttle(() => {
    if (frappe.session.user !== "Guest") {
        updateClientInfo();
    }
}, 500));

// setInterval(updateClientInfo, 300000);

setInterval(() => {
    if (frappe.session.user !== "Guest") {
        updateClientInfo();
    }
}, 300000);