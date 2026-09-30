# Development image: odoo:19.0 plus debugpy. Used by docker-compose.override.yml
# (copy docker-compose.override.yml.example). Production uses the stock odoo:19.0 image.
FROM odoo:19.0

USER root
# The image's Python is Debian-managed, hence --break-system-packages.
RUN pip3 install --no-cache-dir --break-system-packages debugpy==1.8.*
USER odoo
