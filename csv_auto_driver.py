bl_info = {
    "name": "CSV Auto Driver V6 (类型识别版)",
    "author": "AI Assistant",
    "version": (6, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > CSV Driver",
    "description": "通过节点类型识别，完美支持中文版Blender",
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
        
        # 路径修复
        raw_path = props.csv_filepath
        filepath = bpy.path.abspath(raw_path)
        if not filepath or not os.path.exists(filepath):
            self.report({'ERROR'}, "找不到CSV文件！")
            return {'CANCELLED'}

        target_type = props.driver_type
        col_idx = props.column_index
        scale = props.scale_multiplier
        offset = props.frame_offset
        fps = scene.render.fps
        
        print(f"Start V6 Processing on: {obj.name}")
        
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

                    frame_num = (time_sec * fps) + offset
                    final_value = raw_value * scale

                    # --- V6 核心修改：按类型找节点 (语言无关) ---
                    if target_type == 'MAT_COLOR':
                        if obj.active_material and obj.active_material.node_tree:
                            nodes = obj.active_material.node_tree.nodes
                            target_node = None
                            
                            # 遍历查找类型为 BSDF_PRINCIPLED 的节点
                            for n in nodes:
                                if n.type == 'BSDF_PRINCIPLED' or n.type == 'EMISSION':
                                    target_node = n
                                    break # 找到一个就停
                            
                            if target_node:
                                # 你的日志显示端口名是 'Base Color' (英文ID)，这很好！
                                input_socket = target_node.inputs.get('Base Color') or target_node.inputs.get('Color')
                                
                                if input_socket:
                                    val = max(0.0, final_value)
                                    # 分通道打关键帧 (最稳)
                                    input_socket.default_value[0] = val # R
                                    input_socket.default_value[1] = val # G
                                    input_socket.default_value[2] = val # B
                                    input_socket.default_value[3] = 1.0 # Alpha
                                    
                                    input_socket.keyframe_insert(data_path="default_value", index=0, frame=frame_num)
                                    input_socket.keyframe_insert(data_path="default_value", index=1, frame=frame_num)
                                    input_socket.keyframe_insert(data_path="default_value", index=2, frame=frame_num)
                    
                    # 灯光逻辑
                    elif target_type == 'LIGHT_ENERGY':
                        if obj.type == 'LIGHT':
                            obj.data.energy = final_value
                            obj.data.keyframe_insert(data_path="energy", frame=frame_num)
                    
                    # UV 逻辑 (也加上类型查找，防万一)
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

        self.report({'INFO'}, "V6 生成完毕！")
        return {'FINISHED'}

class VIEW3D_PT_CSVDriverPanel(bpy.types.Panel):
    bl_label = "CSV 驱动器 V6 (中文适配版)"
    bl_idname = "VIEW3D_PT_csv_driver"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CSV Driver"

    def draw(self, context):
        layout = self.layout
        props = context.scene.csv_driver_props
        layout.prop(props, "csv_filepath", text="")
        layout.separator()
        row = layout.row()
        row.prop(props, "column_index")
        row.prop(props, "scale_multiplier")
        layout.separator()
        row = layout.row()
        row.prop(props, "frame_offset")
        layout.label(text="(帧)")
        layout.separator()
        layout.prop(props, "driver_type", text="")
        layout.separator()
        layout.operator("csv.generate_animation", icon='PLAY', text="生成动画")

class CSVDriverProperties(bpy.types.PropertyGroup):
    csv_filepath: bpy.props.StringProperty(name="CSV路径", subtype='FILE_PATH')
    column_index: bpy.props.IntProperty(name="列号", default=1, min=1)
    scale_multiplier: bpy.props.FloatProperty(name="强度倍数", default=1.0)
    frame_offset: bpy.props.IntProperty(name="时间偏移", default=0)
    driver_type: bpy.props.EnumProperty(
        name="类型",
        items=[
            ('LIGHT_ENERGY', "灯光功率", ""),
            ('MAT_COLOR', "物体材质颜色", ""),
            ('UV_MAPPING', "UV 贴图位移", ""),
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