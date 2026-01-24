bl_info = {
    "name": "CSV Auto Driver V4.2",
    "author": "闲鱼：Ryan_Code",
    "version": (4, 2),
    "blender": (4, 4, 3),
    "location": "View3D > Sidebar > CSV Driver",
    "description": "修复了相对模式下前段动画位置偏移的问题（增加了起始帧锚点）。",
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
        
        color_a = props.color_start
        color_b = props.color_end
        
        initial_location = obj.location.copy()
        initial_rotation = obj.rotation_euler.copy()
        
        start_frame = scene.frame_start
        
        if target_type.startswith('LOC'):
            obj.keyframe_insert(data_path="location", frame=start_frame)
        elif target_type.startswith('ROT'):
            obj.keyframe_insert(data_path="rotation_euler", frame=start_frame)
        
        print(f"Start Processing on: {obj.name} | Type: {target_type}")
        print(f"Initial State Locked at frame {start_frame}")
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                if not rows:
                    self.report({'ERROR'}, "CSV文件是空的！")
                    return {'CANCELLED'}

                if len(rows) > 1:
                    first_data_row = rows[1]
                    if col_idx >= len(first_data_row):
                        self.report({'ERROR'}, f"列号越界！CSV只有 {len(first_data_row)} 列，你填了 {col_idx}。")
                        return {'CANCELLED'}

                keyframe_count = 0

                for i, row in enumerate(rows):
                    if i == 0: continue
                    if len(row) <= col_idx: continue
                    
                    try:
                        time_sec = float(row[0])
                        raw_value = float(row[col_idx])
                    except ValueError:
                        continue

                    frame_num = (time_sec * fps) + offset
                    final_value = raw_value * scale

                    if target_type in ['LIGHT_COLOR', 'MAT_COLOR']:
                        mix_factor = max(0.0, min(1.0, final_value))
                        r = color_a[0] * (1 - mix_factor) + color_b[0] * mix_factor
                        g = color_a[1] * (1 - mix_factor) + color_b[1] * mix_factor
                        b = color_a[2] * (1 - mix_factor) + color_b[2] * mix_factor
                        
                        if target_type == 'LIGHT_COLOR':
                            if obj.type == 'LIGHT':
                                obj.data.color = (r, g, b)
                                obj.data.keyframe_insert(data_path="color", frame=frame_num)

                        elif target_type == 'MAT_COLOR':
                            if obj.active_material and obj.active_material.node_tree:
                                nodes = obj.active_material.node_tree.nodes
                                target_node = None
                                for n in nodes:
                                    if n.type == 'BSDF_PRINCIPLED' or n.type == 'EMISSION':
                                        target_node = n
                                        break
                                
                                if target_node:
                                    input_socket = target_node.inputs.get('Base Color') or target_node.inputs.get('Color')
                                    if input_socket:
                                        input_socket.default_value[0] = r
                                        input_socket.default_value[1] = g
                                        input_socket.default_value[2] = b
                                        input_socket.default_value[3] = 1.0
                                        input_socket.keyframe_insert(data_path="default_value", index=0, frame=frame_num)
                                        input_socket.keyframe_insert(data_path="default_value", index=1, frame=frame_num)
                                        input_socket.keyframe_insert(data_path="default_value", index=2, frame=frame_num)

                    elif target_type == 'LOC_X':
                        obj.location.x = initial_location.x + final_value
                        obj.keyframe_insert(data_path="location", index=0, frame=frame_num)
                    elif target_type == 'LOC_Y':
                        obj.location.y = initial_location.y + final_value
                        obj.keyframe_insert(data_path="location", index=1, frame=frame_num)
                    elif target_type == 'LOC_Z':
                        obj.location.z = initial_location.z + final_value
                        obj.keyframe_insert(data_path="location", index=2, frame=frame_num)

                    elif target_type == 'ROT_X':
                        obj.rotation_euler.x = initial_rotation.x + final_value
                        obj.keyframe_insert(data_path="rotation_euler", index=0, frame=frame_num)
                    elif target_type == 'ROT_Y':
                        obj.rotation_euler.y = initial_rotation.y + final_value
                        obj.keyframe_insert(data_path="rotation_euler", index=1, frame=frame_num)
                    elif target_type == 'ROT_Z':
                        obj.rotation_euler.z = initial_rotation.z + final_value
                        obj.keyframe_insert(data_path="rotation_euler", index=2, frame=frame_num)

                    elif target_type == 'LIGHT_ENERGY':
                        if obj.type == 'LIGHT':
                            obj.data.energy = final_value
                            obj.data.keyframe_insert(data_path="energy", frame=frame_num)

                    elif target_type in ['UV_MAPPING_X', 'UV_MAPPING_Y']:
                        if obj.active_material and obj.active_material.node_tree:
                            mapping_node = None
                            for n in obj.active_material.node_tree.nodes:
                                if n.type == 'MAPPING':
                                    mapping_node = n
                                    break
                            
                            if mapping_node:
                                axis_idx = 0 if target_type == 'UV_MAPPING_X' else 1
                                
                                mapping_node.inputs['Location'].default_value[axis_idx] = final_value
                                mapping_node.inputs['Location'].keyframe_insert(data_path="default_value", index=axis_idx, frame=frame_num)
                    
                    keyframe_count += 1

        except Exception as e:
            self.report({'ERROR'}, f"错误: {str(e)}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"完成！已生成 {keyframe_count} 帧。")
        return {'FINISHED'}

class VIEW3D_PT_CSVDriverPanel(bpy.types.Panel):
    bl_label = "CSV 驱动器 V4.2"
    bl_idname = "VIEW3D_PT_csv_driver"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CSV Driver"

    def draw(self, context):
        layout = self.layout
        props = context.scene.csv_driver_props
        
        layout.label(text="1. 数据源:", icon='FILE_TEXT')
        layout.prop(props, "csv_filepath", text="")
        
        row = layout.row(align=True)
        row.prop(props, "column_index")
        row.prop(props, "frame_offset")
        
        layout.separator()
        layout.label(text="2. 强度控制:", icon='PREFERENCES')
        layout.prop(props, "scale_multiplier")

        layout.separator()
        layout.label(text="3. 自定义颜色 (红蓝渐变):", icon='COLOR')
        row = layout.row(align=True)
        row.prop(props, "color_start", text="起始")
        row.prop(props, "color_end", text="结束")
        
        layout.separator()
        layout.label(text="4. 驱动目标 (功能选择):", icon='OUTLINER_OB_ARMATURE')
        layout.prop(props, "driver_type", text="")

        layout.separator()
        col = layout.column()
        col.scale_y = 1.6
        col.operator("csv.generate_animation", icon='PLAY', text="开始生成动画")

class CSVDriverProperties(bpy.types.PropertyGroup):
    csv_filepath: bpy.props.StringProperty(name="CSV路径", subtype='FILE_PATH')
    column_index: bpy.props.IntProperty(name="列号", default=1, min=1)
    scale_multiplier: bpy.props.FloatProperty(name="强度倍数", default=1.0)
    frame_offset: bpy.props.IntProperty(name="帧偏移", default=0)
    
    color_start: bpy.props.FloatVectorProperty(
        name="起始色", subtype='COLOR', default=(1.0, 0.0, 0.0), min=0.0, max=1.0
    )
    color_end: bpy.props.FloatVectorProperty(
        name="结束色", subtype='COLOR', default=(0.0, 0.0, 1.0), min=0.0, max=1.0
    )

    driver_type: bpy.props.EnumProperty(
        name="类型",
        items=[
            ('LIGHT_ENERGY', "💡 灯光功率", ""),
            ('LIGHT_COLOR', "🎨 灯光颜色 (自定义)", ""),
            ('MAT_COLOR', "🌈 物体材质颜色 (自定义)", ""),
            ('LOC_Z', "⬆️ 物体位置 Z (上下)", ""),
            ('LOC_Y', "➡️ 物体位置 Y (前后)", ""),
            ('LOC_X', "↗️ 物体位置 X (左右)", ""),
            ('ROT_X', "🔄 物体旋转 X", ""),
            ('ROT_Y', "🔄 物体旋转 Y", ""),
            ('ROT_Z', "🔄 物体旋转 Z", ""),
            ('UV_MAPPING_X', "🌊 UV 位移 X (横向)", ""),
            ('UV_MAPPING_Y', "🌊 UV 位移 Y (纵向)", ""),
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