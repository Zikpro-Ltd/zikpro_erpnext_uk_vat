app_name = "zikpro_erpnext_uk_vat"
app_title = "Zikpro Erpnext Uk Vat"
app_publisher = "Zikpro"
app_description = "Uk VAT Compliance"
app_email = "info@zikpro.com"
app_license = "mit"
# required_apps = []

app_version = "2.1.1"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/zikpro_erpnext_uk_vat/css/zikpro_erpnext_uk_vat.css"
# app_include_js = "/assets/zikpro_erpnext_uk_vat/js/zikpro_erpnext_uk_vat.js"
app_include_js = [
    "/assets/zikpro_erpnext_uk_vat/js/hmrc_fraud_prevention.js"
]

whitelisted_methods = [
    "zikpro_erpnext_uk_vat.utils.update_client_info"
]

# override_whitelisted_methods = {
#     "frappe.twofactor.confirm_otp_token": "zikpro_erpnext_uk_vat.utils.patched_confirm_otp_token"
# }
override_whitelisted_methods = {
    "login": "zikpro_erpnext_uk_vat.utils.custom_login"
}

after_migrate = [
    "zikpro_erpnext_uk_vat.utils.patch_login_manager"
]

after_install = "zikpro_erpnext_uk_vat.utils.create_initial_records"

# boot_session = "zikpro_erpnext_uk_vat.utils.patch_twofactor"

socketio_handlers = [
    {
        "event": "mfa_updated",
        "handler": "zikpro_erpnext_uk_vat.utils.clear_user_cache"
    }
]


# include js, css files in header of web template
# web_include_css = "/assets/zikpro_erpnext_uk_vat/css/zikpro_erpnext_uk_vat.css"
# web_include_js = "/assets/zikpro_erpnext_uk_vat/js/zikpro_erpnext_uk_vat.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "zikpro_erpnext_uk_vat/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "zikpro_erpnext_uk_vat/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "zikpro_erpnext_uk_vat.utils.jinja_methods",
# 	"filters": "zikpro_erpnext_uk_vat.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "zikpro_erpnext_uk_vat.install.before_install"
# after_install = "zikpro_erpnext_uk_vat.install.after_install"
# This ensures patches run on install/update
# after_install = "zikpro_erpnext_uk_vat.setup.after_install"
# after_migrate = "zikpro_erpnext_uk_vat.setup.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "zikpro_erpnext_uk_vat.uninstall.before_uninstall"
# after_uninstall = "zikpro_erpnext_uk_vat.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "zikpro_erpnext_uk_vat.utils.before_app_install"
# after_app_install = "zikpro_erpnext_uk_vat.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "zikpro_erpnext_uk_vat.utils.before_app_uninstall"
# after_app_uninstall = "zikpro_erpnext_uk_vat.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "zikpro_erpnext_uk_vat.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events
doc_events = {
    "User": {
        "on_login": "zikpro_erpnext_uk_vat.utils.set_default_client_info"
    }
}

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"zikpro_erpnext_uk_vat.tasks.all"
# 	],
# 	"daily": [
# 		"zikpro_erpnext_uk_vat.tasks.daily"
# 	],
# 	"hourly": [
# 		"zikpro_erpnext_uk_vat.tasks.hourly"
# 	],
# 	"weekly": [
# 		"zikpro_erpnext_uk_vat.tasks.weekly"
# 	],
# 	"monthly": [
# 		"zikpro_erpnext_uk_vat.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "zikpro_erpnext_uk_vat.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "zikpro_erpnext_uk_vat.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "zikpro_erpnext_uk_vat.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["zikpro_erpnext_uk_vat.utils.before_request"]
# after_request = ["zikpro_erpnext_uk_vat.utils.after_request"]

# Job Events
# ----------
# before_job = ["zikpro_erpnext_uk_vat.utils.before_job"]
# after_job = ["zikpro_erpnext_uk_vat.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"zikpro_erpnext_uk_vat.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

