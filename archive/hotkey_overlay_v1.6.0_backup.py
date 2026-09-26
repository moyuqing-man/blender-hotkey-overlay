# SPDX‑License‑Identifier: GPL‑3.0‑only
bl_info = {
    "name": "Hotkey Overlay",
    "author": "Custom",
    "version": (1, 6, 0),
    "blender": (3, 6, 0),
    "location": "3D View → N面板 → HotkeyOverlay",
    "description": "Realtime key & mouse display, auto‑generate hints from user keymap, customizable hotkey hint",
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
modal_operator_instance = None

# 获取自动配置文件路径
def get_auto_config_path():
    scripts_dir = bpy.utils.user_resource('SCRIPTS', create=True)
    return os.path.join(scripts_dir, "hotkey_overlay_config.json")

# -------------------------- Keymap 映射表 idname → 中文说明（高频常用） --------------------------
KEYMAP_OP_MAP = {
    # 物体模式
    "object.select_all": "A 全选 / 取消全选",
    "transform.translate": "G 移动",
    "transform.rotate": "R 旋转",
    "transform.resize": "S 缩放",
    "object.duplicate_move": "Shift+D 复制物体",
    "object.delete": "X / Delete 删除物体",
    "object.mode_set": "Tab 切换编辑模式",
    "object.shade_smooth": "Shift+G 平滑着色",
    "object.shade_flat": "Shift+F 平面着色",
    # 编辑模式
    "mesh.select_all": "A 点/边/面全选",
    "transform.translate": "G 移动元素",
    "transform.rotate": "R 旋转元素",
    "transform.resize": "S 缩放元素",
    "mesh.extrude_region_move": "E 挤出",
    "mesh.edge_face_add": "F 填充面",
    "mesh.bevel": "Ctrl+B 倒角",
    "mesh.delete": "X 删除元素",
    "object.mode_set": "Tab 返回物体模式",
    "wm.context_set_enum": {"MESH_VERTEX": "1 点选择", "MESH_EDGE": "2 边选择", "MESH_FACE": "3 面选择"},
    # 姿态模式
    "pose.select_all": "A 骨骼全选",
    "transform.translate": "G 移动骨骼",
    "transform.rotate": "R 旋转骨骼",
    "transform.resize": "S 缩放骨骼",
    "anim.keyframe_insert": "I 插入关键帧",
    "object.mode_set": "Tab 返回物体模式",
    # 雕刻模式
    "brush.size": "F 调整笔刷大小",
    "sculpt.brush_stroke": "Shift 平滑笔刷",
    "sculpt.brush_stroke": "Ctrl 向内雕刻",
    "object.mode_set": "Tab 返回物体模式",
}

KEYMAP_CONTEXT_MAP = {
    "OBJECT": "Object Mode",
    "EDIT": "Mesh Edit",
    "POSE": "Pose",
    "SCULPT": "Sculpt"
}

def keymap_item_to_label(kmi):
    """把keymap_item转为 修饰键+按键字符串"""
    mods = []
    if kmi.shift:
        mods.append("Shift")
    if kmi.ctrl:
        mods.append("Ctrl")
    if kmi.alt:
        mods.append("Alt")
    if kmi.oskey:
        mods.append("Win")
    key = kmi.name if kmi.name else kmi.type
    if mods:
        return " + ".join(mods) + " + " + key
    return key

def generate_hints_from_keymap(mode_name, settings):
    """从系统keymap自动生成提示文本，填入对应mode的collection"""
    target_coll = None
    header_title = ""
    if mode_name == "OBJECT":
        target_coll = settings.object_hints
        header_title = "【物体模式】自动生成"
        km_context = "Object Mode"
    elif mode_name == "EDIT":
        target_coll = settings.edit_hints
        header_title = "【编辑模式】自动生成"
        km_context = "Mesh Edit"
    elif mode_name == "POSE":
        target_coll = settings.pose_hints
        header_title = "【姿态模式】自动生成"
        km_context = "Pose"
    elif mode_name == "SCULPT":
        target_coll = settings.sculpt_hints
        header_title = "【雕刻模式】自动生成"
        km_context = "Sculpt"
    else:
        return False

    target_coll.clear()
    item_head = target_coll.add()
    item_head.text = header_title

    wm = bpy.context.window_manager
    keyconf = wm.keyconfigs.user
    found_ops = set()
    for km in keyconf.keymaps:
        if km.name != km_context:
            continue
        for kmi in km.keymap_items:
            if not kmi.active:
                continue
            op_id = kmi.idname
            if op_id in KEYMAP_OP_MAP and op_id not in found_ops:
                found_ops.add(op_id)
                disp_text = KEYMAP_OP_MAP[op_id]
                # 如果映射是dict（选择模式1/2/3）跳过，直接用内置文本
                if isinstance(disp_text, dict):
                    continue
                line_item = target_coll.add()
                line_item.text = disp_text
    return True

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
    with open(filepath, "w", encoding="utf‑8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_config_from_file(settings, filepath):
    with open(filepath, "r", encoding="utf‑8") as f:
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

# ====================== 视口绘制【修复：增加region,rv3d参数】 ======================
def draw_callback_px(region, rv3d):
    global display_text, display_time
    ctx = bpy.context
    if ctx.space_data is None or ctx.space_data.type != 'VIEW_3D':
        return
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

# -------------------------- 新增：从系统快捷键自动生成提示算子 --------------------------
class HOTKEYOVERLAY_OT_AutoGenHintFromKeymap(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.autogen_hint_keymap"
    bl_label = "从系统快捷键生成当前模式提示"
    bl_description = "读取用户自定义键位，生成提示文本；修改快捷键后需要手动点此刷新"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        mode = settings.selected_mode
        ok = generate_hints_from_keymap(mode, settings)
        if ok:
            self.report({'INFO'}, f"{mode}模式：已从系统快捷键自动生成提示")
        else:
            self.report({'ERROR'}, "生成失败")
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
        row.operator("hotkeyoverlay.add_hint_line", icon='PLUS')
        row.operator("hotkeyoverlay.remove_hint_line", icon='TRASH')
        row.operator("hotkeyoverlay.reset_hints", icon='RECOVER_LAST')
        # 新增：从系统快捷键自动生成按钮
        box.operator("hotkeyoverlay.autogen_hint_keymap", icon='KEYINGSET')

        box = layout.box()
        box.label(text="自动配置")
        row = box.row()
        row.operator("hotkeyoverlay.save_auto_config", icon='EXPORT')
        row.operator("hotkeyoverlay.load_auto_config", icon='RECOVER_LAST')

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
    HOTKEYOVERLAY_OT_AutoGenHintFromKeymap,
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

def delayed_init():
    context = bpy.context
    settings = context.scene.hotkey_overlay_settings
    auto_path = get_auto_config_path()
    if os.path.exists(auto_path):
        try:
            load_config_from_file(settings, auto_path)
        except Exception:
            init_default_hints(settings)
    else:
        init_default_hints(settings)
    return None

def delayed_start_modal():
    global modal_operator_instance
    if modal_operator_instance is not None:
        return None
    bpy.ops.hotkeyoverlay.capture_input('INVOKE_DEFAULT')
    return None

def _start_modal_on_load(dummy):
    bpy.app.timers.register(delayed_start_modal, first_interval=0.1, persistent=False)


def register():
    global draw_handle
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass

    try:
        bpy.types.Scene.hotkey_overlay_settings = bpy.props.PointerProperty(type=HotkeyOverlaySettings)
    except Exception:
        pass

    bpy.app.timers.register(delayed_init, first_interval=0.2, persistent=False)

    draw_handle = bpy.types.SpaceView3D.draw_handler_add(
        draw_callback_px, (), 'WINDOW', 'POST_PIXEL'
    )
    if _start_modal_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_start_modal_on_load)


def unregister():
    global draw_handle, modal_operator_instance
    if _start_modal_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_start_modal_on_load)
    modal_operator_instance = None

    if draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handle, 'WINDOW')
        draw_handle = None

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass

    if hasattr(bpy.types.Scene, "hotkey_overlay_settings"):
        del bpy.types.Scene.hotkey_overlay_settings


if __name__ == "__main__":
    register()
