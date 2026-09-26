# Hotkey Overlay 项目知识传承文档

> **用途**：本文件是 Blender 快捷键提示插件 `hotkey_overlay` 项目的完整知识沉淀。
> 另开新项目时，把本文件发给 AI（或让 AI 读取本路径），即可完整继承本项目的所有上下文：代码位置、版本历史、踩坑记录、验证方法与用户偏好。
>
> 最终稳定版本：**v1.12.3**（黑色简约浮窗默认 + 拖拽性能优化 + 最近按键块底色独立 + 兼容性收口到 Blender 4.2+）。v1.12.0 玻璃拟态：圆角/磨砂/悬浮投影/简约玻璃风预设。

---

## 一、项目概况

| 项目 | 内容 |
|---|---|
| 插件名称 | hotkey_overlay（按键/鼠标实时捕获 + 四模式快捷键提示卡 + 最近按键历史渐隐） |
| 目标软件 | Blender **5.2.2 LTS（Steam 版）**，扩展目录 `...\Blender\5.2\extensions\user_default\hotkey_overlay\` |
| 开发语言 | Python（Blender 扩展，bpy + gpu 绘制 + blf 文字） |
| 最终版本 | v1.12.3（bl_info 版本 (1,12,3)，blender min (4,2,0)；三副本 md5 发版后校验） |
| 最终安装包 | `C:\Users\29427\Desktop\安装包\hotkey_overlay_v1.12.3.zip`（zip 内前缀 `hotkey_overlay/`，含 blender_manifest.toml + hotkey_overlay.py + __init__.py；v1.9.7~v1.12.2 旧 zip 保留在同目录） |

## 二、关键路径（改代码/发版必用）

### 三份代码副本（必须三处同步，发版后 md5 比对一致）
1. **dev**：`C:\Users\29427\Desktop\hotkey_overlay_extension\hotkey_overlay.py`
2. **已部署**：`C:\Users\29427\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\user_default\hotkey_overlay\hotkey_overlay.py`
3. **git**：`C:\Users\29427\Desktop\blender-hotkey-overlay-git\hotkey_overlay.py`

### 配套文件
- manifest：各目录 `blender_manifest.toml`（版本号三处同步）
- 文档：git 目录 `CHANGELOG.md`、`README.md`（每个版本都要更新顶部新节/版本串）
- 配置：`C:\Users\29427\AppData\Roaming\Blender Foundation\Blender\5.2\scripts\hotkey_overlay_config.json`（UTF-8 无 BOM；字段名 key_font_size/key_bg_opacity/hint_bg_opacity/... 跨版本保持不变）
- Blender 可执行：`D:\steam\steamapps\common\Blender\blender.exe`
- 调试工具目录：`C:\Users\29427\AppData\Local\Temp\hotkey_check\`（**2026-09-23 磁盘清理时已整体删除**；后续需要时按原模式重建：`realshot.py` = PowerShell CopyFromScreen 截图 1707x960 PNG + PIL 裁剪放大脚本）
  - 注意 `cu.screenshot()` 是虚拟桌面，用户明确说过不能用，真实屏幕观察必须用系统截图

## 三、最终功能清单（v1.11.0 形态）

1. **四模式快捷键提示卡**：物体模式 / 编辑模式 / 姿态模式 / 雕刻模式，每模式独立快捷键列表
2. **实时按键捕获**（modal operator）：键盘 + 鼠标左/中/右键 + 滚轮
   - 修饰键按住常驻显示（"按住 Ctrl/Shift"行），3 秒无新事件自动清除（RELEASE 被菜单吞掉的兜底）
   - 最近按键历史：最多 3 条，最新在最左，越老越透明（Screencast-Keys 风格教学渐隐）
   - 滚轮 0.3s 内同方向合并只记一次（"滚轮上/下"）
3. **板子逻辑（v1.11.0 重构核心）**：
   - **背景板宽度**（key_font_size，220~800px，默认 360）：控制卡片宽度
   - **文本超宽自动换行**（边框检测器）：内容行"键位+说明"段超出背景板宽度时自动换行缩进
   - **字体跟随提示字体**：键位字号 = 提示字体 + 4（hint_font_size 控制一切字号，字体大板子跟着大）
   - **背景板透明度**（key_bg_opacity）= **只控制背景本身**（背景矩形/标题栏/投影），调低时物体轮廓、游标、网格能透出来；**文字、键位块、最近按键块保持清晰不透明**（Screencast-Keys 风格：背景独立透明、内容不透明）
   - **按键块透明度**（hint_bg_opacity，原名"卡片透明度"）= 控制最近按键/按住行**键位块整体透明度（背景+文字+描边一起淡出）**，与渐隐效果叠加
   - **边框颜色独立**：边框使用"边框颜色"自定义色原色（不被背景板透明度混合淡出），alpha 以 0.6 / 0.35 系数跟随背景板
4. **外观自定义**：卡片/标题/标题文字/键位/说明/边框/最近按键文字 全色自定义 + 透明度滑块 + 恢复默认外观按钮
5. **交互**：卡片标题栏可拖动、可折叠、位置保存；背景板宽度/字体/透明度全部实时保存
6. **自动启动 + 健康检查**：进 Blender 自动开启捕获；modal 心跳 + 每 1s 健康检查，2s 无事件自动重启捕获

## 四、版本历史（踩坑全记录）

| 版本 | 核心内容与踩坑 |
|---|---|
| v1.8~v1.9.4 | 早期版本：基础提示卡 + 捕获；UI 改名（key_font_size→背景板大小、key_bg_opacity→背景板透明度、hint_bg_opacity→卡片透明度） |
| v1.9.5 | 修"最近按键不显示"：捕获后强制重绘 + fade_time 太短；加"恢复默认外观" |
| v1.9.6 | WH_MOUSE_LL 低层鼠标钩子两轮失败（err=126 / 挂成功不回调）→ 放弃；合成鼠标注入（keybd_event/SendInput）实测到不了 modal → 结论：真实点击才能被 modal 捕获 |
| v1.9.7 | 对齐 Screencast-Keys（nutti 插件）：查 GitHub 源码确认 modal 直接处理鼠标事件机制一致；新增"按住修饰键"常驻行 |
| v1.9.8 | **splash 根因闭环**：插件自动启动时若 Blender 启动画面还开着，modal 挂到 splash 窗口的 3D 区域，splash 关闭后窗口销毁 modal 静默死亡 → 加 modal 心跳 + 健康检查 timer 自动重启 |
| v1.9.9 | 最近按键文字默认改亮白 + 新增"最近按键文字色"滑块；按键块高度适配；滚轮合并 |
| v1.10.0 | 鼠标文本短词化（左键/右键/中键/滚轮上/滚轮下）；状态行长文本字号下限；按键块描边；内容行键位金色底块+顶部亮线 |
| v1.10.1 | **Shift+A 弹菜单关掉后"按住 Shift"不消失**：根因 RELEASE 被菜单窗口吃掉 → _hold_mods 改 dict + 3s 超时兜底；"按住"行与"最近按键"行重叠 → 标签移到状态行顶部同排；内容行键位随背景板（line_h 引用 key_font 时未定义 → NameError 卡片不绘制，修定义顺序） |
| **v1.11.0** | **板子逻辑重构（用户最终认可）**：背景板宽度 / 换行检测器 / 字体跟随提示字体 / 透明度语义理清（背景板透明度=卡片整体，按键块透明度独立） |
| v1.11.1 | 边框随背景板透明度淡出（RGB 向背景色混合）——用户不满意，下版撤销 |
| v1.11.2 | **透明逻辑重构（参考 Screencast-Keys 悬浮插件做法）**：背景独立透明、内容不透明——物体轮廓/游标/网格透出、文字清晰；边框恢复原色（"边框颜色"滑块真正生效）；"去掉自动生成"标题字样保持 |
| v1.11.3 | **按键块透明度真正有用**：改为控制键位块整体（背景+文字+描边）透明度，与渐隐叠加（之前只控底色、文字恒亮，调了没变化） |
| v1.11.4 | **删除 Ctrl 拖拽精细微调**（Blender 5.2 下报错）；位置写入转 int 防浮点 RNA 报错；UI 文字同步删"按住 Ctrl 拖拽 = 精细微调" |
| **v1.12.1** | **拖拽卡顿修复 + 黑色简约默认配色**：SDF draw ~47/帧→~6/帧（投影并 1 层、键位块/按住块改直角 draw_rect）；默认配色改近黑底+白字+Blender 橙键位，与 Blender 本体一致 |
| **v1.12.2** | **最近按键块底色独立成可调配色**：新增 `hint_recent_chip_color` 属性（默认 Blender 橙 0.98,0.48,0.10），面板外观区新增「最近按键块底色」色板，与键位文字色分离；随配置保存/加载 |
| **v1.12.3** | **兼容性收口**：`bl_info["blender"]` 从 (3,6,0) 改为 (4,2,0)；文件头注释与 README 中英双语删除「支持 3.6~4.1 legacy 附加组件」段落，明确仅支持 Blender 4.2 ~ 5.x 扩展包形式（实测 5.2.2 Steam 版）；无功能变化 |
| **v1.12.0** | **玻璃拟态美化（用户参考"04 玻璃拟态"宣传图）**：全圆角化（卡片 12 / 标题栏 10 / 键位块 4 / 按住行胶囊 / 最近按键 4）；磨砂半透明 + 顶部高光条 + 三层悬浮投影 + 1px 圆角描边；标题栏简约化（淡圆角块+细分隔线）；新增"简约玻璃风"一键预设。**踩坑**：① Blender 5.2 禁止直接实例化 `GPUShader`（`cannot create GPUShader instances`）→ 改用 `GPUShaderCreateInfo` 构建；② manifest TOML 被 PowerShell Set-Content -Encoding UTF8 写入 **BOM** 导致扩展加载报 `Invalid statement (at line 1, column 1)` → 必须 UTF-8 无 BOM（Python 写） |

## 五、已验证死路（不要再浪费时间重试）

1. **WH_MOUSE_LL 低层鼠标钩子**：err=126 或挂成功不回调 → 不可用
2. **合成鼠标注入**（keybd_event 0x01/0x02/0x04、SendInput MOUSEEVENTF_*）：不产生 modal 鼠标事件 → 鼠标功能只能靠用户真实点击验收
3. **cu.click / cu.screenshot**：只作用虚拟桌面，不是用户真实屏幕 → 真实屏幕观察必须用 realshot.py
4. **keybd_event 注入键盘键偶发不被 modal 捕获**（与窗口焦点关联）——"时有时无"的又一来源，v1.9.8 健康检查已兜住 splash 场景

## 六、关键代码结构（改代码时定位）

- `HotkeyOverlaySettings`（约 L233+）：全部属性定义——`key_font_size`（背景板宽度 360/220-800）、`key_bg_opacity`（背景板透明度 0.85，只控背景）、`hint_bg_opacity`（按键块透明度 1.0，控键位块整体含文字）、`fade_time`（3.0/0.3-8.0）、`hint_font_size`（16/10-40）、`border_col`（边框颜色）、各类颜色、`hint_pos_x/y`、`hint_collapsed`、`selected_mode`、四模式 hints
- `_draw_hint_card`（约 L623+）：卡片全部绘制——布局阶段（render_rows 换行检测）→ 背景/边框/标题 → 内容行 → 最近按键状态行 + 按住行
- `draw_callback_px`（L818+）：绘制回调入口
- modal operator（约 L893+）：事件捕获、TIMER 分支（_hold_mods 3s 超时清理、健康检查）、鼠标/键盘/滚轮捕获、key_history 修剪（最多 3 条）、拖拽/折叠交互
- `_hold_mods`：模块级 dict（修饰键名→最后事件时间）
- `save_config_to_file` / `load_config_from_file`（约 L359/L396）：JSON 存取，UTF-8 无 BOM
- `reset_appearance`（约 L1326）：恢复默认外观
- UI 面板（约 L1368）：`col.prop(settings, "key_font_size")` 等（显示名自动跟随属性 name）

## 七、验证方法（发版前必做）

1. **改代码**：dev 副本改 → 同步到已部署 + git → md5 比对一致
2. **重启 Blender**：杀进程 → 启动 → 等 12~15s → 注入 ESC 关 splash（keybd_event 0x1B down/up 间隔 90ms）→ 等 2s
3. **截图**：`python realshot.py <out.png>`（真实屏幕）
4. **注入按键验证**：keybd_event（Ctrl=0x11、Shift=0x10、字母=VK 码），每键 down/up；注意 Shift 注入偶发不可靠、鼠标只能用户实测
5. **录屏**：Xbox Game Bar，Win+Alt+R 三键 keybd_event（0x5B+0x12+0x52），**每键 150ms 间隔才有效**；输出 `C:\Users\29427\Videos\Captures\`；交付前复制到桌面，视频要短（手机豆包可看）
6. **验证截图裁剪**：PIL crop + LANCZOS 放大后用 Read 肉眼检查（换行、对齐、透明度、块位置）

## 八、用户偏好（跨项目持续有效）

- 回复始终用简体中文；插件/软件 UI 中文标注，不要特殊 unicode
- 更新版本**绝不删除旧功能**；发版前**自己先在 Blender 跑一遍**再交付
- 截图必须用**真实屏幕**（系统工具），不用虚拟桌面截图
- 录屏用系统 Xbox Game Bar；交付视频短、手机可看
- 文件命名按用户文件夹规则；清理/卸载仅限 hotkey_overlay 相关，**禁止动游戏/其他文件**
- 鼠标/滚轮显示效果只能用户真实操作验收，注入无法覆盖

## 九、可能的前进方向（用户未提但符合趋势）

- 更多模式（权重绘制/纹理绘制/节点编辑）的快捷键提示卡
- Screencast-Keys 式鼠标图形绘制（三键图形 + 滚轮图标，而非文字）
- 多显示器位置记忆 / 每显示器独立位置
- 性能优化：绘制批量化、帧率限制
- 设置面板的搜索/导入导出主题（配色方案分享）

## 十、磁盘空间维护记录（2026-09-23）

背景：C 盘 552.8 GB 仅剩 41.4 GB。排查结论：**不是突然变少，是长期累积**——WeGame 游戏 155 GB（最大头）+ 我的世界全家桶 ~45 GB + 桌面「新建文件夹→沉浸战斗v4.0.8完整包」25.3 GB + 系统/软件 ~127 GB（Windows 40 + Program Files 68 + 页面文件 18）+ Videos 视频 25.7 GB + 软件缓存 ~25 GB。

已清理（严格限定范围，用户授权项）：
- **AMD 着色器缓存**（AppData\Local\AMD 下 DxcCache/OglCache/DxCache/VkCache/PPC/DX9Cache/CN，合计 ~6.7 GB）——驱动预编译缓存，删除后首次运行 3D 软件/游戏自动重建，不影响驱动与程序
- **Windows Temp 临时文件**（~2.7 GB，锁定的在用文件自动跳过）
- **剪映缓存**（JianyingPro\User Data\Cache，~0.45 GB）——**保留 Projects 草稿**
- 任务调试目录 hotkey_check（51.5 MB，291 个文件）

清理结果：C 盘剩余 **41.4 → 53.6 GB（释放 12.2 GB）**。

明确保留（用户点名不可动）：.gradle / JetBrains 开发工具缓存、剪映草稿、AMD 程序本体（Radeonsoftware）、**全部游戏（WeGame/Steam/我的世界/沉浸战斗）、视频、个人文档**。

---

*文档生成日期：2026-09-23（v1.12.0 追加 2026-09-24；v1.12.1/v1.12.2/v1.12.3 追加 2026-09-26）。当前最终版本 v1.12.3。*

> **兼容声明（v1.12.3 起）**：本插件仅支持 **Blender 4.2 ~ 5.x** 扩展包形式。不再为 Blender 3.6 ~ 4.1 legacy 附加组件形式做兼容声明或构建；圆角 SDF shader 依赖 `GPUShaderCreateInfo`（4.0+ API），扩展 manifest 已锁 `blender_version_min = "4.2.0"`。
该文本用于ai传承