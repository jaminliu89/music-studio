import os

app_path = defines.get('app')
bg_path = defines.get('bg')
pdf_path = defines.get('pdf')
icon_path = defines.get('icon')

format = 'UDZO'
compression_level = 9
window_rect = ((200, 120), (1000, 600))
icon_size = 128
text_size = 14
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
sidebar_width = 0

background = bg_path
files = [app_path, pdf_path]
symlinks = {'Applications': '/Applications'}
if icon_path:
    icon = icon_path

icon_locations = {
    os.path.basename(app_path): (200, 230),
    'Applications': (700, 230),
    os.path.basename(pdf_path): (450, 460),
}
hide_extension = [os.path.basename(app_path)]
default_view = 'icon-view'
