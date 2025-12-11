bl_info = {
    "name": "CSV Auto Driver V3 (CSV自动驱动器)",
    "author": "AI Assistant",
    "version": (3, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > CSV Driver",
    "description": "读取CSV文件驱动物体，支持时间偏移与强度倍数",
    "category": "Animation",
}

import bpy
import csv
import os

class CSV_OT_GenerateAnimation(bpy.types.Operator):
    """读取CSV并生成动画关键帧"""
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
        
        filepath = props.csv_filepath
        if not filepath or not os.path.exists(filepath):
            self.report({'ERROR'}, "找不到CSV文件，请检查路径。")
            return {'CANCELLED'}

        # 参数准备
        target_type = props.driver_type
        col_idx = props.column_index
        scale = props.scale_multiplier
        offset = props.frame_offset  # <--- V3 新增：时间偏移
        fps = scene.render.fps
        
        keyframe_count = 0
        print(f"Start processing CSV: {filepath} on Object: {obj.name}")
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                try:
                    header = next(reader) # 跳过标题
                except StopIteration:
                    return {'CANCELLED'}

                for row in reader:
                    if len(row) <= col_idx: continue
                    
                    try:
                        time_sec = float(row[0]) # 第1列是时间
                        raw_value = float(row[col_idx]) # 用户指定的列
                    except ValueError:
                        continue

                    # 核心时间逻辑：时间 * FPS + 偏移量
                    # 比如：80秒 * 30帧 = 2400。如果偏移是 -3，结果就是 2397帧。
                    frame_num = (time_sec * fps) + offset
                    
                    final_value = raw_value * scale

                    # --- 驱动逻辑分发 ---
                    
                    # 1. 驱动位置 Z (Location Z)
                    if target_type == 'LOC_Z':
                        obj.location.z = final_value
                        obj.keyframe_insert(data_path="location", index=2, frame=frame_num)

                    # 2. 驱动位置 X (Location X)
                    elif target_type == 'LOC_X':
                        obj.location.x = final_value
                        obj.keyframe_insert(data_path="location", index=0, frame=frame_num)
                        
                    # 3. 驱动灯光功率 (Light Energy)
                    elif target_type == 'LIGHT_ENERGY':
                        if obj.type == 'LIGHT':
                            obj.data.energy = final_value
                            obj.data.keyframe_insert(data_path="energy", frame=frame_num)

                    # 4. 驱动灯光颜色 (Light Color)
                    elif target_type == 'LIGHT_COLOR':
                        if obj.type == 'LIGHT':
                            val = max(0.0, final_value)
                            obj.data.color = (val, val, val)
                            obj.data.keyframe_insert(data_path="color", frame=frame_num)

                    # 5. 驱动材质颜色 (Material Base Color)
                    elif target_type == 'MAT_COLOR':
                        if obj.active_material and obj.active_material.node_tree:
                            nodes = obj.active_material.node_tree.nodes
                            target_node = nodes.get("Principled BSDF") or nodes.get("Emission")
                            if target_node:
                                input_socket = target_node.inputs.get('Base Color') or target_node.inputs.get('Color')
                                if input_socket:
                                    val = max(0.0, final_value)
                                    input_socket.default_value = (val, val, val, 1.0)
                                    input_socket.keyframe_insert(data_path="default_value", frame=frame_num)
                    
                    # 6. 驱动 UV (Mapping Node)
                    elif target_type == 'UV_MAPPING':
                        if obj.active_material and obj.active_material.node_tree:
                            nodes = obj.active_material.node_tree.nodes
                            mapping_node = nodes.get("Mapping")
                            if mapping_node:
                                mapping_node.inputs['Location'].default_value[0] = final_value
                                mapping_node.inputs['Location'].keyframe_insert(data_path="default_value", index=0, frame=frame_num)

                    keyframe_count += 1

        except Exception as e:
            self.report({'ERROR'}, f"错误: {str(e)}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"成功！生成 {keyframe_count} 帧。偏移量: {offset}")
        return {'FINISHED'}

class VIEW3D_PT_CSVDriverPanel(bpy.types.Panel):
    bl_label = "CSV 驱动器 V3"
    bl_idname = "VIEW3D_PT_csv_driver"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CSV Driver"

    def draw(self, context):
        layout = self.layout
        props = context.scene.csv_driver_props

        layout.label(text="1. 选择 CSV 文件:")
        layout.prop(props, "csv_filepath", text="")
        
        layout.separator()
        layout.label(text="2. 设置参数:")
        
        # 将列号和倍数放在一行
        row = layout.row()
        row.prop(props, "column_index")
        row.prop(props, "scale_multiplier")
        
        # V3 新增：时间偏移输入框
        layout.separator()
        row = layout.row()
        row.prop(props, "frame_offset") # <--- UI显示偏移设置
        layout.label(text="(帧)")

        layout.separator()
        layout.label(text="3. 驱动目标:")
        layout.prop(props, "driver_type", text="")

        layout.separator()
        layout.operator("csv.generate_animation", icon='PLAY', text="生成动画")

class CSVDriverProperties(bpy.types.PropertyGroup):
    csv_filepath: bpy.props.StringProperty(name="CSV路径", subtype='FILE_PATH')
    column_index: bpy.props.IntProperty(name="列号", default=1, min=1)
    scale_multiplier: bpy.props.FloatProperty(name="强度倍数", default=1.0)
    
    # V3 新增：帧偏移属性
    frame_offset: bpy.props.IntProperty(
        name="时间偏移", 
        default=0, 
        description="正数推后，负数提前。例如 -5 表示提前5帧开始"
    )
    
    driver_type: bpy.props.EnumProperty(
        name="类型",
        items=[
            ('LIGHT_ENERGY', "灯光功率 (Light Power)", ""),
            ('LIGHT_COLOR', "灯光颜色 (Light Color)", ""),
            ('MAT_COLOR', "物体材质颜色 (Mesh Color)", ""),
            ('LOC_Z', "物体位置 Z (Up/Down)", ""),
            ('LOC_X', "物体位置 X (Left/Right)", ""),
            ('UV_MAPPING', "UV 贴图位移 (UV Move)", ""),
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