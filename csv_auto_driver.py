bl_info = {
    "name": "CSV Auto Driver V7 (全功能交付版)",
    "author": "AI Assistant",
    "version": (7, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > CSV Driver",
    "description": "完美支持：灯光功率/颜色、物体位置/颜色、UV贴图。修复所有已知Bug。",
    "category": "Animation",
}

import bpy
import csv
import os

class CSV_OT_GenerateAnimation(bpy.types.Operator):
    bl_idname = "csv.generate_animation"
    bl_label = "生成动画 (Generate)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.csv_driver_props
        obj = context.active_object

        if not obj:
            self.report({'ERROR'}, "请先选中一个物体！")
            return {'CANCELLED'}
        
        # 1. 路径修复 (V4修复)
        raw_path = props.csv_filepath
        filepath = bpy.path.abspath(raw_path)
        if not filepath or not os.path.exists(filepath):
            self.report({'ERROR'}, "找不到CSV文件！请检查路径。")
            return {'CANCELLED'}

        target_type = props.driver_type
        col_idx = props.column_index
        scale = props.scale_multiplier
        offset = props.frame_offset
        fps = scene.render.fps
        
        print(f"Start V7 Processing on: {obj.name} | Type: {target_type}")
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    return {'CANCELLED'}

                for row in reader:
                    if len(row) <= col_idx: continue
                    try:
                        time_sec = float(row[0])
                        raw_value = float(row[col_idx])
                    except ValueError:
                        continue

                    # 2. 时间计算 (含偏移)
                    frame_num = (time_sec * fps) + offset
                    final_value = raw_value * scale

                    # =====================================================
                    #                 核心驱动逻辑 (5大功能)
                    # =====================================================

                    # --- A. 驱动物体位置 (Z轴高度) ---
                    if target_type == 'LOC_Z':
                        obj.location.z = final_value
                        obj.keyframe_insert(data_path="location", index=2, frame=frame_num)

                    # --- B. 驱动物体材质颜色 (V6修复: 智能识别中文节点) ---
                    elif target_type == 'MAT_COLOR':
                        if obj.active_material and obj.active_material.node_tree:
                            nodes = obj.active_material.node_tree.nodes
                            target_node = None
                            # 遍历查找 BSDF 或 Emission 节点
                            for n in nodes:
                                if n.type == 'BSDF_PRINCIPLED' or n.type == 'EMISSION':
                                    target_node = n
                                    break
                            
                            if target_node:
                                input_socket = target_node.inputs.get('Base Color') or target_node.inputs.get('Color')
                                if input_socket:
                                    val = max(0.0, final_value)
                                    # 分通道打关键帧 (防死线)
                                    input_socket.default_value[0] = val # R
                                    input_socket.default_value[1] = val # G
                                    input_socket.default_value[2] = val # B
                                    input_socket.default_value[3] = 1.0 # Alpha
                                    input_socket.keyframe_insert(data_path="default_value", index=0, frame=frame_num)
                                    input_socket.keyframe_insert(data_path="default_value", index=1, frame=frame_num)
                                    input_socket.keyframe_insert(data_path="default_value", index=2, frame=frame_num)

                    # --- C. 驱动灯光功率 ---
                    elif target_type == 'LIGHT_ENERGY':
                        if obj.type == 'LIGHT':
                            obj.data.energy = final_value
                            obj.data.keyframe_insert(data_path="energy", frame=frame_num)
                        else:
                            # 容错：如果用户选了网格却选了灯光模式，不报错但打印提示
                            print(f"警告: {obj.name} 不是灯光")

                    # --- D. 驱动灯光颜色 (明暗变化) ---
                    elif target_type == 'LIGHT_COLOR':
                        if obj.type == 'LIGHT':
                            val = max(0.0, final_value)
                            # 灯光颜色只有3个通道 RGB
                            obj.data.color = (val, val, val)
                            obj.data.keyframe_insert(data_path="color", frame=frame_num)

                    # --- E. 驱动 UV 贴图 (智能识别 Mapping) ---
                    elif target_type == 'UV_MAPPING':
                        if obj.active_material and obj.active_material.node_tree:
                            mapping_node = None
                            for n in obj.active_material.node_tree.nodes:
                                if n.type == 'MAPPING':
                                    mapping_node = n
                                    break
                            
                            if mapping_node:
                                mapping_node.inputs['Location'].default_value[0] = final_value
                                mapping_node.inputs['Location'].keyframe_insert(data_path="default_value", index=0, frame=frame_num)

        except Exception as e:
            self.report({'ERROR'}, f"错误: {str(e)}")
            return {'CANCELLED'}

        self.report({'INFO'}, "V7 动画生成完毕！")
        return {'FINISHED'}

class VIEW3D_PT_CSVDriverPanel(bpy.types.Panel):
    bl_label = "CSV 驱动器 V7 (交付版)"
    bl_idname = "VIEW3D_PT_csv_driver"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CSV Driver"

    def draw(self, context):
        layout = self.layout
        props = context.scene.csv_driver_props
        
        layout.label(text="1. 数据源:")
        layout.prop(props, "csv_filepath", text="")
        
        layout.separator()
        layout.label(text="2. 参数设置:")
        row = layout.row()
        row.prop(props, "column_index")
        row.prop(props, "scale_multiplier")
        
        row = layout.row()
        row.prop(props, "frame_offset")
        layout.label(text="(帧修正)")

        layout.separator()
        layout.label(text="3. 驱动目标 (功能选择):")
        layout.prop(props, "driver_type", text="")

        layout.separator()
        col = layout.column()
        col.scale_y = 1.5
        col.operator("csv.generate_animation", icon='PLAY', text="开始生成动画")

class CSVDriverProperties(bpy.types.PropertyGroup):
    csv_filepath: bpy.props.StringProperty(name="CSV路径", subtype='FILE_PATH')
    column_index: bpy.props.IntProperty(name="列号", default=1, min=1)
    scale_multiplier: bpy.props.FloatProperty(name="强度倍数", default=1.0)
    frame_offset: bpy.props.IntProperty(name="时间偏移", default=0)
    
    # 这里补齐了所有选项
    driver_type: bpy.props.EnumProperty(
        name="类型",
        items=[
            ('LIGHT_ENERGY', "💡 灯光功率 (Light Power)", "驱动灯光的瓦数"),
            ('LIGHT_COLOR', "🎨 灯光颜色 (Light Color)", "驱动灯光的明暗"),
            ('MAT_COLOR', "🌈 物体材质颜色 (Mesh Color)", "驱动模型材质变色"),
            ('LOC_Z', "⬆️ 物体位置 Z (Position Z)", "驱动物体上下移动"),
            ('UV_MAPPING', "🌊 UV 贴图位移 (UV Move)", "驱动纹理流动"),
        ],
        default='LIGHT_ENERGY'
    )

classes = (CSVDriverProperties, CSV_OT_GenerateAnimation, VIEW3D_PT_CSVDriverPanel)

def register():
    for cls in classes: bpy.utils.register_class(cls)
    bpy.types.Scene.csv_driver_props = bpy.props.PointerProperty(type=CSVDriverProperties)

def unregister():
    for cls in reversed(classes): bpy.utils.unregister_class(cls)
    del bpy.types.Scene.csv_driver_props

if __name__ == "__main__":
    register()