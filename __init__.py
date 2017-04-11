# pylint: disable=invalid-name

"""Blenderfarm addon for Blender 2.78 and up."""

import bpy # pylint: disable=import-error

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

    server_insecure = bpy.props.BoolProperty(
        name='Use HTTP',
        description='Use HTTP (insecure!) instead of the default HTTPS',
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
        name='Perform single task',
        description='Disconnect from server after task is complete.',
        default=False
    )

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

    # Disable user preferences settings
    
    def draw_disabled(self, context):
        """Draw the preferences panel (this is in Blender's user preferences and the addon info box must be expanded for this to be visible.)"""
        
        # Disable pylint warning.
        _ = context

        layout = self.layout

        # Create a 50/50 horizontal split for `[ server info | user credentials ]`.
        main_split = layout.split(percentage=0.5)

        # Left column; server info (host/port).
        server_info = main_split.column(align=True)

        server_info.label(text='Server')

        server_info.prop(self, 'server_host', text='')
        server_info.prop(self, 'server_port')

        # Right column; user credentials (username/key).
        credentials = main_split.column(align=True)

        credentials.label(text='Credentials')

        credentials.prop(self, 'credentials_username', text='Username')
        credentials.prop(self, 'credentials_key', text='Key')

        # Left column (below server info): connection info
        connection_status = server_info.box().column(align=True)

        connection_status.label(text='Connected: ' + 'FALSE')

        layout.operator('wm.save_userpref')

# # Operators

class BlenderfarmConnect(bpy.types.Operator):
    """Connects to the server."""

    bl_idname = 'blenderfarm.connect'
    bl_label = 'Connect to server'

    def execute(self, context): # pylint: disable=missing-docstring,no-self-use
        global CLIENT
        
        prefs = BlenderfarmAddonPreferences.get(context)

        CLIENT.set_host_port(prefs.server_host, prefs.server_port)
        CLIENT.set_insecure(prefs.server_insecure)

        try:
            CLIENT.connect()
        except blenderfarm.client.Error as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

        if not CLIENT.is_connected():
            self.report({'ERROR'}, 'Could not connect to ' + CLIENT.get_host_port())

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
    """Cancels all current tasks and calls the `blenderfarm.disconnect`
operator to prevent new tasks from being connected."""

    bl_idname = 'blenderfarm.node_task_cancel'
    bl_label = 'Cancel in-progress tasks'

    def execute(self, context): # pylint: disable=missing-docstring,no-self-use,unused-argument
        bpy.ops.blenderfarm.disconnect()

        bpy.ops.wm.read_homefile()
        return {'FINISHED'}

class BlenderfarmNodeTaskPerform(bpy.types.Operator):
    """Requests a new task from the server and begins executing it."""

    bl_idname = 'blenderfarm.node_task_perform'
    bl_label = 'Fetch and perform task'

    def execute(self, context): # pylint: disable=missing-docstring,no-self-use,unused-argument
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
        self.add_row(box, 'Connected', str(CLIENT.is_connected()))
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

        task_buttons.prop(prefs, 'node_task_single')


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

        row = server_row.split(percentage=0.6, align=True)
        row.prop(prefs, 'server_host', text='')
        row.prop(prefs, 'server_port', text='')

        # ### Credentials row
        credentials_row = get_new_table_row(status_box)

        credentials_row.label('Credentials:')

        row = credentials_row.split(percentage=0.6, align=True)
        row.prop(prefs, 'credentials_username', text='')
        row.prop(prefs, 'credentials_key', text='', icon='KEY_HLT')

        # And now for a row at the bottom
        row = get_new_table_row(layout, align=False)
        row.prop(prefs, 'server_insecure', text='Use HTTP')

        row.operator('wm.save_userpref', text='Save Settings')

        if CLIENT.is_connected():
            row.enabled = False
            
        row = layout.row()
        row.prop(prefs, 'developer_mode')
        
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

def register():
    """Registers the Blenderfarm addon."""

    for _class in CLASSES_TO_REGISTER:
        bpy.utils.register_class(_class)

def unregister():
    """Unregisters the Blenderfarm Node addon."""

    # First, cancel any operations.
    #bpy.ops.blenderfarm.node_task_cancel()

    for _class in CLASSES_TO_REGISTER:
        bpy.utils.unregister_class(_class)
