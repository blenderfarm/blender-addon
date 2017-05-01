# pylint: disable=invalid-name

"""Blenderfarm addon for Blender 2.78 and up."""

import math
import tempfile
import time
import os

import bpy # pylint: disable=import-error
from bpy.app.handlers import persistent

from . import blenderfarm

bl_info = { # pylint: disable=invalid-name
    'name': 'Blenderfarm client',
    'description': 'Blenderfarm client addon',
    'author': 'Jon Ross',
    # This should stay up-to-date with the Blenderfarm version.
    'version': (0, 1, 0),
    'blender': (2, 78, 0),
    #'location': 'View3D > Add > Mesh',
    #'warning': '',
    #'wiki_url': 'http://wiki.blender.org/index.php/Extensions:2.6/Py/'
    'tracker_url': 'https://developer.blender.org/maniphest/task/edit/form/2/',
    'support': 'COMMUNITY',
    'category': 'Render'
}

CLIENT = blenderfarm.client.Client()

FIRST_LOAD = True

# # Tasks

def perform_task(context, task):
    task_type = task.task_info.get_info_type()

    if task_type == 'render':
        perform_task_render(context, task)

    prefs = BlenderfarmAddonPreferences.get(context)
    
    # If continuous rendering is enabled, keep going.
    if not prefs.node_task_single:
        bpy.ops.blenderfarm.node_task_perform()
        
        
def perform_task_render(context, task):
    global CLIENT
    
    temp_dir = tempfile.gettempdir()

    ext = 'png'

    print('Rendering frame ' + str(task.task_info.frame))
    print(task.job.job_id)

    blend_filename = os.path.join(temp_dir, 'blenderfarm-' + task.job.job_id + '.blend')
    render_filename = os.path.join(temp_dir, 'blenderfarm-' + task.job.job_id + '.' + ext)

    CLIENT.download_job_file(task.job, blend_filename)

    print('opening filename')
    bpy.ops.wm.open_mainfile(filepath=blend_filename)
    print('opened file')
    
    context.scene.render.filepath = render_filename
    context.scene.frame_current = task.task_info.frame

    start_time = time.time()
    
    bpy.ops.render.render('EXEC_DEFAULT', write_still=True)

    elapsed_seconds = time.time() - start_time
    
    CLIENT.upload_render_result(task, render_filename, elapsed_seconds)
    

# # Blender panels

class BlenderfarmAddonPreferences(bpy.types.AddonPreferences):
    """Addon preferences (persistent across all of Blender.)"""

    # `bl_idname` MUST be the name of the package, so we use
    # `__package__` here (if this were a module, i.e. a single file
    # instead of a directory, we'd use `__name__` instead.)
    bl_idname = __package__

    # Blenderfarm server information (host/port)

    server_host = bpy.props.StringProperty(
        name='Host',
        description='The host of the Blenderfarm server',
        default='localhost'
    )

    server_port = bpy.props.IntProperty(
        name='Port',
        description='The port that the Blenderfarm server is listening on',
        default=44363
    )

    server_security = bpy.props.EnumProperty(
        name='Security',
        description='',
        items=[
            ('https', 'HTTPS', 'Use secure HTTPS connection'),
            ('http', 'HTTP', 'Use an insecure HTTP connection')
        ],
        default='https'
    )

    server_autoconnect = bpy.props.BoolProperty(
        name='Auto-connect',
        description='Automatically connect to the server when Blender starts',
        default=False
    )

    # Blenderfarm user credentials (username/key)

    credentials_username = bpy.props.StringProperty(
        name='Username',
        description='Username for the Blenderfarm server',
        default='anon'
    )

    credentials_key = bpy.props.StringProperty(
        name='Key',
        description='Authentication key for this user. '
                    'Request a key from the Blenderfarm server administrator.',
        default='1234'
    )

    # Client ID

    client_id = bpy.props.StringProperty(
        name='Client ID',
        description='The ID of this client.',
        default=''
    )

    # Whether or not to request a new task after the current task is
    # completed.

    node_task_single = bpy.props.BoolProperty(
        name='Stop when complete',
        description='Stop processing new tasks after current task is complete.',
        default=True
    )

    node_task_autostart = bpy.props.BoolProperty(
        name='Autostart on connection',
        description='Automatically start rendering when connecting to a server',
        default=False
    )

    # Developer mode. Shows more information in the "Blenderfarm
    # Control" panel.

    developer_mode = bpy.props.BoolProperty(
        name='Show Developer Information',
        description='Show debugging information',
        default=False
    )

    @staticmethod
    def get(context):
        """Returns the global instance of the `BlenderfarmAddonPreferences` class."""

        user_preferences = context.user_preferences
        return user_preferences.addons[__package__].preferences

    def get_host_port(self):
        """Returns the user-facing `host:port` string."""

        return self.server_host + ':' + str(self.server_port)

# # Operators

class BlenderfarmConnect(bpy.types.Operator):
    """Connects to the server."""

    bl_idname = 'blenderfarm.connect'
    bl_label = 'Connect to server'

    def execute(self, context): # pylint: disable=missing-docstring,no-self-use
        global CLIENT

        context.user_preferences.view.show_splash = False
        
        prefs = BlenderfarmAddonPreferences.get(context)

        CLIENT.set_host_port(prefs.server_host, prefs.server_port)
        CLIENT.set_insecure(prefs.server_security == 'http')

        try:
            CLIENT.connect(prefs.credentials_username, prefs.credentials_key)
        except blenderfarm.error.Error as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

        if not CLIENT.is_connected():
            self.report({'ERROR'}, 'Could not connect to ' + CLIENT.get_host_port())

        # If autostart is enabled, begin to perform tasks.
        if prefs.node_task_autostart:
            bpy.ops.blenderfarm.node_task_perform()
            
        return {'FINISHED'}


class BlenderfarmDisconnect(bpy.types.Operator):
    """Disconnects from the Blenderfarm server. Does not cancel currently-running tasks, if present."""

    bl_idname = 'blenderfarm.disconnect'
    bl_label = 'Disconnect from server'

    def execute(self, context): # pylint: disable=missing-docstring,no-self-use
        global CLIENT

        _ = context
        
        CLIENT.disconnect()

        return {'FINISHED'}

class BlenderfarmNodeTaskCancel(bpy.types.Operator):
    """Cancels all current tasks and reverts Blender back to a new file."""

    bl_idname = 'blenderfarm.node_task_cancel'
    bl_label = 'Cancel in-progress tasks'

    def execute(self, context): # pylint: disable=missing-docstring,no-self-use,unused-argument
        bpy.ops.blenderfarm.disconnect()

        # This horrible, horrible hack simply loads a new file,
        # thereby canceling any in-progress render.
        bpy.ops.wm.read_homefile()
        return {'FINISHED'}

class BlenderfarmNodeTaskPerform(bpy.types.Operator):
    """Requests a new task from the server and begins executing it."""

    bl_idname = 'blenderfarm.node_task_perform'
    bl_label = 'Fetch and perform task'

    def execute(self, context): # pylint: disable=missing-docstring,no-self-use,unused-argument
        try:
            task = CLIENT.request_next_task()

            if task:
                perform_task(context, task)
            else:
                print('No tasks to perform!')
                return {'FINISHED'}
            
        except blenderfarm.error.Error as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

        return {'FINISHED'}

# # Properties

class BlenderfarmControlPanel(bpy.types.Panel):
    """Draws the UI in the properties panel (Properties/Render)."""

    bl_label = 'Blenderfarm Control'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}
    bl_context = 'render'

    @staticmethod
    def add_row(table, key, value, percentage=0.4):
        """Adds a left/right row to the table."""
        
        row = table.split(percentage=percentage)

        row.label(key + ':')
        row.label(value)

    def draw(self, context):
        """Draws the panel in the render view."""

        global CLIENT
        
        # Get the global instance of the preferences object. This is
        # where server/credentials are stored.
        prefs = BlenderfarmAddonPreferences.get(context)

        # Get the Blenderfarm client.

        # I don't want to type `self.layout` every time.
        layout = self.layout

        # Top row of the panel (contains the control buttons)
        control_row = layout.row(align=False)
        control_row.alignment = 'EXPAND'

        connect_disconnect_button = control_row.column()
        connect_disconnect_button.scale_y = 2

        if CLIENT.is_connected():
            connect_disconnect_button.operator('blenderfarm.disconnect', 'Disconnect')
        else:
            connect_disconnect_button.operator('blenderfarm.connect', 'Connect')

        if prefs.developer_mode:
            self.draw_developer_info(context, layout)

    def draw_developer_info(self, context, layout):
        """Draws the developer information box in `layout`."""
        global CLIENT
        
        prefs = BlenderfarmAddonPreferences.get(context)

        column = layout.column_flow(columns=1)

        # Developer info box.
        box = column.box()

        # Server name row
        
        version = CLIENT.get_server_info('version')
        uptime = CLIENT.get_server_info('uptime')

        if uptime:
            # pylint: disable=bad-whitespace
            seconds = math.floor(uptime % 60)
            minutes = math.floor(uptime / 60)
            hours   = math.floor(uptime / 60 / 60)
            days    = math.floor(uptime / 60 / 60 / 24)
            years   = math.floor(uptime / 60 / 60 / 24 / 365)

            days -= years * 365
            
            uptime = str(minutes) + 'm ' + str(seconds) + 's'

            if hours:
                uptime = str(hours) + 'h ' + uptime
                
            if days:
                uptime = str(days) + 'd ' + uptime
        
            if years:
                uptime = str(years) + 'y ' + uptime
        
        self.add_row(box, 'Server Version', version or '<not connected>')
        self.add_row(box, 'Server Uptime', uptime or '<not connected>')
        self.add_row(box, 'Client ID', prefs.client_id or '<not connected>')

        self.draw_task_info(context, column)

    def draw_task_info(self, context, layout):
        """Draws information about the current task."""
        global CLIENT

        _ = context

        if CLIENT.is_performing_task():
            # Tasks list box
            box = layout.box()

            self.add_row(box, 'Performing task', str(CLIENT.is_performing_task()))

            task = CLIENT.get_task()
            task_id = '<not perfoming task>'

            if task:
                task_id = task.task_id

            self.add_row(box, 'Task ID', task_id)

class BlenderfarmNodePanel(bpy.types.Panel):
    """Draws the UI in the properties panel (Properties/Render)."""

    bl_label = 'Blenderfarm Node'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}
    bl_context = 'render'

    def draw(self, context):
        """Draws the panel in the render view."""
        
        global CLIENT

        # Get the global instance of the preferences object. This is
        # where server/credentials are stored.
        prefs = BlenderfarmAddonPreferences.get(context)

        # I don't want to type `self.layout` every time.
        layout = self.layout

        task_buttons = layout.column(align=True)
        task_buttons.scale_y = 1

        if CLIENT.is_performing_task():
            task_buttons.operator('blenderfarm.node_task_cancel', 'Cancel', icon='CANCEL')
        else:
            task_buttons.operator('blenderfarm.node_task_perform', 'Run Task', icon='PLAY')

            if not CLIENT.is_connected():
                task_buttons.enabled = False

        row = layout.row()
        
        row.prop(prefs, 'node_task_single')
        row.prop(prefs, 'node_task_autostart')


class BlenderfarmSettingsPanel(bpy.types.Panel):
    """Draws the "Blenderfarm Settings" UI in the properties panel (Properties/Render)."""

    bl_label = 'Blenderfarm Settings'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}
    bl_context = 'render'

    def draw(self, context):
        """Draws the panel in the render view."""

        global CLIENT

        # Get the global instance of the preferences object. This is
        # where server/credentials are stored.
        prefs = BlenderfarmAddonPreferences.get(context)

        # I don't want to type `self.layout` every time.
        layout = self.layout

        # Status box. Contains connection settings (duplicating addon
        # preferences, yes I know.)

        status_box = layout.column()

        def get_new_table_row(table, percentage=0.2, align=False):
            """Returns a new row for `table`."""
            return table.split(percentage=percentage, align=align)

        if CLIENT.is_connected():
            status_box.enabled = False

        # ### Server name row
        server_row = get_new_table_row(status_box)

        server_row.label('Server:')

        row = server_row.split(percentage=0.5, align=True)
        row.prop(prefs, 'server_host', text='')
        
        misc_row = row.split(percentage=0.6, align=True)
        misc_row.prop(prefs, 'server_port', text='')
        misc_row.prop(prefs, 'server_security', text='')

        # ### Credentials row
        credentials_row = get_new_table_row(status_box)

        credentials_row.label('Credentials:')

        row = credentials_row.split(percentage=0.5, align=True)
        row.prop(prefs, 'credentials_username', text='')
        row.prop(prefs, 'credentials_key', text='', icon='KEY_HLT')

        # And now for a row at the bottom
        row = get_new_table_row(layout, align=False)
        row.label('Settings:')

        row = row.row()
        row.prop(prefs, 'server_autoconnect')
        row.prop(prefs, 'developer_mode', text='Developer Info')

        # And now for a row at the bottom
        row = get_new_table_row(layout, align=False)
        row.label('')

        row = row.row()
        row.operator('wm.save_userpref', text='Save Settings')

        if CLIENT.is_connected():
            row.enabled = False
        
CLASSES_TO_REGISTER = [
    BlenderfarmConnect,
    BlenderfarmDisconnect,

    BlenderfarmNodeTaskCancel,
    BlenderfarmNodeTaskPerform,

    BlenderfarmControlPanel,
    BlenderfarmNodePanel,
    BlenderfarmSettingsPanel,

    BlenderfarmAddonPreferences
]

@persistent
def load_post(dummy):
    global FIRST_LOAD

    if not FIRST_LOAD:
        return
    
    FIRST_LOAD = False
    
    prefs = BlenderfarmAddonPreferences.get(bpy.context)

    if prefs.server_autoconnect:
        bpy.ops.blenderfarm.connect()
    
@persistent
def render_complete(dummy):
    print('render complete!')

def register():
    """Registers the Blenderfarm addon."""

    for _class in CLASSES_TO_REGISTER:
        bpy.utils.register_class(_class)
        
    bpy.app.handlers.load_post.append(load_post)
    bpy.app.handlers.render_complete.append(render_complete)

def unregister():
    """Unregisters the Blenderfarm Node addon."""

    # First, cancel any operations.
    #bpy.ops.blenderfarm.node_task_cancel()

    for _class in CLASSES_TO_REGISTER:
        bpy.utils.unregister_class(_class)
