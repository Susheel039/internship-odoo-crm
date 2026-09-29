from odoo import api, SUPERUSER_ID

from . import models


def _post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    admin_user = env.ref("base.user_admin")
    platform_group = env.ref("internship_base.group_platform_administrator")
    if admin_user and platform_group:
        admin_user.write({"group_ids": [(4, platform_group.id)]})
