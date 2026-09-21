# SPDX-License-Identifier: GPL-3.0-only
bl_info = {
    "name": "Hotkey Overlay",
    "author": "Custom",
    "version": (1, 5, 0),
    "blender": (3, 6, 0),
    "location": "3D View → N面板 → HotkeyOverlay",
    "description": "Realtime key & mouse display + customizable mode hotkey hint, auto save config to blender user folder",
    "category": "3D View",
}
import bpy
import blf
import json
import time
import os

# ====================== 全局变量 ======================
draw_handle = None
display_text = ""
display_time = 0.0
DISPLAY_DURATION = 1.2
modal_operator_instance = None  # 保存模态算子实例，用于停止

# 获取自动配置文件路径
def get_auto_config_path():
    scripts_dir = bpy.utils.user_resource('SCRIPTS', create=True)
    return os.path.join(scripts_dir, "hotkey_overlay_config.json")

# ====================== 数据结构 ======================
class HOTKEYOVERLAY_UL_HintItem(bpy.types.PropertyGroup):
    text: bpy.props.StringProperty(name="提示行")

class HotkeyOverlaySettings(bpy.types.PropertyGroup):
    # 键盘按键显示
    enable_key_display: bpy.props.BoolProperty(name="开启键盘按键显示", default=False)
    key_font_size: bpy.props.IntProperty(name="按键字体大小", default=24, min=10, max=80)
    key_bg_opacity: bpy.props.FloatProperty(name="按键背景透明度", default=0.4, min=0, max=1)
    # 鼠标点击显示
    enable_mouse_display: bpy.props.BoolProperty(name="开启鼠标点击显示", default=True)
    # 常驻快捷键提示
    enable_hotkey_hint: bpy.props.BoolProperty(name="开启模式快捷键提示", default=True)
    hint_font_size: bpy.props.IntProperty(name="提示字体大小", default=18, min=10, max=40)
    hint_bg_opacity: bpy.props.FloatProperty(name="提示背景透明度", default=0.3, min=0, max=1)
    # 各模式自定义提示
    object_hints: bpy.props.CollectionProperty(type=HOTKEYOVERLAY_UL_HintItem)
    edit_hints: bpy.props.CollectionProperty(type=HOTKEYOVERLAY_UL_HintItem)
    pose_hints: bpy.props.CollectionProperty(type=HOTKEYOVERLAY_UL_HintItem)
    sculpt_hints: bpy.props.CollectionProperty(type=HOTKEYOVERLAY_UL_HintItem)
    selected_mode: bpy.props.EnumProperty(
        name="编辑模式",
        items=[
            ('OBJECT', "物体模式", "编辑物体模式提示"),
            ('EDIT', "编辑模式", "编辑编辑模式提示"),
            ('POSE', "姿态模式", "编辑姿态模式提示"),
            ('SCULPT', "雕刻模式", "编辑雕刻模式提示"),
        ],
        default='OBJECT'
    )
    selected_hint_index: bpy.props.IntProperty(default=0)
    # 手动备份用路径
    backup_path: bpy.props.StringProperty(
        name="备份文件路径",
        default="hotkey_backup.json",
        subtype='FILE_PATH'
    )

# ====================== 默认提示初始化 ======================
def reset_hint_list(collection, default_lines):
    collection.clear()
    for line in default_lines:
        item = collection.add()
        item.text = line

def init_default_hints(settings):
    reset_hint_list(settings.object_hints, [
        "【物体模式】",
        "A 全选 / 取消全选",
        "G 移动 | R 旋转 | S 缩放",
        "Shift+D 复制物体",
        "X / Delete 删除",
        "Tab 进入编辑模式"
    ])
    reset_hint_list(settings.edit_hints, [
        "【编辑模式】",
        "1点 2边 3面",
        "G移动 R旋转 S缩放",
        "E挤出 | F填充面",
        "Ctrl+B 倒角",
        "Tab 返回物体模式"
    ])
    reset_hint_list(settings.pose_hints, [
        "【姿态模式】",
        "G移动 R旋转 S缩放",
        "Shift 多选骨骼",
        "I 插入关键帧",
        "Tab 返回物体模式"
    ])
    reset_hint_list(settings.sculpt_hints, [
        "【雕刻模式】",
        "F 调整笔刷大小",
        "Shift 平滑",
        "Ctrl 向内雕刻",
        "Tab 返回物体模式"
    ])

# ====================== 配置读写函数 ======================
def save_config_to_file(settings, filepath):
    config = {
        "enable_key_display": settings.enable_key_display,
        "enable_mouse_display": settings.enable_mouse_display,
        "key_font_size": settings.key_font_size,
        "key_bg_opacity": settings.key_bg_opacity,
        "enable_hotkey_hint": settings.enable_hotkey_hint,
        "hint_font_size": settings.hint_font_size,
        "hint_bg_opacity": settings.hint_bg_opacity,
        "object_hints": [item.text for item in settings.object_hints],
        "edit_hints": [item.text for item in settings.edit_hints],
        "pose_hints": [item.text for item in settings.pose_hints],
        "sculpt_hints": [item.text for item in settings.sculpt_hints],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_config_from_file(settings, filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        config = json.load(f)
    settings.enable_key_display = config.get("enable_key_display", False)
    settings.enable_mouse_display = config.get("enable_mouse_display", True)
    settings.key_font_size = config.get("key_font_size", 24)
    settings.key_bg_opacity = config.get("key_bg_opacity", 0.4)
    settings.enable_hotkey_hint = config.get("enable_hotkey_hint", True)
    settings.hint_font_size = config.get("hint_font_size", 18)
    settings.hint_bg_opacity = config.get("hint_bg_opacity", 0.3)
    reset_hint_list(settings.object_hints, config.get("object_hints", []))
    reset_hint_list(settings.edit_hints, config.get("edit_hints", []))
    reset_hint_list(settings.pose_hints, config.get("pose_hints", []))
    reset_hint_list(settings.sculpt_hints, config.get("sculpt_hints", []))

# ====================== 获取当前模式提示 ======================
def get_current_hint_list(context):
    obj = context.active_object
    settings = context.scene.hotkey_overlay_settings
    if not obj:
        return ["【无选中物体】"]
    mode = obj.mode
    if mode == "OBJECT":
        return [item.text for item in settings.object_hints]
    elif mode == "EDIT":
        return [item.text for item in settings.edit_hints]
    elif mode == "POSE":
        return [item.text for item in settings.pose_hints]
    elif mode == "SCULPT":
        return [item.text for item in settings.sculpt_hints]
    else:
        return [f"【{mode}模式】暂无快捷键"]

# ====================== 绘制半透明黑底 ======================
def draw_rect(x, y, w, h, color):
    import gpu
    from gpu_extras.batch import batch_for_shader
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(
        shader,
        'TRIS',
        {
            "pos": [
                (x, y),
                (x + w, y),
                (x, y + h),
                (x + w, y),
                (x + w, y + h),
                (x, y + h),
            ]
        },
    )
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

# ====================== 视口绘制 ======================
def draw_callback_px():
    global display_text, display_time
    ctx = bpy.context
    settings = ctx.scene.hotkey_overlay_settings
    now = time.time()
    # 常驻快捷键提示
    if settings.enable_hotkey_hint:
        lines = get_current_hint_list(ctx)
        font_id = 0
        blf.size(font_id, settings.hint_font_size, 72)
        line_height = settings.hint_font_size + 6
        total_h = line_height * len(lines)
        y_start = 30
        draw_rect(10, y_start, 420, total_h, (0, 0, 0, settings.hint_bg_opacity))
        y_pos = y_start
        for line in reversed(lines):
            blf.color(font_id, 0.95, 0.95, 0.95, 1)
            blf.position(font_id, 16, y_pos + 4, 0)
            blf.draw(font_id, line)
            y_pos += line_height
    # 键盘/鼠标文字显示 + 淡出
    if display_text != "":
        elapsed = now - display_time
        if elapsed > DISPLAY_DURATION:
            display_text = ""
            return
        alpha = max(0.0, 1.0 - (elapsed / DISPLAY_DURATION))
        font_id = 0
        blf.size(font_id, settings.key_font_size, 72)
        tw = blf.dimensions(font_id, display_text)[0]
        x_pos = 20
        y_pos = 220
        draw_rect(
            x_pos - 6,
            y_pos - 6,
            tw + 12,
            settings.key_font_size + 14,
            (0, 0, 0, settings.key_bg_opacity * alpha),
        )
        blf.color(font_id, 1.0, 1.0, 1.0, alpha)
        blf.position(font_id, x_pos, y_pos, 0)
        blf.draw(font_id, display_text)

# ====================== 键盘+鼠标捕获模态器 ======================
class HOTKEYOVERLAY_OT_CaptureInput(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.capture_input"
    bl_label = "开启输入捕获"
    bl_options = {'REGISTER'}

    def modal(self, context, event):
        global display_text, display_time, modal_operator_instance
        if modal_operator_instance is not self:
            return {'CANCELLED'}

        settings = context.scene.hotkey_overlay_settings
        input_text = None
        # 键盘捕获
        if event.type != 'MOUSEMOVE' and event.value == 'PRESS' and settings.enable_key_display:
            mods = []
            if event.shift:
                mods.append("Shift")
            if event.ctrl:
                mods.append("Ctrl")
            if event.alt:
                mods.append("Alt")
            if event.oskey:
                mods.append("Win")
            ignore_keys = {"LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_CTRL", "RIGHT_CTRL", "LEFT_ALT", "RIGHT_ALT"}
            if event.type not in ignore_keys:
                if mods:
                    input_text = " + ".join(mods) + " + " + event.type
                else:
                    input_text = event.type
        # 鼠标捕获
        if settings.enable_mouse_display:
            if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                input_text = "鼠标左键"
            elif event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
                input_text = "鼠标右键"
            elif event.type == 'MIDDLEMOUSE' and event.value == 'PRESS':
                input_text = "鼠标中键"
            elif event.type == 'WHEELUPMOUSE':
                input_text = "鼠标滚轮向上"
            elif event.type == 'WHEELDOWNMOUSE':
                input_text = "鼠标滚轮向下"
        if input_text is not None:
            display_text = input_text
            display_time = time.time()
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        global modal_operator_instance
        # 防止重复启动
        if modal_operator_instance is not None:
            self.report({'WARNING'}, "输入捕获已经在运行")
            return {'CANCELLED'}
        modal_operator_instance = self
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    @classmethod
    def poll(cls, context):
        global modal_operator_instance
        return modal_operator_instance is None


class HOTKEYOVERLAY_OT_StopCapture(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.stop_capture"
    bl_label = "停止输入捕获"
    bl_options = {'REGISTER'}

    def execute(self, context):
        global modal_operator_instance
        if modal_operator_instance is not None:
            modal_operator_instance = None
            self.report({'INFO'}, "已停止输入捕获")
        return {'FINISHED'}

# ====================== 列表编辑操作 ======================
class HOTKEYOVERLAY_OT_AddHintLine(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.add_hint_line"
    bl_label = "添加一行"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        coll = getattr(settings, f"{settings.selected_mode.lower()}_hints")
        item = coll.add()
        item.text = "新提示"
        return {'FINISHED'}

class HOTKEYOVERLAY_OT_RemoveHintLine(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.remove_hint_line"
    bl_label = "删除选中行"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        coll = getattr(settings, f"{settings.selected_mode.lower()}_hints")
        if 0 <= settings.selected_hint_index < len(coll):
            coll.remove(settings.selected_hint_index)
        return {'FINISHED'}

class HOTKEYOVERLAY_OT_ResetHints(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.reset_hints"
    bl_label = "重置当前模式为默认"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        mode = settings.selected_mode
        if mode == 'OBJECT':
            reset_hint_list(settings.object_hints, [
                "【物体模式】",
                "A 全选 / 取消全选",
                "G 移动 | R 旋转 | S 缩放",
                "Shift+D 复制物体",
                "X / Delete 删除",
                "Tab 进入编辑模式"
            ])
        elif mode == 'EDIT':
            reset_hint_list(settings.edit_hints, [
                "【编辑模式】",
                "1点 2边 3面",
                "G移动 R旋转 S缩放",
                "E挤出 | F填充面",
                "Ctrl+B 倒角",
                "Tab 返回物体模式"
            ])
        elif mode == 'POSE':
            reset_hint_list(settings.pose_hints, [
                "【姿态模式】",
                "G移动 R旋转 S缩放",
                "Shift 多选骨骼",
                "I 插入关键帧",
                "Tab 返回物体模式"
            ])
        elif mode == 'SCULPT':
            reset_hint_list(settings.sculpt_hints, [
                "【雕刻模式】",
                "F 调整笔刷大小",
                "Shift 平滑",
                "Ctrl 向内雕刻",
                "Tab 返回物体模式"
            ])
        return {'FINISHED'}

# ====================== 自动保存/加载 + 手动备份操作 ======================
class HOTKEYOVERLAY_OT_SaveAutoConfig(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.save_auto_config"
    bl_label = "保存到默认配置"
    bl_description = "保存当前全部设置到Blender脚本目录，下次启动自动加载"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        path = get_auto_config_path()
        try:
            save_config_to_file(settings, path)
            self.report({'INFO'}, f"已自动保存到：{path}")
        except Exception as e:
            self.report({'ERROR'}, f"保存失败：{e}")
        return {'FINISHED'}

class HOTKEYOVERLAY_OT_LoadAutoConfig(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.load_auto_config"
    bl_label = "加载默认配置"
    bl_description = "读取Blender脚本目录里保存的配置"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        path = get_auto_config_path()
        if not os.path.exists(path):
            self.report({'WARNING'}, "默认配置文件不存在！")
            return {'CANCELLED'}
        try:
            load_config_from_file(settings, path)
            self.report({'INFO'}, "已加载默认配置")
        except Exception as e:
            self.report({'ERROR'}, f"加载失败：{e}")
        return {'FINISHED'}

class HOTKEYOVERLAY_OT_ExportBackup(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.export_backup"
    bl_label = "导出备份"
    bl_description = "另存为备份文件，用于分享或异地备份"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        path = bpy.path.abspath(settings.backup_path)
        try:
            save_config_to_file(settings, path)
            self.report({'INFO'}, "备份导出成功")
        except Exception as e:
            self.report({'ERROR'}, f"备份导出失败：{e}")
        return {'FINISHED'}

class HOTKEYOVERLAY_OT_ImportBackup(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.import_backup"
    bl_label = "导入备份"
    bl_description = "从外部备份文件载入配置"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        path = bpy.path.abspath(settings.backup_path)
        if not os.path.exists(path):
            self.report({'WARNING'}, "备份文件不存在！")
            return {'CANCELLED'}
        try:
            load_config_from_file(settings, path)
            self.report({'INFO'}, "备份导入成功")
        except Exception as e:
            self.report({'ERROR'}, f"备份导入失败：{e}")
        return {'FINISHED'}

# ====================== UI 面板 ======================
class HOTKEYOVERLAY_UL_List(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, "text", text="")

class HOTKEYOVERLAY_PT_Panel(bpy.types.Panel):
    bl_label = "Hotkey Overlay"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'HotkeyOverlay'
    def draw(self, context):
        global modal_operator_instance
        layout = self.layout
        settings = context.scene.hotkey_overlay_settings

        # 捕获控制按钮
        box_run = layout.box()
        if modal_operator_instance is None:
            box_run.operator("hotkeyoverlay.capture_input", icon='PLAY')
        else:
            box_run.operator("hotkeyoverlay.stop_capture", icon='PAUSE')

        box = layout.box()
        box.label(text="输入显示")
        box.prop(settings, "enable_key_display")
        box.prop(settings, "enable_mouse_display")
        box.prop(settings, "key_font_size")
        box.prop(settings, "key_bg_opacity")

        box = layout.box()
        box.label(text="常驻快捷键提示")
        box.prop(settings, "enable_hotkey_hint")
        box.prop(settings, "hint_font_size")
        box.prop(settings, "hint_bg_opacity")

        box = layout.box()
        box.label(text="自定义提示文本编辑器")
        box.prop(settings, "selected_mode")
        coll = getattr(settings, f"{settings.selected_mode.lower()}_hints")
        box.template_list(
            "HOTKEYOVERLAY_UL_List",
            "",
            settings,
            f"{settings.selected_mode.lower()}_hints",
            settings,
            "selected_hint_index",
        )
        row = box.row()
        row.operator("hotkeyoverlay.add_hint_line", icon='ADD')
        row.operator("hotkeyoverlay.remove_hint_line", icon='REMOVE')
        row.operator("hotkeyoverlay.reset_hints", icon='FILE_REFRESH')

        box = layout.box()
        box.label(text="自动配置")
        row = box.row()
        row.operator("hotkeyoverlay.save_auto_config", icon='SAVE')
        row.operator("hotkeyoverlay.load_auto_config", icon='FILE_REFRESH')

        box = layout.box()
        box.label(text="备份 / 分享配置")
        box.prop(settings, "backup_path")
        row = box.row()
        row.operator("hotkeyoverlay.export_backup", icon='EXPORT')
        row.operator("hotkeyoverlay.import_backup", icon='IMPORT')


# ====================== 注册 / 注销 ======================
classes = (
    HOTKEYOVERLAY_UL_HintItem,
    HotkeyOverlaySettings,
    HOTKEYOVERLAY_OT_CaptureInput,
    HOTKEYOVERLAY_OT_StopCapture,
    HOTKEYOVERLAY_OT_AddHintLine,
    HOTKEYOVERLAY_OT_RemoveHintLine,
    HOTKEYOVERLAY_OT_ResetHints,
    HOTKEYOVERLAY_OT_SaveAutoConfig,
    HOTKEYOVERLAY_OT_LoadAutoConfig,
    HOTKEYOVERLAY_OT_ExportBackup,
    HOTKEYOVERLAY_OT_ImportBackup,
    HOTKEYOVERLAY_UL_List,
    HOTKEYOVERLAY_PT_Panel,
)

def _start_modal_on_load(dummy):
    """加载blend文件后自动启动捕获"""
    global modal_operator_instance
    if modal_operator_instance is not None:
        return
    for win in bpy.context.window_manager.windows:
        ctx = bpy.context.copy()
        ctx["window"] = win
        bpy.ops.hotkeyoverlay.capture_input(ctx, 'INVOKE_DEFAULT')
        break


def register():
    global draw_handle
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.hotkey_overlay_settings = bpy.props.PointerProperty(type=HotkeyOverlaySettings)
    settings = bpy.context.scene.hotkey_overlay_settings
    auto_path = get_auto_config_path()
    if os.path.exists(auto_path):
        try:
            load_config_from_file(settings, auto_path)
        except Exception:
            init_default_hints(settings)
    else:
        init_default_hints(settings)

    draw_handle = bpy.types.SpaceView3D.draw_handler_add(
        draw_callback_px, (), 'WINDOW', 'POST_PIXEL'
    )
    bpy.app.handlers.load_post.append(_start_modal_on_load)


def unregister():
    global draw_handle, modal_operator_instance
    # 清理加载处理器
    if _start_modal_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_start_modal_on_load)
    # 停止正在运行的模态
    modal_operator_instance = None

    if draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handle, 'WINDOW')
        draw_handle = None

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types.Scene, "hotkey_overlay_settings"):
        del bpy.types.Scene.hotkey_overlay_settings


if __name__ == "__main__":
    register()
