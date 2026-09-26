# SPDX-License-Identifier: GPL-3.0-only
# HOTKEY OVERLAY v1.12.3
# 仅支持 Blender 4.2 ~ 5.x（扩展包形式，实测 5.2.2 Steam 版）；不再兼容 3.6-4.1 legacy
# 醒目按键弹出（类 Screen Keys 效果）+ 四模式快捷键提示 + 自动读取用户键位生成提示
bl_info = {
    "name": "Hotkey Overlay",
    "author": "Custom",
    "version": (1, 12, 3),
    "blender": (4, 2, 0),
    "location": "3D View → N面板 → HotkeyOverlay",
    "description": "Screen-Keys style key/mouse overlay + rich per-mode hotkey hints + auto-generate from user keymap + draggable/collapsible themed hint card",
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
modal_operator_instance = None
key_history = []    # 最近按键历史（教学渐隐），元素 {"text": str, "t": float}，最新在前
_hint_rect = None   # (x0, y0, w, h, title_h) 区域相对，供拖拽/折叠交互
_drag_state = None  # 拖拽会话状态
_REGION_WIN = None  # (region 窗口左 x, region 顶部窗口 y)，供 modal 换算鼠标坐标
_hold_mods = {}  # 当前按住的修饰键（Screencast Keys 风格：按住常驻显示，松开消失），值=最后事件时间戳
_modal_last_event = 0.0  # modal 最近收到事件的时间（健康检查：splash 窗口销毁导致 modal 静默死亡时自动重启）
_last_scroll = {"dir": None, "t": 0.0}  # 滚轮合并：0.3s 内同方向连续增量只记一次（人一次滚动=一次操作）
_CURRENT_MODE = "OBJECT"  # 实时模式缓存（绘制回调 context.mode 滞后，由 modal 更新）


def get_auto_config_path():
    scripts_dir = bpy.utils.user_resource('SCRIPTS', create=True)
    return os.path.join(scripts_dir, "hotkey_overlay_config.json")


# ====================== Keymap 映射表：算子idname → 中文说明（可扩充） ======================
KEYMAP_OP_MAP = {
    # ---------- 物体模式 ----------
    "object.select_all": "A 全选 / 取消全选",
    "transform.translate": "G 移动",
    "transform.rotate": "R 旋转",
    "transform.resize": "S 缩放",
    "object.duplicate_move": "Shift+D 复制",
    "object.duplicate_move_linked": "Alt+D 关联复制",
    "object.delete": "X / Delete 删除",
    "object.mode_set": "Tab 切换模式",
    "object.join": "Ctrl+J 合并",
    "object.move_to_collection": "M 移到集合",
    "object.apply": "Ctrl+A 应用变换",
    "object.shade_smooth": "Shift+G 平滑着色",
    "object.shade_flat": "Shift+F 平面着色",
    "object.select_linked": "Shift+L 关联选择",
    "object.select_grouped": "Shift+G 组合选择",
    "object.rename": "F2 重命名",
    # ---------- 编辑模式 ----------
    "mesh.select_all": "A 全选",
    "mesh.extrude_region_move": "E 挤出",
    "mesh.duplicate_move": "Shift+D 复制元素",
    "mesh.edge_face_add": "F 填充面",
    "mesh.bevel": "Ctrl+B 倒角",
    "mesh.loopcut_slide": "Ctrl+R 环切",
    "mesh.knife_tool": "K 切刀",
    "mesh.merge": "M 合并",
    "mesh.separate": "P 分离",
    "mesh.delete": "X / Delete 删除元素",
    "mesh.inset": "I 内插面",
    "mesh.hide": "H 隐藏",
    "mesh.reveal": "Alt+H 显示",
    "mesh.select_linked_pick": "L 选择关联",
    "mesh.select_more": "Ctrl+加号 扩大选择",
    "mesh.subdivide": "细分网格",
    # ---------- 姿态模式 ----------
    "pose.select_all": "A 骨骼全选",
    "anim.keyframe_insert": "I 插入关键帧",
    "pose.rot_clear": "Alt+R 清除旋转",
    "pose.loc_clear": "Alt+G 清除位移",
    "pose.scale_clear": "Alt+S 清除缩放",
    "pose.copy": "Ctrl+C 复制姿态",
    "pose.paste": "Ctrl+V 粘贴姿态",
    "armature.delete": "X / Delete 删除骨骼",
    "armature.parent_set": "Ctrl+P 设置父级",
    "pose.select_linked": "Shift+L 关联选择骨骼",
    # ---------- 雕刻模式 ----------
    "brush.size": "F 调整笔刷大小",
    "brush.stroke": "笔刷绘制",
    "sculpt.brush_stroke": "笔刷绘制",
}

# 自动生成时额外补充的固定行（保证每模式 10+ 条；keymap 匹配不到的手势类快捷键）
EXTRA_GEN_HINTS = {
    "OBJECT": [
        "Shift+A 添加物体",
        "Z 着色模式切换",
        "Shift+S 吸附菜单",
        "N 属性面板",
        "Ctrl+A 应用变换",
    ],
    "EDIT": [
        "1 / 2 / 3 点线面选择",
        "H 隐藏 | Alt+H 显示",
        "L 选择关联元素",
        "Ctrl+R 环切",
        "K 切刀",
        "I 内插面",
    ],
    "POSE": [
        "Alt+R / G / S 清除变换",
        "Ctrl+C / Ctrl+V 复制粘贴姿态",
        "Ctrl+P 设置父级",
        "M 移到集合",
    ],
    "SCULPT": [
        "F 笔刷大小",
        "Shift+F 笔刷强度",
        "[ ] 减小/增大笔刷",
        "Shift 平滑笔刷",
        "Ctrl 反向雕刻",
        "X / Y / Z 对称轴切换",
        "M 遮罩 | Alt+M 清除",
        "Ctrl+I 反转遮罩",
        "R 旋转笔刷纹理",
        "T 显示工具栏",
    ],
}

KEYMAP_CONTEXT = {
    "OBJECT": ["Object Mode", "Object Non-modal"],
    "EDIT": ["Mesh Edit", "Mesh"],  # 4.x 叫 Mesh Edit，5.2 叫 Mesh
    "POSE": ["Pose"],
    "SCULPT": ["Sculpt"],
}


def keymap_item_to_label(kmi):
    """把 keymap 项转为 修饰键+按键 字符串（显示用户当前真实键位）"""
    mods = []
    if kmi.shift:
        mods.append("Shift")
    if kmi.ctrl:
        mods.append("Ctrl")
    if kmi.alt:
        mods.append("Alt")
    if kmi.oskey:
        mods.append("Win")
    try:
        key = kmi.name or kmi.type
    except Exception:
        key = kmi.type
    if mods:
        return " + ".join(mods) + " + " + key
    return key


def generate_hints_from_keymap(mode_name, settings):
    """读取用户当前 keymap（含自定义键位），自动生成当前模式提示列表"""
    target_coll = {
        "OBJECT": settings.object_hints,
        "EDIT": settings.edit_hints,
        "POSE": settings.pose_hints,
        "SCULPT": settings.sculpt_hints,
    }.get(mode_name)
    if target_coll is None:
        return False

    target_coll.clear()
    header = target_coll.add()
    header.text = "【%s】" % {
        "OBJECT": "物体模式", "EDIT": "编辑模式", "POSE": "姿态模式", "SCULPT": "雕刻模式"
    }.get(mode_name, mode_name)

    wm = bpy.context.window_manager
    keyconf = wm.keyconfigs.user
    km_names = KEYMAP_CONTEXT.get(mode_name, [])
    matched = []
    if keyconf is not None:
        for km in keyconf.keymaps:
            if km.name not in km_names:
                continue
            for kmi in km.keymap_items:
                if not kmi.active:
                    continue
                op_id = kmi.idname
                if op_id in KEYMAP_OP_MAP and op_id not in matched:
                    matched.append(op_id)
                    label = KEYMAP_OP_MAP[op_id]
                    real = keymap_item_to_label(kmi)
                    line = target_coll.add()
                    line.text = "%s [%s]" % (label, real)
    # 补充固定行（去重）
    for extra in EXTRA_GEN_HINTS.get(mode_name, []):
        exists = any(i.text == extra for i in target_coll)
        if not exists:
            line = target_coll.add()
            line.text = extra
    return True


# ====================== 外观/位置修改自动保存（防抖） ======================
_save_timer_handle = None

def _schedule_auto_save(self=None, context=None):
    global _save_timer_handle
    def _do_save():
        global _save_timer_handle
        _save_timer_handle = None
        try:
            sc = bpy.context.scene
            if sc is not None and hasattr(sc, "hotkey_overlay_settings"):
                save_config_to_file(sc.hotkey_overlay_settings, get_auto_config_path())
        except Exception:
            pass
        return None
    if _save_timer_handle is not None:
        try:
            bpy.app.timers.unregister(_save_timer_handle)
        except Exception:
            pass
        _save_timer_handle = None
    try:
        _save_timer_handle = bpy.app.timers.register(_do_save, first_interval=0.8)
    except Exception:
        pass


# ====================== 数据结构 ======================
class HOTKEYOVERLAY_UL_HintItem(bpy.types.PropertyGroup):
    text: bpy.props.StringProperty(name="提示行")


class HotkeyOverlaySettings(bpy.types.PropertyGroup):
    # 键盘按键显示
    enable_key_display: bpy.props.BoolProperty(name="开启键盘按键显示", default=True, update=_schedule_auto_save)
    key_font_size: bpy.props.IntProperty(name="背景板宽度", default=360, min=220, max=800, update=_schedule_auto_save)
    key_bg_opacity: bpy.props.FloatProperty(name="背景板透明度", default=0.85, min=0.1, max=1, update=_schedule_auto_save)
    # 鼠标点击显示
    enable_mouse_display: bpy.props.BoolProperty(name="开启鼠标点击显示", default=True, update=_schedule_auto_save)
    # 显示时长
    fade_time: bpy.props.FloatProperty(name="按键显示时长(秒)", default=3.0, min=0.3, max=8.0, update=_schedule_auto_save)
    # 常驻快捷键提示
    enable_hotkey_hint: bpy.props.BoolProperty(name="开启模式快捷键提示", default=True, update=_schedule_auto_save)
    hint_font_size: bpy.props.IntProperty(name="提示字体大小", default=16, min=10, max=40, update=_schedule_auto_save)
    hint_bg_opacity: bpy.props.FloatProperty(name="按键块透明度", default=1.0, min=0.1, max=1, update=_schedule_auto_save)
    # 外观自定义（调色）
    hint_bg_color: bpy.props.FloatVectorProperty(name="卡片背景色", subtype='COLOR', default=(0.06, 0.06, 0.06), min=0, max=1, size=3, update=_schedule_auto_save)
    hint_title_bg_color: bpy.props.FloatVectorProperty(name="标题栏背景色", subtype='COLOR', default=(0.11, 0.11, 0.11), min=0, max=1, size=3, update=_schedule_auto_save)
    hint_title_color: bpy.props.FloatVectorProperty(name="标题文字色", subtype='COLOR', default=(0.90, 0.90, 0.90), min=0, max=1, size=3, update=_schedule_auto_save)
    hint_key_color: bpy.props.FloatVectorProperty(name="键位文字色", subtype='COLOR', default=(0.98, 0.48, 0.10), min=0, max=1, size=3, update=_schedule_auto_save)
    hint_text_color: bpy.props.FloatVectorProperty(name="说明文字色", subtype='COLOR', default=(0.80, 0.80, 0.80), min=0, max=1, size=3, update=_schedule_auto_save)
    hint_border_color: bpy.props.FloatVectorProperty(name="边框色", subtype='COLOR', default=(0.30, 0.30, 0.30), min=0, max=1, size=3, update=_schedule_auto_save)
    hint_recent_text_color: bpy.props.FloatVectorProperty(name="最近按键文字色", subtype='COLOR', default=(0.92, 0.92, 0.92), min=0, max=1, size=3, update=_schedule_auto_save)
    hint_recent_chip_color: bpy.props.FloatVectorProperty(name="最近按键块底色", subtype='COLOR', default=(0.98, 0.48, 0.10), min=0, max=1, size=3, update=_schedule_auto_save)
    # 卡片位置与折叠
    hint_pos_x: bpy.props.IntProperty(name="卡片位置X", default=12, min=-2000, max=4000, update=_schedule_auto_save)
    hint_pos_y: bpy.props.IntProperty(name="卡片位置Y", default=150, min=-2000, max=4000, update=_schedule_auto_save)
    hint_collapsed: bpy.props.BoolProperty(name="折叠提示卡", default=False, update=_schedule_auto_save)
    # 各模式自定义提示
    object_hints: bpy.props.CollectionProperty(type=HOTKEYOVERLAY_UL_HintItem)
    edit_hints: bpy.props.CollectionProperty(type=HOTKEYOVERLAY_UL_HintItem)
    pose_hints: bpy.props.CollectionProperty(type=HOTKEYOVERLAY_UL_HintItem)
    sculpt_hints: bpy.props.CollectionProperty(type=HOTKEYOVERLAY_UL_HintItem)
    selected_mode: bpy.props.EnumProperty(
        name="编辑模式",
        items=[
            ('OBJECT', "物体模式", "编辑物体模式提示"),
            ('EDIT', "编辑模式", "编辑模式提示"),
            ('POSE', "姿态模式", "姿态模式提示"),
            ('SCULPT', "雕刻模式", "雕刻模式提示"),
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


# ====================== 默认提示初始化（每模式 14~15 条） ======================
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
        "Shift+D 复制 | Alt+D 关联复制",
        "X / Delete 删除物体",
        "Shift+A 添加物体",
        "Ctrl+J 合并 | M 移到集合",
        "Ctrl+A 应用变换",
        "F2 重命名",
        "Z 着色模式切换",
        "Shift+S 吸附菜单",
        "N 属性面板",
        "Shift+L 关联选择",
        "Tab 进入编辑模式",
    ])
    reset_hint_list(settings.edit_hints, [
        "【编辑模式】",
        "1 点 | 2 边 | 3 面",
        "A 全选",
        "G 移动 | R 旋转 | S 缩放",
        "E 挤出 | I 内插面",
        "F 填充面 | Ctrl+R 环切",
        "K 切刀 | Ctrl+B 倒角",
        "M 合并 | P 分离",
        "Shift+D 复制元素",
        "H 隐藏 | Alt+H 显示",
        "L 选择关联元素",
        "Ctrl+E 边菜单 | Alt+E 挤出菜单",
        "X / Delete 删除元素",
        "Ctrl+Shift+B 顶点倒角",
        "Tab 返回物体模式",
    ])
    reset_hint_list(settings.pose_hints, [
        "【姿态模式】",
        "A 全选骨骼",
        "G 移动 | R 旋转 | S 缩放",
        "Shift 多选骨骼",
        "I 插入关键帧",
        "Alt+R 清除旋转",
        "Alt+G 清除位移",
        "Alt+S 清除缩放",
        "Ctrl+C 复制姿态",
        "Ctrl+V 粘贴姿态",
        "Ctrl+P 设置父级",
        "M 移到集合",
        "X / Delete 删除骨骼",
        ". 切换枢轴点",
        "Tab 返回物体模式",
    ])
    reset_hint_list(settings.sculpt_hints, [
        "【雕刻模式】",
        "F 笔刷大小",
        "Shift+F 笔刷强度",
        "[ ] 减小/增大笔刷",
        "Shift 平滑笔刷",
        "Ctrl 反向雕刻",
        "X / Y / Z 对称轴切换",
        "M 遮罩笔刷",
        "Alt+M 清除遮罩",
        "Ctrl+I 反转遮罩",
        "R 旋转笔刷纹理",
        "T 显示工具栏",
        "N 属性面板",
        "Tab 返回物体模式",
    ])


# ====================== 配置读写 ======================
def save_config_to_file(settings, filepath):
    config = {
        "enable_key_display": settings.enable_key_display,
        "enable_mouse_display": settings.enable_mouse_display,
        "key_font_size": settings.key_font_size,
        "key_bg_opacity": settings.key_bg_opacity,
        "fade_time": settings.fade_time,
        "enable_hotkey_hint": settings.enable_hotkey_hint,
        "hint_font_size": settings.hint_font_size,
        "hint_bg_opacity": settings.hint_bg_opacity,
        "hint_bg_color": list(settings.hint_bg_color),
        "hint_title_bg_color": list(settings.hint_title_bg_color),
        "hint_title_color": list(settings.hint_title_color),
        "hint_key_color": list(settings.hint_key_color),
        "hint_recent_text_color": list(settings.hint_recent_text_color),
        "hint_recent_chip_color": list(settings.hint_recent_chip_color),
        "hint_text_color": list(settings.hint_text_color),
        "hint_border_color": list(settings.hint_border_color),
        "hint_pos_x": settings.hint_pos_x,
        "hint_pos_y": settings.hint_pos_y,
        "hint_collapsed": settings.hint_collapsed,
        "object_hints": [item.text for item in settings.object_hints],
        "edit_hints": [item.text for item in settings.edit_hints],
        "pose_hints": [item.text for item in settings.pose_hints],
        "sculpt_hints": [item.text for item in settings.sculpt_hints],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_config_from_file(settings, filepath):
    # utf-8-sig 自动去除 BOM（部分编辑器/脚本写入时可能带 BOM 导致 json 解析失败）
    with open(filepath, "r", encoding="utf-8-sig") as f:
        config = json.load(f)
    settings.enable_key_display = config.get("enable_key_display", True)
    settings.enable_mouse_display = config.get("enable_mouse_display", True)
    settings.key_font_size = config.get("key_font_size", 360)
    settings.key_bg_opacity = config.get("key_bg_opacity", 0.85)
    settings.fade_time = config.get("fade_time", 1.4)
    settings.enable_hotkey_hint = config.get("enable_hotkey_hint", True)
    settings.hint_font_size = config.get("hint_font_size", 16)
    settings.hint_bg_opacity = config.get("hint_bg_opacity", 0.82)
    for _k in ("hint_bg_color", "hint_title_bg_color", "hint_title_color", "hint_key_color", "hint_text_color", "hint_border_color", "hint_recent_text_color", "hint_recent_chip_color"):
        _v = config.get(_k)
        if _v:
            try:
                setattr(settings, _k, tuple(_v))
            except Exception:
                pass
    settings.hint_pos_x = config.get("hint_pos_x", 12)
    settings.hint_pos_y = config.get("hint_pos_y", 150)
    settings.hint_collapsed = config.get("hint_collapsed", False)
    # 空/缺失列表用默认提示兜底，避免配置文件损坏或旧版字段为空时把用户提示清空
    _mode_map = {
        "object_hints": "OBJECT",
        "edit_hints": "EDIT",
        "pose_hints": "POSE",
        "sculpt_hints": "SCULPT",
    }
    for _attr, _mode in _mode_map.items():
        _v = config.get(_attr)
        if _v:
            reset_hint_list(getattr(settings, _attr), _v)
        else:
            reset_hint_list(getattr(settings, _attr), _DEFAULT_HINTS[_mode])


# ====================== 获取当前模式提示 ======================
_DEFAULT_HINTS = {
    "OBJECT": [
        "【物体模式】",
        "A 全选 / 取消全选",
        "G 移动 | R 旋转 | S 缩放",
        "Shift+D 复制 | Alt+D 关联复制",
        "X / Delete 删除物体",
        "Shift+A 添加物体",
        "Ctrl+J 合并 | M 移到集合",
        "Ctrl+A 应用变换",
        "F2 重命名",
        "Z 着色模式切换",
        "Shift+S 吸附菜单",
        "N 属性面板",
        "Shift+L 关联选择",
        "Tab 进入编辑模式",
    ],
    "EDIT": [
        "【编辑模式】",
        "1 点 | 2 边 | 3 面",
        "A 全选",
        "G 移动 | R 旋转 | S 缩放",
        "E 挤出 | I 内插面",
        "F 填充面 | Ctrl+R 环切",
        "K 切刀 | Ctrl+B 倒角",
        "M 合并 | P 分离",
        "Shift+D 复制元素",
        "H 隐藏 | Alt+H 显示",
        "L 选择关联元素",
        "Ctrl+E 边菜单 | Alt+E 挤出菜单",
        "X / Delete 删除元素",
        "Ctrl+Shift+B 顶点倒角",
        "Tab 返回物体模式",
    ],
    "POSE": [
        "【姿态模式】",
        "A 全选骨骼",
        "G 移动 | R 旋转 | S 缩放",
        "Shift 多选骨骼",
        "I 插入关键帧",
        "Alt+R 清除旋转",
        "Alt+G 清除位移",
        "Alt+S 清除缩放",
        "Ctrl+C 复制姿态",
        "Ctrl+V 粘贴姿态",
        "Ctrl+P 设置父级",
        "M 移到集合",
        "X / Delete 删除骨骼",
        ". 切换枢轴点",
        "Tab 返回物体模式",
    ],
    "SCULPT": [
        "【雕刻模式】",
        "F 笔刷大小",
        "Shift+F 笔刷强度",
        "[ ] 减小/增大笔刷",
        "Shift 平滑笔刷",
        "Ctrl 反向雕刻",
        "X / Y / Z 对称轴切换",
        "M 遮罩笔刷",
        "Alt+M 清除遮罩",
        "Ctrl+I 反转遮罩",
        "R 旋转笔刷纹理",
        "T 显示工具栏",
        "N 属性面板",
        "Tab 返回物体模式",
    ],
}
def get_current_hint_list(context):
    settings = context.scene.hotkey_overlay_settings
    obj = context.active_object
    # 优先用 modal 缓存的实时模式（绘制回调 context.mode 恒为旧值，Tab 切换后必须用缓存）
    global _CURRENT_MODE
    mode = _CURRENT_MODE or getattr(context, "mode", None)
    if mode is None or not isinstance(mode, str) or mode.startswith("NORMAL"):
        mode = obj.mode if obj else "OBJECT"
    # 兜底：绘制回调的 obj.mode 也可能滞后，用缓存模式校正
    if obj is not None and _CURRENT_MODE not in ("", "OBJECT", "NORMAL"):
        mode = _CURRENT_MODE
    # 归一化：EDIT_MESH / EDIT_CURVE / EDIT_SURFACE / EDIT_LATTICE → EDIT
    if mode in ("EDIT_MESH", "EDIT_CURVE", "EDIT_SURFACE", "EDIT_LATTICE", "EDIT_METABALL"):
        mode = "EDIT"
    elif mode == "EDIT_ARMATURE":
        mode = "EDIT"
    elif mode == "POSE":
        mode = "POSE"
    elif mode == "SCULPT":
        mode = "SCULPT"
    else:
        mode = "OBJECT"
    if not obj and mode == "OBJECT":
        return ["【无选中物体】", "Shift+A 添加物体", "Tab 切换模式"]
    hints_map = {
        "OBJECT": [item.text for item in settings.object_hints],
        "EDIT": [item.text for item in settings.edit_hints],
        "POSE": [item.text for item in settings.pose_hints],
        "SCULPT": [item.text for item in settings.sculpt_hints],
    }
    items = hints_map.get(mode)
    if items:
        return items
    if mode in _DEFAULT_HINTS:
        return list(_DEFAULT_HINTS[mode])
    return [f"【{mode}模式】暂无快捷键"]


# ====================== blf 字号兼容（Blender 4.x 为 3 参 / 5.x 移除 dpi 参数） ======================
def blf_set_size(font_id, size):
    try:
        blf.size(font_id, size, 72)
    except TypeError:
        blf.size(font_id, size)


# ====================== GPU 绘制半透明矩形 ======================
# 注意：Blender 5.2 起 POST_PIXEL 不再自动提供像素空间矩阵，
# 需显式加载 NDC 矩阵并按 region 尺寸把像素坐标换算为 NDC 才可见。
# blf 文字同样受当前矩阵影响，绘制文字前必须加载“像素→NDC”正交矩阵（y 翻转），
# 且 blf 坐标以【窗口像素】为准（region 相对坐标 + region.x / region.y）。
_VIEW_W = 900
_VIEW_H = 600


def draw_rect(x, y, w, h, color):
    import gpu
    from gpu_extras.batch import batch_for_shader
    rw = _VIEW_W if _VIEW_W else 900
    rh = _VIEW_H if _VIEW_H else 600
    x0 = x / rw * 2.0 - 1.0
    y0 = 1.0 - (y + h) / rh * 2.0
    x1 = (x + w) / rw * 2.0 - 1.0
    y1 = 1.0 - y / rh * 2.0
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(
        shader,
        'TRIS',
        {
            "pos": [
                (x0, y0),
                (x1, y0),
                (x0, y1),
                (x1, y0),
                (x1, y1),
                (x0, y1),
            ]
        },
    )
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


# ====================== v1.12.0 玻璃拟态：圆角矩形（SDF 抗锯齿） ======================
_ROUNDED_SHADER = None
_ROUNDED_FAILED = False
_ROUNDED_VERT = """
out vec2 v_uv;
void main() {
    v_uv = uv;
    gl_Position = vec4(pos, 0.0, 1.0);
}
"""
_ROUNDED_FRAG = """
in vec2 v_uv;
void main() {
    vec2 halfv = size * 0.5;
    vec2 d = abs(v_uv - 0.5) * size - (halfv - radius);
    float lenv = length(max(d, 0.0)) - radius;
    float alpha = color.a * (1.0 - smoothstep(0.0, 1.5, lenv));
    if (alpha <= 0.003) discard;
    fragColor = vec4(color.rgb, alpha);
}
"""


def _build_rounded_shader():
    """用 GPUShaderCreateInfo 构建圆角 SDF shader（Blender 5.2 不允许直接实例化 GPUShader）"""
    import gpu
    info = gpu.types.GPUShaderCreateInfo()
    info.vertex_in(0, 'VEC2', "pos")
    info.vertex_in(1, 'VEC2', "uv")
    info.fragment_out(0, 'VEC4', "fragColor")
    info.push_constant('VEC4', "color")
    info.push_constant('FLOAT', "radius")
    info.push_constant('VEC2', "size")
    info.vertex_source(_ROUNDED_VERT)
    info.fragment_source(_ROUNDED_FRAG)
    return gpu.shader.create_from_info(info)


def draw_rounded_rect(x, y, w, h, radius, color):
    """圆角矩形（玻璃拟态）。radius 为像素圆角半径；shader 编译失败时回退直角 draw_rect。"""
    global _ROUNDED_SHADER, _ROUNDED_FAILED
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        if _ROUNDED_SHADER is None and not _ROUNDED_FAILED:
            _ROUNDED_SHADER = _build_rounded_shader()
        if _ROUNDED_SHADER is None:
            raise RuntimeError("rounded shader unavailable")
        rw = _VIEW_W if _VIEW_W else 900
        rh = _VIEW_H if _VIEW_H else 600
        x0 = x / rw * 2.0 - 1.0
        y0 = 1.0 - (y + h) / rh * 2.0
        x1 = (x + w) / rw * 2.0 - 1.0
        y1 = 1.0 - y / rh * 2.0
        r = max(0.0, min(radius, min(w, h) / 2.0))
        batch = batch_for_shader(
            _ROUNDED_SHADER,
            'TRIS',
            {
                "pos": [
                    (x0, y0), (x1, y0), (x0, y1),
                    (x1, y0), (x1, y1), (x0, y1),
                ],
                "uv": [
                    (0, 0), (1, 0), (0, 1),
                    (1, 0), (1, 1), (0, 1),
                ],
            },
        )
        _ROUNDED_SHADER.bind()
        _ROUNDED_SHADER.uniform_float("color", color)
        _ROUNDED_SHADER.uniform_float("radius", r)
        _ROUNDED_SHADER.uniform_float("size", (w, h))
        batch.draw(_ROUNDED_SHADER)
    except Exception:
        _ROUNDED_FAILED = True
        draw_rect(x, y, w, h, color)


# ====================== 5.2 绘制矩阵辅助 ======================
# 绘制调用约定：矩形使用 NDC（单位矩阵）；blf 文字使用像素→NDC 正交矩阵（y 翻转）。
_PIXEL_MATRIX_CACHE = {}


def load_pixel_matrix(rw, rh):
    """加载像素→NDC 正交矩阵（y 向上不翻转；blf 坐标=窗口 x + 从底部数的 y）。
    注意：Blender 5.2 下 y 翻转矩阵会导致 blf 文字镜像，故必须用 y 向上矩阵。"""
    from mathutils import Matrix
    key = (rw, rh)
    m = _PIXEL_MATRIX_CACHE.get(key)
    if m is None:
        m = Matrix([[2.0 / rw, 0, 0, -1],
                    [0, 2.0 / rh, 0, -1],
                    [0, 0, 1, 0],
                    [0, 0, 0, 1]])
        _PIXEL_MATRIX_CACHE[key] = m
    import gpu
    gpu.matrix.load_matrix(m)
    gpu.matrix.load_projection_matrix(Matrix.Identity(4))


# ====================== 视口绘制回调（兼容 Blender 4.x 与 5.2 两种调用约定） ======================
# 4.x: Blender 以 (self, context) 调用回调；5.2: 只传注册时的 args（空元组）。
_DEBUG_FRAMES = 0
def _parse_hint_line(line):
    """解析提示行：'G 移动 | R 旋转 | S 缩放' → [('G','移动'),('R','旋转'),('S','缩放')]"""
    out = []
    for part in line.split("|"):
        part = part.strip()
        if not part:
            continue
        if " " in part:
            k, _, d = part.partition(" ")
            out.append((k.strip(), d.strip()))
        else:
            out.append((part, ""))
    return out


_VIEWOX_LOGGED = False


def _draw_hint_card(context, settings, rw, rh, rx, ry):
    """左上角常驻快捷键提示卡片：背景板宽度 + 字体跟随提示字体 + 文本超宽自动换行 + 可拖动 + 可折叠。"""
    global display_text, display_time, key_history, _hint_rect, _VIEWOX_LOGGED
    lines = get_current_hint_list(context)
    if not lines:
        return
    font_id = 0
    title_line = lines[0]
    body_lines = lines[1:]
    pad = 15
    title_h = settings.hint_font_size + 18
    _key_font = settings.hint_font_size + 4  # 键位字号跟随"提示字体大小"
    line_h = settings.hint_font_size + 12
    status_h = max(_key_font + 12, settings.hint_font_size + 14) + (22 if _hold_mods else 0)
    board_w = int(getattr(settings, "key_font_size", 360))  # 背景板宽度
    if board_w < 220:
        board_w = 220

    # ---- 布局：内容行超宽自动换行（检测器：超出背景板宽度即换到下一行）----
    blf_set_size(font_id, _key_font)
    render_rows = []  # 渲染行列表，每行 [(x, key, desc, kw), ...]
    for line in body_lines:
        parts = _parse_hint_line(line)
        cur = []
        x = pad
        for key, desc in parts:
            blf_set_size(font_id, _key_font)
            kw = blf.dimensions(font_id, key)[0]
            if desc:
                blf_set_size(font_id, settings.hint_font_size)
                dw = blf.dimensions(font_id, desc)[0]
            else:
                dw = 0
            seg_w = kw + 5 + (dw + 14 if desc else 0)
            if cur and x + seg_w > board_w - pad * 2:
                render_rows.append(cur)  # 本行已满，换行
                cur = []
                x = pad
            cur.append((x, key, desc, kw))
            x += seg_w
        if cur:
            render_rows.append(cur)

    # ---- 状态行宽度预留（受背景板宽度限制，不足时以状态行为准）----
    blf_set_size(font_id, _key_font)
    _lbl_w = blf.dimensions(font_id, "最近按键")[0]
    _kb_maxw = int(_key_font * 2.6)
    _hist_min = _lbl_w + 12 + 3 * (_kb_maxw + 18)
    if board_w < _hist_min:
        board_w = _hist_min
    max_w = board_w

    collapsed = bool(getattr(settings, "hint_collapsed", False))
    if collapsed:
        total_h = title_h + status_h + pad * 2
    else:
        total_h = title_h + line_h * len(render_rows) + pad * 2 + status_h
    x0 = int(getattr(settings, "hint_pos_x", 12))
    y0 = int(getattr(settings, "hint_pos_y", 150))
    bw = max_w + pad * 2
    bh = total_h
    if x0 < 4:
        x0 = 4
    if y0 < 4:
        y0 = 4
    if x0 + bw > rw - 4:
        x0 = max(4, rw - bw - 4)
    if y0 + bh > rh - 4:
        y0 = max(4, rh - bh - 4)
    _hint_rect = (x0, y0, bw, bh, title_h)

    def _c3(prop, default):
        try:
            return tuple(prop)
        except Exception:
            return default

    bg = _c3(settings.hint_bg_color, (0.06, 0.06, 0.06))
    title_bg = _c3(settings.hint_title_bg_color, (0.11, 0.11, 0.11))
    title_col = _c3(settings.hint_title_color, (0.90, 0.90, 0.90))
    key_col = _c3(settings.hint_key_color, (0.98, 0.48, 0.10))
    text_col = _c3(settings.hint_text_color, (0.80, 0.80, 0.80))
    border_col = _c3(settings.hint_border_color, (0.30, 0.30, 0.30))
    # 背景板透明度 = 卡片整体透明度（用户可真正控制背景板本身）
    bg_a = max(0.1, min(1.0, settings.key_bg_opacity))
    # 按键块透明度（最近按键块 / 按住行块）
    chip_a = max(0.1, min(1.0, settings.hint_bg_opacity))
    # ===== v1.12.0 玻璃拟态：三层悬浮投影 + 圆角背景 + 圆角描边 + 顶部高光 =====
    _rad = 12
    draw_rounded_rect(x0 + 2, y0 - 3, bw, bh, _rad, (0, 0, 0, 0.16 * bg_a))  # v1.12.1: 单层投影
    draw_rounded_rect(x0, y0, bw, bh, _rad, (border_col[0], border_col[1], border_col[2], 0.5 * bg_a))
    draw_rounded_rect(x0 + 1, y0 + 1, bw - 2, bh - 2, _rad - 1, (bg[0], bg[1], bg[2], bg_a))
    draw_rounded_rect(x0 + 4, y0 + 2, bw - 8, 2, 1, (1, 1, 1, 0.14 * bg_a))
    if title_line:
        # 简约：标题栏淡圆角块 + 细分隔线（不再用实色块）
        draw_rounded_rect(x0 + 2, y0 + 2, bw - 4, title_h - 3, 10, (title_bg[0], title_bg[1], title_bg[2], 0.30 * bg_a))
        draw_rect(x0 + 10, y0 + title_h - 2, bw - 20, 1, (1, 1, 1, 0.10 * bg_a))
    view_ox = rx
    load_pixel_matrix(rw, rh)
    if title_line:
        blf_set_size(font_id, settings.hint_font_size + 1)
        tw = blf.dimensions(font_id, title_line)[0]
        tx = x0 + (bw - tw) / 2
        ty = y0 + title_h - 9
        blf.color(font_id, title_col[0], title_col[1], title_col[2], 1.0)
        blf.position(font_id, view_ox + tx, rh - ty, 0)
        blf.draw(font_id, title_line)
    # 内容行（折叠时跳过），按渲染行布局
    if not collapsed:
        row_i = 0
        for row in render_rows:
            y = y0 + title_h + pad + row_i * line_h
            row_i += 1
            for (x, key, desc, kw) in row:
                _px = x0 + x
                blf_set_size(font_id, _key_font)
                draw_rect(_px - 4, y - 2, kw + 8, _key_font + 6, (key_col[0], key_col[1], key_col[2], 0.12))  # v1.12.1: 轻量直角块
                blf.color(font_id, key_col[0], key_col[1], key_col[2], 1.0)
                blf.position(font_id, view_ox + _px, rh - (y + _key_font / 2 - 1), 0)
                blf.draw(font_id, key)
                if desc:
                    blf_set_size(font_id, settings.hint_font_size)
                    _dx = _px + kw + 5
                    blf.color(font_id, text_col[0], text_col[1], text_col[2], 1.0)
                    blf.position(font_id, view_ox + _dx, rh - (y + _key_font / 2 - 1 + (_key_font - settings.hint_font_size) / 2), 0)
                    blf.draw(font_id, desc)
    # 最近按键状态行
    hold_h = 22 if _hold_mods else 0
    s_y = y0 + total_h - status_h - pad + 6
    draw_rect(x0 + pad, s_y, bw - pad * 2, 1, (1.0, 1.0, 1.0, 0.10))
    # 按住修饰键行
    if _hold_mods:
        hy = s_y + status_h - hold_h + 4
        blf_set_size(font_id, settings.hint_font_size)
        _lw2 = blf.dimensions(font_id, "按住")[0]
        blf.color(font_id, 0.78, 0.84, 1.0, 0.98)
        blf.position(font_id, view_ox + x0 + pad, rh - (hy + settings.hint_font_size / 2 - 1), 0)
        blf.draw(font_id, "按住")
        kx2 = x0 + pad + _lw2 + 10
        for _m in _hold_mods:
            blf_set_size(font_id, settings.hint_font_size)
            _tw2 = blf.dimensions(font_id, _m)[0]
            _hh2 = settings.hint_font_size + 10
            draw_rect(kx2 - 6, hy, _tw2 + 12, _hh2,
                      (key_col[0], key_col[1], key_col[2], 0.85 * chip_a))  # v1.12.1: 轻量直角块
            _rc2 = _c3(settings.hint_recent_text_color, (0.97, 0.98, 1.0))
            blf.color(font_id, _rc2[0], _rc2[1], _rc2[2], chip_a)
            blf.position(font_id, view_ox + kx2, rh - (hy + 5 + settings.hint_font_size / 2), 0)
            blf.draw(font_id, _m)
            kx2 += _tw2 + 10 + 6
    blf_set_size(font_id, settings.hint_font_size)
    lw = blf.dimensions(font_id, "最近按键")[0]
    blf.color(font_id, 0.78, 0.84, 1.0, 0.98)
    _lbl_cy = s_y + 1 + (_key_font + 8) / 2.0
    blf.position(font_id, view_ox + x0 + pad, rh - (_lbl_cy + settings.hint_font_size / 2 - 1), 0)
    blf.draw(font_id, "最近按键")
    _now = time.time()
    key_history = [h for h in key_history if _now - h["t"] <= settings.fade_time]
    kx = x0 + pad + lw + 12
    _right_edge = x0 + max_w - pad - 6
    if key_history:
        blf_set_size(font_id, _key_font)
        for idx, item in enumerate(key_history):
            age = _now - item["t"]
            a = max(0.0, min(1.0, 1.0 - age / settings.fade_time))
            if a <= 0.02:
                continue
            txt = item["text"]
            if not txt:
                continue
            _fs = _key_font
            _tw = blf.dimensions(font_id, txt)[0]
            if _tw > _kb_maxw:
                # 文本过长时缩小字号，避免撑破卡片
                _fs = max(settings.hint_font_size - 2, int(_fs * _kb_maxw / _tw))
                blf_set_size(font_id, _fs)
                _kw = blf.dimensions(font_id, txt)[0]
            else:
                _kw = _tw
            if kx + _kw + 12 > _right_edge:
                break  # 超出背景板宽度，停止放置更多块
            _kb_a = chip_a * a
            _kb_y = s_y + 1
            _kb_h = _key_font + 8
            draw_rounded_rect(kx - 7, _kb_y - 1, _kw + 14, _kb_h + 2, 5, (border_col[0], border_col[1], border_col[2], 0.30 * chip_a * a))
            _chip_c = _c3(settings.hint_recent_chip_color, (0.98, 0.48, 0.10))
            draw_rounded_rect(kx - 6, _kb_y, _kw + 12, _kb_h, 4, (_chip_c[0], _chip_c[1], _chip_c[2], _kb_a))
            _ta = chip_a * max(0.15, a)
            _rc = _c3(settings.hint_recent_text_color, (0.97, 0.98, 1.0))
            blf.color(font_id, _rc[0], _rc[1], _rc[2], _ta)
            blf.position(font_id, view_ox + kx, rh - (_kb_y + _kb_h / 2 + _fs / 2 - 1), 0)
            blf.draw(font_id, txt)
            kx += _kw + 12 + 8
            blf_set_size(font_id, _key_font)
    else:
        blf_set_size(font_id, settings.hint_font_size)
        blf.color(font_id, 0.42, 0.45, 0.53, 0.85)
        blf.position(font_id, view_ox + kx, rh - (s_y + status_h / 2 + settings.hint_font_size / 2 - 1), 0)
        blf.draw(font_id, "—")


def draw_callback_px(*args, **kwargs):
    global display_text, display_time, _DEBUG_FRAMES, _REGION_WIN
    _DEBUG_FRAMES += 1
    try:
        import gpu
        from mathutils import Matrix
        from gpu_extras.batch import batch_for_shader
        gpu.matrix.load_matrix(Matrix.Identity(4))
        gpu.matrix.load_projection_matrix(Matrix.Identity(4))
        context = None
        if len(args) >= 2:
            context = args[1]
        elif len(args) == 1:
            context = args[0]
        if context is None:
            context = bpy.context
        # 5.2 空参回调下 bpy.context.region 会随鼠标所在区域漂移，
        # 必须显式固定到 3D 视口的 WINDOW region，否则卡片位置/尺寸会算错。
        region = None
        try:
            scr = getattr(context, "screen", None)
            if scr is not None:
                for ar in scr.areas:
                    if ar.type == 'VIEW_3D':
                        for r in ar.regions:
                            if r.type == 'WINDOW' and r.width > 0 and r.height > 0:
                                region = r
                                break
                        if region is not None:
                            break
        except Exception:
            region = None
        if region is None:
            region = getattr(context, "region", None)
        if region is None or getattr(region, "width", 0) == 0:
            area = getattr(context, "area", None)
            if area is not None:
                for r in area.regions:
                    if r.type == 'WINDOW':
                        region = r
                        break
        if region is None or getattr(region, "width", 0) == 0:
            return
        rw = region.width
        rh = region.height
        rx = getattr(region, "x", 0) or 0
        ry = getattr(region, "y", 0) or 0
        # 记录 region 窗口左 x 与 底部窗口 y（从底向上），供 modal 用 mouse_x/mouse_y 换算
        # 注意：Blender event.mouse_y 从窗口底部向上，region 相对 y = (ry+rh) - mouse_y
        _REGION_WIN = (rx, ry + rh)
        global _VIEW_W, _VIEW_H
        _VIEW_W = rw
        _VIEW_H = rh
        # 5.2：POST_PIXEL 需显式 NDC 矩阵，否则像素坐标绘制不可见
        import gpu
        from mathutils import Matrix
        gpu.matrix.load_matrix(Matrix.Identity(4))
        gpu.matrix.load_projection_matrix(Matrix.Identity(4))
        settings = context.scene.hotkey_overlay_settings
        now = time.time()

        # ---------- 常驻模式快捷键提示（左上角，自适应宽度卡片） ----------
        if settings.enable_hotkey_hint:
            try:
                _draw_hint_card(context, settings, rw, rh, rx, ry)
            except Exception:
                pass
            # 常驻提示绘制后继续绘制按键卡片（不能 return）
        # ---------- 按键/鼠标显示已整合进上方提示卡的状态行 ----------
    except Exception:
        pass


# ====================== 键盘+鼠标捕获模态器 ======================
class HOTKEYOVERLAY_OT_CaptureInput(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.capture_input"
    bl_label = "开启输入捕获"
    bl_options = {'REGISTER'}

    def modal(self, context, event):
        global display_text, display_time, modal_operator_instance, key_history
        if modal_operator_instance is not self:
            return {'CANCELLED'}
        global _modal_last_event
        _modal_last_event = time.time()

        area = getattr(context, "area", None)
        # 持续定时刷新：保证属性改动（透明度/颜色/位置）即时反映到视口
        if event.type == 'TIMER':
            # 修饰键超时兜底：RELEASE 被弹窗/菜单吞掉时（如 Shift+A 后关闭菜单）3s 自动清除
            try:
                _ht = time.time()
                for _k in list(_hold_mods):
                    if _ht - _hold_mods[_k] > 3.0:
                        _hold_mods.pop(_k)
            except Exception:
                pass
            global _CURRENT_MODE
            try:
                _cm = bpy.context.mode
                if isinstance(_cm, str) and not _cm.startswith("NORMAL"):
                    _CURRENT_MODE = _cm
            except Exception:
                pass
            if area is not None:
                try:
                    area.tag_redraw()
                except Exception:
                    pass
            return {'PASS_THROUGH'}

        settings = context.scene.hotkey_overlay_settings
        # ===== 卡片拖拽 / 折叠交互（拖拽期间消费事件，防止穿透触发 Blender 框选） =====
        global _drag_state
        consumed = False
        if event.type in ('LEFTMOUSE', 'MOUSEMOVE') and _hint_rect is not None:
            # Blender 5.2 modal 事件 mouse_region_x/y 恒为 -1，改用 mouse_x/y（窗口坐标）换算
            if _REGION_WIN is not None:
                mx = event.mouse_x - _REGION_WIN[0]
                my = _REGION_WIN[1] - event.mouse_y

            else:
                mx = -1
                my = -1
            if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                hx, hy, hw, hh, htitle = _hint_rect
                if hx <= mx <= hx + hw and hy <= my <= hy + hh:
                    _drag_state = {
                        "mx": mx, "my": my,
                        "ox": int(settings.hint_pos_x), "oy": int(settings.hint_pos_y),
                        "in_title": hy <= my <= hy + htitle,
                    }
                    consumed = True
                else:
                    _drag_state = None
            elif event.type == 'MOUSEMOVE' and _drag_state:
                dx = mx - _drag_state["mx"]
                dy = my - _drag_state["my"]
                settings.hint_pos_x = int(_drag_state["ox"] + dx)
                settings.hint_pos_y = _drag_state["oy"] + dy
                consumed = True
                if area is not None:
                    try:
                        area.tag_redraw()
                    except Exception:
                        pass
            elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and _drag_state:
                moved = abs(mx - _drag_state["mx"]) + abs(my - _drag_state["my"])
                if _drag_state["in_title"] and moved < 6:
                    settings.hint_collapsed = not settings.hint_collapsed
                _drag_state = None
                consumed = True
        # 维护按住修饰键状态（Screencast Keys 风格：按住常驻显示，松开消失）
        if event.type in ('LEFT_SHIFT', 'RIGHT_SHIFT'):
            if event.value == 'PRESS':
                _hold_mods['Shift'] = time.time()
            elif event.value == 'RELEASE':
                _hold_mods.pop('Shift', None)
        elif event.type in ('LEFT_CTRL', 'RIGHT_CTRL'):
            if event.value == 'PRESS':
                _hold_mods['Ctrl'] = time.time()
            elif event.value == 'RELEASE':
                _hold_mods.pop('Ctrl', None)
        elif event.type in ('LEFT_ALT', 'RIGHT_ALT'):
            if event.value == 'PRESS':
                _hold_mods['Alt'] = time.time()
            elif event.value == 'RELEASE':
                _hold_mods.pop('Alt', None)

        input_text = None

        # 收集当前修饰键
        mods = []
        if event.shift:
            mods.append("Shift")
        if event.ctrl:
            mods.append("Ctrl")
        if event.alt:
            mods.append("Alt")
        if event.oskey:
            mods.append("Win")

        mouse_types = {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'MOUSEMOVE'}

        # ---------- 鼠标捕获 ----------
        if settings.enable_mouse_display:
            mouse_text = None
            if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                mouse_text = "左键"
            elif event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
                mouse_text = "右键"
            elif event.type == 'MIDDLEMOUSE' and event.value == 'PRESS':
                mouse_text = "中键"
            elif event.type in ('WHEELUPMOUSE', 'WHEELDOWNMOUSE'):
                _sc_txt = "滚轮上" if event.type == 'WHEELUPMOUSE' else "滚轮下"
                _now_sc = time.time()
                if not (_sc_txt == _last_scroll["dir"] and _now_sc - _last_scroll["t"] < 0.3):
                    mouse_text = _sc_txt
                _last_scroll["dir"] = _sc_txt
                _last_scroll["t"] = _now_sc
            if mouse_text:
                if mods:
                    input_text = " + ".join(mods) + " + " + mouse_text
                else:
                    input_text = mouse_text

        # ---------- 键盘捕获 ----------
        if input_text is None and settings.enable_key_display:
            if event.type not in mouse_types and event.value == 'PRESS':
                ignore_keys = {"LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_CTRL", "RIGHT_CTRL", "LEFT_ALT", "RIGHT_ALT"}
                # 空 type 事件（Blender 5.2 偶发）不捕获，避免插入空白按键
                if event.type and event.type not in ignore_keys:
                    if mods:
                        input_text = " + ".join(mods) + " + " + event.type
                    else:
                        input_text = event.type

        if input_text is not None:
            display_text = input_text
            display_time = time.time()
            # 教学渐隐：把新按键写入历史（最新在前），最多保留 3 个
            _now = time.time()
            key_history = [h for h in key_history if _now - h["t"] <= settings.fade_time]
            key_history.insert(0, {"text": input_text, "t": _now})
            if len(key_history) > 3:
                key_history.pop()
            # 立即强制重绘所有 3D 视口，确保状态行"最近按键"即时更新
            try:
                _scr = bpy.context.screen
                if _scr is not None:
                    for _ar in _scr.areas:
                        if _ar.type == 'VIEW_3D':
                            _ar.tag_redraw()
            except Exception:
                pass
        # 拖拽/折叠期间消费事件，避免穿透给 Blender 触发框选等操作
        if consumed:
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        global modal_operator_instance
        if modal_operator_instance is not None:
            self.report({'WARNING'}, "输入捕获已经在运行")
            return {'CANCELLED'}
        modal_operator_instance = self
        context.window_manager.modal_handler_add(self)
        try:
            self._timer = context.window_manager.event_timer_add(0.15, window=context.window)
        except Exception:
            self._timer = None
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        global modal_operator_instance
        if getattr(self, "_timer", None) is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        if modal_operator_instance is self:
            modal_operator_instance = None

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


# ====================== 从系统快捷键自动生成当前模式提示 ======================
class HOTKEYOVERLAY_OT_AutoGenHintFromKeymap(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.autogen_hint_keymap"
    bl_label = "从系统快捷键生成当前模式提示"
    bl_description = "读取用户自定义键位自动生成提示；改过快捷键后手动点此刷新"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        mode = settings.selected_mode
        ok = generate_hints_from_keymap(mode, settings)
        if ok:
            self.report({'INFO'}, "已生成当前模式提示")
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
        defaults = {
            'OBJECT': [
                "【物体模式】",
                "A 全选 / 取消全选",
                "G 移动 | R 旋转 | S 缩放",
                "Shift+D 复制 | Alt+D 关联复制",
                "X / Delete 删除物体",
                "Shift+A 添加物体",
                "Ctrl+J 合并 | M 移到集合",
                "Ctrl+A 应用变换",
                "F2 重命名",
                "Z 着色模式切换",
                "Shift+S 吸附菜单",
                "N 属性面板",
                "Shift+L 关联选择",
                "Tab 进入编辑模式",
            ],
            'EDIT': [
                "【编辑模式】",
                "1 点 | 2 边 | 3 面",
                "A 全选",
                "G 移动 | R 旋转 | S 缩放",
                "E 挤出 | I 内插面",
                "F 填充面 | Ctrl+R 环切",
                "K 切刀 | Ctrl+B 倒角",
                "M 合并 | P 分离",
                "Shift+D 复制元素",
                "H 隐藏 | Alt+H 显示",
                "L 选择关联元素",
                "Ctrl+E 边菜单 | Alt+E 挤出菜单",
                "X / Delete 删除元素",
                "Ctrl+Shift+B 顶点倒角",
                "Tab 返回物体模式",
            ],
            'POSE': [
                "【姿态模式】",
                "A 全选骨骼",
                "G 移动 | R 旋转 | S 缩放",
                "Shift 多选骨骼",
                "I 插入关键帧",
                "Alt+R 清除旋转",
                "Alt+G 清除位移",
                "Alt+S 清除缩放",
                "Ctrl+C 复制姿态",
                "Ctrl+V 粘贴姿态",
                "Ctrl+P 设置父级",
                "M 移到集合",
                "X / Delete 删除骨骼",
                ". 切换枢轴点",
                "Tab 返回物体模式",
            ],
            'SCULPT': [
                "【雕刻模式】",
                "F 笔刷大小",
                "Shift+F 笔刷强度",
                "[ ] 减小/增大笔刷",
                "Shift 平滑笔刷",
                "Ctrl 反向雕刻",
                "X / Y / Z 对称轴切换",
                "M 遮罩笔刷",
                "Alt+M 清除遮罩",
                "Ctrl+I 反转遮罩",
                "R 旋转笔刷纹理",
                "T 显示工具栏",
                "N 属性面板",
                "Tab 返回物体模式",
            ],
        }
        reset_hint_list(getattr(settings, f"{mode.lower()}_hints"), defaults.get(mode, []))
        return {'FINISHED'}


# ====================== 自动保存/加载 + 备份操作 ======================
class HOTKEYOVERLAY_OT_SaveAutoConfig(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.save_auto_config"
    bl_label = "保存到默认配置"
    bl_description = "保存当前全部设置到Blender脚本目录，下次启动自动加载"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        path = get_auto_config_path()
        try:
            save_config_to_file(settings, path)
            self.report({'INFO'}, "已自动保存配置")
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


class HOTKEYOVERLAY_OT_ToggleCollapse(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.toggle_collapse"
    bl_label = "折叠 / 展开提示卡"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        settings.hint_collapsed = not settings.hint_collapsed
        return {'FINISHED'}


class HOTKEYOVERLAY_OT_ResetPosition(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.reset_position"
    bl_label = "重置卡片位置"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        settings.hint_pos_x = 12
        settings.hint_pos_y = 150
        return {'FINISHED'}


class HOTKEYOVERLAY_OT_GlassPreset(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.glass_preset"
    bl_label = "简约玻璃风"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        settings.hint_bg_color = (0.06, 0.09, 0.14)
        settings.hint_title_bg_color = (0.10, 0.15, 0.22)
        settings.hint_title_color = (0.95, 0.88, 0.65)
        settings.hint_key_color = (0.95, 0.88, 0.65)
        settings.hint_text_color = (0.95, 0.96, 1.0)
        settings.hint_border_color = (0.75, 0.85, 1.0)
        settings.hint_recent_text_color = (0.97, 0.98, 1.0)
        settings.key_bg_opacity = 0.55
        settings.hint_bg_opacity = 1.0
        _schedule_auto_save()
        self.report({'INFO'}, "已应用简约玻璃风外观")
        return {'FINISHED'}


class HOTKEYOVERLAY_OT_ResetAppearance(bpy.types.Operator):
    bl_idname = "hotkeyoverlay.reset_appearance"
    bl_label = "恢复默认外观"
    def execute(self, context):
        settings = context.scene.hotkey_overlay_settings
        settings.hint_bg_color = (0.06, 0.06, 0.06)
        settings.hint_title_bg_color = (0.11, 0.11, 0.11)
        settings.hint_title_color = (0.90, 0.90, 0.90)
        settings.hint_key_color = (0.98, 0.48, 0.10)
        settings.hint_text_color = (0.80, 0.80, 0.80)
        settings.hint_border_color = (0.30, 0.30, 0.30)
        settings.hint_recent_text_color = (0.92, 0.92, 0.92)
        settings.hint_recent_chip_color = (0.98, 0.48, 0.10)
        settings.hint_bg_opacity = 1.0
        settings.key_font_size = 360
        settings.key_bg_opacity = 0.85
        settings.fade_time = 2.0
        settings.hint_font_size = 16
        settings.hint_pos_x = 12
        settings.hint_pos_y = 150
        settings.hint_collapsed = False
        _schedule_auto_save()
        self.report({'INFO'}, "已恢复默认外观")
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
            box_run.operator("hotkeyoverlay.capture_input", text="开启输入捕获", icon='PLAY')
        else:
            box_run.operator("hotkeyoverlay.stop_capture", text="停止输入捕获", icon='PAUSE')

        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 1.1
        col.label(text="按键 / 鼠标显示", icon='KEYINGSET')
        col.prop(settings, "enable_key_display")
        col.prop(settings, "enable_mouse_display")
        col.separator()
        col.prop(settings, "key_font_size")
        col.prop(settings, "key_bg_opacity")
        col.prop(settings, "fade_time")

        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 1.1
        col.label(text="常驻快捷键提示", icon='TEXT')
        col.prop(settings, "enable_hotkey_hint")
        col.prop(settings, "hint_font_size")
        col.prop(settings, "hint_bg_opacity")
        col.label(text="按键块透明度：控制最近按键 / 按住行键位块整体透明度（含文字）")

        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 1.1
        col.label(text="外观自定义", icon='COLORSET_01_VEC')
        col.prop(settings, "hint_bg_color")
        col.prop(settings, "hint_title_bg_color")
        col.prop(settings, "hint_title_color")
        col.prop(settings, "hint_key_color")
        col.prop(settings, "hint_recent_text_color")
        col.prop(settings, "hint_recent_chip_color")
        col.prop(settings, "hint_text_color")
        col.prop(settings, "hint_border_color")
        col.separator()
        row2 = col.row()
        row2.operator("hotkeyoverlay.glass_preset", text="简约玻璃风", icon='SHADING_RENDERED')
        row2.operator("hotkeyoverlay.reset_appearance", text="恢复默认外观", icon='RECOVER_LAST')

        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 1.1
        col.label(text="卡片位置与折叠", icon='COLLAPSEMENU')
        row = col.row()
        row.prop(settings, "hint_pos_x")
        row.prop(settings, "hint_pos_y")
        row = col.row()
        row.operator("hotkeyoverlay.toggle_collapse", text="折叠 / 展开", icon='COLLAPSEMENU')
        row.operator("hotkeyoverlay.reset_position", text="重置位置", icon='RECOVER_LAST')
        col.label(text="拖拽卡片任意位置 = 移动")
        col.label(text="单击标题栏 = 折叠 / 展开")

        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 1.1
        col.label(text="提示文本编辑", icon='GREASEPENCIL')
        col.prop(settings, "selected_mode")
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
        box.operator("hotkeyoverlay.autogen_hint_keymap", icon='KEYINGSET')

        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 1.1
        col.label(text="自动配置", icon='FILE_TICK')
        row = col.row()
        row.operator("hotkeyoverlay.save_auto_config", text="保存配置", icon='EXPORT')
        row.operator("hotkeyoverlay.load_auto_config", text="加载配置", icon='RECOVER_LAST')

        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 1.1
        col.label(text="备份 / 分享配置", icon='PACKAGE')
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
    HOTKEYOVERLAY_OT_ToggleCollapse,
    HOTKEYOVERLAY_OT_ResetPosition,
    HOTKEYOVERLAY_OT_ResetAppearance,
    HOTKEYOVERLAY_OT_GlassPreset,
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
    try:
        wm = bpy.context.window_manager
        if wm is None or not wm.windows:
            return 0.3  # 窗口未就绪，稍后重试
        win = wm.windows[0]
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                with bpy.context.temp_override(window=win, area=area, screen=win.screen):
                    bpy.ops.hotkeyoverlay.capture_input('INVOKE_DEFAULT')
                return None
        return 0.3  # 尚无 3D 视口区域，稍后重试
    except Exception:
        return 0.5


def _check_modal_alive():
    """每 1s 检查 modal 是否存活。modal 若在 Blender 启动画面(splash)窗口上启动，splash 关闭后
    modal 会静默死亡（不再收到任何事件）但 modal_operator_instance 仍非 None，导致按键捕获永久失效。
    发现 2s 无事件即重置并重启。"""
    global modal_operator_instance
    try:
        if modal_operator_instance is not None and time.time() - _modal_last_event > 2.0:
            modal_operator_instance = None
            try:
                bpy.app.timers.register(delayed_start_modal, first_interval=0.4, persistent=True)
            except Exception:
                pass
    except Exception:
        pass
    return 1.0


def _redraw_view3d_timer():
    """每 0.15s 强制 3D 视口重绘，保证常驻快捷键提示持续可见（静止场景视口不会自动重绘）。
    0.05s 会带来每秒约 20 次视口重绘的高 CPU 占用，0.15s 足够平滑且大幅降低开销。"""
    try:
        screen = bpy.context.screen
        if screen is not None:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except Exception:
        pass
    return 0.15


def _start_modal_on_load(dummy):
    try:
        bpy.app.timers.register(_redraw_view3d_timer, first_interval=0.1, persistent=True)
    except Exception:
        pass
    try:
        bpy.app.timers.register(delayed_start_modal, first_interval=0.2, persistent=True)
    except Exception:
        pass
    # 启动输入捕获 modal：延迟启动并在窗口上下文就绪后由 timer 循环尝试


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

    bpy.app.timers.register(delayed_init, first_interval=0.2, persistent=True)
    try:
        bpy.app.timers.register(_redraw_view3d_timer, first_interval=0.1, persistent=True)
    except Exception:
        pass
    try:
        bpy.app.timers.register(_check_modal_alive, first_interval=1.0, persistent=True)
    except Exception:
        pass
    # 无论通过何种方式进入（load_post / register / 重新启用），都自动启动输入捕获
    try:
        bpy.app.timers.register(delayed_start_modal, first_interval=0.6, persistent=True)
    except Exception:
        pass

    draw_handle = bpy.types.SpaceView3D.draw_handler_add(
        draw_callback_px, (), 'WINDOW', 'POST_PIXEL'
    )
    if _start_modal_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_start_modal_on_load)


def unregister():
    global draw_handle, modal_operator_instance
    if _start_modal_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_start_modal_on_load)
    try:
        bpy.app.timers.unregister(_check_modal_alive)
    except Exception:
        pass
    modal_operator_instance = None

    # 移除强制重绘 timer
    try:
        for timer in bpy.app.timers:
            pass
    except Exception:
        pass
    # 简单方式：直接遍历注册过的 timer 不可行，改为记录 handle 不必要；
    # Blender 会在扩展卸载时自动清理 persistent=False 的 timer，
    # 但为稳妥，这里通过函数对象移除。
    try:
        bpy.app.timers.unregister(_redraw_view3d_timer)
    except Exception:
        pass

    if draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handle, 'WINDOW')
        draw_handle = None

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except (ValueError, RuntimeError):
            pass

    if hasattr(bpy.types.Scene, "hotkey_overlay_settings"):
        del bpy.types.Scene.hotkey_overlay_settings


if __name__ == "__main__":
    register()
